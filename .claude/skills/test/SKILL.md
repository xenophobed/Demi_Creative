---
name: test
description: Generate or improve tests for specific code. Use when adding test coverage, writing tests for new MCP tools, agent functions, API routes, or improving existing tests.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file path or function to test, e.g. "backend/src/mcp_servers/safety_check_server.py"]
---

# Test Generation Skill

Write tests for: $ARGUMENTS

## Process

1. **Analyze the target code**: Read the file/function to understand behaviour and contracts

2. **Study existing test patterns**:
   - Contract tests: `backend/tests/contracts/` — define input/output schemas
   - API tests: `backend/tests/api/` — use FastAPI `TestClient`
   - Integration tests: `backend/tests/integration/`
   - Note assertion patterns, fixtures, mocking strategy, `@pytest.mark.asyncio` usage

3. **Identify test cases**:
   - **Happy path**: normal operation with valid inputs
   - **Edge cases**: empty inputs, boundary values (age 3, age 12), large inputs
   - **Error cases**: invalid inputs, missing files, API failures, SDK unavailable
   - **Contract verification**: input/output schema adherence for MCP tools
   - **Safety**: content safety pass/fail scenarios

4. **Write tests**:
   - Use `pytest` with `@pytest.mark.asyncio` for async functions
   - Use `TestClient` from `fastapi.testclient` for API routes
   - Mock `claude_agent_sdk` when testing agent orchestration in isolation
   - Follow the contract test pattern: define expected schema, then assert against it
   - Group by behaviour/scenario with descriptive test names
   - Use `conftest.py` fixtures for shared setup

5. **Run and verify**:
   ```bash
   cd backend && python -m pytest tests/ -k "<test_name>" -v
   ```
   - Confirm tests pass
   - Verify they fail when the code is broken (mutation check)

## Project Test Patterns

```python
# Contract test for an MCP tool
class TestSafetyCheckContract:
    @pytest.mark.asyncio
    async def test_check_content_safety_contract(self):
        result = await check_content_safety({"content": "...", "target_age": 7})
        data = json.loads(result["content"][0]["text"])
        assert "is_safe" in data
        assert "safety_score" in data
        assert 0.0 <= data["safety_score"] <= 1.0

# API test
def test_create_story_endpoint(client):
    response = client.post("/api/v1/image-to-story", ...)
    assert response.status_code == 200
    assert "story" in response.json()

# Agent test with SDK unavailable (mock mode)
def test_generates_mock_opening_without_sdk():
    result = asyncio.run(generate_story_opening(...))
    assert "title" in result
    assert "segment" in result
```

## Test Runner

```bash
# Run all tests
cd backend && python -m pytest tests/ -v

# Run specific file
cd backend && python -m pytest tests/contracts/mcp_tools_contract.py -v

# Run with coverage
cd backend && python -m pytest tests/ --cov=src --cov-report=term-missing
```
