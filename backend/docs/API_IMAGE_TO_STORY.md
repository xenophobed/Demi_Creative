# Image to Story API

> API service for transforming children's drawings into personalized stories

## Overview

The Image to Story API allows users to upload children's drawings. An AI Agent analyzes the drawing content and generates a personalized story appropriate for the child's age group.

**Base URL:** `/api/v1`

---

## Endpoint List

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/image-to-story` | Upload a drawing and generate a story |
| GET | `/stories/{story_id}` | Get story details |
| GET | `/stories` | List all stories |

---

## 1. Image to Story

### `POST /api/v1/image-to-story`

Upload a child's drawing and have AI generate a personalized story.

#### Request Format

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | File | Yes | Child's drawing image (PNG/JPG/WEBP, max 10MB) |
| `child_id` | string | Yes | Child's unique identifier |
| `age_group` | string | Yes | Age group: `3-5`, `6-8`, `9-12` |
| `interests` | string | No | Interest tags, comma-separated (max 5) |
| `voice` | string | No | Voice type, default `nova` |
| `enable_audio` | boolean | No | Whether to generate audio, default `true` |

#### Voice Types

| Value | Description |
|-------|-------------|
| `nova` | Gentle female |
| `shimmer` | Lively female |
| `alloy` | Neutral |
| `echo` | Male |
| `fable` | Storyteller |
| `onyx` | Deep male |

#### Request Example

```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8" \
  -F "interests=animals,adventure,space" \
  -F "voice=nova" \
  -F "enable_audio=true"
```

#### Response Format

**Status Code:** `201 Created`

```json
{
  "story_id": "550e8400-e29b-41d4-a716-446655440000",
  "story": {
    "text": "On a bright sunny morning, Little Rabbit discovered a magical garden...",
    "word_count": 285,
    "age_adapted": true
  },
  "audio_url": "/data/audio/550e8400-e29b-41d4-a716-446655440000.mp3",
  "educational_value": {
    "themes": ["friendship", "courage"],
    "concepts": ["colors", "nature"],
    "moral": "Helping friends is a joyful thing to do"
  },
  "characters": [
    {
      "character_name": "Little Rabbit",
      "description": "A cute white little rabbit",
      "appearances": 1
    }
  ],
  "analysis": {
    "detected_objects": ["rabbit", "garden", "sun"],
    "emotions": ["happy", "curious"],
    "colors": ["green", "pink", "yellow"]
  },
  "safety_score": 0.95,
  "created_at": "2026-01-31T10:30:00"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Invalid request parameters (unsupported file format, too many interest tags, etc.) |
| 413 | File size exceeds limit (10MB) |
| 500 | Internal server error |

```json
{
  "error": "ValidationError",
  "message": "Unsupported file format. Allowed formats: .jpg, .jpeg, .png, .webp",
  "timestamp": "2026-01-31T10:30:00"
}
```

---

## 2. Get Story Details

### `GET /api/v1/stories/{story_id}`

Retrieve details of a previously generated story by its ID.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `story_id` | string | Story unique identifier |

#### Request Example

```bash
curl "http://localhost:8000/api/v1/stories/550e8400-e29b-41d4-a716-446655440000"
```

#### Response Format

**Status Code:** `200 OK`

```json
{
  "story_id": "550e8400-e29b-41d4-a716-446655440000",
  "child_id": "child_001",
  "age_group": "6-8",
  "story": {
    "text": "On a bright sunny morning...",
    "word_count": 285,
    "age_adapted": true
  },
  "audio_url": "/data/audio/550e8400-e29b-41d4-a716-446655440000.mp3",
  "educational_value": {
    "themes": ["friendship", "courage"],
    "concepts": ["colors", "nature"],
    "moral": "Helping friends is a joyful thing to do"
  },
  "characters": [...],
  "analysis": {...},
  "safety_score": 0.95,
  "created_at": "2026-01-31T10:30:00",
  "image_path": "./data/uploads/child_001/abc123.png",
  "stored_at": "2026-01-31T10:30:05"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 404 | Story not found |

---

## 3. List All Stories

### `GET /api/v1/stories`

Retrieve a list of all generated stories.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `child_id` | string | No | Filter by child ID |
| `limit` | integer | No | Limit number of results, default 20 |

#### Request Example

```bash
# Get all stories
curl "http://localhost:8000/api/v1/stories"

# Filter by child ID
curl "http://localhost:8000/api/v1/stories?child_id=child_001&limit=10"
```

#### Response Format

**Status Code:** `200 OK`

```json
{
  "total": 3,
  "stories": [
    {
      "story_id": "550e8400-e29b-41d4-a716-446655440000",
      "child_id": "child_001",
      "created_at": "2026-01-31T10:30:00",
      "word_count": 285,
      "has_audio": true
    },
    {
      "story_id": "661f9511-f30c-52e5-b827-557766551111",
      "child_id": "child_001",
      "created_at": "2026-01-30T15:20:00",
      "word_count": 320,
      "has_audio": true
    }
  ]
}
```

---

## Age Adaptation

Generated stories are automatically adjusted based on the age group:

| Age Group | Word Count Range | Sentence Length | Vocabulary Level |
|-----------|-----------------|-----------------|------------------|
| 3-5 years | 100-200 words | 5-10 words | Basic everyday vocabulary |
| 6-8 years | 200-400 words | 10-15 words | Lower elementary vocabulary |
| 9-12 years | 400-800 words | 15-25 words | Upper elementary vocabulary |

---

## Content Safety Review

All generated stories undergo safety review:

- **Safety score range:** 0.0 - 1.0
- **Passing threshold:** >= 0.85
- **Review criteria:**
  - Filter violence, horror, inappropriate language
  - Ensure gender equality and cultural diversity
  - Integrate character education elements

---

## Usage Examples

### Python

```python
import requests

url = "http://localhost:8000/api/v1/image-to-story"

files = {
    "image": ("drawing.png", open("drawing.png", "rb"), "image/png")
}

data = {
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": "animals,adventure",
    "voice": "fable",
    "enable_audio": "true"
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"Story preview: {result['story']['text'][:50]}...")
print(f"Educational themes: {result['educational_value']['themes']}")
```

### JavaScript

```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('child_id', 'child_001');
formData.append('age_group', '6-8');
formData.append('interests', 'animals,adventure');

const response = await fetch('http://localhost:8000/api/v1/image-to-story', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('Story:', result.story.text);
```
