"""
Shared path constants

Single source of truth for all data directory paths, anchored to the
backend package location so they resolve correctly regardless of CWD.
"""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
AUDIO_DIR = DATA_DIR / "audio"
VIDEO_DIR = DATA_DIR / "videos"
VIDEO_JOBS_DIR = DATA_DIR / "video_jobs"
STYLED_DIR = DATA_DIR / "styled"
DB_PATH = DATA_DIR / "creative_agent.db"
SHARED_DIR = BACKEND_DIR.parent / "shared"
# Prefer the repo-root shared/ copy; fall back to the copy bundled inside the
# backend package. The bundled copy guarantees the seed bank ships even when the
# deploy excludes shared/ (e.g. .railwayignore / watchPatterns scoped to backend/**),
# so /api/v1/inspiration-daily never 503s on a missing file.
_SEED_BANK_SHARED = SHARED_DIR / "inspiration-seed-bank.json"
_SEED_BANK_BUNDLED = BACKEND_DIR / "src" / "services" / "inspiration-seed-bank.json"
SEED_BANK_PATH = _SEED_BANK_SHARED if _SEED_BANK_SHARED.exists() else _SEED_BANK_BUNDLED
