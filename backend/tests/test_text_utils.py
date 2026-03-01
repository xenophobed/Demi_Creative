"""Tests for CJK-aware word counting utility (#78)."""

from backend.src.utils.text import count_words


class TestCountWords:
    """count_words handles Latin, CJK, and mixed text."""

    def test_empty_string(self):
        assert count_words("") == 0

    def test_none_like_empty(self):
        assert count_words("") == 0

    def test_english_words(self):
        assert count_words("Hello world") == 2

    def test_english_sentence(self):
        assert count_words("The quick brown fox jumps over the lazy dog") == 9

    def test_chinese_characters(self):
        # Each CJK character = 1 word
        assert count_words("从前有一个小女孩") == 8

    def test_chinese_story(self):
        text = "从前有一个勇敢的小女孩，她住在一个美丽的村庄里。"
        # Each CJK char counts as 1 word; punctuation is not CJK
        result = count_words(text)
        assert result >= 20  # Should be ~22 CJK chars

    def test_mixed_chinese_english(self):
        text = "Hello 世界 test"
        # 2 latin words + 2 CJK chars = 4
        assert count_words(text) == 4

    def test_japanese_text(self):
        # Kanji characters should be counted
        text = "日本語テスト"
        result = count_words(text)
        assert result >= 3  # At least the kanji chars

    def test_only_whitespace(self):
        assert count_words("   \n\t  ") == 0

    def test_punctuation_only(self):
        # Punctuation is not CJK and produces no space-separated tokens
        assert count_words("。！？，") == 0

    def test_numbers_count_as_words(self):
        assert count_words("I have 3 cats") == 4

    def test_multiline_text(self):
        text = "Line one\nLine two\nLine three"
        assert count_words(text) == 6
