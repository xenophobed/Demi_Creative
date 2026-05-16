"""Contract tests for the programmatic post-generation safety gate (#421).

These tests pin down the behavior of ``backend.src.agents._safety.enforce_post_gen_safety``
and the three agent integrations that call it. The contract is:

1. PASS path — initial check >= threshold, return original text untouched,
   ``was_retried`` = ``False``.
2. RETRY-SUCCESS path — initial check < threshold,
   ``suggest_content_improvements`` returns a repaired version, recheck
   >= threshold, return repaired text, ``was_retried`` = ``True``.
3. RETRY-FAIL path — both checks below threshold → raise ``RuntimeError``.
4. AGE-AWARE THRESHOLD — score 0.87 passes for 6-8 but fails for 3-5
   (3-5 uses the tighter 0.90 floor).
5. AGENT INTEGRATION — kids_daily, interactive_story, and image_to_story
   each invoke ``enforce_post_gen_safety`` exactly once per generation
   and emit a ``safety_check`` log line on the success path.

These tests intentionally mock ``check_content_safety.handler`` /
``suggest_content_improvements.handler`` so no Anthropic API call is
made; they validate the *enforcement structure*, not the LLM behavior.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _envelope(payload: dict) -> dict:
    """Wrap a payload dict the way the SDK ``@tool`` handler does."""

    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
        ]
    }


# --------------------------------------------------------------------------- #
# 1 — Pass path                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_pass_path_returns_original_text_no_retry():
    from backend.src.agents import _safety

    check_mock = AsyncMock(return_value=_envelope({"safety_score": 0.95}))
    suggest_mock = AsyncMock()

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         patch.object(_safety.suggest_content_improvements, "handler", suggest_mock):
        text, score, retried = await _safety.enforce_post_gen_safety(
            "A gentle bunny shared carrots with friends.",
            content_type="image_story",
            age_group="6-8",
        )

    assert text == "A gentle bunny shared carrots with friends."
    assert score == pytest.approx(0.95)
    assert retried is False
    # The repair path must NOT fire on the pass case.
    suggest_mock.assert_not_awaited()


# --------------------------------------------------------------------------- #
# 2 — Retry success                                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_retry_success_returns_improved_text():
    from backend.src.agents import _safety

    check_mock = AsyncMock(side_effect=[
        _envelope({"safety_score": 0.70, "issues": [{"type": "violence"}]}),
        _envelope({"safety_score": 0.92}),
    ])
    suggest_mock = AsyncMock(
        return_value=_envelope({"improved_content": "A gentler version."})
    )

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         patch.object(_safety.suggest_content_improvements, "handler", suggest_mock):
        text, score, retried = await _safety.enforce_post_gen_safety(
            "Originally a bit too rough.",
            content_type="interactive_story",
            age_group="6-8",
        )

    assert text == "A gentler version."
    assert score == pytest.approx(0.92)
    assert retried is True
    assert check_mock.await_count == 2
    suggest_mock.assert_awaited_once()


# --------------------------------------------------------------------------- #
# 3 — Retry fail                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_retry_fail_raises_runtime_error():
    from backend.src.agents import _safety

    check_mock = AsyncMock(side_effect=[
        _envelope({"safety_score": 0.70}),
        _envelope({"safety_score": 0.75}),
    ])
    suggest_mock = AsyncMock(
        return_value=_envelope({"improved_content": "Still not safe enough."})
    )

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         patch.object(_safety.suggest_content_improvements, "handler", suggest_mock):
        with pytest.raises(RuntimeError, match="safety_below_threshold_after_retry"):
            await _safety.enforce_post_gen_safety(
                "Persistently unsafe content.",
                content_type="kids_daily",
                age_group="6-8",
            )

    assert check_mock.await_count == 2
    suggest_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_retry_when_allow_retry_false():
    from backend.src.agents import _safety

    check_mock = AsyncMock(return_value=_envelope({"safety_score": 0.50}))
    suggest_mock = AsyncMock()

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         patch.object(_safety.suggest_content_improvements, "handler", suggest_mock):
        with pytest.raises(RuntimeError, match="safety_below_threshold:"):
            await _safety.enforce_post_gen_safety(
                "Unsafe text.",
                content_type="kids_daily",
                age_group="6-8",
                allow_retry=False,
            )

    suggest_mock.assert_not_awaited()


# --------------------------------------------------------------------------- #
# 4 — Age-aware threshold                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_age_3_5_uses_tighter_threshold_0_90():
    """0.87 passes for 6-8 but fails for 3-5 (tighter 0.90 floor)."""

    from backend.src.agents import _safety

    # 6-8 with 0.87 → passes (>= 0.85).
    check_mock_pass = AsyncMock(return_value=_envelope({"safety_score": 0.87}))
    with patch.object(_safety.check_content_safety, "handler", check_mock_pass):
        text, score, retried = await _safety.enforce_post_gen_safety(
            "Borderline content.",
            content_type="image_story",
            age_group="6-8",
        )
    assert retried is False
    assert score == pytest.approx(0.87)

    # 3-5 with same 0.87 → must trigger a retry attempt (below 0.90 floor).
    check_mock_fail = AsyncMock(side_effect=[
        _envelope({"safety_score": 0.87}),
        _envelope({"safety_score": 0.86}),
    ])
    suggest_mock = AsyncMock(
        return_value=_envelope({"improved_content": "still borderline"})
    )
    with patch.object(_safety.check_content_safety, "handler", check_mock_fail), \
         patch.object(_safety.suggest_content_improvements, "handler", suggest_mock):
        with pytest.raises(RuntimeError):
            await _safety.enforce_post_gen_safety(
                "Borderline content.",
                content_type="image_story",
                age_group="3-5",
            )


def test_safety_threshold_age_groups():
    from backend.src.agents._safety import safety_threshold

    assert safety_threshold("3-5") == 0.90
    assert safety_threshold("6-8") == 0.85
    assert safety_threshold("9-12") == 0.85


# --------------------------------------------------------------------------- #
# Empty content guard                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_empty_content_raises_without_calling_safety_api():
    from backend.src.agents import _safety

    check_mock = AsyncMock()
    with patch.object(_safety.check_content_safety, "handler", check_mock):
        with pytest.raises(RuntimeError, match="empty_content"):
            await _safety.enforce_post_gen_safety(
                "",
                content_type="image_story",
                age_group="6-8",
            )

    check_mock.assert_not_awaited()


# --------------------------------------------------------------------------- #
# 5 — Agent integration: each agent path logs safety_check                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_kids_daily_text_invokes_post_gen_safety(monkeypatch, caplog):
    """`_generate_kids_daily_text_live` must run the programmatic gate."""

    from backend.src.agents import _safety, kids_daily_agent

    # Force the direct-API path to return well-formed JSON.
    async def fake_direct_generate(prompt, max_tokens=4096):  # noqa: ARG001
        return json.dumps({
            "kid_title": "Title",
            "kid_content": "Friendly news for kids about a community garden.",
            "why_care": "It teaches sharing.",
            "key_concepts": [],
            "interactive_questions": [],
        })

    monkeypatch.setattr(
        kids_daily_agent, "_direct_generate_daily", fake_direct_generate
    )

    check_mock = AsyncMock(return_value=_envelope({"safety_score": 0.95}))

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         caplog.at_level(logging.INFO, logger="backend.src.agents._safety"):
        result = await kids_daily_agent._generate_kids_daily_text_live(
            source="A neighborhood started a community garden today.",
            age_group="6-8",
            category="community",
            enable_audio=False,
            voice=None,
            child_id="",
        )

    assert result["safety_score"] == pytest.approx(0.95)
    check_mock.assert_awaited()
    # One safety_check log line should have been emitted.
    assert any(
        "safety_check content_type=kids_daily" in rec.getMessage()
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_interactive_opening_invokes_post_gen_safety(monkeypatch, caplog):
    """`generate_story_opening` must run the programmatic gate."""

    from backend.src.agents import _safety, interactive_story_agent

    async def fake_direct_generate(prompt, max_tokens=4096):  # noqa: ARG001
        return json.dumps({
            "title": "Forest Adventure",
            "segment": {
                "segment_id": 0,
                "text": "Pip the squirrel skipped through the sunny forest.",
                "choices": [
                    {"id": "a", "text": "Follow the stream", "preview": "..."},
                    {"id": "b", "text": "Climb the oak", "preview": "..."},
                ],
            },
        })

    monkeypatch.setattr(
        interactive_story_agent, "_direct_generate", fake_direct_generate
    )
    monkeypatch.setattr(
        interactive_story_agent,
        "_fetch_preference_context",
        AsyncMock(return_value=""),
    )
    monkeypatch.setattr(
        interactive_story_agent,
        "_search_story_dedup",
        AsyncMock(return_value=""),
    )
    # The agent short-circuits to a deterministic mock under pytest;
    # force the live path so the post-gen safety gate actually runs.
    monkeypatch.setattr(
        interactive_story_agent, "_should_use_mock", lambda: False
    )

    check_mock = AsyncMock(return_value=_envelope({"safety_score": 0.93}))

    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         caplog.at_level(logging.INFO, logger="backend.src.agents._safety"):
        result = await interactive_story_agent.generate_story_opening(
            child_id="child_test",
            age_group="6-8",
            interests=["animals"],
            theme="forest",
            enable_audio=False,
            voice="shimmer",
            user_id="user_test",
        )

    assert result["safety_score"] == pytest.approx(0.93)
    check_mock.assert_awaited()
    assert any(
        "safety_check content_type=interactive_story" in rec.getMessage()
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_image_to_story_direct_stream_invokes_post_gen_safety(
    monkeypatch, caplog, tmp_path
):
    """`_direct_stream_image_to_story` must run the programmatic gate."""

    from backend.src.agents import _safety, image_to_story_agent

    # Make a fake image so the path-existence guard passes.
    fake_image = tmp_path / "drawing.jpg"
    fake_image.write_bytes(b"\x89PNG\r\n")

    # Stub the analyze tool to return well-formed JSON. The real symbol
    # is an SdkMcpTool wrapper, but the agent code does
    # `await analyze_children_drawing({...})` directly — we replace it
    # with an awaitable that returns the same envelope shape.
    async def fake_analyze(_args):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "description": "A friendly dragon",
                        "elements": ["dragon", "castle"],
                        "themes": ["bravery"],
                        "colors": ["red"],
                        "mood": "cheerful",
                        "objects": ["dragon"],
                        "scene": "castle",
                        "confidence_score": 0.9,
                    }),
                }
            ]
        }

    monkeypatch.setattr(
        image_to_story_agent, "analyze_children_drawing", fake_analyze
    )

    # Stub the AsyncAnthropic client used inside _direct_stream_image_to_story.
    class _StubResponse:
        def __init__(self, text):
            self.content = [type("Block", (), {"text": text})()]

    class _StubMessages:
        async def create(self, **_kwargs):
            return _StubResponse(json.dumps({
                "story": "Once upon a time, a friendly dragon helped a knight.",
                "themes": ["friendship"],
                "concepts": ["kindness"],
                "moral": "Be kind.",
                "characters": [
                    {"name": "Dragon", "description": "Friendly", "appearances": 1}
                ],
            }))

    class _StubAsyncAnthropic:
        def __init__(self, *_args, **_kwargs):
            self.messages = _StubMessages()

    # `_direct_stream_image_to_story` does `from anthropic import AsyncAnthropic`
    # at function scope, so we must patch the attribute on the `anthropic`
    # module before the import binds.
    import anthropic as _anthropic_mod
    monkeypatch.setattr(_anthropic_mod, "AsyncAnthropic", _StubAsyncAnthropic)

    check_mock = AsyncMock(return_value=_envelope({"safety_score": 0.91}))

    events = []
    with patch.object(_safety.check_content_safety, "handler", check_mock), \
         caplog.at_level(logging.INFO, logger="backend.src.agents._safety"):
        async for event in image_to_story_agent._direct_stream_image_to_story(
            image_path=str(fake_image),
            child_id="child_test",
            child_age=7,
            interests=["animals"],
            enable_audio=False,
            voice=None,
            art_theme=None,
            user_id="user_test",
            provider=None,
        ):
            events.append(event)

    # The result event must carry the enforced safety score.
    result_events = [e for e in events if e.get("type") == "result"]
    assert result_events, (
        f"no result event emitted; events={[e.get('type') for e in events]} "
        f"err={[e for e in events if e.get('type') == 'error']}"
    )
    assert result_events[-1]["data"]["safety_score"] == pytest.approx(0.91)
    check_mock.assert_awaited()
    assert any(
        "safety_check content_type=image_story" in rec.getMessage()
        for rec in caplog.records
    )
