"""
API real test script

Runs real tests against API endpoints
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project path to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== Creative Agent API Real Tests ===\n")


async def test_health_check():
    """Test health check"""
    print("📋 Test 1: Health Check")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test root path
            response = await client.get("/")
            print(f"GET / - Status code: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")

            assert response.status_code == 200
            assert result["status"] in ["healthy", "degraded"]
            print("✅ Root path health check passed\n")

            # Test /health endpoint
            response = await client.get("/health")
            print(f"GET /health - Status code: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")

            assert response.status_code == 200
            assert "services" in result
            print("✅ Health check endpoint passed\n")

    except Exception as e:
        print(f"❌ Health check test failed: {e}\n")
        return False

    return True


async def test_session_manager():
    """Test session manager"""
    print("📋 Test 2: Session Manager")
    print("-" * 50)

    try:
        from backend.src.services import SessionManager

        # Create test session manager
        manager = SessionManager(sessions_dir="./data/test_sessions")

        # Create session
        print("Creating test session...")
        session = manager.create_session(
            child_id="test_child_001",
            story_title="Test story",
            age_group="6-8",
            interests=["animals", "adventure"],
            theme="Forest exploration",
            voice="fable",
            enable_audio=True,
            total_segments=5
        )

        print(f"Session ID: {session.session_id}")
        print(f"Child ID: {session.child_id}")
        print(f"Story title: {session.story_title}")
        print(f"Status: {session.status}")
        assert session.status == "active"
        print("✅ Session created successfully\n")

        # Get session
        print("Retrieving session...")
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        print("✅ Session retrieved successfully\n")

        # Update session
        print("Updating session...")
        segment = {
            "segment_id": 1,
            "text": "Story segment one",
            "choices": [
                {"choice_id": "c1_a", "text": "Option A", "emoji": "🅰️"}
            ]
        }

        success = manager.update_session(
            session_id=session.session_id,
            segment=segment,
            choice_id="c1_a"
        )

        assert success is True
        updated = manager.get_session(session.session_id)
        assert len(updated.segments) == 1
        assert "c1_a" in updated.choice_history
        print("✅ Session updated successfully\n")

        # List sessions
        print("Listing sessions...")
        sessions = manager.list_sessions(child_id="test_child_001")
        assert len(sessions) >= 1
        print(f"Found {len(sessions)} session(s)")
        print("✅ Session listing succeeded\n")

        # Delete session
        print("Deleting session...")
        success = manager.delete_session(session.session_id)
        assert success is True

        # Verify deletion
        deleted = manager.get_session(session.session_id)
        assert deleted is None
        print("✅ Session deleted successfully\n")

        # Clean up test directory
        import shutil
        test_dir = Path("./data/test_sessions")
        if test_dir.exists():
            shutil.rmtree(test_dir)

    except Exception as e:
        print(f"❌ Session manager test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_interactive_story_api():
    """Test interactive story API"""
    print("📋 Test 3: Interactive Story API")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app
        from backend.src.services import session_manager

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Start interactive story
            print("Starting interactive story...")
            start_payload = {
                "child_id": "test_child_api",
                "age_group": "6-8",
                "interests": ["animals", "adventure"],
                "theme": "Forest exploration",
                "voice": "fable",
                "enable_audio": True
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=start_payload
            )

            print(f"Status code: {response.status_code}")
            if response.status_code != 201:
                print(f"Error response: {response.text}")

            assert response.status_code == 201
            result = response.json()

            session_id = result["session_id"]
            print(f"Session ID: {session_id}")
            print(f"Story title: {result['story_title']}")
            print(f"Opening paragraph: {result['opening']['text'][:50]}...")
            print(f"Number of choices: {len(result['opening']['choices'])}")
            print("✅ Interactive story started successfully\n")

            # Get session status
            print("Getting session status...")
            status_response = await client.get(
                f"/api/v1/story/interactive/{session_id}/status"
            )

            assert status_response.status_code == 200
            status = status_response.json()
            print(f"Session status: {status['status']}")
            print(f"Current segment: {status['current_segment']}/{status['total_segments']}")
            print("✅ Status query succeeded\n")

            # Choose branch
            print("Choosing story branch...")
            choice_payload = {
                "choice_id": "choice_0_a"
            }

            choice_response = await client.post(
                f"/api/v1/story/interactive/{session_id}/choose",
                json=choice_payload
            )

            assert choice_response.status_code == 200
            choice_result = choice_response.json()
            print(f"Next paragraph: {choice_result['next_segment']['text'][:50]}...")
            print(f"Progress: {choice_result['progress'] * 100:.0f}%")
            print(f"Choice history: {choice_result['choice_history']}")
            print("✅ Branch selection succeeded\n")

            # Clean up test session
            session_manager.delete_session(session_id)

    except Exception as e:
        print(f"❌ Interactive story API test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_api_error_handling():
    """Test API error handling"""
    print("📋 Test 4: API Error Handling")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test invalid age group
            print("Testing invalid age group...")
            invalid_payload = {
                "child_id": "test_child",
                "age_group": "invalid",
                "interests": ["animals"]
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=invalid_payload
            )

            assert response.status_code == 422
            error = response.json()
            print(f"Error type: {error['error']}")
            print("✅ Validation error correctly caught\n")

            # Test nonexistent session
            print("Testing nonexistent session...")
            response = await client.get(
                "/api/v1/story/interactive/nonexistent_session/status"
            )

            assert response.status_code == 404
            error = response.json()
            print(f"Error message: {error['detail']}")
            print("✅ 404 error correctly handled\n")

            # Test missing required fields
            print("Testing missing required fields...")
            incomplete_payload = {
                "child_id": "test_child"
                # Missing age_group and interests
            }

            response = await client.post(
                "/api/v1/story/interactive/start",
                json=incomplete_payload
            )

            assert response.status_code == 422
            error = response.json()
            print(f"Number of error details: {len(error.get('details', []))}")
            print("✅ Required field validation succeeded\n")

    except Exception as e:
        print(f"❌ Error handling test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_api_documentation():
    """Test API documentation"""
    print("📋 Test 5: API Documentation Access")
    print("-" * 50)

    try:
        from httpx import AsyncClient
        from backend.src.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test OpenAPI JSON
            print("Testing OpenAPI spec...")
            response = await client.get("/api/openapi.json")

            assert response.status_code == 200
            openapi = response.json()
            assert "openapi" in openapi
            assert "info" in openapi
            assert "paths" in openapi
            print(f"API title: {openapi['info']['title']}")
            print(f"API version: {openapi['info']['version']}")
            print(f"Number of endpoints: {len(openapi['paths'])}")
            print("✅ OpenAPI spec accessible\n")

            # Test Swagger UI
            print("Testing Swagger UI...")
            response = await client.get("/api/docs")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            print("✅ Swagger UI accessible\n")

            # Test ReDoc
            print("Testing ReDoc...")
            response = await client.get("/api/redoc")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            print("✅ ReDoc accessible\n")

    except Exception as e:
        print(f"❌ API documentation test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    return True


async def main():
    """Run all tests"""
    print("Starting API real tests...\n")

    results = []

    # Run tests
    results.append(("Health Check", await test_health_check()))
    results.append(("Session Manager", await test_session_manager()))
    results.append(("Interactive Story API", await test_interactive_story_api()))
    results.append(("Error Handling", await test_api_error_handling()))
    results.append(("API Documentation", await test_api_documentation()))

    # Summarize results
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{name}: {status}")

    print("\n" + "=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
