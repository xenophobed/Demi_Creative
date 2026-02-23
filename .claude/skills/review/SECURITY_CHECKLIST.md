# Security & Safety Checklist for Code Review

## General Security
- [ ] No hardcoded API keys or secrets (ANTHROPIC_API_KEY, OPENAI_API_KEY)
- [ ] No credentials committed to git
- [ ] Input validation on all API endpoints (Pydantic models)
- [ ] File upload paths sanitized (no path traversal: `../`, absolute paths outside data/)
- [ ] SQL injection risk — only parameterized queries via repository pattern
- [ ] Authentication required on user-specific endpoints

## Child Content Safety (Critical)
- [ ] All AI-generated story/interactive content passes through `check_content_safety` MCP tool
- [ ] Safety score threshold enforced (>= 0.85 to pass)
- [ ] Age adaptation rules applied before content delivery
- [ ] No direct user input injected into prompts without sanitization
- [ ] Image uploads validated (file type, size limits)
- [ ] No personally identifiable information (child names, photos) stored unencrypted
- [ ] Session data does not leak between different child accounts
- [ ] Vector database queries filtered by `child_id` to prevent cross-user data leakage

## Agent / MCP Tool Security
- [ ] `allowed_tools` in `ClaudeAgentOptions` is minimal (principle of least privilege)
- [ ] `permission_mode="acceptEdits"` only granted where necessary
- [ ] MCP server tool schemas validate input types and ranges
- [ ] Agent `max_turns` set to prevent runaway loops
- [ ] Structured output schemas (`output_format`) prevent prompt injection via JSON

## API Security
- [ ] CORS configured appropriately for production
- [ ] Rate limiting considered for AI endpoints (they're expensive)
- [ ] Error messages don't expose internal stack traces to clients
- [ ] File serving endpoints don't expose arbitrary filesystem paths

## Data Privacy
- [ ] Child data (drawings, stories, audio) stored only in designated paths (`data/`)
- [ ] No child data sent to third parties beyond Anthropic/OpenAI for generation
- [ ] Session cleanup: old session files purged after story completion
