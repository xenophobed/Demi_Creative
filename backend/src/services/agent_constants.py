"""
Server-side mirror of the animal-emoji avatar whitelist.

DO NOT EDIT WITHOUT UPDATING `frontend/src/lib/avatars.ts`.
The drift contract test in
`backend/tests/contracts/test_avatar_whitelist_drift.py` will fail
if these two lists diverge.
"""
from __future__ import annotations

# Exact same 20 emojis, exact same order, as frontend/src/lib/avatars.ts.
ANIMAL_EMOJIS: tuple[str, ...] = (
    "🐶",
    "🐱",
    "🐼",
    "🐨",
    "🦊",
    "🐰",
    "🐸",
    "🦁",
    "🐯",
    "🐮",
    "🐷",
    "🐵",
    "🐔",
    "🐧",
    "🦄",
    "🐲",
    "🐢",
    "🦋",
    "🐬",
    "🐙",
)

AVATAR_IDS: frozenset[str] = frozenset(f"emoji:{e}" for e in ANIMAL_EMOJIS)

MAX_AGENT_NAME_LENGTH: int = 32
MAX_AGENT_TITLE_LENGTH: int = 32

# Curated title list (#439) — derived from PRD §3.11.3.
# Pre-approved titles bypass the runtime safety check because they have
# already been reviewed by the product team.
CURATED_TITLES: tuple[str, ...] = (
    "Story Wizard",
    "Brave Lion",
    "Galaxy Explorer",
    "Dragon Friend",
    "Magic Painter",
    "Forest Guardian",
    "Ocean Adventurer",
    "Star Dreamer",
    "Dance Captain",
    "Inventor",
    "Riddle Master",
    "Cloud Surfer",
    "Tiny Hero",
    "Silly Scientist",
    "Music Maker",
    "Treasure Hunter",
    "Kindness Knight",
    "Robot Buddy",
    "Time Traveler",
    "Sunshine Maker",
)

CURATED_TITLES_SET: frozenset[str] = frozenset(CURATED_TITLES)
