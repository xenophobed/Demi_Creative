#!/usr/bin/env python3
"""
API test script
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("Creative Agent API Tests")
print("=" * 60)
print()

# Test 1: Health check
print("Test 1: Health check")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print("✅ Health check passed\n")
except Exception as e:
    print(f"❌ Error: {e}\n")

# Test 2: Start interactive story
print("Test 2: Start interactive story")
print("-" * 60)
try:
    payload = {
        "child_id": "test_001",
        "age_group": "6-8",
        "interests": ["animals", "adventure"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/story/interactive/start",
        json=payload
    )

    print(f"Status code: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if response.status_code == 201:
        session_id = result['session_id']
        print(f"\n✅ Interactive story created successfully")
        print(f"   Session ID: {session_id}")
        print(f"   Story title: {result['story_title']}")
        print(f"   Opening text: {result['opening']['text'][:50]}...")
        print()

        # Test 3: Get session status
        print("Test 3: Get session status")
        print("-" * 60)
        status_response = requests.get(
            f"{BASE_URL}/api/v1/story/interactive/{session_id}/status"
        )
        print(f"Status code: {status_response.status_code}")
        status_result = status_response.json()
        print(f"Response: {json.dumps(status_result, indent=2, ensure_ascii=False)}")
        print("✅ Status query succeeded\n")

        # Test 4: Choose branch
        print("Test 4: Choose story branch")
        print("-" * 60)
        choice_payload = {
            "choice_id": "choice_0_a"
        }

        choice_response = requests.post(
            f"{BASE_URL}/api/v1/story/interactive/{session_id}/choose",
            json=choice_payload
        )
        print(f"Status code: {choice_response.status_code}")
        choice_result = choice_response.json()
        print(f"Response: {json.dumps(choice_result, indent=2, ensure_ascii=False)}")
        print("✅ Branch selection succeeded\n")

    else:
        print(f"❌ Story creation failed\n")

except Exception as e:
    print(f"❌ Error: {e}\n")

# Test 5: Error handling - invalid age group
print("Test 5: Error handling - invalid age group")
print("-" * 60)
try:
    invalid_payload = {
        "child_id": "test_002",
        "age_group": "invalid",
        "interests": ["animals"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/story/interactive/start",
        json=invalid_payload
    )

    print(f"Status code: {response.status_code}")
    if response.status_code == 422:
        print("✅ Validation error correctly caught")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ Validation error not handled correctly")
    print()

except Exception as e:
    print(f"❌ Error: {e}\n")

# Test 6: Error handling - nonexistent session
print("Test 6: Error handling - nonexistent session")
print("-" * 60)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/story/interactive/nonexistent_id/status"
    )

    print(f"Status code: {response.status_code}")
    if response.status_code == 404:
        print("✅ 404 error correctly handled")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ 404 error not handled correctly")
    print()

except Exception as e:
    print(f"❌ Error: {e}\n")

print("=" * 60)
print("✅ API tests completed!")
print("=" * 60)
