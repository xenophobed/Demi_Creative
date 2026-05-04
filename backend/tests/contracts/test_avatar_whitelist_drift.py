"""Drift contract test: keep frontend ANIMAL_EMOJIS aligned with backend mirror.

The frontend (`frontend/src/lib/avatars.ts`) and backend
(`backend/src/services/agent_constants.py`) must agree on the
animal-emoji avatar whitelist exactly — same set, same order, no
duplicates. This test parses the TypeScript source as text and
compares it to the Python tuple so the two never silently drift.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Ensure backend/ is importable from any cwd in CI.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.services.agent_constants import ANIMAL_EMOJIS as BACKEND_ANIMAL_EMOJIS


def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` until we find a repo root marker.

    Markers (in priority order): a `frontend/package.json` or a
    `pytest.ini` at the candidate directory. Falls back to the
    filesystem root if nothing matches, which will cause the test
    to fail loudly with a clear path error rather than silently
    pass.
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "frontend" / "package.json").is_file():
            return candidate
        if (candidate / "pytest.ini").is_file() and (
            candidate / "frontend"
        ).is_dir():
            return candidate
    raise RuntimeError(
        f"Could not locate repo root walking up from {start}; "
        "expected a `frontend/package.json` marker."
    )


def _frontend_avatars_path() -> Path:
    repo_root = _find_repo_root(Path(__file__))
    return repo_root / "frontend" / "src" / "lib" / "avatars.ts"


# Matches the contents between `[` and `]` of:
#   export const ANIMAL_EMOJIS = [ ... ] as const;
# Tolerant of whitespace and trailing commas; intolerant of nested arrays
# (which we don't want anyway — the contract requires a flat list).
_ARRAY_BLOCK_RE = re.compile(
    r"export\s+const\s+ANIMAL_EMOJIS\s*=\s*\[(?P<body>[^\]]*)\]\s*as\s+const\s*;",
    re.DOTALL,
)
# Pulls every double-quoted string from the captured array body.
# We intentionally only accept double-quoted strings to keep the parser
# simple — the source file is constrained to that style by convention.
_QUOTED_RE = re.compile(r'"([^"\\]*)"')


def _parse_frontend_emojis(source: str) -> list[str]:
    match = _ARRAY_BLOCK_RE.search(source)
    if match is None:
        raise AssertionError(
            "Could not find `export const ANIMAL_EMOJIS = [...] as const;` "
            "in frontend/src/lib/avatars.ts"
        )
    body = match.group("body")
    return _QUOTED_RE.findall(body)


def test_frontend_and_backend_avatar_lists_match_in_order() -> None:
    avatars_path = _frontend_avatars_path()
    assert avatars_path.is_file(), f"missing frontend avatar file: {avatars_path}"

    frontend_emojis = _parse_frontend_emojis(avatars_path.read_text(encoding="utf-8"))
    backend_emojis = list(BACKEND_ANIMAL_EMOJIS)

    # Order-sensitive equality: same elements in the same positions.
    assert frontend_emojis == backend_emojis, (
        "ANIMAL_EMOJIS drift detected between "
        "frontend/src/lib/avatars.ts and "
        "backend/src/services/agent_constants.py.\n"
        f"frontend: {frontend_emojis}\nbackend:  {backend_emojis}"
    )

    # Locked length — the UI grid + buddy picker assume exactly 20.
    assert len(frontend_emojis) == 20, (
        f"expected 20 avatars, got {len(frontend_emojis)} in frontend"
    )
    assert len(backend_emojis) == 20, (
        f"expected 20 avatars, got {len(backend_emojis)} in backend"
    )

    # No duplicates in either list.
    assert len(set(frontend_emojis)) == len(frontend_emojis), (
        f"duplicate emoji in frontend list: {frontend_emojis}"
    )
    assert len(set(backend_emojis)) == len(backend_emojis), (
        f"duplicate emoji in backend list: {backend_emojis}"
    )


def test_drift_detector_catches_reversed_list() -> None:
    """Negative-path sanity check: the comparison is not a tautology.

    If we silently reverse one side, the equality check must fail.
    This protects against accidental no-op asserts (e.g. comparing a
    list to itself) regressing the drift guarantee.
    """
    avatars_path = _frontend_avatars_path()
    frontend_emojis = _parse_frontend_emojis(avatars_path.read_text(encoding="utf-8"))
    reversed_backend = list(reversed(BACKEND_ANIMAL_EMOJIS))

    assert frontend_emojis != reversed_backend, (
        "Negative-path fixture failed: reversed list matched frontend, "
        "which means the comparison would pass even under drift. "
        "Check for accidental palindromic ordering."
    )
