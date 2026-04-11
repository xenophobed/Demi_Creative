# Creative Agent API Documentation

> Kids Creative Workshop API Documentation Index

## Overview

The Creative Agent API is an AI Agent-powered creative content generation platform that provides safe, engaging, and educational content creation services for children aged 3-12.

**API Version:** 1.0.0
**Base URL:** `http://localhost:8000`

---

## API Documentation Index

| Document | Description |
|----------|-------------|
| [API_IMAGE_TO_STORY.md](API_IMAGE_TO_STORY.md) | Image to Story API |
| [API_INTERACTIVE_STORY.md](API_INTERACTIVE_STORY.md) | Interactive Story API |
| [API_HEALTH_CHECK.md](API_HEALTH_CHECK.md) | Health Check API |

---

## Quick Reference

### Image to Story

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/image-to-story` | Upload a drawing and generate a story |
| GET | `/api/v1/stories/{story_id}` | Get story details |
| GET | `/api/v1/stories` | List all stories |

### Interactive Story

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/story/interactive/start` | Start an interactive story |
| POST | `/api/v1/story/interactive/{session_id}/choose` | Choose a branch |
| GET | `/api/v1/story/interactive/{session_id}/status` | Get session status |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Quick health check |
| GET | `/health` | Detailed health check |

---

## Authentication

The current API version does not require authentication. Appropriate authentication mechanisms should be added for production deployments.

---

## Common Response Format

### Success Response

```json
{
  "field1": "value1",
  "field2": "value2",
  ...
}
```

### Error Response

```json
{
  "error": "ErrorType",
  "message": "Error description",
  "details": [...],
  "timestamp": "2026-01-31T10:30:00"
}
```

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created successfully |
| 400 | Invalid request parameters |
| 404 | Resource not found |
| 413 | Request body too large |
| 422 | Request validation failed |
| 500 | Internal server error |

---

## Age Groups

All APIs use a unified age group definition:

| Age Group | Description | Content Characteristics |
|-----------|-------------|------------------------|
| `3-5` | Preschool children | Simple vocabulary, short sentences, concrete concepts |
| `6-8` | Lower elementary school | Basic vocabulary, simple plots, moral choices |
| `9-12` | Upper elementary school | Rich vocabulary, complex plots, in-depth themes |

---

## Voice Types

TTS audio generation supports the following voice types:

| Type | Description | Recommended Use |
|------|-------------|-----------------|
| `nova` | Gentle female | Warm stories |
| `shimmer` | Lively female | Cheerful adventures |
| `alloy` | Neutral | General purpose |
| `echo` | Male | Adventure stories |
| `fable` | Storyteller | Interactive stories (default) |
| `onyx` | Deep male | Mystery stories |

---

## Content Safety Review

All generated content undergoes safety review:

### Filtered Content
- Violence, fighting, gore
- Horror, thriller elements
- Inappropriate language, discrimination
- Adult topics

### Positive Guidance
- Gender equality
- Cultural diversity
- Character education
- Environmental awareness

### Safety Score
- **0.0-0.3**: Severely non-compliant
- **0.3-0.7**: Non-compliant
- **0.7-0.85**: Marginally compliant
- **0.85-1.0**: Excellent (pass)

---

## Developer Tools

### Swagger UI

Visit `http://localhost:8000/api/docs` for the interactive API documentation.

### ReDoc

Visit `http://localhost:8000/api/redoc` for ReDoc-style documentation.

### OpenAPI Schema

Visit `http://localhost:8000/api/openapi.json` to obtain the OpenAPI specification file.

---

## Quick Start

### 1. Start the Service

```bash
cd backend
source venv/bin/activate
uvicorn src.main:app --reload --port 8000
```

### 2. Test Image to Story

```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8"
```

### 3. Test Interactive Story

```bash
# Start a story
curl -X POST "http://localhost:8000/api/v1/story/interactive/start" \
  -H "Content-Type: application/json" \
  -d '{"child_id": "child_001", "age_group": "6-8", "interests": ["dinosaurs"]}'

# Choose a branch
curl -X POST "http://localhost:8000/api/v1/story/interactive/{session_id}/choose" \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice_0_a"}'
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `OPENAI_API_KEY` | Yes | OpenAI API key (TTS) |
| `FRONTEND_URL` | No | Frontend URL (CORS) |

---

## Related Documentation

- [PRD.md](../../docs/PRD.md) - Product Requirements Document
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Technical Architecture Document
- [DOMAIN.md](../../docs/DOMAIN.md) - Domain Background Document
