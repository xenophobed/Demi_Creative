---
name: test
description: Generate or improve tests for specific code. Use when adding test coverage, writing tests for new MCP tools, agent functions, API routes, frontend components, or improving existing tests.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, mcp__playwright__browser_navigate, mcp__playwright__browser_navigate_back, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_select_option, mcp__playwright__browser_hover, mcp__playwright__browser_drag, mcp__playwright__browser_press_key, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_wait_for, mcp__playwright__browser_tabs, mcp__playwright__browser_close, mcp__playwright__browser_resize, mcp__playwright__browser_console_messages, mcp__playwright__browser_handle_dialog, mcp__playwright__browser_file_upload, mcp__playwright__browser_network_requests, mcp__playwright__browser_fill_form, mcp__playwright__browser_evaluate, mcp__playwright__browser_run_code, mcp__playwright__browser_install
argument-hint: [file path, component, or page to test, e.g. "backend/src/mcp_servers/safety_check_server.py" or "frontend landing page" or "frontend upload flow"]
---

# Test Generation Skill

Write tests for: $ARGUMENTS

## Step 0 — Detect Test Layer

Determine which layer to test based on the argument:

| Argument pattern | Layer | Strategy |
|-----------------|-------|----------|
| `backend/...` or MCP tool / agent / API route name | **Backend** | pytest (see Backend Process below) |
| `frontend/...` or page / component / flow / UI name | **Frontend** | Playwright MCP live testing (see Frontend Process below) |
| Ambiguous | **Both** | Run backend tests first, then frontend verification |

---

## Backend Process

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

---

## Frontend Process (Playwright MCP)

Use the Playwright MCP tools to test frontend pages, components, and user flows **live in the browser**. The dev server runs at `http://localhost:5173`.

### Steps

1. **Navigate** to the relevant page:
   - Use `browser_navigate` to open `http://localhost:5173` (or the specific route)

2. **Capture initial state**:
   - Use `browser_snapshot` to get an accessibility snapshot of the page (preferred for structural checks)
   - Use `browser_screenshot` when visual appearance matters

3. **Interact and verify flows**:
   - Use `browser_click`, `browser_type`, `browser_select_option` etc. to simulate user actions
   - After each significant interaction, take a snapshot/screenshot to verify the result
   - Check for expected text, elements, navigation changes

4. **Test responsive layouts** (when relevant):
   - Use `browser_resize` to test mobile (375×667), tablet (768×1024), desktop (1280×800)
   - Snapshot after each resize to verify layout adapts

5. **Check for errors**:
   - Use `browser_console_messages` to catch JavaScript errors or warnings
   - Verify no unexpected network failures with `browser_network_requests`

6. **Report findings**:
   - Summarize what was tested, what passed, and any issues found
   - Include screenshots for visual issues
   - Suggest fixes for any failures

### Frontend Test Scenarios

| Scenario | What to check |
|----------|--------------|
| Page load | Renders without JS errors, key elements visible |
| Navigation | Links/buttons route to correct pages |
| Form submission | Validation works, success/error states show |
| Upload flow | File picker works, progress shown, result displays |
| Age selector | Options render, selection persists, content adapts |
| Story display | Text renders, TTS button works, branching options show |
| Responsive | Layout adapts at mobile/tablet/desktop breakpoints |
| Empty states | Graceful UI when no data exists |

### Playwright MCP Quick Reference

| Tool | Use for |
|------|---------|
| `browser_navigate` | Go to a URL |
| `browser_navigate_back` | Go back to previous page |
| `browser_snapshot` | Get accessibility tree (fast, structural) |
| `browser_take_screenshot` | Capture visual screenshot (png/jpeg) |
| `browser_click` | Click an element (by ref from snapshot) |
| `browser_type` | Type text into an input |
| `browser_fill_form` | Fill multiple form fields at once |
| `browser_select_option` | Choose from a dropdown |
| `browser_hover` | Hover over an element |
| `browser_press_key` | Press keyboard keys (Enter, Tab, etc.) |
| `browser_wait_for` | Wait for an element or condition |
| `browser_resize` | Change viewport size |
| `browser_console_messages` | Read JS console output |
| `browser_network_requests` | Inspect network calls |
| `browser_file_upload` | Upload a file to a file input |
| `browser_tabs` | List open browser tabs |
| `browser_evaluate` | Run JS expression in the page |
| `browser_close` | Close the browser |

---

## Project Test Patterns (Backend)

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

## Test Runner (Backend)

```bash
# Run all tests
cd backend && python -m pytest tests/ -v

# Run specific file
cd backend && python -m pytest tests/contracts/mcp_tools_contract.py -v

# Run with coverage
cd backend && python -m pytest tests/ --cov=src --cov-report=term-missing
```
