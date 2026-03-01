"""
Image to Story API Routes

Image-to-story API endpoints
Supports streaming responses (SSE) for a better user experience
"""

import json
import logging
import mimetypes
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from ..models import (
    ImageToStoryResponse,
    StoryContent,
    EducationalValue,
    CharacterMemory,
    AgeGroup
)
from ..deps import get_current_user, get_story_for_owner
from ...agents.image_to_story_agent import image_to_story, stream_image_to_story
from ...utils.audio_strategy import get_audio_strategy
from ...services.database import story_repo, preference_repo, db_manager
from ...services.user_service import UserData
from ...services.provenance_tracker import ProvenanceTracker
from ...services.models.artifact_models import (
    ArtifactType, WorkflowType, StoryArtifactRole,
    ArtifactMetadata, RunArtifactStage,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1",
    tags=["Image to Story"]
)


# ============================================================================
# Configuration
# ============================================================================
from ...paths import UPLOAD_DIR
from ...utils.text import count_words

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CHILD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def validate_image_file(file: UploadFile) -> None:
    """
    Validate the uploaded image file

    Args:
        file: The uploaded file

    Raises:
        HTTPException: If the file does not meet requirements
    """
    filename = file.filename
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename"
        )

    # Check file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件必须是图片类型"
        )

    # Check MIME type
    content_type = file.content_type
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image type"
        )


def validate_child_id(child_id: str) -> str:
    """
    Validate child_id used in file paths.

    Allows only simple identifier characters to prevent path traversal.
    """
    normalized = child_id.strip()
    if not CHILD_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid child_id format. Use 1-100 characters: letters, numbers, underscore, hyphen"
        )
    return normalized


async def save_upload_file(file: UploadFile, child_id: str) -> Path:
    """
    Save the uploaded file

    Args:
        file: The uploaded file
        child_id: Child ID

    Returns:
        Path: The saved file path

    Raises:
        HTTPException: If the file is too large
    """
    base_upload_dir = UPLOAD_DIR.resolve()

    # Create child-specific directory
    child_dir = (base_upload_dir / child_id).resolve()
    if base_upload_dir not in child_dir.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload path"
        )

    child_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    filename = file.filename
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename"
        )

    file_ext = Path(filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = (child_dir / unique_filename).resolve()
    if file_path.parent != child_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload file path"
        )

    # Save file and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="文件大小超过限制"
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return file_path


def parse_age_group(age_group: str) -> int:
    """
    Convert an age group to a specific age (using the midpoint)

    Args:
        age_group: Age group (e.g. "3-5")

    Returns:
        int: Age
    """
    age_map = {
        "3-5": 4,
        "6-9": 7,
        "10-12": 11
    }
    return age_map.get(age_group, 7)


@router.post(
    "/image-to-story",
    response_model=ImageToStoryResponse,
    summary="Image to Story",
    description="Upload a child's artwork and AI generates a personalized story",
    status_code=status.HTTP_201_CREATED
)
async def create_story_from_image(
    image: UploadFile = File(..., description="Child's artwork image (PNG/JPG, max 10MB)"),
    child_id: str = Form(..., description="Child unique identifier"),
    age_group: AgeGroup = Form(..., description="Age group: 3-5, 6-8, 9-12"),
    interests: Optional[str] = Form(None, description="Interest tags, comma-separated (max 5)"),
    voice: str = Form("nova", description="Voice type"),
    enable_audio: bool = Form(True, description="Whether to generate audio"),
    user: UserData = Depends(get_current_user),
):
    """
    Image to Story API

    **Workflow**:
    1. Validate and save the uploaded image
    2. Call image_to_story_agent
    3. Return the story, audio, and educational value

    **Example request**:
    ```bash
    curl -X POST "http://localhost:8000/api/v1/image-to-story" \\
      -F "image=@drawing.png" \\
      -F "child_id=child_001" \\
      -F "age_group=6-8" \\
      -F "interests=animals,adventure,space" \\
      -F "voice=nova" \\
      -F "enable_audio=true"
    ```
    """
    try:
        # 1. Validate image
        validate_image_file(image)
        safe_child_id = validate_child_id(child_id)

        # 2. Save image
        image_path = await save_upload_file(image, safe_child_id)

        # 3. Parse parameters
        child_age = parse_age_group(age_group.value)
        interests_list = None
        if interests:
            interests_list = [i.strip() for i in interests.split(",") if i.strip()]
            if len(interests_list) > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="兴趣标签最多5个"
                )

        story_id = str(uuid.uuid4())

        # --- Provenance tracking (Issue #17) ---
        tracker = ProvenanceTracker(db_manager)
        run_id = None
        try:
            run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)
        except Exception:
            logger.warning("Failed to start provenance run", exc_info=True)

        # Step 1: Record uploaded image as artifact
        image_artifact_id = None
        if run_id:
            try:
                upload_step_id = await tracker.start_step(
                    run_id, "image_upload", 1,
                    input_data={"image_path": str(image_path), "child_id": safe_child_id},
                )
                mime, _ = mimetypes.guess_type(str(image_path))
                file_size = image_path.stat().st_size if image_path.exists() else None
                image_artifact_id = await tracker.record_artifact(
                    upload_step_id,
                    ArtifactType.IMAGE,
                    run_id=run_id,
                    artifact_path=str(image_path),
                    description="Uploaded child drawing",
                    mime_type=mime,
                    file_size=file_size,
                    agent_name="image_upload",
                )
                await tracker.complete_step(upload_step_id, output_data={"artifact_id": image_artifact_id})
            except Exception:
                logger.warning("Failed to record image artifact", exc_info=True)

        # 4. Call Agent to generate story
        agent_step_id = None
        if run_id:
            try:
                agent_step_id = await tracker.start_step(
                    run_id, "story_generation", 2,
                    input_data={
                        "child_age": child_age,
                        "interests": interests_list or [],
                        "enable_audio": enable_audio,
                    },
                    model_name="claude-agent-sdk",
                    prompt_hash=ProvenanceTracker.compute_prompt_hash(
                        f"image_to_story:{safe_child_id}:{child_age}"
                    ),
                )
            except Exception:
                logger.warning("Failed to start story generation step", exc_info=True)

        result = await image_to_story(
            image_path=str(image_path),
            child_id=safe_child_id,
            child_age=child_age,
            interests=interests_list if interests_list is not None else [],
            enable_audio=enable_audio,
            voice=voice
        )

        if agent_step_id:
            try:
                await tracker.complete_step(
                    agent_step_id,
                    output_data={"story_keys": list(result.keys())},
                )
            except Exception:
                logger.warning("Failed to complete story generation step", exc_info=True)

        # 5. Parse result and build response

        # Extract story text
        story_text = result.get("story", "")
        word_count = count_words(story_text)

        # Extract educational value
        educational_value = EducationalValue(
            themes=result.get("themes", []),
            concepts=result.get("concepts", []),
            moral=result.get("moral")
        )

        # Extract character memory
        characters = []
        for char_data in result.get("characters", []):
            characters.append(CharacterMemory(
                character_name=char_data.get("name", ""),
                description=char_data.get("description", ""),
                appearances=char_data.get("appearances", 1)
            ))

        # Build image URL (relative to static file server)
        image_url = f"/data/uploads/{safe_child_id}/{image_path.name}"

        # Handle audio URL from agent result
        audio_url = None
        if result.get("audio_path"):
            audio_filename = Path(result["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        # --- Record story text as artifact (Issue #17) ---
        text_artifact_id = None
        if run_id:
            try:
                text_step_id = await tracker.start_step(
                    run_id, "text_artifact", 3,
                    input_data={"story_id": story_id},
                )
                text_artifact_id = await tracker.record_artifact(
                    text_step_id,
                    ArtifactType.TEXT,
                    run_id=run_id,
                    artifact_payload=story_text,
                    description="Generated story text",
                    safety_score=result.get("safety_score", 0.9),
                    agent_name="story_generation",
                    input_artifact_ids=[image_artifact_id] if image_artifact_id else None,
                    metadata=ArtifactMetadata(
                        char_count=len(story_text),
                        word_count=word_count,
                    ),
                )
                await tracker.complete_step(text_step_id, output_data={"artifact_id": text_artifact_id})
            except Exception:
                logger.warning("Failed to record text artifact", exc_info=True)

        # --- Record audio as artifact (Issue #17) ---
        audio_artifact_id = None
        if run_id and audio_url and result.get("audio_path"):
            try:
                audio_step_id = await tracker.start_step(
                    run_id, "tts_artifact", 4,
                    input_data={"audio_path": result["audio_path"]},
                )
                audio_mime, _ = mimetypes.guess_type(result["audio_path"])
                audio_artifact_id = await tracker.record_artifact(
                    audio_step_id,
                    ArtifactType.AUDIO,
                    run_id=run_id,
                    artifact_path=result["audio_path"],
                    artifact_url=audio_url,
                    description="TTS narration audio",
                    mime_type=audio_mime,
                    agent_name="tts_generation",
                    input_artifact_ids=[text_artifact_id] if text_artifact_id else None,
                )
                await tracker.complete_step(audio_step_id, output_data={"artifact_id": audio_artifact_id})
            except Exception:
                logger.warning("Failed to record audio artifact", exc_info=True)

        # --- Link artifacts to story and complete run (Issue #17 + #18) ---
        if run_id:
            try:
                art_repo = tracker._artifact_repo

                # Promote and link all created artifacts
                for artifact_id, role in [
                    (image_artifact_id, StoryArtifactRole.COVER),
                    (text_artifact_id, None),
                    (audio_artifact_id, StoryArtifactRole.FINAL_AUDIO),
                ]:
                    if not artifact_id:
                        continue
                    await art_repo.update_lifecycle_state(artifact_id, "candidate")
                    await art_repo.update_lifecycle_state(artifact_id, "published")
                    if role:
                        await tracker.link_to_story(story_id, artifact_id, role)

                await tracker.complete_run(run_id, result_summary={
                    "artifacts_created": sum(1 for a in [image_artifact_id, text_artifact_id, audio_artifact_id] if a),
                    "story_id": story_id,
                })
            except Exception:
                logger.warning("Failed to link artifacts and complete run", exc_info=True)

        # Build response
        created_at = datetime.now()
        response = ImageToStoryResponse(
            story_id=story_id,
            story=StoryContent(
                text=story_text,
                word_count=word_count,
                age_adapted=True
            ),
            image_url=image_url,
            audio_url=audio_url,
            video_url=None,
            video_job_id=None,
            educational_value=educational_value,
            characters=characters,
            analysis=result.get("analysis", {}),
            safety_score=result.get("safety_score", 0.9),
            created_at=created_at
        )

        # Save story to database
        story_data = {
            "story_id": story_id,
            "story": {
                "text": story_text,
                "word_count": word_count,
                "age_adapted": True
            },
            "image_url": image_url,
            "audio_url": audio_url,
            "educational_value": {
                "themes": result.get("themes", []),
                "concepts": result.get("concepts", []),
                "moral": result.get("moral")
            },
            "characters": [
                {
                    "character_name": c.character_name,
                    "description": c.description,
                    "appearances": c.appearances
                }
                for c in characters
            ],
            "analysis": result.get("analysis", {}),
            "safety_score": result.get("safety_score", 0.9),
            "created_at": created_at.isoformat(),
            "child_id": safe_child_id,
            "age_group": age_group.value,
            "image_path": str(image_path)
        }
        story_data["user_id"] = user.user_id
        await story_repo.create(story_data)

        # Update child preferences (Advanced Memory)
        try:
            await preference_repo.update_from_story_result(safe_child_id, result)
        except Exception:
            pass  # Non-critical: don't fail the request

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # Mark run as failed if provenance was started
        if run_id:
            try:
                await tracker.fail_run(run_id, str(e))
            except Exception:
                logger.warning("Failed to mark run as failed", exc_info=True)

        logger.error("Error in image-to-story: %s", e, exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Story generation failed, please try again later"
        )

    finally:
        # Optional: clean up temporary files (if not needed)
        # if image_path and image_path.exists():
        #     image_path.unlink()
        pass


@router.post(
    "/image-to-story/stream",
    summary="Image to Story (streaming)",
    description="Upload a child's artwork and use SSE streaming to return story generation progress",
    status_code=status.HTTP_200_OK
)
async def create_story_from_image_stream(
    image: UploadFile = File(..., description="Child's artwork image (PNG/JPG, max 10MB)"),
    child_id: str = Form(..., description="Child unique identifier"),
    age_group: AgeGroup = Form(..., description="Age group: 3-5, 6-8, 9-12"),
    interests: Optional[str] = Form(None, description="Interest tags, comma-separated (max 5)"),
    voice: str = Form("nova", description="Voice type"),
    enable_audio: bool = Form(True, description="Whether to generate audio"),
    user: UserData = Depends(get_current_user),
):
    """
    Streaming Image to Story API

    Uses Server-Sent Events (SSE) to stream story generation progress.

    **Event types**:
    - `status`: Status update (started, processing)
    - `thinking`: AI thinking process
    - `tool_use`: Tool usage notification (artwork analysis, safety check, etc.)
    - `tool_result`: Tool result
    - `result`: Story content
    - `complete`: Generation complete
    - `error`: Error message
    """
    # Validate image
    try:
        validate_image_file(image)
        safe_child_id = validate_child_id(child_id)
    except HTTPException as e:
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': 'ValidationError', 'message': e.detail}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Save image
    try:
        image_path = await save_upload_file(image, safe_child_id)
    except HTTPException as e:
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': 'UploadError', 'message': e.detail}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Parse parameters
    child_age = parse_age_group(age_group.value)
    interests_list = None
    if interests:
        interests_list = [i.strip() for i in interests.split(",") if i.strip()]
        if len(interests_list) > 5:
            async def error_generator():
                yield f"event: error\ndata: {json.dumps({'error': 'ValidationError', 'message': '兴趣标签最多5个'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Build image URL (relative to static file server)
    image_url = f"/data/uploads/{safe_child_id}/{image_path.name}"

    async def event_generator() -> AsyncGenerator[str, None]:
        story_id = str(uuid.uuid4())
        result_data = None

        try:
            # Stream story generation
            async for event in stream_image_to_story(
                image_path=str(image_path),
                child_id=safe_child_id,
                child_age=child_age,
                interests=interests_list if interests_list is not None else [],
                enable_audio=enable_audio,
                voice=voice
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                # When receiving a result, build the complete response
                if event_type == "result":
                    result_data = event_data

                    # Extract story text
                    story_text = result_data.get("story", "")
                    word_count = count_words(story_text)

                    # Handle audio URL from agent result
                    audio_url = None
                    if result_data.get("audio_path"):
                        audio_filename = Path(result_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    # Build complete response data
                    response_data = {
                        "story_id": story_id,
                        "story": {
                            "text": story_text,
                            "word_count": word_count,
                            "age_adapted": True
                        },
                        "image_url": image_url,
                        "audio_url": audio_url,
                        "educational_value": {
                            "themes": result_data.get("themes", []),
                            "concepts": result_data.get("concepts", []),
                            "moral": result_data.get("moral")
                        },
                        "characters": [
                            {
                                "character_name": c.get("name", ""),
                                "description": c.get("description", ""),
                                "appearances": c.get("appearances", 1)
                            }
                            for c in result_data.get("characters", [])
                        ],
                        "analysis": result_data.get("analysis", {}),
                        "safety_score": result_data.get("safety_score", 0.9),
                        "created_at": datetime.now().isoformat()
                    }

                    # Save story to database
                    story_save_data = {
                        **response_data,
                        "child_id": safe_child_id,
                        "age_group": age_group.value,
                        "image_path": str(image_path)
                    }
                    story_save_data["user_id"] = user.user_id
                    await story_repo.create(story_save_data)

                    # Update child preferences (Advanced Memory)
                    try:
                        await preference_repo.update_from_story_result(safe_child_id, result_data)
                    except Exception:
                        pass  # Non-critical

                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    # Forward other events
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_data = {"error": str(type(e).__name__), "message": f"Story generation failed: {str(e)}"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get(
    "/stories/{story_id}",
    summary="Get story",
    description="Get details of a generated story by story ID",
    responses={
        200: {"description": "Successfully retrieved story"},
        404: {"description": "Story not found"}
    }
)
async def get_story_by_id(
    story_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Get story details (requires authentication + ownership verification)
    """
    story = await get_story_for_owner(story_id, user.user_id)
    return JSONResponse(content=story)


@router.get(
    "/stories/history/{child_id}",
    summary="Get child's story history",
    description="Get the complete story list for a specific child (including images, themes, and other details)"
)
async def get_child_story_history(
    child_id: str,
    limit: int = 20,
    user: UserData = Depends(get_current_user),
):
    """
    Get story history for a specific child (requires authentication, filtered by user)
    """
    stories = await story_repo.list_by_user_and_child(user.user_id, child_id, limit)
    return JSONResponse(content=stories)


@router.delete(
    "/stories/{story_id}",
    summary="Delete a story",
    description="Delete a story (art story or news conversion) from the library"
)
async def delete_story(
    story_id: str,
    user: UserData = Depends(get_current_user),
):
    """
    Delete a story by ID (requires authentication + ownership verification).
    Covers both art stories and news conversions since they share the stories table.
    """
    # Verify ownership first
    await get_story_for_owner(story_id, user.user_id)

    deleted = await story_repo.delete(story_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete story"
        )

    return {"message": "Story deleted successfully", "story_id": story_id}
