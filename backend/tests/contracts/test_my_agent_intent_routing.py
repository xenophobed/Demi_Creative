"""
My Agent Intent Routing Contract Tests (#497)

Locks down the intent routing contract for the My Agent proxy so the
right specialist is invoked for a given child utterance. This is the
foundation that turns the SDK-orchestrated multi-agent setup
(landed in #495 / PR #501) from a generic "chat with an agent" into
a buddy that actually delegates correctly.

What this file pins:

  - A pure `_classify_intent(message, *, has_image, child_age)` helper
    exists in `my_agent_proxy` and returns deterministic routing strings
    so the contract is testable WITHOUT a live LLM call.
  - At least 10 sample utterances per intent class route to the right
    specialist (per issue #497 acceptance criteria).
  - "Vague story" utterances (e.g. "story?", "tell me a story") for
    ages 3–5 default to image-to-story (when an image is present) and
    interactive-story otherwise — younger kids benefit from a guided
    visual hook.
  - Ages 6–8 with a vague story request and NO image receive a
    `disambiguate` signal so the proxy can ask one clarifying question
    instead of guessing.
  - Inline/small-talk utterances ("hi", "what did we make yesterday?")
    do NOT trigger a specialist — the proxy answers inline. This
    protects from over-delegation that would burn tool calls on
    conversation.
  - The proxy's `system_prompt` and user-turn prompt both contain
    explicit routing rules naming all four specialists, so the SDK's
    `Agent` tool has unambiguous guidance.
  - Every subagent's `description` field mentions concrete trigger
    phrases — the SDK uses the description for delegation matching, so
    drift here is a silent regression.

Parent Epic: #436 (My Agent — Personal Creative Buddy)
Issue: #497
"""

from __future__ import annotations

import pytest

from backend.src.agents import my_agent_proxy


# ---------------------------------------------------------------------------
# Public routing labels — pinned so a rename breaks tests.
# ---------------------------------------------------------------------------

IMAGE_STORY = "image-story-specialist"
INTERACTIVE_STORY = "interactive-story-specialist"
KIDS_DAILY = "kids-daily-specialist"
SAFETY_REVIEW = "safety-review-specialist"
INLINE = "inline"
DISAMBIGUATE = "disambiguate"


# ---------------------------------------------------------------------------
# Per-domain sample utterances. Each list MUST stay >= 10 (issue #497 AC).
# ---------------------------------------------------------------------------

IMAGE_STORY_UTTERANCES = [
    "Tell me a story about this drawing!",
    "Can you make a story from my picture?",
    "I drew a dragon — turn it into a story please.",
    "What story does my drawing tell?",
    "Make my drawing into a story",
    "Build a story around this picture",
    "Use my drawing for a story",
    "Tell me a story about what I drew",
    "Look at my drawing and make a story",
    "Story about this image please",
    "Write a story about my picture",
]

INTERACTIVE_STORY_UTTERANCES = [
    "Let's have an adventure!",
    "I want a branching story",
    "Can we do a choose your own adventure?",
    "I want to pick what happens next",
    "Let's play an interactive story",
    "I want choices in my story",
    "Make a story where I decide",
    "Adventure time! I want to choose",
    "Let's go on a quest together",
    "Start an interactive adventure",
    "Story with choices please",
]

KIDS_DAILY_UTTERANCES = [
    "What's happening in the world?",
    "Tell me about the news today",
    "Any news for kids?",
    "What happened today in the news?",
    "I want today's news",
    "Tell me what's new in the world",
    "Daily news update please",
    "What's going on in the news",
    "Read me today's headlines",
    "Any kid-friendly news today?",
    "I want my kids daily episode",
]

INLINE_UTTERANCES = [
    "hi",
    "hello buddy!",
    "How are you?",
    "What did we make yesterday?",
    "Do you remember my dragon story?",
    "What's your name?",
    "Thank you!",
    "Good morning",
    "Can we talk?",
    "Tell me a joke",
    "How old are you?",
]


# ---------------------------------------------------------------------------
# Helper presence
# ---------------------------------------------------------------------------


class TestClassifyIntentHelperExists:
    """`_classify_intent` is the contract surface this file pins. It MUST
    exist as a pure synchronous function so routing is deterministically
    testable without spinning up the SDK."""

    def test_classify_intent_is_a_callable(self):
        assert hasattr(my_agent_proxy, "_classify_intent")
        assert callable(my_agent_proxy._classify_intent)


# ---------------------------------------------------------------------------
# Routing per intent class (>= 10 utterances each, per #497 AC)
# ---------------------------------------------------------------------------


class TestImageStoryRouting:
    """Image-attached drawing-to-story utterances must route to image-story-specialist."""

    @pytest.mark.parametrize("msg", IMAGE_STORY_UTTERANCES)
    def test_routes_image_story_with_image(self, msg: str):
        result = my_agent_proxy._classify_intent(msg, has_image=True, child_age=7)
        assert result == IMAGE_STORY, f"{msg!r} routed to {result} instead of {IMAGE_STORY}"


class TestInteractiveStoryRouting:
    """Branching / adventure / choice phrases must route to interactive-story-specialist."""

    @pytest.mark.parametrize("msg", INTERACTIVE_STORY_UTTERANCES)
    def test_routes_interactive_story(self, msg: str):
        result = my_agent_proxy._classify_intent(msg, has_image=False, child_age=8)
        assert result == INTERACTIVE_STORY, (
            f"{msg!r} routed to {result} instead of {INTERACTIVE_STORY}"
        )


class TestKidsDailyRouting:
    """News / world / today / daily phrases must route to kids-daily-specialist."""

    @pytest.mark.parametrize("msg", KIDS_DAILY_UTTERANCES)
    def test_routes_kids_daily(self, msg: str):
        result = my_agent_proxy._classify_intent(msg, has_image=False, child_age=8)
        assert result == KIDS_DAILY, f"{msg!r} routed to {result} instead of {KIDS_DAILY}"


class TestInlineRouting:
    """Greetings + small-talk + memory recall must NOT delegate. The
    proxy answers inline so we don't burn tool calls on conversation."""

    @pytest.mark.parametrize("msg", INLINE_UTTERANCES)
    def test_inline_does_not_delegate(self, msg: str):
        result = my_agent_proxy._classify_intent(msg, has_image=False, child_age=8)
        assert result == INLINE, f"{msg!r} routed to {result} instead of {INLINE}"


# ---------------------------------------------------------------------------
# Age-aware vague routing (issue #497 AC)
# ---------------------------------------------------------------------------


class TestAgeAwareVagueStoryRouting:
    """
    Acceptance criteria from #497:
      - Vague "story?" for ages 3–5 routes to image-to-story
      - Ages 6–8 may receive ONE clarifying question for unclear intent
    """

    @pytest.mark.parametrize("msg", ["story?", "tell me a story", "I want a story"])
    def test_vague_story_with_image_routes_image_story_for_3_5(self, msg: str):
        """3–5 with an image — image-to-story is the natural anchor."""
        result = my_agent_proxy._classify_intent(msg, has_image=True, child_age=4)
        assert result == IMAGE_STORY

    @pytest.mark.parametrize("msg", ["story?", "tell me a story", "I want a story"])
    def test_vague_story_no_image_routes_image_story_for_3_5(self, msg: str):
        """3–5 without an image — still default to image-to-story flow
        per #497 AC ('Vague \"story?\" routes to image-to-story for ages 3–5').
        The proxy will then prompt for a drawing."""
        result = my_agent_proxy._classify_intent(msg, has_image=False, child_age=4)
        assert result == IMAGE_STORY

    @pytest.mark.parametrize("msg", ["story?", "tell me a story", "I want a story"])
    def test_vague_story_for_6_8_disambiguates(self, msg: str):
        """6–8 without an image — emit `disambiguate` so the proxy
        asks one clarifying question instead of guessing wrong."""
        result = my_agent_proxy._classify_intent(msg, has_image=False, child_age=7)
        assert result == DISAMBIGUATE

    @pytest.mark.parametrize("msg", ["story?", "tell me a story"])
    def test_vague_story_with_image_for_6_8_routes_image_story(self, msg: str):
        """6–8 WITH an image — the image is a strong signal, route to
        image-to-story instead of pestering the child."""
        result = my_agent_proxy._classify_intent(msg, has_image=True, child_age=7)
        assert result == IMAGE_STORY


# ---------------------------------------------------------------------------
# Image attachment never breaks news / interactive routing
# ---------------------------------------------------------------------------


class TestImagePresenceDoesNotOverrideExplicitIntent:
    """Having an image attached must not blindly force image-to-story
    if the child explicitly asks for an adventure or for news."""

    def test_image_attached_but_news_still_routes_kids_daily(self):
        result = my_agent_proxy._classify_intent(
            "What's happening in the news today?", has_image=True, child_age=8
        )
        assert result == KIDS_DAILY

    def test_image_attached_but_adventure_still_routes_interactive(self):
        result = my_agent_proxy._classify_intent(
            "Let's go on a branching adventure!", has_image=True, child_age=8
        )
        assert result == INTERACTIVE_STORY


# ---------------------------------------------------------------------------
# System prompt routing language
# ---------------------------------------------------------------------------


class TestSystemPromptIntentRouting:
    """The parent agent's `system_prompt` must enumerate all four
    specialists by name + use routing language. The SDK's `Agent` tool
    delegation depends on this guidance — vague prompts cause silent
    drift to wrong specialists."""

    def _build_system_prompt(self) -> str:
        # `_build_system_prompt` is a pure helper that returns the
        # exact string handed to ClaudeAgentOptions(system_prompt=...).
        return my_agent_proxy._build_system_prompt()

    def test_system_prompt_mentions_all_four_specialists_by_name(self):
        prompt = self._build_system_prompt()
        for specialist in (
            "image-story-specialist",
            "interactive-story-specialist",
            "kids-daily-specialist",
            "safety-review-specialist",
        ):
            assert specialist in prompt, (
                f"system_prompt missing specialist: {specialist}"
            )

    def test_system_prompt_uses_routing_language(self):
        prompt = self._build_system_prompt().lower()
        # Must use delegation vocabulary so the SDK Agent tool kicks in.
        assert "delegate" in prompt or "delegation" in prompt
        assert "specialist" in prompt

    def test_system_prompt_mentions_image_news_and_branching_triggers(self):
        """The routing rules must surface the trigger families so the
        parent agent (a fast model) doesn't have to infer them."""
        prompt = self._build_system_prompt().lower()
        assert "image" in prompt or "drawing" in prompt or "picture" in prompt
        assert "news" in prompt
        assert "branching" in prompt or "adventure" in prompt or "choice" in prompt


# ---------------------------------------------------------------------------
# User prompt routing language
# ---------------------------------------------------------------------------


class TestUserPromptCarriesRoutingHint:
    """The per-turn prompt built inside stream_my_agent_chat must
    surface the routing rules too — the parent agent re-reads it every
    turn, so it's the cheapest place to put nudge text."""

    def test_user_prompt_template_mentions_specialists(self):
        # `_build_user_prompt` is a pure helper used by stream_my_agent_chat.
        text = my_agent_proxy._build_user_prompt(
            my_agent_context="ctx",
            history="",
            image_path=None,
            message="hi",
        )
        assert "image-story-specialist" in text
        assert "interactive-story-specialist" in text
        assert "kids-daily-specialist" in text


# ---------------------------------------------------------------------------
# Subagent description must include concrete triggers
# ---------------------------------------------------------------------------


class TestSubagentDescriptionsCarryTriggerPhrases:
    """The SDK uses each AgentDefinition.description for delegation
    matching — generic descriptions cause routing to drift. Pin that
    every specialist mentions at least one trigger keyword."""

    def test_image_story_specialist_description_mentions_drawing(self):
        sub = my_agent_proxy._build_subagents("ctx")["image-story-specialist"]
        desc = (getattr(sub, "description", "") or "").lower()
        assert "drawing" in desc or "picture" in desc or "image" in desc

    def test_interactive_story_specialist_description_mentions_branching(self):
        sub = my_agent_proxy._build_subagents("ctx")["interactive-story-specialist"]
        desc = (getattr(sub, "description", "") or "").lower()
        assert "branching" in desc or "adventure" in desc or "choice" in desc

    def test_kids_daily_specialist_description_mentions_news(self):
        sub = my_agent_proxy._build_subagents("ctx")["kids-daily-specialist"]
        desc = (getattr(sub, "description", "") or "").lower()
        assert "news" in desc or "daily" in desc

    def test_safety_review_specialist_description_mentions_safety(self):
        sub = my_agent_proxy._build_subagents("ctx")["safety-review-specialist"]
        desc = (getattr(sub, "description", "") or "").lower()
        assert "safety" in desc
