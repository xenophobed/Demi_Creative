"""Contract tests for avatar_url validation on UpdateProfileRequest (#263)."""

import pytest
from pydantic import ValidationError

from src.api.models import UpdateProfileRequest


class TestAvatarUrlValidation:
    def test_accepts_emoji_format(self):
        req = UpdateProfileRequest(avatar_url="emoji:🐼")
        assert req.avatar_url == "emoji:🐼"

    def test_accepts_https_url(self):
        req = UpdateProfileRequest(avatar_url="https://example.com/pic.png")
        assert req.avatar_url == "https://example.com/pic.png"

    def test_accepts_none(self):
        req = UpdateProfileRequest(avatar_url=None)
        assert req.avatar_url is None

    def test_accepts_omitted(self):
        req = UpdateProfileRequest()
        assert req.avatar_url is None

    def test_rejects_script_injection(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="<script>alert(1)</script>")

    def test_rejects_http_url(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="http://example.com/pic.png")

    def test_rejects_arbitrary_string(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="some random text")

    def test_rejects_javascript_url(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="javascript:alert(1)")

    def test_rejects_data_url(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="data:image/png;base64,abc")

    def test_rejects_empty_emoji_prefix(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="emoji:")

    def test_rejects_emoji_prefix_with_text(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(avatar_url="emoji:hello")

    def test_accepts_various_animal_emojis(self):
        for emoji in ['🐶', '🐱', '🦊', '🐙', '🦁', '🐼', '🦄', '🐲']:
            req = UpdateProfileRequest(avatar_url=f"emoji:{emoji}")
            assert req.avatar_url == f"emoji:{emoji}"
