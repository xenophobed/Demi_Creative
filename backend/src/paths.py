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
SEED_BANK_PATH = SHARED_DIR / "inspiration-seed-bank.json"
