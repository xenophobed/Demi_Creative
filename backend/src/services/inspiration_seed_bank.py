"""
Inspiration Daily seed bank loader.

Loads and serves curated creative project entries from the shared JSON seed bank.
Provides deterministic daily rotation and category filtering.
"""

import json
import logging
from datetime import date
from typing import Optional

from ..api.models import InspirationCard
from ..paths import SEED_BANK_PATH

logger = logging.getLogger(__name__)

_seed_bank: list[InspirationCard] = []


def _load_seed_bank() -> list[InspirationCard]:
    """Load and validate seed bank from JSON file. Cached after first call."""
    global _seed_bank
    if _seed_bank:
        return _seed_bank

    try:
        with open(SEED_BANK_PATH) as f:
            data = json.load(f)
        entries = data.get("entries", [])
        _seed_bank = [InspirationCard(**entry) for entry in entries]
        logger.info("Loaded %d inspiration seed bank entries", len(_seed_bank))
    except FileNotFoundError:
        logger.error("Seed bank not found at %s", SEED_BANK_PATH)
        _seed_bank = []
    except Exception as exc:
        logger.error("Failed to load seed bank: %s", exc)
        _seed_bank = []

    return _seed_bank


def get_seed_bank() -> list[InspirationCard]:
    """Return all seed bank entries."""
    return _load_seed_bank()


def get_daily_seed(day: Optional[date] = None) -> Optional[InspirationCard]:
    """Return today's seed bank entry using deterministic day-of-year rotation."""
    entries = _load_seed_bank()
    if not entries:
        return None
    target = day or date.today()
    index = target.timetuple().tm_yday % len(entries)
    return entries[index]


def get_seeds_by_category(category: str) -> list[InspirationCard]:
    """Return all seed bank entries matching a category."""
    return [e for e in _load_seed_bank() if e.category == category]
