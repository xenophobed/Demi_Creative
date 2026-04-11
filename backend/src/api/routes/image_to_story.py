"""
Image to Story API Routes

Image-to-story API endpoints
Supports streaming responses (SSE) for a better user experience
"""

import json
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse

from ...agents.image_to_story_agent import (
    image_to_story,
    stream_image_to_story,
    validate_story_length,
)
from ...mcp_servers.image_style_server import (
    transform_art_style as _raw_transform_art_style,
)
from ...mcp_servers.image_style_server import (
    validate_and_fallback,
)
from ...services.database import (
    character_repo,
    db_manager,
    preference_repo,
    story_repo,
    usage_repo,
)
from ...services.models.artifact_models import (
    ArtifactMetadata,
    ArtifactType,
    RunArtifactStage,
    StoryArtifactRole,
    WorkflowType,
)
from ...services.provenance_tracker import ProvenanceTracker
from ...services.user_service import UserData
from ...utils.audio_strategy import get_audio_strategy
from ..deps import check_generation_quota, get_current_user, get_story_for_owner
from ..models import (
    AgeGroup,
    ArtTheme,
    CharacterMemory,
    EducationalValue,
    ImageToStoryResponse,
    StoryContent,
)

logger = logging.getLogger(__name__)

# claude_agent_sdk @tool returns SdkMcpTool, which is not directly callable.
# Use the original handler for direct fallback invocation in API routes.
transform_art_style = getattr(
    _raw_transform_art_style, "handler", _raw_transform_art_style
)


def _skip_styled_safety_in_dev() -> bool:
    """Allow style preview in development even if safety validation is unavailable.

    In production/test envs we keep strict fail-closed behavior.
    Set STYLE_SAFETY_VALIDATE_IN_DEV=1 to force validation in development.
    """
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    if env not in {"development", "dev", "local"}:
        return False
    force_validate = os.getenv("STYLE_SAFETY_VALIDATE_IN_DEV", "").strip().lower()
    return force_validate not in {"1", "true", "yes"}


def _extract_character_enrichment(
    char_data: dict,
    analysis: dict,
) -> tuple:
    """Extract visual_features and traits for a character from available data.

    Looks up the character by name in the vision analysis recurring_characters
    to get visual_features. Derives simple personality traits from the
    character description when explicit trait data is not available.

    Returns (visual_features_dict | None, traits_list | None).
    """
    name = char_data.get("character_name") or char_data.get("name", "")

    # --- visual_features ---
    visual_features = None
    # First try: direct visual_features on the character dict (if agent provides it)
    if char_data.get("visual_features"):
        raw = char_data["visual_features"]
        if isinstance(raw, dict):
            visual_features = raw
        elif isinstance(raw, list):
            visual_features = {"features": raw}

    # Second try: match against recurring_characters from vision analysis
    if not visual_features and analysis:
        for rc in analysis.get("recurring_characters", []):
            rc_name = rc.get("name", "")
            if rc_name and rc_name.lower() == name.lower():
                vf = rc.get("visual_features")
                if isinstance(vf, list):
                    visual_features = {"features": vf}
                elif isinstance(vf, dict):
                    visual_features = vf
                break

    # Third try: extract from description
    if not visual_features:
        desc = char_data.get("description", "")
        if desc:
            visual_features = {"description_summary": desc}

    # --- traits ---
    traits = None
    if char_data.get("traits"):
        raw_traits = char_data["traits"]
        if isinstance(raw_traits, list):
            traits = raw_traits
        elif isinstance(raw_traits, str):
            traits = [t.strip() for t in raw_traits.split(",") if t.strip()]

    return visual_features, traits


def _extract_unique_character_names_for_decrement(story: dict) -> list[str]:
    """Extract deduplicated character names from a story payload."""
    names: list[str] = []
    seen: set[str] = set()

    for item in story.get("characters") or []:
        candidate = ""
        if isinstance(item, dict):
            candidate = item.get("character_name") or item.get("name") or ""
        elif isinstance(item, str):
            candidate = item

        token = str(candidate or "").strip()
        if not token:
            continue
        key = character_repo._normalized_name_key(token)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(token)

    return names


def _extract_styled_path_from_tool_result(result: dict) -> Optional[str]:
    """Parse styled image path from an MCP tool result payload."""
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return None
    first = content[0]
    if not isinstance(first, dict):
        return None

    payload_text = first.get("text")
    if not payload_text:
        return None

    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if not payload.get("success"):
        return None

    styled_path = payload.get("styled_image_path")
    if not isinstance(styled_path, str) or not styled_path.strip():
        return None
    return styled_path


def _extract_style_error_from_tool_result(result: dict) -> Optional[str]:
    """Parse error message from an MCP style tool result payload."""
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return None
    first = content[0]
    if not isinstance(first, dict):
        return None

    payload_text = first.get("text")
    if not payload_text:
        return None

    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error
    return None


async def _ensure_styled_image_path(
    *,
    current_styled_path: Optional[str],
    image_path: Path,
    art_theme: ArtTheme,
    child_age: int,
    session_id: str,
) -> Optional[str]:
    """Ensure styled image exists when user selected a non-none art theme.

    Primary path: use styled path returned from the agent/tool call.
    Fallback path: invoke style transfer tool directly if agent path missing.
    """
    if art_theme == ArtTheme.NONE:
        return None

    if current_styled_path and Path(current_styled_path).exists():
        return current_styled_path

    if current_styled_path and not Path(current_styled_path).exists():
        logger.warning(
            "Agent returned non-existent styled image path; retrying style transfer. "
            "path=%s session_id=%s theme=%s",
            current_styled_path,
            session_id,
            art_theme.value,
        )

    try:
        style_result = await transform_art_style(
            {
                "image_path": str(image_path),
                "theme": art_theme.value,
                "child_age": child_age,
                "session_id": session_id,
            }
        )
        styled_path = _extract_styled_path_from_tool_result(style_result)
        if styled_path and Path(styled_path).exists():
            return styled_path

        style_error = _extract_style_error_from_tool_result(style_result)
        logger.warning(
            "Style fallback did not produce a usable styled image. "
            "session_id=%s theme=%s error=%s",
            session_id,
            art_theme.value,
            style_error or "unknown",
        )
        return None
    except Exception:
        logger.warning(
            "Style fallback execution failed. session_id=%s theme=%s",
            session_id,
            art_theme.value,
            exc_info=True,
        )
        return None


router = APIRouter(prefix="/api/v1", tags=["Image to Story"])


# ============================================================================
# Configuration
# ============================================================================
from ...paths import UPLOAD_DIR
from ...services.storage_adapter import storage
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
            detail="Uploaded file must include a filename",
        )

    # Check file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image type"
        )

    # Check MIME type
    content_type = file.content_type
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image type"
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
            detail="Invalid child_id format. Use 1-100 characters: letters, numbers, underscore, hyphen",
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
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload path"
        )

    child_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    filename = file.filename
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename",
        )

    file_ext = Path(filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = (child_dir / unique_filename).resolve()
    if file_path.parent != child_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload file path"
        )

    # Save file and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds limit",
        )

    # Use storage adapter (#343) — writes to local disk or Supabase Storage.
    # We still write locally so that downstream code (agent vision analysis)
    # can read the file by path.  The adapter additionally handles remote
    # upload when STORAGE_BACKEND=supabase.
    with open(file_path, "wb") as f:
        f.write(content)

    # Upload via storage adapter for URL generation / CDN replication.
    content_type = file.content_type or ""
    bucket_path = f"{child_id}/{unique_filename}"
    await storage.upload("uploads", bucket_path, content, content_type)

    return file_path


def parse_age_group(age_group: str) -> int:
    """
    Convert an age group to a specific age (using the midpoint)

    Args:
        age_group: Age group (e.g. "3-5")

    Returns:
        int: Age
    """
    age_map = {"3-5": 4, "6-8": 7, "9-12": 11}
    return age_map.get(age_group, 7)


@router.post(
    "/image-to-story",
    response_model=ImageToStoryResponse,
    summary="Image to Story",
    description="Upload a child's artwork and AI generates a personalized story",
    status_code=status.HTTP_201_CREATED,
)
async def create_story_from_image(
    image: UploadFile = File(
        ..., description="Child's artwork image (PNG/JPG, max 10MB)"
    ),
    child_id: str = Form(..., description="Child unique identifier"),
    age_group: AgeGroup = Form(..., description="Age group: 3-5, 6-8, 9-12"),
    interests: Optional[str] = Form(
        None, description="Interest tags, comma-separated (max 5)"
    ),
    voice: str = Form("nova", description="Voice type"),
    enable_audio: bool = Form(True, description="Whether to generate audio"),
    art_theme: ArtTheme = Form(
        ArtTheme.NONE, description="Art style theme for image transformation"
    ),
    provider: Optional[str] = Form(None, description="TTS provider (openai, replicate, elevenlabs)"),
    user: UserData = Depends(check_generation_quota),
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

        # Validate art_theme for age group (#270)
        YOUNG_CHILD_THEMES = {
            ArtTheme.CARTOON,
            ArtTheme.CRAYON,
            ArtTheme.WATERCOLOR,
            ArtTheme.STORYBOOK,
            ArtTheme.NONE,
        }
        if child_age <= 5 and art_theme not in YOUNG_CHILD_THEMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Art theme '{art_theme.value}' is not available for age group 3-5",
            )

        interests_list = None
        if interests:
            interests_list = [i.strip() for i in interests.split(",") if i.strip()]
            if len(interests_list) > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 5 interest tags"
                )

        story_id = str(uuid.uuid4())
        run_id = None  # Provenance run_id; initialized here for error handler access
        tracker = ProvenanceTracker(db_manager)

        # 4. Call Agent to generate story
        result = await image_to_story(
            image_path=str(image_path),
            child_id=safe_child_id,
            child_age=child_age,
            interests=interests_list if interests_list is not None else [],
            enable_audio=enable_audio,
            voice=voice,
            art_theme=art_theme.value if art_theme != ArtTheme.NONE else None,
            user_id=user.user_id,
            provider=provider,
        )

        # 4b. Validate story length per age group (#233)
        length_info = validate_story_length(result.get("story", ""), age_group.value)

        if length_info["needs_retry"]:
            logger.info(
                "Story length drastically out of range (%d words for %s), retrying once",
                length_info["word_count"],
                age_group.value,
            )
            result = await image_to_story(
                image_path=str(image_path),
                child_id=safe_child_id,
                child_age=child_age,
                interests=interests_list if interests_list is not None else [],
                enable_audio=enable_audio,
                voice=voice,
                art_theme=art_theme.value if art_theme != ArtTheme.NONE else None,
                user_id=user.user_id,
            )
            length_info = validate_story_length(
                result.get("story", ""), age_group.value
            )

        # 5. Parse result and build response

        # Extract story text
        story_text = result.get("story", "")
        word_count = count_words(story_text)

        # Extract educational value
        educational_value = EducationalValue(
            themes=result.get("themes", []),
            concepts=result.get("concepts", []),
            moral=result.get("moral"),
        )

        # Extract character memory
        characters = []
        for char_data in result.get("characters", []):
            characters.append(
                CharacterMemory(
                    character_name=char_data.get("name", ""),
                    description=char_data.get("description", ""),
                    appearances=char_data.get("appearances", 1),
                )
            )

        # Build image URL (relative to static file server)
        image_url = f"/data/uploads/{safe_child_id}/{image_path.name}"

        # Handle audio URL from agent result
        audio_url = None
        if result.get("audio_path"):
            audio_filename = Path(result["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        # Ensure style transfer output exists when user selected a style.
        styled_image_path = await _ensure_styled_image_path(
            current_styled_path=result.get("styled_image_path"),
            image_path=image_path,
            art_theme=art_theme,
            child_age=child_age,
            session_id=safe_child_id,
        )

        cover_image_url = image_url
        styled_image_safety = None
        if styled_image_path and Path(styled_image_path).exists():
            if _skip_styled_safety_in_dev():
                cover_image_url = f"/data/styled/{Path(styled_image_path).name}"
                styled_image_safety = {
                    "safety_passed": True,
                    "fell_back": False,
                    "flagged_keywords": [],
                    "reason": "skipped_in_development",
                }
            else:
                # Validate styled image safety before use (#273)
                try:
                    styled_image_safety = await validate_and_fallback(
                        styled_image_path=styled_image_path,
                        original_image_path=str(image_path),
                        child_age=child_age,
                        theme=art_theme.value if art_theme else "none",
                        session_id=safe_child_id,
                    )
                    if styled_image_safety["safety_passed"]:
                        cover_image_url = f"/data/styled/{Path(styled_image_path).name}"
                    else:
                        # Unsafe: discard styled image, fall back to original
                        styled_image_path = None
                except Exception:
                    logger.warning(
                        "Styled image safety validation failed, using original",
                        exc_info=True,
                    )
                    styled_image_path = None

        # Build response
        created_at = datetime.now()
        degraded_length = length_info["degraded_length"]
        story_content = StoryContent(
            text=story_text,
            word_count=word_count,
            age_adapted=True,
            degraded_length=degraded_length,
        )
        styled_image_url = cover_image_url if cover_image_url != image_url else None

        response = ImageToStoryResponse(
            story_id=story_id,
            story=story_content,
            image_url=image_url,
            styled_image_url=styled_image_url,
            audio_url=audio_url,
            video_url=None,
            video_job_id=None,
            educational_value=educational_value,
            characters=characters,
            analysis=result.get("analysis", {}),
            safety_score=result.get("safety_score", 0.0),
            created_at=created_at,
        )

        # Save story to database
        story_data = {
            "story_id": story_id,
            "story": {
                "text": story_text,
                "word_count": word_count,
                "age_adapted": True,
                "degraded_length": degraded_length,
            },
            "image_url": image_url,
            "audio_url": audio_url,
            "educational_value": {
                "themes": result.get("themes", []),
                "concepts": result.get("concepts", []),
                "moral": result.get("moral"),
            },
            "characters": [
                {
                    "character_name": c.character_name,
                    "description": c.description,
                    "appearances": c.appearances,
                }
                for c in characters
            ],
            "analysis": result.get("analysis", {}),
            "safety_score": result.get("safety_score", 0.0),
            "created_at": created_at.isoformat(),
            "child_id": safe_child_id,
            "age_group": age_group.value,
            "image_path": str(image_path),
            "art_theme": art_theme.value if art_theme != ArtTheme.NONE else None,
            "styled_image_path": styled_image_path,
            "styled_image_url": styled_image_url,
            "cover_image_url": cover_image_url,
        }
        story_data["user_id"] = user.user_id
        await story_repo.create(story_data)
        await usage_repo.increment(
            user.user_id, "image_to_story"
        )  # quota tracking (#314)

        # Store story embedding for dedup detection (#290)
        try:
            from ...mcp_servers import store_story_embedding

            await store_story_embedding(
                {
                    "child_id": safe_child_id,
                    "story_id": story_id,
                    "story_text": story_text,
                    "themes": ", ".join(result.get("themes", [])),
                    "age_group": age_group.value,
                }
            )
        except Exception:
            logger.debug("store_story_embedding skipped (non-critical)", exc_info=True)

        # Update child preferences (Advanced Memory)
        try:
            await preference_repo.update_from_story_result(
                safe_child_id, result, user_id=user.user_id
            )
        except Exception:
            pass  # Non-critical: don't fail the request

        # Sync detected characters to characters table (#160, #288, #289)
        analysis = result.get("analysis", {})
        for c in characters:
            try:
                char_data = {
                    "character_name": c.character_name,
                    "description": c.description,
                }
                visual_features, traits = _extract_character_enrichment(
                    char_data, analysis
                )
                await character_repo.upsert_character(
                    user_id=user.user_id,
                    child_id=safe_child_id,
                    name=c.character_name,
                    description=c.description,
                    visual_features=visual_features,
                    traits=traits,
                )
            except Exception:
                pass  # Non-critical

        # --- Provenance tracking (Issue #17, fixed FK ordering #234) ---
        # Provenance is recorded after story_repo.create() so that the
        # runs.story_id FK constraint is satisfied.
        try:
            run_id = await tracker.start_run(story_id, WorkflowType.IMAGE_TO_STORY)
        except Exception:
            logger.warning("Failed to start provenance run", exc_info=True)

        image_artifact_id = None
        if run_id:
            try:
                upload_step_id = await tracker.start_step(
                    run_id,
                    "image_upload",
                    1,
                    input_data={
                        "image_path": str(image_path),
                        "child_id": safe_child_id,
                    },
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
                await tracker.complete_step(
                    upload_step_id, output_data={"artifact_id": image_artifact_id}
                )
            except Exception:
                logger.warning("Failed to record image artifact", exc_info=True)

        # Provenance: vision_analysis step — detect silent MCP tool failures
        if run_id:
            try:
                vision_input = {"image_path": str(image_path), "child_age": child_age}
                vision_step_id = await tracker.start_step(
                    run_id,
                    "vision_analysis",
                    2,
                    input_data=vision_input,
                )
                vision_raw = result.get("analysis", {})
                vision_text = str(vision_raw.get("vision_analysis", ""))
                vision_ok = bool(
                    vision_raw.get("objects")
                    or (
                        vision_text
                        and "unable" not in vision_text.lower()
                        and "无法" not in vision_text
                        and "error" not in vision_text.lower()
                    )
                )
                vision_output = {
                    "vision_succeeded": vision_ok,
                    "objects_detected": vision_raw.get("objects", []),
                    "scene": vision_raw.get("scene"),
                    "raw_diagnostic": vision_text[:200] if vision_text else None,
                }
                if not vision_ok:
                    await tracker.complete_step(
                        vision_step_id,
                        output_data=vision_output,
                        error_message=f"Vision degraded: {vision_text[:150]}",
                    )
                else:
                    await tracker.complete_step(
                        vision_step_id, output_data=vision_output
                    )
            except Exception:
                logger.warning("Failed to record vision_analysis step", exc_info=True)

        styled_artifact_id = None
        if run_id and styled_image_path and Path(styled_image_path).exists():
            try:
                styled_step_id = await tracker.start_step(
                    run_id,
                    "style_transfer",
                    3,
                    input_data={
                        "image_path": str(image_path),
                        "theme": art_theme.value if art_theme else "none",
                    },
                )
                styled_mime, _ = mimetypes.guess_type(styled_image_path)
                styled_file_size = Path(styled_image_path).stat().st_size
                styled_artifact_id = await tracker.record_artifact(
                    styled_step_id,
                    ArtifactType.IMAGE,
                    run_id=run_id,
                    artifact_path=styled_image_path,
                    description=f"Style-transferred image ({art_theme.value if art_theme else 'none'})",
                    mime_type=styled_mime,
                    file_size=styled_file_size,
                    agent_name="style_transfer",
                    input_artifact_ids=[image_artifact_id]
                    if image_artifact_id
                    else None,
                )
                step_output = {"artifact_id": styled_artifact_id}
                if styled_image_safety:
                    step_output["image_safety_passed"] = styled_image_safety[
                        "safety_passed"
                    ]
                    step_output["image_safety_fell_back"] = styled_image_safety[
                        "fell_back"
                    ]
                    step_output["image_safety_flagged"] = styled_image_safety.get(
                        "flagged_keywords", []
                    )
                await tracker.complete_step(styled_step_id, output_data=step_output)
            except Exception:
                logger.warning("Failed to record styled image artifact", exc_info=True)

        text_artifact_id = None
        if run_id:
            try:
                text_step_id = await tracker.start_step(
                    run_id,
                    "text_artifact",
                    4,
                    input_data={"story_id": story_id},
                )
                text_artifact_id = await tracker.record_artifact(
                    text_step_id,
                    ArtifactType.TEXT,
                    run_id=run_id,
                    artifact_payload=story_text,
                    description="Generated story text",
                    safety_score=result.get("safety_score", 0.0),
                    agent_name="story_generation",
                    input_artifact_ids=[image_artifact_id]
                    if image_artifact_id
                    else None,
                    metadata=ArtifactMetadata(
                        char_count=len(story_text), word_count=word_count
                    ),
                )
                await tracker.complete_step(
                    text_step_id, output_data={"artifact_id": text_artifact_id}
                )
            except Exception:
                logger.warning("Failed to record text artifact", exc_info=True)

        audio_artifact_id = None
        if run_id and audio_url and result.get("audio_path"):
            try:
                audio_step_id = await tracker.start_step(
                    run_id,
                    "tts_artifact",
                    5,
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
                await tracker.complete_step(
                    audio_step_id, output_data={"artifact_id": audio_artifact_id}
                )
            except Exception:
                logger.warning("Failed to record audio artifact", exc_info=True)

        if run_id:
            try:
                art_repo = tracker._artifact_repo
                for artifact_id, role in [
                    (image_artifact_id, StoryArtifactRole.COVER),
                    (styled_artifact_id, StoryArtifactRole.COVER),
                    (text_artifact_id, StoryArtifactRole.STORY_TEXT),
                    (audio_artifact_id, StoryArtifactRole.FINAL_AUDIO),
                ]:
                    if not artifact_id:
                        continue
                    await art_repo.update_lifecycle_state(artifact_id, "candidate")
                    await art_repo.update_lifecycle_state(artifact_id, "published")
                    await tracker.link_to_story(story_id, artifact_id, role)
                await tracker.complete_run(
                    run_id,
                    result_summary={
                        "artifacts_created": sum(
                            1
                            for a in [
                                image_artifact_id,
                                styled_artifact_id,
                                text_artifact_id,
                                audio_artifact_id,
                            ]
                            if a
                        ),
                        "story_id": story_id,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to link artifacts and complete run", exc_info=True
                )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
            detail="Story generation failed, please try again later",
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
    status_code=status.HTTP_200_OK,
)
async def create_story_from_image_stream(
    request: Request,
    image: UploadFile = File(
        ..., description="Child's artwork image (PNG/JPG, max 10MB)"
    ),
    child_id: str = Form(..., description="Child unique identifier"),
    age_group: AgeGroup = Form(..., description="Age group: 3-5, 6-8, 9-12"),
    interests: Optional[str] = Form(
        None, description="Interest tags, comma-separated (max 5)"
    ),
    voice: str = Form("nova", description="Voice type"),
    enable_audio: bool = Form(True, description="Whether to generate audio"),
    art_theme: ArtTheme = Form(
        ArtTheme.NONE, description="Art style theme for image transformation"
    ),
    provider: Optional[str] = Form(None, description="TTS provider (openai, replicate, elevenlabs)"),
    user: UserData = Depends(check_generation_quota),
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

    # Validate art_theme for age group (#270)
    YOUNG_CHILD_THEMES = {
        ArtTheme.CARTOON,
        ArtTheme.CRAYON,
        ArtTheme.WATERCOLOR,
        ArtTheme.STORYBOOK,
        ArtTheme.NONE,
    }
    if child_age <= 5 and art_theme not in YOUNG_CHILD_THEMES:
        err_msg = f"Art theme '{art_theme.value}' is not available for age group 3-5"

        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': 'ValidationError', 'message': err_msg}, ensure_ascii=False)}\n\n"

        return StreamingResponse(error_generator(), media_type="text/event-stream")

    interests_list = None
    if interests:
        interests_list = [i.strip() for i in interests.split(",") if i.strip()]
        if len(interests_list) > 5:

            async def error_generator():
                yield f"event: error\ndata: {json.dumps({'error': 'ValidationError', 'message': 'Maximum 5 interest tags'}, ensure_ascii=False)}\n\n"

            return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Build image URL (relative to static file server)
    image_url = f"/data/uploads/{safe_child_id}/{image_path.name}"

    async def event_generator() -> AsyncGenerator[str, None]:
        story_id = str(uuid.uuid4())
        result_data = None
        client_disconnected = False
        tracker = ProvenanceTracker(db_manager)
        run_id = None

        try:
            async for event in stream_image_to_story(
                image_path=str(image_path),
                child_id=safe_child_id,
                child_age=child_age,
                interests=interests_list if interests_list is not None else [],
                enable_audio=enable_audio,
                voice=voice,
                art_theme=art_theme.value if art_theme != ArtTheme.NONE else None,
                user_id=user.user_id,
                provider=provider,
            ):
                if await request.is_disconnected():
                    logger.info(
                        "Client disconnected during story generation (story_id=%s), aborting",
                        story_id,
                    )
                    client_disconnected = True
                    break

                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    result_data = event_data

                    if await request.is_disconnected():
                        logger.info(
                            "Client disconnected before save (story_id=%s), skipping persist",
                            story_id,
                        )
                        client_disconnected = True
                        break

                    # Validate story length (#233)
                    length_info = validate_story_length(
                        result_data.get("story", ""),
                        age_group.value,
                    )
                    degraded_length = length_info["degraded_length"]

                    story_text = result_data.get("story", "")
                    word_count = count_words(story_text)

                    audio_url = None
                    if result_data.get("audio_path"):
                        audio_filename = Path(result_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    # Ensure style transfer output exists when user selected a style.
                    styled_image_path = await _ensure_styled_image_path(
                        current_styled_path=result_data.get("styled_image_path"),
                        image_path=image_path,
                        art_theme=art_theme,
                        child_age=child_age,
                        session_id=safe_child_id,
                    )

                    cover_image_url = image_url
                    styled_image_safety = None
                    if styled_image_path and Path(styled_image_path).exists():
                        if _skip_styled_safety_in_dev():
                            cover_image_url = (
                                f"/data/styled/{Path(styled_image_path).name}"
                            )
                            styled_image_safety = {
                                "safety_passed": True,
                                "fell_back": False,
                                "flagged_keywords": [],
                                "reason": "skipped_in_development",
                            }
                        else:
                            # Validate styled image safety before use (#273)
                            try:
                                styled_image_safety = await validate_and_fallback(
                                    styled_image_path=styled_image_path,
                                    original_image_path=str(image_path),
                                    child_age=child_age,
                                    theme=art_theme.value if art_theme else "none",
                                    session_id=safe_child_id,
                                )
                                if styled_image_safety["safety_passed"]:
                                    cover_image_url = (
                                        f"/data/styled/{Path(styled_image_path).name}"
                                    )
                                else:
                                    styled_image_path = None
                            except Exception:
                                logger.warning(
                                    "Styled image safety validation failed (streaming), using original",
                                    exc_info=True,
                                )
                                styled_image_path = None

                    # Build complete response data
                    response_data = {
                        "story_id": story_id,
                        "story": {
                            "text": story_text,
                            "word_count": word_count,
                            "age_adapted": True,
                            "degraded_length": degraded_length,
                        },
                        "image_url": image_url,
                        "styled_image_url": cover_image_url
                        if cover_image_url != image_url
                        else None,
                        "audio_url": audio_url,
                        "educational_value": {
                            "themes": result_data.get("themes", []),
                            "concepts": result_data.get("concepts", []),
                            "moral": result_data.get("moral"),
                        },
                        "characters": [
                            {
                                "character_name": c.get("name", ""),
                                "description": c.get("description", ""),
                                "appearances": c.get("appearances", 1),
                            }
                            for c in result_data.get("characters", [])
                        ],
                        "analysis": result_data.get("analysis", {}),
                        "safety_score": result_data.get("safety_score", 0.0),
                        "created_at": datetime.now().isoformat(),
                    }

                    # Save story to database (must happen before provenance — FK constraint)
                    story_save_data = {
                        **response_data,
                        "child_id": safe_child_id,
                        "age_group": age_group.value,
                        "image_path": str(image_path),
                        "art_theme": art_theme.value
                        if art_theme != ArtTheme.NONE
                        else None,
                        "styled_image_path": styled_image_path,
                        "cover_image_url": cover_image_url,
                    }
                    story_save_data["user_id"] = user.user_id
                    await story_repo.create(story_save_data)
                    await usage_repo.increment(
                        user.user_id, "image_to_story"
                    )  # quota tracking (#314)

                    # Store story embedding for dedup detection (#290)
                    try:
                        from ...mcp_servers import store_story_embedding

                        await store_story_embedding(
                            {
                                "child_id": safe_child_id,
                                "story_id": story_id,
                                "story_text": result_data.get("story", {}).get(
                                    "text", ""
                                ),
                                "themes": ", ".join(result_data.get("themes", [])),
                                "age_group": age_group.value,
                            }
                        )
                    except Exception:
                        logger.debug(
                            "store_story_embedding skipped (non-critical)",
                            exc_info=True,
                        )

                    try:
                        await preference_repo.update_from_story_result(
                            safe_child_id, result_data, user_id=user.user_id
                        )
                    except Exception:
                        pass

                    # Sync detected characters to characters table (#235, #288, #289)
                    stream_analysis = result_data.get("analysis", {})
                    for c in result_data.get("characters", []):
                        try:
                            visual_features, traits = _extract_character_enrichment(
                                c, stream_analysis
                            )
                            await character_repo.upsert_character(
                                user_id=user.user_id,
                                child_id=safe_child_id,
                                name=c.get("name", ""),
                                description=c.get("description", ""),
                                visual_features=visual_features,
                                traits=traits,
                            )
                        except Exception:
                            pass  # Non-critical

                    # --- Provenance: record run + all artifacts (Issue #234) ---
                    # Provenance is recorded after story_repo.create() so that the
                    # runs.story_id FK constraint is satisfied.
                    image_artifact_id = styled_artifact_id = text_artifact_id = (
                        audio_artifact_id
                    ) = None
                    try:
                        run_id = await tracker.start_run(
                            story_id, WorkflowType.IMAGE_TO_STORY
                        )
                    except Exception:
                        logger.warning(
                            "Failed to start streaming provenance run", exc_info=True
                        )

                    if run_id:
                        try:
                            upload_step_id = await tracker.start_step(
                                run_id,
                                "image_upload",
                                1,
                                input_data={
                                    "image_path": str(image_path),
                                    "child_id": safe_child_id,
                                },
                            )
                            mime, _ = mimetypes.guess_type(str(image_path))
                            file_size = (
                                image_path.stat().st_size
                                if image_path.exists()
                                else None
                            )
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
                            await tracker.complete_step(
                                upload_step_id,
                                output_data={"artifact_id": image_artifact_id},
                            )
                        except Exception:
                            logger.warning(
                                "Failed to record image artifact (streaming)",
                                exc_info=True,
                            )

                    # Provenance: vision_analysis step (streaming) — detect silent MCP tool failures
                    if run_id:
                        try:
                            s_vision_raw = result_data.get("analysis", {})
                            s_vision_text = str(s_vision_raw.get("vision_analysis", ""))
                            s_vision_ok = bool(
                                s_vision_raw.get("objects")
                                or (
                                    s_vision_text
                                    and "unable" not in s_vision_text.lower()
                                    and "无法" not in s_vision_text
                                    and "error" not in s_vision_text.lower()
                                )
                            )
                            s_vision_step = await tracker.start_step(
                                run_id,
                                "vision_analysis",
                                2,
                                input_data={
                                    "image_path": str(image_path),
                                    "child_age": child_age,
                                },
                            )
                            s_vision_output = {
                                "vision_succeeded": s_vision_ok,
                                "objects_detected": s_vision_raw.get("objects", []),
                                "raw_diagnostic": s_vision_text[:200]
                                if s_vision_text
                                else None,
                            }
                            if not s_vision_ok:
                                await tracker.complete_step(
                                    s_vision_step,
                                    output_data=s_vision_output,
                                    error_message=f"Vision degraded: {s_vision_text[:150]}",
                                )
                            else:
                                await tracker.complete_step(
                                    s_vision_step, output_data=s_vision_output
                                )
                        except Exception:
                            logger.warning(
                                "Failed to record vision_analysis step (streaming)",
                                exc_info=True,
                            )

                    styled_artifact_id = None
                    if (
                        run_id
                        and styled_image_path
                        and Path(styled_image_path).exists()
                    ):
                        try:
                            styled_step_id = await tracker.start_step(
                                run_id,
                                "style_transfer",
                                3,
                                input_data={
                                    "image_path": str(image_path),
                                    "theme": art_theme.value if art_theme else "none",
                                },
                            )
                            styled_mime, _ = mimetypes.guess_type(styled_image_path)
                            styled_file_size = Path(styled_image_path).stat().st_size
                            styled_artifact_id = await tracker.record_artifact(
                                styled_step_id,
                                ArtifactType.IMAGE,
                                run_id=run_id,
                                artifact_path=styled_image_path,
                                description=f"Style-transferred image ({art_theme.value if art_theme else 'none'})",
                                mime_type=styled_mime,
                                file_size=styled_file_size,
                                agent_name="style_transfer",
                                input_artifact_ids=[image_artifact_id]
                                if image_artifact_id
                                else None,
                            )
                            stream_step_output = {"artifact_id": styled_artifact_id}
                            if styled_image_safety:
                                stream_step_output["image_safety_passed"] = (
                                    styled_image_safety["safety_passed"]
                                )
                                stream_step_output["image_safety_fell_back"] = (
                                    styled_image_safety["fell_back"]
                                )
                                stream_step_output["image_safety_flagged"] = (
                                    styled_image_safety.get("flagged_keywords", [])
                                )
                            await tracker.complete_step(
                                styled_step_id, output_data=stream_step_output
                            )
                        except Exception:
                            logger.warning(
                                "Failed to record styled image artifact (streaming)",
                                exc_info=True,
                            )

                    if run_id:
                        try:
                            text_step_id = await tracker.start_step(
                                run_id,
                                "text_artifact",
                                4,
                                input_data={"story_id": story_id},
                            )
                            text_artifact_id = await tracker.record_artifact(
                                text_step_id,
                                ArtifactType.TEXT,
                                run_id=run_id,
                                artifact_payload=story_text,
                                description="Generated story text",
                                safety_score=result_data.get("safety_score", 0.0),
                                agent_name="story_generation",
                                input_artifact_ids=[image_artifact_id]
                                if image_artifact_id
                                else None,
                                metadata=ArtifactMetadata(
                                    char_count=len(story_text), word_count=word_count
                                ),
                            )
                            await tracker.complete_step(
                                text_step_id,
                                output_data={"artifact_id": text_artifact_id},
                            )
                        except Exception:
                            logger.warning(
                                "Failed to record text artifact (streaming)",
                                exc_info=True,
                            )

                    if run_id and audio_url and result_data.get("audio_path"):
                        try:
                            audio_step_id = await tracker.start_step(
                                run_id,
                                "tts_artifact",
                                5,
                                input_data={"audio_path": result_data["audio_path"]},
                            )
                            audio_mime, _ = mimetypes.guess_type(
                                result_data["audio_path"]
                            )
                            audio_artifact_id = await tracker.record_artifact(
                                audio_step_id,
                                ArtifactType.AUDIO,
                                run_id=run_id,
                                artifact_path=result_data["audio_path"],
                                artifact_url=audio_url,
                                description="TTS narration audio",
                                mime_type=audio_mime,
                                agent_name="tts_generation",
                                input_artifact_ids=[text_artifact_id]
                                if text_artifact_id
                                else None,
                            )
                            await tracker.complete_step(
                                audio_step_id,
                                output_data={"artifact_id": audio_artifact_id},
                            )
                        except Exception:
                            logger.warning(
                                "Failed to record audio artifact (streaming)",
                                exc_info=True,
                            )

                    if run_id:
                        try:
                            art_repo = tracker._artifact_repo
                            for artifact_id, role in [
                                (image_artifact_id, StoryArtifactRole.COVER),
                                (styled_artifact_id, StoryArtifactRole.COVER),
                                (text_artifact_id, StoryArtifactRole.STORY_TEXT),
                                (audio_artifact_id, StoryArtifactRole.FINAL_AUDIO),
                            ]:
                                if not artifact_id:
                                    continue
                                await art_repo.update_lifecycle_state(
                                    artifact_id, "candidate"
                                )
                                await art_repo.update_lifecycle_state(
                                    artifact_id, "published"
                                )
                                await tracker.link_to_story(story_id, artifact_id, role)
                            await tracker.complete_run(
                                run_id,
                                result_summary={
                                    "artifacts_created": sum(
                                        1
                                        for a in [
                                            image_artifact_id,
                                            styled_artifact_id,
                                            text_artifact_id,
                                            audio_artifact_id,
                                        ]
                                        if a
                                    ),
                                    "story_id": story_id,
                                },
                            )
                            run_id = None  # Prevent double-close in finally
                        except Exception:
                            logger.warning(
                                "Failed to link artifacts and complete streaming run",
                                exc_info=True,
                            )

                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            # Mark run as failed if provenance was started
            if run_id:
                try:
                    await tracker.fail_run(run_id, str(e))
                    run_id = None  # Prevent double-close in finally
                except Exception:
                    logger.warning(
                        "Failed to mark streaming run as failed", exc_info=True
                    )

            error_data = {
                "error": str(type(e).__name__),
                "message": f"Story generation failed: {str(e)}",
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

        finally:
            # Handle client disconnect — mark run as cancelled
            if client_disconnected and run_id:
                try:
                    await tracker.cancel_run(run_id, reason="client_disconnect")
                except Exception:
                    logger.warning(
                        "Failed to mark streaming run as cancelled", exc_info=True
                    )
                logger.info(
                    "Streaming aborted for story_id=%s due to client disconnect; provenance run cancelled",
                    story_id,
                )
            elif client_disconnected:
                logger.info(
                    "Streaming aborted for story_id=%s due to client disconnect; story was not saved",
                    story_id,
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/stories/{story_id}",
    summary="Get story",
    description="Get details of a generated story by story ID",
    responses={
        200: {"description": "Successfully retrieved story"},
        404: {"description": "Story not found"},
    },
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
    description="Get the complete story list for a specific child (including images, themes, and other details)",
)
async def get_child_story_history(
    child_id: str,
    limit: int = 20,
    user: UserData = Depends(get_current_user),
):
    """
    Get story history for a specific child (requires authentication, filtered by user)
    """
    stories = await story_repo.list_by_user_and_child(
        user.user_id, child_id, limit, story_type="image_to_story"
    )
    return JSONResponse(content=stories)


@router.delete(
    "/stories/{story_id}",
    summary="Delete a story",
    description="Delete a story (art story or news conversion) from the library",
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
    story = await get_story_for_owner(story_id, user.user_id)

    deleted = await story_repo.delete(story_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete story",
        )

    # Keep character memory aligned with library deletion:
    # each deleted story removes one appearance for each unique character.
    try:
        child_id = story.get("child_id")
        if child_id:
            for name in _extract_unique_character_names_for_decrement(story):
                await character_repo.decrement_appearance(
                    user.user_id,
                    child_id,
                    name,
                    amount=1,
                )
    except Exception:
        logger.warning(
            "Failed to decrement character appearances after story deletion: story_id=%s user_id=%s",
            story_id,
            user.user_id,
            exc_info=True,
        )

    return {"message": "Story deleted successfully", "story_id": story_id}
