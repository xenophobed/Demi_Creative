"""
Standalone Agent Function Signature Contracts (Issue #499)

Locks the public function signatures of the four agent entry points that
the My Agent multi-agent layer (#436) delegates to. If any of these
signatures drift, this test fires before broken proxy code reaches main.

Covers:
1. image_to_story_agent.image_to_story
2. interactive_story_agent.generate_story_opening
3. interactive_story_agent.generate_next_segment
4. kids_daily_agent.generate_kids_daily_episode

Parent Epic: #436 (My Agent — Personal Creative Buddy)
"""

from __future__ import annotations

import inspect
from inspect import Parameter
from typing import Any


def _params(func: Any) -> dict[str, Parameter]:
    return dict(inspect.signature(func).parameters)


class TestImageToStorySignature:
    """Contract: image_to_story() public signature is stable."""

    def test_function_is_async(self):
        from backend.src.agents.image_to_story_agent import image_to_story

        assert inspect.iscoroutinefunction(image_to_story), (
            "image_to_story must remain an async function"
        )

    def test_required_parameters(self):
        from backend.src.agents.image_to_story_agent import image_to_story

        params = _params(image_to_story)

        # Required (no default)
        assert "image_path" in params
        assert params["image_path"].default is Parameter.empty

        assert "child_id" in params
        assert params["child_id"].default is Parameter.empty

        assert "child_age" in params
        assert params["child_age"].default is Parameter.empty

    def test_optional_parameters_with_defaults(self):
        from backend.src.agents.image_to_story_agent import image_to_story

        params = _params(image_to_story)

        # Optional kwargs the proxy + standalone route both rely on
        for name in ("interests", "enable_audio", "voice", "art_theme", "user_id"):
            assert name in params, f"missing optional param: {name}"
            assert params[name].default is not Parameter.empty, (
                f"{name} must have a default"
            )

    def test_enable_audio_defaults_to_true(self):
        from backend.src.agents.image_to_story_agent import image_to_story

        assert _params(image_to_story)["enable_audio"].default is True

    def test_user_id_defaults_to_empty_string(self):
        """user_id default must remain '' so unauthenticated test paths don't error."""
        from backend.src.agents.image_to_story_agent import image_to_story

        assert _params(image_to_story)["user_id"].default == ""


class TestGenerateStoryOpeningSignature:
    """Contract: generate_story_opening() public signature is stable."""

    def test_function_is_async(self):
        from backend.src.agents.interactive_story_agent import generate_story_opening

        assert inspect.iscoroutinefunction(generate_story_opening)

    def test_required_parameters(self):
        from backend.src.agents.interactive_story_agent import generate_story_opening

        params = _params(generate_story_opening)

        for name in ("child_id", "age_group", "interests"):
            assert name in params, f"missing required param: {name}"
            assert params[name].default is Parameter.empty, (
                f"{name} must remain required"
            )

    def test_optional_parameters(self):
        from backend.src.agents.interactive_story_agent import generate_story_opening

        params = _params(generate_story_opening)

        for name in ("theme", "enable_audio", "voice", "user_id"):
            assert name in params, f"missing optional param: {name}"
            assert params[name].default is not Parameter.empty

    def test_enable_audio_defaults_to_true(self):
        from backend.src.agents.interactive_story_agent import generate_story_opening

        assert _params(generate_story_opening)["enable_audio"].default is True


class TestGenerateNextSegmentSignature:
    """Contract: generate_next_segment() public signature is stable."""

    def test_function_is_async(self):
        from backend.src.agents.interactive_story_agent import generate_next_segment

        assert inspect.iscoroutinefunction(generate_next_segment)

    def test_required_parameters(self):
        from backend.src.agents.interactive_story_agent import generate_next_segment

        params = _params(generate_next_segment)

        for name in ("session_id", "choice_id", "session_data"):
            assert name in params, f"missing required param: {name}"
            assert params[name].default is Parameter.empty

    def test_optional_parameters(self):
        from backend.src.agents.interactive_story_agent import generate_next_segment

        params = _params(generate_next_segment)

        for name in ("enable_audio", "voice"):
            assert name in params, f"missing optional param: {name}"
            assert params[name].default is not Parameter.empty


class TestGenerateKidsDailyEpisodeSignature:
    """Contract: generate_kids_daily_episode() is keyword-only, signature stable."""

    def test_function_is_async(self):
        from backend.src.agents.kids_daily_agent import generate_kids_daily_episode

        assert inspect.iscoroutinefunction(generate_kids_daily_episode)

    def test_required_keyword_only_parameters(self):
        from backend.src.agents.kids_daily_agent import generate_kids_daily_episode

        params = _params(generate_kids_daily_episode)

        # All real params are keyword-only (the function starts with `*,`)
        for name in ("news_text", "age_group", "child_id", "category"):
            assert name in params, f"missing param: {name}"
            assert params[name].kind == Parameter.KEYWORD_ONLY, (
                f"{name} must remain keyword-only"
            )
            assert params[name].default is Parameter.empty, (
                f"{name} must remain required"
            )

    def test_optional_news_url_parameter(self):
        from backend.src.agents.kids_daily_agent import generate_kids_daily_episode

        params = _params(generate_kids_daily_episode)

        assert "news_url" in params
        assert params["news_url"].kind == Parameter.KEYWORD_ONLY
        assert params["news_url"].default is None


class TestSignaturesAreCallableFromProxy:
    """Smoke test: the proxy's expected call-shape is satisfiable by these signatures.

    The proxy in `backend/src/agents/my_agent_proxy.py` calls each of these
    functions with a fixed kwarg shape. If any required param is renamed,
    the proxy will TypeError at runtime. This test catches that drift.
    """

    def test_image_to_story_accepts_proxy_kwargs(self):
        from backend.src.agents.image_to_story_agent import image_to_story

        sig = inspect.signature(image_to_story)
        # Should not raise — these are the kwargs my_agent_proxy passes
        sig.bind(
            image_path="/tmp/x.png",
            child_id="c1",
            child_age=7,
            interests=["dragons"],
            enable_audio=True,
            voice=None,
            art_theme=None,
            user_id="u1",
        )

    def test_generate_story_opening_accepts_proxy_kwargs(self):
        from backend.src.agents.interactive_story_agent import generate_story_opening

        sig = inspect.signature(generate_story_opening)
        sig.bind(
            child_id="c1",
            age_group="6-8",
            interests=["adventure"],
            theme=None,
            enable_audio=True,
            user_id="u1",
        )

    def test_generate_next_segment_accepts_proxy_kwargs(self):
        from backend.src.agents.interactive_story_agent import generate_next_segment

        sig = inspect.signature(generate_next_segment)
        sig.bind(
            session_id="s1",
            choice_id="c1",
            session_data={"segments": [], "age_group": "6-8"},
            enable_audio=True,
        )

    def test_generate_kids_daily_episode_accepts_proxy_kwargs(self):
        from backend.src.agents.kids_daily_agent import generate_kids_daily_episode

        sig = inspect.signature(generate_kids_daily_episode)
        sig.bind(
            news_text="A news story.",
            age_group="6-8",
            child_id="c1",
            category="general",
            news_url=None,
        )
