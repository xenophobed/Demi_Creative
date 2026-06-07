import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from backend.src.agents import image_to_story_agent


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


@pytest.mark.asyncio
async def test_direct_stream_pipeline_accepts_sdk_wrapped_mcp_tools(monkeypatch):
    async def fake_memory_prompt(*args, **kwargs):
        return ""

    async def fake_story_dedup(*args, **kwargs):
        return ""

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
