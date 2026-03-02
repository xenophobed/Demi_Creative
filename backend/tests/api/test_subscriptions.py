"""API tests for topic subscription CRUD (#88, #94)."""

import uuid

import pytest


@pytest.mark.asyncio
class TestSubscriptionEndpoints:
    async def test_create_list_delete_subscription(self, test_client):
        child_id = f"child-sub-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            create = await client.post(
                "/api/v1/subscriptions",
                json={"child_id": child_id, "topic": "science"},
            )
            assert create.status_code == 201
            assert create.json()["topic"] == "science"
            assert create.json()["is_active"] is True

            list_resp = await client.get(f"/api/v1/subscriptions/{child_id}")
            assert list_resp.status_code == 200
            payload = list_resp.json()
            assert isinstance(payload.get("items"), list)
            assert any(item["topic"] == "science" for item in payload["items"])

            delete = await client.delete(f"/api/v1/subscriptions/{child_id}/science")
            assert delete.status_code == 204

            list_after = await client.get(f"/api/v1/subscriptions/{child_id}")
            assert list_after.status_code == 200
            assert all(item["topic"] != "science" for item in list_after.json()["items"])

    async def test_duplicate_subscription_returns_409(self, test_client):
        child_id = f"child-sub-{uuid.uuid4().hex[:8]}"

        async with test_client as client:
            first = await client.post(
                "/api/v1/subscriptions",
                json={"child_id": child_id, "topic": "animals"},
            )
            assert first.status_code == 201

            second = await client.post(
                "/api/v1/subscriptions",
                json={"child_id": child_id, "topic": "animals"},
            )
            assert second.status_code == 409

    async def test_subscription_limit_max_5(self, test_client):
        child_id = f"child-sub-{uuid.uuid4().hex[:8]}"
        topics = ["science", "nature", "technology", "space", "animals", "sports"]

        async with test_client as client:
            for topic in topics[:5]:
                response = await client.post(
                    "/api/v1/subscriptions",
                    json={"child_id": child_id, "topic": topic},
                )
                assert response.status_code == 201

            over_limit = await client.post(
                "/api/v1/subscriptions",
                json={"child_id": child_id, "topic": topics[5]},
            )
            assert over_limit.status_code == 400
            assert "Maximum subscriptions per child is 5" in over_limit.json()["detail"]

    async def test_topic_validation_enum_only(self, test_client):
        async with test_client as client:
            response = await client.post(
                "/api/v1/subscriptions",
                json={"child_id": f"child-sub-{uuid.uuid4().hex[:8]}", "topic": "dinosaurs"},
            )
            assert response.status_code == 422
