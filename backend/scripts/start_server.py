#!/usr/bin/env python3
"""
Start FastAPI server.

This script is intentionally runnable from both the repository root:

    python backend/scripts/start_server.py

and the backend directory:

    cd backend
    python scripts/start_server.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configure_import_path() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def main() -> int:
    _configure_import_path()

    print("=== Starting Creative Agent API Service ===\n")

    try:
        print("1. Importing FastAPI...")
        import fastapi
        print(f"   ✅ FastAPI version: {fastapi.__version__}")

        print("2. Importing uvicorn...")
        import uvicorn
        print("   ✅ Uvicorn imported")

        print("3. Importing application...")
        from backend.src.main import app
        print("   ✅ Application imported successfully")

        if os.getenv("CREATIVE_AGENT_STARTUP_IMPORT_CHECK") == "1":
            return 0

        print("\n4. Starting server...")
        print("   Address: http://localhost:8000")
        print("   Docs: http://localhost:8000/api/docs")
        print("   Press Ctrl+C to stop the server\n")

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
        return 0

    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("\nPlease ensure all dependencies are installed:")
        print("  cd backend")
        print("  pip install -r requirements.txt")
        return 1

    except Exception as e:
        print(f"\n❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
