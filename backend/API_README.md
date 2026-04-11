# Creative Agent API - User Guide

Kids Creative Workshop FastAPI Service

## Table of Contents

- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Development Guide](#development-guide)
- [Testing Guide](#testing-guide)

---

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp ../.env.example ../.env
# Edit the .env file and add the required API keys
```

Required environment variables:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. Start the Service

```bash
# Development mode (auto-reload)
python -m backend.src.main

# Or use uvicorn
uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000
```

The service will start at `http://localhost:8000`

### 4. Access API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## API Endpoints

### Health Check

#### GET /
Root path health check

**Response example**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:00:00",
  "services": {
    "api": "running",
    "session_manager": "running"
  }
}
```

#### GET /health
Detailed health check

**Response example**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:00:00",
  "services": {
    "api": "running",
    "session_manager": "running",
    "environment": "configured"
  }
}
```

---

### Image to Story

#### POST /api/v1/image-to-story
Upload a child's drawing and generate a personalized story

**Request parameters** (Form Data):
- `image` (file, required): Drawing image (PNG/JPG, max 10MB)
- `child_id` (string, required): Child's unique identifier
- `age_group` (enum, required): Age group ("3-5", "6-8", "9-12")
- `interests` (string, optional): Interest tags, comma-separated (max 5)
- `voice` (string, optional): Voice type (default: "nova")
- `enable_audio` (boolean, optional): Whether to generate audio (default: true)

**Request example**:
```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8" \
  -F "interests=animals,adventure,space" \
  -F "voice=nova" \
  -F "enable_audio=true"
```

**Response example** (201 Created):
```json
{
  "story_id": "uuid-here",
  "story": {
    "text": "Once upon a time there was a little dog...",
    "word_count": 350,
    "age_adapted": true
  },
  "audio_url": "https://example.com/audio.mp3",
  "educational_value": {
    "themes": ["friendship", "courage"],
    "concepts": ["colors", "animals"],
    "moral": "Friendship makes us stronger"
  },
  "characters": [
    {
      "character_name": "Lightning Pup",
      "description": "A brave little dog",
      "appearances": 2
    }
  ],
  "analysis": {
    "objects": ["dog", "tree"],
    "emotions": ["happy"]
  },
  "safety_score": 0.95,
  "created_at": "2024-01-26T10:00:00"
}
```

---

### Interactive Story

#### POST /api/v1/story/interactive/start
Start a new interactive story session

**Request body** (JSON):
```json
{
  "child_id": "child_001",
  "age_group": "6-8",
  "interests": ["animals", "adventure"],
  "theme": "Forest Expedition",
  "voice": "fable",
  "enable_audio": true
}
```

**Response example** (201 Created):
```json
{
  "session_id": "uuid-here",
  "story_title": "The Mysterious Forest Expedition",
  "opening": {
    "segment_id": 0,
    "text": "On a bright sunny morning...",
    "audio_url": "https://example.com/audio.mp3",
    "choices": [
      {
        "choice_id": "choice_0_a",
        "text": "Open it right away",
        "emoji": "🔓"
      },
      {
        "choice_id": "choice_0_b",
        "text": "Find friends to come along",
        "emoji": "👫"
      }
    ],
    "is_ending": false
  },
  "created_at": "2024-01-26T10:00:00"
}
```

#### POST /api/v1/story/interactive/{session_id}/choose
Make a choice in the interactive story

**Path parameters**:
- `session_id`: Session ID

**Request body** (JSON):
```json
{
  "choice_id": "choice_0_a"
}
```

**Response example** (200 OK):
```json
{
  "session_id": "uuid-here",
  "next_segment": {
    "segment_id": 1,
    "text": "The protagonist bravely entered the cave...",
    "audio_url": "https://example.com/audio.mp3",
    "choices": [
      {
        "choice_id": "choice_1_a",
        "text": "Continue deeper",
        "emoji": "➡️"
      },
      {
        "choice_id": "choice_1_b",
        "text": "Stop and observe",
        "emoji": "👀"
      }
    ],
    "is_ending": false
  },
  "choice_history": ["choice_0_a"],
  "progress": 0.2
}
```

#### GET /api/v1/story/interactive/{session_id}/status
Get interactive story session status

**Path parameters**:
- `session_id`: Session ID

**Response example** (200 OK):
```json
{
  "session_id": "uuid-here",
  "status": "active",
  "child_id": "child_001",
  "story_title": "The Mysterious Forest Expedition",
  "current_segment": 2,
  "total_segments": 5,
  "choice_history": ["choice_0_a", "choice_1_b"],
  "educational_summary": null,
  "created_at": "2024-01-26T10:00:00",
  "updated_at": "2024-01-26T10:05:00",
  "expires_at": "2024-01-27T10:00:00"
}
```

---

## Development Guide

### Project Structure

```
backend/
├── src/
│   ├── api/
│   │   ├── models.py          # Pydantic models
│   │   ├── routes/
│   │   │   ├── image_to_story.py
│   │   │   └── interactive_story.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── session_manager.py # Session management
│   │   └── __init__.py
│   ├── agents/
│   │   └── image_to_story_agent.py
│   ├── mcp_servers/           # MCP Tools
│   └── main.py                # FastAPI application
└── requirements.txt
```

### Adding New Endpoints

1. Define request/response models in `src/api/models.py`
2. Create a route file in `src/api/routes/`
3. Register the route in `src/main.py`

Example:
```python
# src/api/routes/new_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["New Feature"])

@router.post("/new-feature")
async def new_feature():
    return {"message": "Hello"}

# src/main.py
from .api.routes import new_feature
app.include_router(new_feature.router)
```

### Environment Configuration

- **Development**: `ENVIRONMENT=development`
- **Testing**: `ENVIRONMENT=test`
- **Production**: `ENVIRONMENT=production`

### Logging

Uses Python standard library logging:
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Info log")
logger.error("Error log")
```

---

## Testing Guide

### Run All Tests

```bash
# Run from the project root directory
pytest tests/ -v
```

### Run Specific Tests

```bash
# API tests
pytest tests/api/ -v

# Integration tests
pytest tests/integration/ -v

# Contract tests
pytest tests/contracts/ -v

# Single test file
pytest tests/api/test_health.py -v

# Single test class
pytest tests/api/test_health.py::TestHealthCheck -v

# Single test function
pytest tests/api/test_health.py::TestHealthCheck::test_root_endpoint -v
```

### Test Coverage

```bash
# Generate coverage report
pytest tests/ --cov=backend/src --cov-report=html

# View the report
open htmlcov/index.html
```

### Skipping Slow Tests

Some tests (such as end-to-end tests) may require external services and are marked with `@pytest.mark.skip`:

```bash
# Run all tests except skipped ones
pytest tests/ -v
```

### Test File Organization

```
tests/
├── api/                      # API endpoint tests
│   ├── test_health.py
│   ├── test_image_to_story.py
│   └── test_interactive_story.py
├── integration/              # Integration tests
│   ├── test_session_integration.py
│   └── test_end_to_end.py
└── contracts/                # Contract tests
    └── mcp_tools_contract.py
```

### Mocking External Dependencies

For tests that depend on external services, use `pytest-mock`:

```python
@pytest.mark.asyncio
async def test_with_mock(mocker):
    # Mock Agent call
    mock_result = {"story": "Test story"}
    mocker.patch(
        "backend.src.agents.image_to_story_agent.image_to_story",
        return_value=mock_result
    )

    # Test code...
```

---

## FAQ

### Q: API fails to start
A: Check the following:
1. Environment variables are correctly configured (`.env` file)
2. Dependencies are fully installed (`pip install -r requirements.txt`)
3. Port 8000 is not occupied by another process

### Q: File upload fails
A: Ensure:
1. File size < 10MB
2. File format is PNG/JPG/WEBP
3. `python-multipart` is installed

### Q: Tests are failing
A: Common causes:
1. Missing environment variables (for tests)
2. External services not mocked
3. Test data directory permission issues

---

## Performance Optimization

### Recommended Production Configuration

```bash
# Use multiple workers
uvicorn backend.src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

### Using Gunicorn (Recommended)

```bash
gunicorn backend.src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

---

## Security Recommendations

1. **Never commit `.env` files to version control**
2. **Use HTTPS in production**
3. **Restrict CORS allowed origins**
4. **Implement rate limiting** (using `slowapi` or similar)
5. **Regularly update dependencies**

---

## Support

For questions, refer to:
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Technical Architecture
- [PRD.md](../PRD.md) - Product Requirements
- [IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md) - Implementation Log

---

**Version**: 1.0.0
**Last Updated**: 2024-01-26
