"""
Text utilities for multilingual content.

Provides CJK-aware word counting for Chinese, Japanese, and Korean text.
"""

import re


# CJK Unicode ranges — each character counts as one "word"
_CJK_RE = re.compile(
    r'[\u4e00-\u9fff'        # CJK Unified Ideographs
    r'\u3400-\u4dbf'          # CJK Unified Ideographs Extension A
    r'\uf900-\ufaff'          # CJK Compatibility Ideographs
    r'\U00020000-\U0002a6df'  # CJK Unified Ideographs Extension B
    r'\U0002a700-\U0002b73f'  # CJK Unified Ideographs Extension C
    r'\U0002b740-\U0002b81f'  # CJK Unified Ideographs Extension D
    r'\U0002b820-\U0002ceaf]' # CJK Unified Ideographs Extension E
)

# CJK and fullwidth punctuation — stripped before Latin word count
_CJK_PUNCT_RE = re.compile(
    r'[\u3000-\u303f'         # CJK Symbols and Punctuation
    r'\uff00-\uff0f'          # Fullwidth digits/punctuation
    r'\uff1a-\uff20'          # Fullwidth colon to at-sign
    r'\uff3b-\uff40'          # Fullwidth brackets
    r'\uff5b-\uff65'          # Fullwidth braces, halfwidth forms
    r'\ufe30-\ufe4f]'         # CJK Compatibility Forms
)


def count_words(text: str) -> int:
    """Count words in multilingual text.

    CJK characters are each counted as one word.
    Latin/other text is counted by space-separated tokens.
    Mixed text combines both counts.
    """
    if not text:
        return 0
    cjk_chars = len(_CJK_RE.findall(text))
    non_cjk = _CJK_RE.sub('', text)
    non_cjk = _CJK_PUNCT_RE.sub(' ', non_cjk)
    latin_words = len(non_cjk.split())
    return cjk_chars + latin_words
