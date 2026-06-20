"""
Tests for Kids Daily multi-segment audio in the Library API.

Regression for the bug where the library card's mini play button only played the
FIRST dialogue line of a Kids Daily show (Curious Kid's opening sentence) instead
of the whole episode. Each show stores one TTS clip per dialogue line in
``analysis.audio_urls`` ({"0": url, "1": url, ...}); the library item now surfaces
the ordered playlist as ``audio_segments`` so the mini player can play it all.
"""

from backend.src.api.models import LibraryItemType
from backend.src.api.routes.library import (
    _ordered_audio_segments,
    _story_to_library_item,
)


# ---------------------------------------------------------------------------
# _ordered_audio_segments helper
# ---------------------------------------------------------------------------


class TestOrderedAudioSegments:
    def test_orders_by_numeric_index_not_string(self):
        # String sort would put "10" before "2"; numeric sort must not.
        raw = {
            "0": "http://x/a.mp3",
            "1": "http://x/b.mp3",
            "2": "http://x/c.mp3",
            "10": "http://x/k.mp3",
        }
        assert _ordered_audio_segments(raw) == [
            "http://x/a.mp3",
            "http://x/b.mp3",
            "http://x/c.mp3",
            "http://x/k.mp3",
        ]

    def test_skips_blank_and_keeps_order(self):
        raw = {"0": "http://x/a.mp3", "1": "", "2": "http://x/c.mp3"}
        assert _ordered_audio_segments(raw) == ["http://x/a.mp3", "http://x/c.mp3"]

    def test_empty_or_invalid_returns_none(self):
        assert _ordered_audio_segments({}) is None
        assert _ordered_audio_segments(None) is None
        assert _ordered_audio_segments("not a dict") is None

    def test_drops_missing_local_files(self):
        # /data/audio/ URLs are validated against disk; a non-existent file is dropped.
        raw = {"0": "http://x/a.mp3", "1": "/data/audio/does-not-exist-xyz.mp3"}
        assert _ordered_audio_segments(raw) == ["http://x/a.mp3"]


# ---------------------------------------------------------------------------
# _story_to_library_item integration
# ---------------------------------------------------------------------------


def _kids_daily_story(audio_urls):
    return {
        "story_id": "daily-1",
        "story": {"text": "Today's show is about friendly robots."},
        "educational_value": {"themes": ["science"]},
        "analysis": {
            "story_type": "kids_daily",
            "kid_title": "Robots!",
            "audio_urls": audio_urls,
        },
        "audio_url": None,
        "story_type": "kids_daily",
        "created_at": "2026-06-19T00:00:00",
    }


class TestKidsDailyLibraryItem:
    def test_surfaces_full_playlist(self):
        story = _kids_daily_story(
            {"0": "http://x/0.mp3", "1": "http://x/1.mp3", "2": "http://x/2.mp3"}
        )
        item = _story_to_library_item(story)
        assert item.type == LibraryItemType.KIDS_DAILY
        assert item.audio_segments == [
            "http://x/0.mp3",
            "http://x/1.mp3",
            "http://x/2.mp3",
        ]

    def test_falls_back_to_first_segment_when_audio_url_missing(self):
        # Episodes that only have per-line audio still get a clickable play button.
        story = _kids_daily_story({"0": "http://x/0.mp3", "1": "http://x/1.mp3"})
        item = _story_to_library_item(story)
        assert item.audio_url == "http://x/0.mp3"

    def test_art_story_has_no_segments(self):
        story = {
            "story_id": "art-1",
            "story": {"text": "A rainbow tale."},
            "educational_value": {},
            "analysis": {},
            "audio_url": "http://x/story.mp3",
            "story_type": "image_to_story",
            "created_at": "2026-06-19T00:00:00",
        }
        item = _story_to_library_item(story)
        assert item.type == LibraryItemType.ART_STORY
        assert item.audio_segments is None
