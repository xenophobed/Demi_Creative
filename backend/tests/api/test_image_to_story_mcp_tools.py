import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from backend.src.agents import image_to_story_agent
from backend.src.mcp_servers.vision_analysis_server import _parse_vision_json_response


class _FakeMessagesAPI:
    async def create(self, **_kwargs):
        payload = {
            "story": "A brave rabbit found a glowing map and shared the treasure with friends.",
            "themes": ["friendship"],
            "concepts": ["sharing"],
            "moral": "Kindness makes adventures brighter.",
            "characters": [{"name": "Rabbit", "description": "A brave helper"}],
        }
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(payload))]
        )


class _FakeAnthropicClient:
    def __init__(self, *args, **kwargs):
        self.messages = _FakeMessagesAPI()


class _FakeSdkTool:
    def __init__(self, handler):
        self.handler = handler


class _FakeVisionMessagesAPI:
    def __init__(self, text):
        self._text = text

    async def create(self, **_kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class _FakeVisionClient:
    response_text = ""

    def __init__(self, *args, **kwargs):
        self.messages = _FakeVisionMessagesAPI(self.response_text)


def test_vision_parser_accepts_prose_wrapped_json():
    result = _parse_vision_json_response(
        'Here is the analysis:\n{"objects":["rabbit"],"scene":"forest",'
        '"mood":"curious","confidence_score":0.91}\nHope this helps.'
    )

    assert result["objects"] == ["rabbit"]
    assert result["scene"] == "forest"
    assert result["confidence_score"] == 0.91


def test_vision_parser_accepts_fenced_json_with_trailing_text():
    result = _parse_vision_json_response(
        '```json\n{"objects":["sun"],"scene":"park","mood":"happy",'
        '"confidence_score":0.88}\n```\nSummary: done.'
    )

    assert result["objects"] == ["sun"]
    assert result["mood"] == "happy"


@pytest.mark.asyncio
async def test_analyze_children_drawing_falls_back_on_non_json_vision_text(
    monkeypatch,
    tmp_path,
):
    from PIL import Image
    from backend.src.mcp_servers import vision_analysis_server

    img_path = tmp_path / "drawing.png"
    Image.new("RGB", (64, 64), color="lightblue").save(img_path)

    _FakeVisionClient.response_text = (
        "I can see a cheerful child drawing with a blue sky and a small animal."
    )
    monkeypatch.setattr(
        vision_analysis_server,
        "AsyncAnthropic",
        _FakeVisionClient,
    )

    result = await image_to_story_agent._call_mcp_tool(
        vision_analysis_server.analyze_children_drawing,
        {"image_path": str(img_path), "child_age": 7}
    )
    data = json.loads(result["content"][0]["text"])

    assert "error" not in data
    assert data["vision_analysis"].startswith("I can see")
    assert data["story_potential"].startswith("I can see")
    assert data["objects"] == []


@pytest.mark.asyncio
async def test_call_mcp_tool_accepts_sdk_wrapped_tool():
    async def fake_handler(args):
        assert args == {"value": "demo"}
        return {"ok": True}

    result = await image_to_story_agent._call_mcp_tool(
        _FakeSdkTool(fake_handler),
        {"value": "demo"},
    )

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_direct_stream_pipeline_accepts_sdk_wrapped_mcp_tools(monkeypatch):
    async def fake_memory_prompt(*args, **kwargs):
        return ""

    async def fake_story_dedup(*args, **kwargs):
        return ""

    async def fake_post_gen_safety(story_text, *args, **kwargs):
        assert kwargs["content_type"] == "image_story"
        assert kwargs["age_group"] == "6-8"
        return story_text, 0.96, False

    async def fake_analyze(args):
        assert args["child_age"] == 7
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "objects": ["rabbit", "map"],
                            "scene": "forest",
                            "mood": "curious",
                            "confidence_score": 0.98,
                        }
                    ),
                }
            ]
        }

    async def fake_safety(args):
        assert args["content_type"] == "story"
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"safety_score": 0.96, "passed": True}),
                }
            ]
        }

    monkeypatch.setattr(
        image_to_story_agent,
        "analyze_children_drawing",
        _FakeSdkTool(fake_analyze),
    )
    monkeypatch.setattr(
        image_to_story_agent,
        "check_content_safety",
        _FakeSdkTool(fake_safety),
    )
    monkeypatch.setattr(
        image_to_story_agent,
        "get_story_memory_prompt",
        fake_memory_prompt,
    )
    monkeypatch.setattr(
        image_to_story_agent,
        "_search_story_dedup",
        fake_story_dedup,
    )
    monkeypatch.setattr(
        image_to_story_agent,
        "enforce_post_gen_safety",
        fake_post_gen_safety,
    )

    fake_anthropic = ModuleType("anthropic")
    fake_anthropic.AsyncAnthropic = _FakeAnthropicClient
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    events = []
    async for event in image_to_story_agent._direct_stream_image_to_story(
        image_path="/tmp/fake-image.png",
        child_id="child-123",
        child_age=7,
        interests=["adventure"],
        enable_audio=False,
        art_theme=None,
    ):
        events.append(event)

    result_event = next(event for event in events if event["type"] == "result")
    assert result_event["data"]["story"].startswith("A brave rabbit")
    assert result_event["data"]["analysis"]["scene"] == "forest"
    assert result_event["data"]["safety_score"] == 0.96
