"""
Content Hub Routes (Epic #437).

Aggregates the sub-routers under one importable `hub` module so:
  - main.py registers a single `app.include_router(hub.router)`.
  - The COPPA contract test (#450) finds the package via
    `from src.api.routes import hub`, which flips its skipif gate
    from True to False and activates the privacy invariant tests.
"""

from fastapi import APIRouter

from . import groups, posts, reactions

router = APIRouter()
router.include_router(groups.router)
router.include_router(posts.router)
router.include_router(reactions.router)

__all__ = ["router"]
