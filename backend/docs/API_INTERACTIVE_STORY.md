# Interactive Story API

> API service for generating multi-branch interactive stories, allowing children to make choices at key points that influence the story's direction

## Overview

The Interactive Story API allows users to create interactive story sessions where children can make choices at key story nodes that influence the story's progression. All branches ultimately lead to positive, uplifting endings.

**Base URL:** `/api/v1/story/interactive`

---

## Endpoint List

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/start` | Start a new interactive story |
| POST | `/{session_id}/choose` | Choose a story branch |
| GET | `/{session_id}/status` | Get session status |

---

## 1. Start an Interactive Story

### `POST /api/v1/story/interactive/start`

Create a new interactive story session and generate the story opening.

#### Request Format

**Content-Type:** `application/json`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `child_id` | string | Yes | Child's unique identifier |
| `age_group` | string | Yes | Age group: `3-5`, `6-8`, `9-12` |
| `interests` | array | Yes | List of interest tags (1-5 items) |
| `theme` | string | No | Story theme (optional) |
| `voice` | string | No | Voice type, default `fable` |
| `enable_audio` | boolean | No | Whether to generate audio, default `true` |

#### Request Example

```bash
curl -X POST "http://localhost:8000/api/v1/story/interactive/start" \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": ["dinosaurs", "adventure"],
    "theme": "Dinosaur Expedition",
    "voice": "fable",
    "enable_audio": false
  }'
```

#### Response Format

**Status Code:** `201 Created`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "story_title": "Dinosaur Expedition Adventure",
  "opening": {
    "segment_id": 0,
    "text": "On a bright sunny morning, Xiao Ming found a glowing dinosaur egg in the garden! It was bigger than a goose egg and had beautiful green patterns on it...",
    "audio_url": null,
    "choices": [
      {
        "choice_id": "choice_0_a",
        "text": "Explore right away",
        "emoji": "🔍"
      },
      {
        "choice_id": "choice_0_b",
        "text": "Find friends to come along",
        "emoji": "👫"
      },
      {
        "choice_id": "choice_0_c",
        "text": "Observe it carefully",
        "emoji": "👀"
      }
    ],
    "is_ending": false
  },
  "created_at": "2026-01-31T10:30:00"
}
```

---

## 2. Choose a Story Branch

### `POST /api/v1/story/interactive/{session_id}/choose`

Make a choice in the interactive story and receive the next story segment.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | Session ID |

#### Request Format

**Content-Type:** `application/json`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `choice_id` | string | Yes | ID of the selected choice |

#### Request Example

```bash
curl -X POST "http://localhost:8000/api/v1/story/interactive/c04adb72-163a-44e3-90b9-4bdce58ba1bb/choose" \
  -H "Content-Type: application/json" \
  -d '{
    "choice_id": "choice_0_a"
  }'
```

#### Response Format (In Progress)

**Status Code:** `200 OK`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "next_segment": {
    "segment_id": 1,
    "text": "Xiao Ming decided to explore right away. He carefully picked up the dinosaur egg and found it was warm and glowing faintly. Suddenly, cracks appeared on the shell...",
    "audio_url": null,
    "choices": [
      {
        "choice_id": "choice_1_a",
        "text": "Help the baby dinosaur hatch",
        "emoji": "🐣"
      },
      {
        "choice_id": "choice_1_b",
        "text": "Wait for it to come out on its own",
        "emoji": "⏳"
      }
    ],
    "is_ending": false
  },
  "choice_history": ["choice_0_a"],
  "progress": 0.25
}
```

#### Response Format (Ending)

When the story reaches its conclusion:

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "next_segment": {
    "segment_id": 3,
    "text": "After this wonderful adventure, Xiao Ming and the little dinosaur became the best of friends. He learned to bravely face the unknown and understood the value of friendship. What an unforgettable experience!",
    "audio_url": null,
    "choices": [],
    "is_ending": true
  },
  "choice_history": ["choice_0_a", "choice_1_a", "choice_2_b"],
  "progress": 1.0
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Session already completed or expired |
| 404 | Session not found |
| 500 | Story generation failed |

---

## 3. Get Session Status

### `GET /api/v1/story/interactive/{session_id}/status`

Query the current status of an interactive story session.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | Session ID |

#### Request Example

```bash
curl "http://localhost:8000/api/v1/story/interactive/c04adb72-163a-44e3-90b9-4bdce58ba1bb/status"
```

#### Response Format

**Status Code:** `200 OK`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "status": "completed",
  "child_id": "child_001",
  "story_title": "Dinosaur Expedition Adventure",
  "current_segment": 4,
  "total_segments": 4,
  "choice_history": ["choice_0_a", "choice_1_a", "choice_2_b"],
  "educational_summary": {
    "themes": ["courage", "friendship"],
    "concepts": ["decision-making", "exploration"],
    "moral": "Facing challenges bravely is easier when you have friends by your side"
  },
  "created_at": "2026-01-31T10:30:00",
  "updated_at": "2026-01-31T10:35:00",
  "expires_at": "2026-02-01T10:30:00"
}
```

#### Session States

| State | Description |
|-------|-------------|
| `active` | Session is in progress; choices can still be made |
| `completed` | Story has been completed |
| `expired` | Session has expired (after 24 hours) |

---

## Age Adaptation Configuration

Story complexity and length are automatically adjusted based on the age group:

| Age Group | Total Segments | Words per Segment | Sentence Length | Theme Depth |
|-----------|---------------|-------------------|-----------------|-------------|
| 3-5 years | 3 | 50-100 words | 5-10 words | Simple, concrete, related to daily life |
| 6-8 years | 4 | 100-200 words | 10-15 words | Fun adventures, simple moral choices |
| 9-12 years | 5 | 150-300 words | 15-25 words | Complex plots, tests of character and wisdom |

---

## Story Flow

```
Start story (POST /start)
    |
Return opening + choices
    |
User makes a choice (POST /{session_id}/choose)
    |
Return next segment + new choices
    |
... Repeat 2-4 rounds ...
    |
Reach ending (is_ending: true)
    |
Return educational summary
```

---

## Design Principles

### 1. All Branches Lead to Good Endings

No matter what choices a child makes, the story always leads to a positive, uplifting ending. Children are never penalized for making a "wrong" choice.

### 2. Integrated Education

Every story naturally incorporates STEAM or character education elements:
- **Scientific curiosity**
- **Friendship and cooperation**
- **Courage and confidence**
- **Empathy and kindness**

### 3. Age Adaptation

Automatically adjusted based on age:
- Vocabulary complexity
- Sentence length
- Plot complexity
- Number of choices

---

## Usage Examples

### Python - Complete Story Flow

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1/story/interactive"

# 1. Start the story
start_response = requests.post(f"{BASE_URL}/start", json={
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": ["dinosaurs", "adventure"],
    "theme": "Dinosaur Expedition"
})
story = start_response.json()
session_id = story["session_id"]

print(f"Story title: {story['story_title']}")
print(f"Opening: {story['opening']['text']}")
print(f"Choices: {[c['text'] for c in story['opening']['choices']]}")

# 2. Loop through choices until reaching the ending
while True:
    # Get available choices
    status = requests.get(f"{BASE_URL}/{session_id}/status").json()

    if status["status"] == "completed":
        print("\nStory finished!")
        print(f"Educational summary: {status['educational_summary']}")
        break

    # Here you can let the user choose; this example auto-selects the first option
    choice_id = story.get('opening', {}).get('choices', [{}])[0].get('choice_id') or \
                next_segment.get('choices', [{}])[0].get('choice_id')

    # Make the choice
    choose_response = requests.post(f"{BASE_URL}/{session_id}/choose", json={
        "choice_id": choice_id
    })
    next_segment = choose_response.json()["next_segment"]

    print(f"\nSegment {next_segment['segment_id']}: {next_segment['text']}")
    print(f"Progress: {choose_response.json()['progress'] * 100:.0f}%")

    if next_segment["is_ending"]:
        break

    print(f"Choices: {[c['text'] for c in next_segment['choices']]}")
```

### JavaScript - React Component Example

```javascript
import { useState, useEffect } from 'react';

function InteractiveStory({ childId, ageGroup, interests }) {
  const [sessionId, setSessionId] = useState(null);
  const [segment, setSegment] = useState(null);
  const [progress, setProgress] = useState(0);
  const [isEnding, setIsEnding] = useState(false);

  // Start the story
  const startStory = async () => {
    const response = await fetch('/api/v1/story/interactive/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ child_id: childId, age_group: ageGroup, interests })
    });
    const data = await response.json();
    setSessionId(data.session_id);
    setSegment(data.opening);
  };

  // Make a choice
  const makeChoice = async (choiceId) => {
    const response = await fetch(`/api/v1/story/interactive/${sessionId}/choose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice_id: choiceId })
    });
    const data = await response.json();
    setSegment(data.next_segment);
    setProgress(data.progress);
    setIsEnding(data.next_segment.is_ending);
  };

  return (
    <div className="story-container">
      {!sessionId ? (
        <button onClick={startStory}>Start Story</button>
      ) : (
        <>
          <div className="progress-bar" style={{ width: `${progress * 100}%` }} />
          <p className="story-text">{segment?.text}</p>

          {!isEnding && segment?.choices?.map(choice => (
            <button
              key={choice.choice_id}
              onClick={() => makeChoice(choice.choice_id)}
            >
              {choice.emoji} {choice.text}
            </button>
          ))}

          {isEnding && <p>Story complete!</p>}
        </>
      )}
    </div>
  );
}
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Session not found | Invalid session_id | Start a new story |
| Session already completed | Story has ended | Check status for educational summary, or start a new story |
| Session expired | More than 24 hours elapsed | Start a new story |
| Invalid choice | choice_id does not match | Use a valid choice_id from the response |

### Error Response Examples

```json
{
  "detail": "Session not found"
}
```

```json
{
  "detail": "Session is already completed and cannot continue"
}
```
