# Kids Creative Workshop - Technical Architecture V2 (Based on Correct Agent SDK Understanding)

> **Important Update**: This architecture was redesigned based on correct understanding of the Claude Agent SDK

---

## Core Architecture Changes

### ❌ Previous Incorrect Understanding

```python
# Wrong: implementing Agent base class and tool execution loop manually
class BaseAgent:
    async def run(self, input_data):
        # Manually managing tool calls...
        while response.stop_reason == "tool_use":
            # Manual handling...
```

### ✅ Correct Agent SDK Usage

```python
# Correct: SDK automatically handles the execution loop
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Analyze this children's drawing and generate a story",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "mcp__vision__analyze"],
        mcp_servers={...}
    )
):
    # SDK automatically handles tool calls
    if isinstance(message, ResultMessage):
        print(message.result)
```

---

## 1. Correct Architecture Design

### 1.0 Artifact Graph (New)

The Artifact system uses a hybrid model of Story containers + Artifact first-class entities. See detailed design:

- [ARTIFACT_GRAPH_MODEL.md](./ARTIFACT_GRAPH_MODEL.md)

### 1.1 Overall Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI (Web API)                     │
│  - Receives user requests (drawings, story requests)   │
│  - Returns generated results                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│           Agent Orchestrator (Dispatch Layer)           │
│  - Creates Agent tasks                                  │
│  - Configures ClaudeAgentOptions                       │
│  - Processes Agent message stream                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│            Claude Agent SDK (Core Engine)               │
│  - Automatically manages tool execution loop           │
│  - Calls MCP Tools                                      │
│  - Calls Skills                                         │
└───────┬─────────────────┬────────────────┬──────────────┘
        │                 │                │
        ↓                 ↓                ↓
   ┌─────────┐      ┌──────────┐    ┌──────────┐
   │  Built  │      │   MCP    │    │  Skills  │
   │  -in    │      │  Tools   │    │ (.claude/│
   │  Tools  │      │(External)│    │  skills/)│
   └─────────┘      └──────────┘    └──────────┘
```

### 1.2 Key Concept Mapping

| Requirement | Implementation | Claude SDK Concept |
|-------------|---------------|-------------------|
| Drawing analysis | MCP Tool (Vision API) | `mcp__vision__analyze` |
| Story generation | Agent Prompt + Skills | `.claude/skills/story-generation/` |
| Vector search | MCP Tool (ChromaDB) | `mcp__vector-search__search_similar_drawings` |
| Content safety review | Custom MCP Tool | SDK MCP Server |
| Age adaptation | Skill (Markdown) | `.claude/skills/age-adapter/` |
| TTS generation | MCP Tool (OpenAI) | `mcp__openai__tts` |

---

## 2. MCP Tools Design

### 2.1 Vision Analysis MCP Server

```python
# src/mcp_servers/vision_analysis_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from anthropic import Anthropic
from typing import Any
import base64

@tool(
    name="analyze_children_drawing",
    description="""Analyze children's drawings, identifying objects, scenes, and emotions.

    Use cases:
    - After a child uploads a drawing, analyze its content
    - Identify main elements in the drawing (animals, people, objects)
    - Determine the scene (indoor/outdoor, day/night)
    - Identify emotional atmosphere (happy, excited, calm)

    Returns:
    - objects: list of identified objects
    - scene: scene description
    - mood: emotion/atmosphere
    - colors: primary colors
    """,
    input_schema={
        "image_path": {"type": "string", "description": "Image file path"}
    }
)
async def analyze_children_drawing(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze children's drawing"""
    client = Anthropic()

    # Read image and convert to base64
    with open(args['image_path'], 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    # Call Claude Vision API
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": """Please analyze this children's drawing:
                    1. List all objects in the drawing (animals, people, plants, items)
                    2. Describe the scene (indoor/outdoor, location)
                    3. Identify the emotional atmosphere (happy, excited, calm, curious, etc.)
                    4. Primary colors

                    Please return in JSON format:
                    {
                        "objects": ["object1", "object2"],
                        "scene": "scene description",
                        "mood": "emotion",
                        "colors": ["color1", "color2"]
                    }
                    """
                }
            ]
        }]
    )

    # Parse returned JSON
    import json
    result = json.loads(response.content[0].text)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


# Create Vision MCP Server
vision_server = create_sdk_mcp_server(
    name="vision-analysis",
    version="1.0.0",
    tools=[analyze_children_drawing]
)
```

### 2.2 Vector Search MCP Server

```python
# src/mcp_servers/vector_search_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
import chromadb
from typing import Any
import json

@tool(
    name="search_similar_drawings",
    description="""Search for similar children's drawings in the vector database.

    Use cases:
    - Find similar works the child has drawn before
    - Identify recurring characters (e.g. "Lightning the puppy")
    - Analyze the child's creative theme preferences

    Returns:
    - List of similar drawings (with similarity scores)
    - Description information for each drawing
    """,
    input_schema={
        "drawing_description": {"type": "string", "description": "Drawing description (used to generate query vector)"},
        "user_id": {"type": "string", "description": "User ID"},
        "top_k": {"type": "integer", "description": "Number of results to return", "default": 5}
    }
)
async def search_similar_drawings(args: dict[str, Any]) -> dict[str, Any]:
    """Search for similar drawings"""
    client = chromadb.PersistentClient(path="./data/vectors")

    # Generate query vector (using Claude's embedding feature)
    from anthropic import Anthropic
    anthropic = Anthropic()

    # Note: actual implementation needs embedding model to generate vectors
    # Simplified here
    query_vector = [0.1] * 1024  # Should be obtained from embedding model in practice

    # Search in vector database
    results = client.search(
        collection_name="children_drawings",
        query_vector=query_vector,
        limit=args.get('top_k', 5),
        query_filter={
            "must": [
                {"key": "user_id", "match": {"value": args['user_id']}}
            ]
        }
    )

    # Format results
    similar_drawings = []
    for hit in results:
        similar_drawings.append({
            "id": hit.id,
            "score": hit.score,
            "objects": hit.payload.get("objects", []),
            "scene": hit.payload.get("scene", ""),
            "created_at": hit.payload.get("created_at", "")
        })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(similar_drawings, ensure_ascii=False, indent=2)
        }]
    }


# Create Vector Search MCP Server
vector_server = create_sdk_mcp_server(
    name="vector-search",
    version="1.0.0",
    tools=[search_similar_drawings]
)
```

### 2.3 Safety Check MCP Server

```python
# src/mcp_servers/safety_check_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from anthropic import Anthropic
from typing import Any
import json

@tool(
    name="check_content_safety",
    description="""Check whether content is appropriate for children (ages 3-12).

    Review dimensions:
    1. Negative content: violence, horror, inappropriate language
    2. Values: gender equality, cultural diversity
    3. Age-appropriateness: whether it matches the target age

    Returns:
    - is_safe: whether it is safe
    - safety_score: safety score (0-1)
    - issues: list of issues found
    - suggestions: modification suggestions
    """,
    input_schema={
        "content": {"type": "string", "description": "Content to check"},
        "target_age": {"type": "integer", "description": "Target age (3-12)"}
    }
)
async def check_content_safety(args: dict[str, Any]) -> dict[str, Any]:
    """Safety check"""
    client = Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system="""You are a children's content safety review expert.

Review standards:

[Prohibited Content]:
- Violence: fighting, blood, weapons
- Horror: ghosts, darkness, thriller
- Inappropriate language: profanity, insults, discrimination
- Adult topics: sex, drugs, political controversy

[Values Check]:
- Gender equality: avoid stereotypes (e.g. doctors always being male)
- Cultural diversity: represent different cultures and racial backgrounds
- Character education: friendship, courage, honesty, empathy

Please evaluate the content and return JSON:
{
    "is_safe": true/false,
    "safety_score": 0.0-1.0,
    "issues": [
        {
            "category": "violence/gender_bias/...",
            "severity": "low/medium/high",
            "description": "Specific issue description"
        }
    ],
    "suggestions": ["Suggestion 1", "Suggestion 2"]
}

Scoring criteria:
- < 0.7: Does not pass
- 0.7-0.85: Warning
- > 0.85: Pass
""",
        messages=[{
            "role": "user",
            "content": f"Target age: {args['target_age']} years old\n\nContent to check:\n{args['content']}"
        }]
    )

    result = json.loads(response.content[0].text)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


# Create Safety Check MCP Server
safety_server = create_sdk_mcp_server(
    name="safety-check",
    version="1.0.0",
    tools=[check_content_safety]
)
```

### 2.4 TTS Generation MCP Server

```python
# src/mcp_servers/tts_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from openai import OpenAI
from typing import Any
import hashlib
import os

@tool(
    name="generate_story_audio",
    description="""Convert story text to audio narration.

    Supported voice types:
    - grandmother: gentle grandma
    - child: playful sprite
    - narrator: narration voice

    Returns audio file path
    """,
    input_schema={
        "text": {"type": "string", "description": "Story text"},
        "voice_type": {"type": "string", "enum": ["grandmother", "child", "narrator"], "default": "grandmother"}
    }
)
async def generate_story_audio(args: dict[str, Any]) -> dict[str, Any]:
    """Generate story audio"""
    client = OpenAI()

    # Map voice type to OpenAI TTS voice
    voice_map = {
        "grandmother": "nova",      # Gentle female voice
        "child": "shimmer",         # Lively female voice
        "narrator": "onyx"          # Steady male voice
    }

    voice = voice_map.get(args.get('voice_type', 'grandmother'), 'nova')

    # Generate audio
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=args['text']
    )

    # Save audio file
    text_hash = hashlib.md5(args['text'].encode()).hexdigest()
    audio_path = f"./data/audio/story_{text_hash}.mp3"
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)

    response.stream_to_file(audio_path)

    return {
        "content": [{
            "type": "text",
            "text": f"Audio generated: {audio_path}"
        }]
    }


# Create TTS MCP Server
tts_server = create_sdk_mcp_server(
    name="tts-generation",
    version="1.0.0",
    tools=[generate_story_audio]
)
```

---

## 3. Skills Design

### 3.1 Story Generation Skill

```markdown
<!-- .claude/skills/story-generation/SKILL.md -->
---
description: "Create age-appropriate personalized stories for children"
allowed_tools:
  - "Read"
  - "mcp__vision__analyze_children_drawing"
  - "mcp__vector__search_similar_drawings"
  - "mcp__safety__check_content_safety"
  - "mcp__tts__generate_story_audio"
---

# Story Generation Skill

You are a professional children's story writer, skilled at creating stories based on children's drawings and interests.

## Workflow

When a user requests "turn a drawing into a story", follow these steps:

### 1. Analyze Drawing
Use the `analyze_children_drawing` tool to analyze the drawing:
- Identify objects, people, and animals in the drawing
- Understand the scene (indoor/outdoor, time of day)
- Perceive the emotional atmosphere

### 2. Search History
Use the `search_similar_drawings` tool to find similar drawings:
- Identify recurring characters (e.g. "Lightning the puppy")
- Understand the child's creative preferences
- Maintain story continuity

### 3. Create Story
Create a story based on the analysis results, following these rules:

**Age Adaptation**:
- Ages 3-5: Simple sentences, 100-200 words, clear ending
- Ages 6-8: Complex sentences, 200-400 words, minor twists allowed
- Ages 9-12: Rich rhetoric, 400-800 words, open-ended endings allowed

**Content Requirements**:
- Incorporate all main elements from the drawing
- If recurring characters exist, maintain consistent character traits
- Story must be positive and educational
- Use everyday vocabulary children can understand

**Educational Integration**:
- Naturally incorporate character education (friendship, courage, honesty)
- Can include STEAM elements (science, math concepts)
- Avoid lecturing; convey values through story plot

### 4. Safety Check
Use the `check_content_safety` tool to check the story:
- Ensure no violence, horror, or inappropriate content
- Check gender equality and cultural diversity
- If safety score < 0.85, modify the story

### 5. Generate Audio
Use the `generate_story_audio` tool to generate audio:
- Ages 3-6: Use grandmother voice (gentle)
- Ages 7-12: Use narrator voice (narration)

## Example Output

```json
{
  "story_title": "Lightning the Puppy's Park Adventure",
  "story_text": "Lightning the puppy came to its favorite park again today. The warm sunlight shone down, and the leaves rustled in the breeze. Lightning wagged its tail happily when suddenly, it spotted something shiny on the grass...",
  "word_count": 245,
  "reading_time_seconds": 90,
  "educational_points": ["friendship", "curiosity", "sharing"],
  "audio_path": "./data/audio/story_abc123.mp3",
  "safety_score": 0.92
}
```

## Notes

- If the drawing content is unclear, ask the user for additional information
- If a recurring character is found, proactively mention: "It's your old friend Lightning the puppy!"
- Adjust story length based on age; do not exceed limits
- All stories must have a clear ending (ages 3-8) or an inspiring conclusion (ages 9-12)
```

### 3.2 Interactive Story Skill

```markdown
<!-- .claude/skills/interactive-story/SKILL.md -->
---
description: "Create multi-branch interactive stories with child participation in choices"
allowed_tools:
  - "Read"
  - "Write"
  - "mcp__vector__search_similar_drawings"
  - "mcp__safety__check_content_safety"
  - "mcp__tts__generate_story_audio"
---

# Interactive Story Skill

You are an interactive story design expert, skilled at creating "choose your adventure" style children's stories.

## Interactive Story Rules

### Decision Point Setup
- 2-4 decision points per story
- One decision point every 100-150 words
- 2-3 options each time
- **Important**: All options lead to "good endings" (never punish children's choices)

### Option Design
```
Example:
The little dinosaur found a mysterious cave. What should it do?
A. Bravely walk inside to explore 🏔️
B. Go home first and bring friends 👫

Analysis:
- Option A: cultivates courage, adventurous spirit
- Option B: emphasizes friendship, teamwork
- Both options are positive, just different emphases
```

### State Management

Use JSON files to store session state:

```json
{
  "session_id": "session_abc123",
  "user_id": "user_123",
  "child_age": 8,
  "current_segment": 2,
  "choices_history": ["choice-1", "choice-3"],
  "character_state": {
    "Little Dinosaur": {
      "location": "cave",
      "has_treasure": true,
      "friends": ["Little Bunny"]
    }
  },
  "story_so_far": "First segment...\nSecond segment..."
}
```

## Workflow

### Start New Story
1. Receive user interest tags (dinosaurs, space, etc.)
2. Use `search_similar_drawings` to understand preferences
3. Generate opening (100-200 words)
4. Create first decision point
5. Save session state to `./data/sessions/session_{id}.json`

### Continue Story
1. Read session state
2. Generate next segment based on user's choice
3. Update character state
4. Create new decision point or ending
5. Save updated state

### End Story
1. Generate ending (based on all choices)
2. Summarize educational highlights
3. Use `generate_story_audio` to generate complete audio
4. Delete session file

## Example Interaction

**Round 1 (Opening)**:
```
The little dinosaur discovered a mysterious cave in the forest, with a strange light flickering at the entrance...

What would you do?
A. Bravely walk inside 🏔️ (cultivates courage)
B. Go home and bring friends 👫 (emphasizes friendship)
```

**Round 2 (After choosing A)**:
```
The little dinosaur gathered its courage and entered the cave, finding a glowing fossil inside! Then, it heard footsteps...

What's next?
A. Study the fossil carefully 🔬 (scientific exploration)
B. Hide and see who it is 🙈 (cautious thinking)
```

**Round 3-4**: Continue...

**Final (Ending)**:
```
The little dinosaur successfully protected the fossil and made a new friend, Little Bunny. They decided to study this amazing discovery together!

🎓 What you learned:
- Courage: dare to explore the unknown
- Friendship: friends make adventures more fun
- Science: stay curious, explore the world
```
```

### 3.3 Age Adapter Skill

```markdown
<!-- .claude/skills/age-adapter/SKILL.md -->
---
description: "Adjust language complexity and content depth based on child's age"
---

# Age Adapter Skill

Automatically adjust story language and content based on child's age.

## Age Group Standards

### Ages 3-5 (Preschool)

**Cognitive Traits**:
- Concrete thinking, needs simple and clear concepts
- Short attention span (10-15 minutes)
- Enjoys repetition, prefers familiar stories

**Language Requirements**:
- Simple sentences: subject-verb-object structure, no more than 10 words
- Common vocabulary: animals, colors, numbers, everyday objects
- Repetitive structures: "The puppy ran and ran, all the way to the park"

**Story Length**: 100-200 words

**Example**:
```
The puppy is playing in the park.
The sun is big, the sky is blue.
The puppy saw a ball.
The puppy is happy and runs to chase the ball.
```

---

### Ages 6-8 (Early Elementary)

**Cognitive Traits**:
- Beginning logical thinking
- Strong curiosity, enjoys exploration
- Can understand simple cause-and-effect

**Language Requirements**:
- Complex sentences: can use adjectives and adverbs
- Expanded vocabulary: can introduce new words (with explanations)
- Moderate rhetoric: similes, personification

**Story Length**: 200-400 words

**Example**:
```
Lightning the puppy was especially excited today because its owner promised to take it to the park.
The warm sunlight felt like a gentle hug from mom.
The leaves in the park rustled softly in the breeze, as if they were singing.
Lightning suddenly spotted something shiny on the grass,
and curiosity made it rush over to take a look...
```

---

### Ages 9-12 (Upper Elementary)

**Cognitive Traits**:
- Enhanced abstract thinking
- Beginning critical thinking
- Can understand complex interpersonal relationships

**Language Requirements**:
- Rich expression: use idioms and rhetorical devices
- Complex plots: can have multi-thread narratives
- Deep thinking: open-ended questions that provoke thought

**Story Length**: 400-800 words

**Example**:
```
The last rays of sunset spilled across every corner of the park,
coating this familiar place in a layer of gold.
Lightning the puppy had lost count of how many times it had been here,
but every time, it managed to discover something new —
perhaps a newly arrived butterfly, or a flower that just bloomed.

Today, its curiosity was drawn to a faint glimmer on the grass.
It wasn't an ordinary stone, nor a dropped coin.
As it approached step by step, an exciting possibility rose in its heart:
could this be the legendary "Star Stone"?

Just then, familiar footsteps sounded from behind...
```

## Conversion Rules

### Vocabulary Substitution Table

| Complex Term | Ages 3-5 | Ages 6-8 | Ages 9-12 |
|-------------|----------|----------|-----------|
| explore | look | go find | explore |
| brave | not scared | brave | brave |
| friendship | good friends | friendship | friendship |
| discover | see | find | discover |
| mysterious | strange | mysterious | mysterious |

### Sentence Conversion

**Original (Ages 9-12)**:
"The last rays of sunset spilled across every corner of the park, coating this familiar place in a layer of gold."

**Converted for Ages 6-8**:
"The sun was going down, and the park turned golden, like it put on a golden coat."

**Converted for Ages 3-5**:
"The sun is going home. The park turned yellow. It looks pretty."

## Usage

After generating a story, automatically check the target age:
1. If ages 3-5, simplify sentences and vocabulary
2. If ages 6-8, maintain moderate complexity
3. If ages 9-12, rich expression can be used
```

---

## 4. Agent Usage Examples

### 4.1 Image-to-Story Agent

```python
# src/agents/image_to_story.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage
from src.mcp_servers.vision_analysis_server import vision_server
from src.mcp_servers.vector_search_server import vector_server
from src.mcp_servers.safety_check_server import safety_server
from src.mcp_servers.tts_server import tts_server
import json

async def image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None
) -> dict:
    """Image to story"""

    # Configure Agent
    options = ClaudeAgentOptions(
        # Configure MCP Servers
        mcp_servers={
            "vision": vision_server,
            "vector": vector_server,
            "safety": safety_server,
            "tts": tts_server
        },

        # Allowed tools
        allowed_tools=[
            "mcp__vision__analyze_children_drawing",
            "mcp__vector__search_similar_drawings",
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Skill"  # Enable Skills
        ],

        # Skills configuration
        cwd=".",  # Project root directory
        setting_sources=["user", "project"],  # Load from .claude/skills/

        # Permission mode
        permission_mode="acceptEdits"  # Auto-approve file read/write
    )

    # Create task prompt
    prompt = f"""
Task: Transform a children's drawing into a personalized story

Drawing information:
- Image path: {image_path}
- Child ID: {child_id}
- Child's age: {child_age} years old
- Interest tags: {', '.join(interests) if interests else 'unknown'}

Please use the Story Generation Skill to complete these steps:

1. Analyze drawing (using analyze_children_drawing)
2. Search similar historical drawings (using search_similar_drawings)
3. Create age-appropriate story (adjust language by age)
4. Safety check (using check_content_safety)
5. Generate audio (using generate_story_audio)

Finally return complete story information (JSON format).
"""

    result_data = {}

    # Execute Agent
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"[Agent] {block.text}")
                elif hasattr(block, 'name'):
                    print(f"[Tool] {block.name}")

        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                result_data = json.loads(message.result)
                print(f"\n[Success] Story generation complete!")

    return result_data


# FastAPI routes
from fastapi import FastAPI, UploadFile, File
import shutil

app = FastAPI()

@app.post("/api/v1/image-to-story")
async def api_image_to_story(
    image: UploadFile = File(...),
    child_id: str,
    child_age: int,
    interests: str = ""
):
    """Image-to-story API"""

    # Save uploaded image
    image_path = f"./data/uploads/{image.filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Call Agent
    result = await image_to_story(
        image_path=image_path,
        child_id=child_id,
        child_age=child_age,
        interests=interests.split(',') if interests else None
    )

    return {
        "success": True,
        "data": result
    }
```

### 4.2 Interactive Story Agent

```python
# src/agents/interactive_story.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from src.mcp_servers.vector_search_server import vector_server
from src.mcp_servers.safety_check_server import safety_server
from src.mcp_servers.tts_server import tts_server
import json
import uuid

async def start_interactive_story(
    child_id: str,
    child_age: int,
    interests: list[str]
) -> dict:
    """Start interactive story"""

    session_id = str(uuid.uuid4())

    options = ClaudeAgentOptions(
        mcp_servers={
            "vector": vector_server,
            "safety": safety_server,
            "tts": tts_server
        },
        allowed_tools=[
            "mcp__vector__search_similar_drawings",
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Read", "Write", "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
    )

    prompt = f"""
Task: Create the opening of an interactive story

User information:
- Child ID: {child_id}
- Age: {child_age} years old
- Interests: {', '.join(interests)}
- Session ID: {session_id}

Use Interactive Story Skill:
1. Search user historical preferences
2. Generate opening (100-200 words)
3. Create first decision point (2-3 options)
4. Save session state to ./data/sessions/session_{session_id}.json

Return opening story and options (JSON format).
"""

    result_data = {}
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            result_data = json.loads(message.result)

    return result_data


async def continue_interactive_story(
    session_id: str,
    choice_id: str
) -> dict:
    """Continue interactive story"""

    options = ClaudeAgentOptions(
        mcp_servers={
            "safety": safety_server,
            "tts": tts_server
        },
        allowed_tools=[
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Read", "Write", "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
    )

    prompt = f"""
Task: Continue interactive story

Session ID: {session_id}
User choice: {choice_id}

Use Interactive Story Skill:
1. Read session state from ./data/sessions/session_{session_id}.json
2. Generate next segment based on choice (100-200 words)
3. Update character state
4. Create new decision point or ending
5. Save updated state

Return next story segment and options (JSON format).
"""

    result_data = {}
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            result_data = json.loads(message.result)

    return result_data


# FastAPI routes
@app.post("/api/v1/story/interactive/start")
async def api_start_interactive_story(
    child_id: str,
    child_age: int,
    interests: str
):
    """Start interactive story"""
    result = await start_interactive_story(
        child_id=child_id,
        child_age=child_age,
        interests=interests.split(',')
    )
    return {"success": True, "data": result}


@app.post("/api/v1/story/interactive/{session_id}/choose")
async def api_continue_interactive_story(
    session_id: str,
    choice_id: str
):
    """Continue interactive story"""
    result = await continue_interactive_story(
        session_id=session_id,
        choice_id=choice_id
    )
    return {"success": True, "data": result}
```

---

## 5. Contract Testing (TDD)

### 5.1 MCP Tool Contract Tests

```python
# tests/contracts/mcp_tools_contract.py
import pytest
from src.mcp_servers.vision_analysis_server import analyze_children_drawing
from src.mcp_servers.vector_search_server import search_similar_drawings
from src.mcp_servers.safety_check_server import check_content_safety
import json

class TestVisionAnalysisContract:
    """Vision Analysis MCP Tool contract tests"""

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_contract(self):
        """Test drawing analysis tool contract"""
        # Input contract
        input_args = {
            "image_path": "./test_data/sample_drawing.jpg"
        }

        # Execute tool
        result = await analyze_children_drawing(input_args)

        # Output contract validation
        assert "content" in result
        assert len(result["content"]) > 0

        content_text = result["content"][0]["text"]
        data = json.loads(content_text)

        # Validate required fields
        assert "objects" in data
        assert "scene" in data
        assert "mood" in data
        assert "colors" in data

        # Validate data types
        assert isinstance(data["objects"], list)
        assert len(data["objects"]) > 0
        assert isinstance(data["scene"], str)
        assert isinstance(data["mood"], str)


class TestSafetyCheckContract:
    """Safety Check MCP Tool contract tests"""

    @pytest.mark.asyncio
    async def test_check_content_safety_contract(self):
        """Test safety check tool contract"""
        # Input contract
        input_args = {
            "content": "A puppy is playing in the park and meets its good friend, a kitten.",
            "target_age": 7
        }

        # Execute tool
        result = await check_content_safety(input_args)

        # Output contract validation
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)

        # Validate required fields
        assert "is_safe" in data
        assert "safety_score" in data
        assert "issues" in data
        assert "suggestions" in data

        # Validate data types and ranges
        assert isinstance(data["is_safe"], bool)
        assert 0.0 <= data["safety_score"] <= 1.0
        assert isinstance(data["issues"], list)
        assert isinstance(data["suggestions"], list)

        # Validate business rules
        if data["safety_score"] < 0.7:
            assert not data["is_safe"]
        if data["safety_score"] > 0.85:
            assert data["is_safe"]
```

### 5.2 Agent Integration Contract Tests

```python
# tests/contracts/agent_integration_contract.py
import pytest
from src.agents.image_to_story import image_to_story
from src.agents.interactive_story import start_interactive_story

class TestImageToStoryAgentContract:
    """Image-to-Story Agent integration contract tests"""

    @pytest.mark.asyncio
    async def test_image_to_story_end_to_end(self):
        """Test complete image-to-story flow"""
        # Input
        result = await image_to_story(
            image_path="./test_data/sample_drawing.jpg",
            child_id="test_user_123",
            child_age=7,
            interests=["animals", "adventure"]
        )

        # Output contract validation
        assert "story_title" in result
        assert "story_text" in result
        assert "word_count" in result
        assert "safety_score" in result
        assert "audio_path" in result

        # Validate business rules
        # Story for a 7-year-old should be 200-400 words
        assert 150 <= result["word_count"] <= 450

        # Safety score should be > 0.85
        assert result["safety_score"] > 0.85

        # Should have educational highlights
        assert "educational_points" in result
        assert len(result["educational_points"]) > 0
```

---

## 6. Project Structure

```
creative_agent/
├── .claude/
│   └── skills/                      # Skills (Markdown files)
│       ├── story-generation/
│       │   └── SKILL.md
│       ├── interactive-story/
│       │   └── SKILL.md
│       └── age-adapter/
│           └── SKILL.md
│
├── src/
│   ├── mcp_servers/                 # MCP Tools
│   │   ├── vision_analysis_server.py
│   │   ├── vector_search_server.py
│   │   ├── safety_check_server.py
│   │   └── tts_server.py
│   │
│   ├── agents/                      # Agent orchestration
│   │   ├── image_to_story.py
│   │   ├── interactive_story.py
│   │   └── news_to_kids.py
│   │
│   └── api/
│       └── main.py                  # FastAPI routes
│
├── tests/
│   └── contracts/                   # Contract tests
│       ├── mcp_tools_contract.py
│       └── agent_integration_contract.py
│
├── data/
│   ├── uploads/                     # Uploaded images
│   ├── audio/                       # Generated audio
│   ├── sessions/                    # Interactive story sessions
│   └── vectors/                     # ChromaDB vector database
│
├── DOMAIN.md                        # Domain document
├── PRD.md                           # Product requirements
├── ARCHITECTURE_V2.md               # Architecture document (this document)
└── README.md                        # Project overview
```

---

## 7. Development Workflow (TDD)

```
Step 1: Write MCP Tool contract tests
  ├─ tests/contracts/mcp_tools_contract.py
  └─ Define input/output formats
        ↓
Step 2: Implement MCP Tool
  ├─ src/mcp_servers/vision_analysis_server.py
  └─ Define tools using @tool decorator
        ↓
Step 3: Run contract tests
  ├─ pytest tests/contracts/mcp_tools_contract.py -v
  └─ Ensure they pass
        ↓
Step 4: Write Skill (Markdown)
  ├─ .claude/skills/story-generation/SKILL.md
  └─ Define Agent behavior and workflow
        ↓
Step 5: Write Agent orchestration code
  ├─ src/agents/image_to_story.py
  └─ Use query() + ClaudeAgentOptions
        ↓
Step 6: Run Agent integration tests
  ├─ pytest tests/contracts/agent_integration_contract.py -v
  └─ Validate end-to-end flow
```

---

## 8. Core Differences Summary

| Previous Incorrect Understanding | Correct Understanding |
|---------------------------------|----------------------|
| Implementing BaseAgent class ourselves | Use SDK's `query()` function |
| Manually managing tool execution loop | SDK handles automatically |
| Skill = Python class | Skill = Markdown file |
| Need to implement `to_claude_tool()` | Use `@tool` decorator |
| Complex database design | Simple JSON + ChromaDB |
| ContractSkill as runtime validation | Contract tests + MCP Tool input validation |

---

## Appendix

### A. Key Dependencies

```
# Python
claude-agent-sdk==1.0.0
anthropic==0.18.1
openai==1.12.0
chromadb==1.4.1
fastapi==0.110.0
pydantic==2.6.1
pytest==8.0.0
```

### B. Environment Variables

```env
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
CHROMA_PATH=./data/vectors
```

### C. Quick Start

```bash
# 1. Install dependencies
pip install claude-agent-sdk anthropic openai chromadb fastapi

# 2. Set API Keys
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key

# 3. Create Skills directory
mkdir -p .claude/skills/story-generation

# 4. Run contract tests
pytest tests/contracts/ -v

# 5. Start API
python -m src.api.main
```
