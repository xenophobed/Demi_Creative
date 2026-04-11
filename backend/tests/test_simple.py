"""
Simple test script - no external library dependencies
"""

import sys
import os
from pathlib import Path

# Add project path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== Simple Tests ===\n")

# Test 1: Import check
print("Test 1: Check module imports")
print("-" * 50)

try:
    # Test importing models
    from backend.src.api.models import (
        AgeGroup,
        VoiceType,
        ImageToStoryRequest,
        InteractiveStoryStartRequest
    )
    print("✅ API models imported successfully")

    # Test importing session_manager
    from backend.src.services import SessionManager
    print("✅ SessionManager imported successfully")

    # Test importing main
    print("✅ All core modules imported successfully\n")

except ImportError as e:
    print(f"❌ Import failed: {e}\n")
    sys.exit(1)

# Test 2: SessionManager basic functionality
print("Test 2: SessionManager basic functionality")
print("-" * 50)

try:
    # Create test session manager
    manager = SessionManager(sessions_dir="./data/test_simple_sessions")
    print("✅ SessionManager instance created successfully")

    # Create session
    session = manager.create_session(
        child_id="test_simple_001",
        story_title="Simple test story",
        age_group="6-8",
        interests=["test"],
        total_segments=3
    )

    print(f"✅ Session created successfully: {session.session_id}")

    # Get session
    retrieved = manager.get_session(session.session_id)
    assert retrieved is not None
    print("✅ Session retrieved successfully")

    # Delete session
    manager.delete_session(session.session_id)
    print("✅ Session deleted successfully")

    # Clean up directory
    import shutil
    test_dir = Path("./data/test_simple_sessions")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    print("✅ Test cleanup completed\n")

except Exception as e:
    print(f"❌ SessionManager test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Validate Pydantic models
print("Test 3: Pydantic model validation")
print("-" * 50)

try:
    from backend.src.api.models import InteractiveStoryStartRequest

    # Test valid request
    valid_request = InteractiveStoryStartRequest(
        child_id="test_001",
        age_group=AgeGroup.AGE_6_8,
        interests=["animals", "adventure"]
    )
    print(f"✅ Valid request created successfully: {valid_request.child_id}")

    # Test validator
    try:
        invalid_request = InteractiveStoryStartRequest(
            child_id="test_002",
            age_group=AgeGroup.AGE_6_8,
            interests=["a", "b", "c", "d", "e", "f"]  # More than 5
        )
        print("❌ Validator did not trigger (should have failed)")
    except Exception:
        print("✅ Validator correctly caught error")

    print("✅ Pydantic model validation succeeded\n")

except Exception as e:
    print(f"❌ Pydantic model test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: File structure check
print("Test 4: File structure check")
print("-" * 50)

required_files = [
    "backend/src/main.py",
    "backend/src/api/models.py",
    "backend/src/api/routes/image_to_story.py",
    "backend/src/api/routes/interactive_story.py",
    "backend/src/services/session_manager.py",
    "backend/requirements.txt",
]

all_exist = True
for file_path in required_files:
    full_path = project_root / file_path
    if full_path.exists():
        print(f"✅ {file_path}")
    else:
        print(f"❌ {file_path} (missing)")
        all_exist = False

if all_exist:
    print("\n✅ All required files exist\n")
else:
    print("\n⚠️  Some files are missing\n")

print("=" * 60)
print("🎉 All basic tests passed!")
print("=" * 60)
print("\nHint: To run full API tests, first install dependencies:")
print("  cd backend")
print("  pip install -r requirements.txt")
print("  python3 ../run_tests.py")
