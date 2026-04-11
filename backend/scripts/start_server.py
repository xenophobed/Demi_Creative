#!/usr/bin/env python3
"""
Start FastAPI server
"""

import sys
from pathlib import Path

# Add project path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== Starting Creative Agent API Service ===\n")

try:
    print("1. Importing FastAPI...")
    import fastapi
    print(f"   ✅ FastAPI version: {fastapi.__version__}")

    print("2. Importing uvicorn...")
    import uvicorn
    print(f"   ✅ Uvicorn imported")

    print("3. Importing application...")
    from backend.src.main import app
    print("   ✅ Application imported successfully")

    print("\n4. Starting server...")
    print("   Address: http://localhost:8000")
    print("   Docs: http://localhost:8000/api/docs")
    print("   Press Ctrl+C to stop the server\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("\nPlease ensure all dependencies are installed:")
    print("  cd backend")
    print("  pip install -r requirements.txt")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ Startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
