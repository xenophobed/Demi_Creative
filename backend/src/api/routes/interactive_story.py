"""
Interactive Story API Routes

Interactive story API endpoints
Supports streaming responses (SSE) for a better user experience
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status, Path as PathParam
from fastapi.responses import JSONResponse, StreamingResponse

from ..models import (
    InteractiveStoryStartRequest,
    InteractiveStoryStartResponse,
    ChoiceRequest,
    ChoiceResponse,
    SessionStatusResponse,
    SessionResumeResponse,
    SaveInteractiveStoryResponse,
    StorySegment,
    StoryChoice,
    EducationalValue,
    AgeGroup,
    SessionStatus as SessionStatusEnum
)
from ..deps import get_current_user, get_session_for_owner
from ...services.database import session_repo, story_repo, preference_repo, character_repo, db_manager
from ...services.user_service import UserData
from ...services.provenance_tracker import ProvenanceTracker
from ...services.models.artifact_models import (
    ArtifactType, WorkflowType, StoryArtifactRole,
    ArtifactMetadata,
)
from ...agents.interactive_story_agent import (
    generate_story_opening,
    generate_story_opening_stream,
    generate_next_segment,
    generate_next_segment_stream,
    AGE_CONFIG
)
from ...utils.audio_strategy import get_audio_strategy
from ...utils.text import count_words

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/story/interactive",
    tags=["Interactive Story"]
)

_AGE_MAP = {"3-5": 4, "6-8": 7, "9-12": 11}


async def _check_story_safety(text: str, age_group: str) -> float:
    """Run check_content_safety on story text, return the safety score.

    Falls back to 0.0 if the MCP tool is unavailable so that callers
    never silently accept unchecked content (fail-closed).
    """
    try:
        from ...mcp_servers import check_content_safety

        result = await check_content_safety({
            "content_text": text,
            "content_type": "interactive_story",
            "target_age": _AGE_MAP.get(age_group, 7),
        })
        data = json.loads(result["content"][0]["text"])
        if "error" in data:
            logger.warning("Safety MCP tool returned error: %s", data["error"])
            return 0.0
        return float(data.get("safety_score", 0.0))
    except Exception:
        logger.warning(
            "Safety check unavailable for interactive story, blocking content (fail-closed)",
            exc_info=True,
        )
        return 0.0


@router.post(
    "/start",
    response_model=InteractiveStoryStartResponse,
    summary="Start interactive story",
    description="Create a new interactive story session",
    status_code=status.HTTP_201_CREATED
)
async def start_interactive_story(
    request: InteractiveStoryStartRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Start an interactive story

    **Workflow**:
    1. Validate request parameters
    2. Create a new session
    3. Generate the story opening
    4. Return the session ID and first segment

    **Example request**:
    ```json
    {
      "child_id": "child_001",
      "age_group": "6-8",
      "interests": ["animals", "adventure"],
      "theme": "forest exploration",
      "voice": "fable",
      "enable_audio": true
    }
    ```
    """
    tracker = ProvenanceTracker(db_manager)
    run_id = None

    try:
        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(request.age_group.value)

        # 1. Generate story opening
        opening_data = await generate_story_opening(
            child_id=request.child_id,
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme,
            enable_audio=request.enable_audio,
            voice=request.voice.value
        )

        # 2. Create session (determine total segments based on age group)
        age_config = AGE_CONFIG.get(request.age_group.value, AGE_CONFIG["6-8"])
        total_segments = age_config["total_segments"]

        session = await session_repo.create_session(
            child_id=request.child_id,
            story_title=opening_data["title"],
            age_group=request.age_group.value,
            interests=request.interests,
            theme=request.theme,
            voice=request.voice.value,
            enable_audio=request.enable_audio,
            total_segments=total_segments,
            user_id=user.user_id,
        )

        # 3. Save opening segment
        segment_data = opening_data["segment"]

        # Handle audio URL from agent result
        audio_url = None
        if opening_data.get("audio_path"):
            audio_filename = Path(opening_data["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        await session_repo.update_session(
            session_id=session.session_id,
            segment=segment_data,
            audio_url=audio_url,
            segment_id=segment_data["segment_id"]
        )

        # --- Provenance tracking (Issue #138) ---
        try:
            run_id = await tracker.start_run(
                session.session_id, WorkflowType.INTERACTIVE_STORY,
                session_id=session.session_id,
            )
            step_id = await tracker.start_step(
                run_id, "story_opening", 1,
                input_data={
                    "child_id": request.child_id,
                    "age_group": request.age_group.value,
                    "theme": request.theme,
                },
                model_name="claude-agent-sdk",
                prompt_hash=ProvenanceTracker.compute_prompt_hash(
                    f"interactive_story:{request.child_id}:{request.age_group.value}"
                ),
            )
            story_text = segment_data.get("text", "")
            text_artifact_id = await tracker.record_artifact(
                step_id, ArtifactType.TEXT, run_id=run_id,
                artifact_payload=story_text,
                description="Interactive story opening segment",
                safety_score=opening_data.get("safety_score"),
                agent_name="interactive_story",
                metadata=ArtifactMetadata(
                    char_count=len(story_text),
                    word_count=count_words(story_text),
                ),
            )
            if audio_url and opening_data.get("audio_path"):
                await tracker.record_artifact(
                    step_id, ArtifactType.AUDIO, run_id=run_id,
                    artifact_path=opening_data["audio_path"],
                    artifact_url=audio_url,
                    description="TTS narration for opening segment",
                    mime_type="audio/mpeg",
                    agent_name="tts_generation",
                    input_artifact_ids=[text_artifact_id],
                )
            await tracker.complete_step(step_id, output_data={
                "segment_id": segment_data["segment_id"],
            })
        except Exception:
            logger.warning("Provenance tracking failed for story opening", exc_info=True)

        # 4. Build response with age-based display settings
        opening_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=audio_url,
            choices=[
                StoryChoice(**choice)
                for choice in segment_data["choices"]
            ],
            is_ending=False,
            primary_mode=audio_strategy.primary_mode,
            optional_content_available=audio_strategy.optional_content_available,
            optional_content_type=audio_strategy.optional_content_type
        )

        response = InteractiveStoryStartResponse(
            session_id=session.session_id,
            story_title=opening_data["title"],
            opening=opening_segment,
            created_at=datetime.now()
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        if run_id:
            try:
                await tracker.fail_run(run_id, str(e))
            except Exception:
                logger.warning("Failed to mark provenance run as failed", exc_info=True)
        print(f"Error starting interactive story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Story creation failed, please try again later"
        )


@router.post(
    "/start/stream",
    summary="Start interactive story (streaming)",
    description="Create a new interactive story session with Server-Sent Events streaming progress",
    status_code=status.HTTP_200_OK
)
async def start_interactive_story_stream(
    request: InteractiveStoryStartRequest,
    user: UserData = Depends(get_current_user),
):
    """
    Start an interactive story with streaming

    Uses Server-Sent Events (SSE) to stream story generation progress.

    **Event types**:
    - `status`: Status update (started, processing)
    - `thinking`: AI thinking process
    - `tool_use`: Tool usage notification
    - `tool_result`: Tool result
    - `session`: Session creation complete
    - `result`: Story content
    - `complete`: Generation complete
    - `error`: Error message

    **Example event stream**:
    ```
    event: status
    data: {"status": "started", "message": "Creating story..."}

    event: thinking
    data: {"content": "Let me think...", "turn": 1}

    event: session
    data: {"session_id": "xxx", "story_title": "Adventure Journey"}

    event: result
    data: {"title": "...", "segment": {...}}

    event: complete
    data: {"status": "completed"}
    ```
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        session = None
        opening_data = None
        tracker = ProvenanceTracker(db_manager)
        run_id = None

        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(request.age_group.value)

        try:
            # Stream story opening generation
            async for event in generate_story_opening_stream(
                child_id=request.child_id,
                age_group=request.age_group.value,
                interests=request.interests,
                theme=request.theme,
                enable_audio=request.enable_audio,
                voice=request.voice.value
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                # When receiving a result, create the session
                if event_type == "result":
                    opening_data = event_data

                    # Create session
                    age_config = AGE_CONFIG.get(request.age_group.value, AGE_CONFIG["6-8"])
                    total_segments = age_config["total_segments"]

                    session = await session_repo.create_session(
                        child_id=request.child_id,
                        story_title=opening_data.get("title", "Untitled Story"),
                        age_group=request.age_group.value,
                        interests=request.interests,
                        theme=request.theme,
                        voice=request.voice.value,
                        enable_audio=request.enable_audio,
                        total_segments=total_segments,
                        user_id=user.user_id,
                    )

                    # Save opening segment
                    segment_data = opening_data.get("segment", {})

                    # Handle audio URL from agent result
                    audio_url = None
                    if opening_data.get("audio_path"):
                        audio_filename = Path(opening_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    await session_repo.update_session(
                        session_id=session.session_id,
                        segment=segment_data,
                        audio_url=audio_url,
                        segment_id=segment_data.get("segment_id", 0)
                    )

                    # --- Provenance tracking (Issue #138) ---
                    try:
                        run_id = await tracker.start_run(
                            session.session_id, WorkflowType.INTERACTIVE_STORY,
                            session_id=session.session_id,
                        )
                        step_id = await tracker.start_step(
                            run_id, "story_opening", 1,
                            input_data={
                                "child_id": request.child_id,
                                "age_group": request.age_group.value,
                                "theme": request.theme,
                            },
                            model_name="claude-agent-sdk",
                            prompt_hash=ProvenanceTracker.compute_prompt_hash(
                                f"interactive_story:{request.child_id}:{request.age_group.value}"
                            ),
                        )
                        story_text = segment_data.get("text", "")
                        text_artifact_id = await tracker.record_artifact(
                            step_id, ArtifactType.TEXT, run_id=run_id,
                            artifact_payload=story_text,
                            description="Interactive story opening segment",
                            safety_score=opening_data.get("safety_score"),
                            agent_name="interactive_story",
                            metadata=ArtifactMetadata(
                                char_count=len(story_text),
                                word_count=count_words(story_text),
                            ),
                        )
                        if audio_url and opening_data.get("audio_path"):
                            await tracker.record_artifact(
                                step_id, ArtifactType.AUDIO, run_id=run_id,
                                artifact_path=opening_data["audio_path"],
                                artifact_url=audio_url,
                                description="TTS narration for opening segment",
                                mime_type="audio/mpeg",
                                agent_name="tts_generation",
                                input_artifact_ids=[text_artifact_id],
                            )
                        await tracker.complete_step(step_id, output_data={
                            "segment_id": segment_data.get("segment_id", 0),
                        })
                    except Exception:
                        logger.warning("Provenance tracking failed for stream opening", exc_info=True)

                    # Send session info
                    yield f"event: session\ndata: {json.dumps({'session_id': session.session_id, 'story_title': opening_data.get('title', '')}, ensure_ascii=False)}\n\n"

                    # Build complete response data with age-based display settings
                    response_data = {
                        "session_id": session.session_id,
                        "story_title": opening_data.get("title", ""),
                        "opening": {
                            "segment_id": segment_data.get("segment_id", 0),
                            "text": segment_data.get("text", ""),
                            "audio_url": audio_url,
                            "choices": segment_data.get("choices", []),
                            "is_ending": False,
                            "primary_mode": audio_strategy.primary_mode,
                            "optional_content_available": audio_strategy.optional_content_available,
                            "optional_content_type": audio_strategy.optional_content_type
                        },
                        "created_at": datetime.now().isoformat()
                    }
                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    # Forward other events
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            if run_id:
                try:
                    await tracker.fail_run(run_id, str(e))
                except Exception:
                    logger.warning("Failed to mark provenance run as failed", exc_info=True)
            error_data = {"error": str(e), "message": "Story creation failed"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post(
    "/{session_id}/choose/stream",
    summary="Choose story branch (streaming)",
    description="Make a choice in the interactive story, use SSE streaming to return the next segment"
)
async def choose_story_branch_stream(
    session_id: str = PathParam(..., description="Session ID"),
    request: ChoiceRequest = ...,
    user: UserData = Depends(get_current_user),
):
    """
    Choose a story branch with streaming (requires authentication + session ownership)
    """
    session = await get_session_for_owner(session_id, user.user_id)

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"会话状态为 {session.status}，无法继续"
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(session.age_group)
        tracker = ProvenanceTracker(db_manager)
        run_id = None
        segment_number = len(session.segments) + 1

        try:
            # Stream next segment generation
            async for event in generate_next_segment_stream(
                session_id=session_id,
                choice_id=request.choice_id,
                session_data={
                    "segments": session.segments,
                    "choice_history": session.choice_history,
                    "age_group": session.age_group,
                    "interests": session.interests,
                    "theme": session.theme,
                    "story_title": session.story_title
                },
                enable_audio=session.enable_audio,
                voice=session.voice
            ):
                event_type = event.get("type", "message")
                event_data = event.get("data", {})

                if event_type == "result":
                    next_data = event_data
                    segment_data = next_data.get("segment", {})
                    is_ending = next_data.get("is_ending", False)

                    # Handle audio URL from agent result
                    audio_url = None
                    if next_data.get("audio_path"):
                        audio_filename = Path(next_data["audio_path"]).name
                        audio_url = f"/data/audio/{audio_filename}"

                    # Update session
                    await session_repo.update_session(
                        session_id=session_id,
                        segment=segment_data,
                        choice_id=request.choice_id,
                        status="completed" if is_ending else "active",
                        educational_summary=next_data.get("educational_summary"),
                        audio_url=audio_url,
                        segment_id=segment_data.get("segment_id", 0)
                    )

                    # --- Provenance tracking (Issue #138) ---
                    try:
                        run_id = await tracker.start_run(
                            session_id, WorkflowType.INTERACTIVE_STORY,
                            session_id=session_id,
                        )
                        step_id = await tracker.start_step(
                            run_id, f"segment_{segment_number}", 1,
                            input_data={
                                "choice_id": request.choice_id,
                                "segment_number": segment_number,
                                "age_group": session.age_group,
                            },
                            model_name="claude-agent-sdk",
                        )
                        story_text = segment_data.get("text", "")
                        text_artifact_id = await tracker.record_artifact(
                            step_id, ArtifactType.TEXT, run_id=run_id,
                            artifact_payload=story_text,
                            description=f"Interactive story segment {segment_number}",
                            safety_score=next_data.get("safety_score"),
                            agent_name="interactive_story",
                            metadata=ArtifactMetadata(
                                char_count=len(story_text),
                                word_count=count_words(story_text),
                            ),
                        )
                        if audio_url and next_data.get("audio_path"):
                            await tracker.record_artifact(
                                step_id, ArtifactType.AUDIO, run_id=run_id,
                                artifact_path=next_data["audio_path"],
                                artifact_url=audio_url,
                                description=f"TTS narration for segment {segment_number}",
                                mime_type="audio/mpeg",
                                agent_name="tts_generation",
                                input_artifact_ids=[text_artifact_id],
                            )
                        await tracker.complete_step(step_id, output_data={
                            "segment_id": segment_data.get("segment_id", 0),
                            "is_ending": is_ending,
                        })
                        await tracker.complete_run(run_id, result_summary={
                            "segment_number": segment_number,
                            "is_ending": is_ending,
                        })
                    except Exception:
                        logger.warning(
                            "Provenance tracking failed for stream segment %d",
                            segment_number, exc_info=True,
                        )

                    # Update preferences on completion (Advanced Memory)
                    if is_ending:
                        try:
                            await preference_repo.update_from_choices(
                                child_id=session.child_id,
                                choice_history=session.choice_history + [request.choice_id],
                                session_data={
                                    "theme": session.theme,
                                    "interests": session.interests,
                                },
                            )
                            if next_data.get("educational_summary"):
                                await preference_repo.update_from_story_result(
                                    session.child_id, next_data["educational_summary"]
                                )
                        except Exception:
                            pass  # Non-critical

                    # Get updated session
                    updated_session = await session_repo.get_session(session_id)

                    # Build response with age-based display settings
                    response_data = {
                        "session_id": session_id,
                        "next_segment": {
                            "segment_id": segment_data.get("segment_id", 0),
                            "text": segment_data.get("text", ""),
                            "audio_url": audio_url,
                            "choices": segment_data.get("choices", []),
                            "is_ending": segment_data.get("is_ending", False),
                            "primary_mode": audio_strategy.primary_mode,
                            "optional_content_available": audio_strategy.optional_content_available,
                            "optional_content_type": audio_strategy.optional_content_type
                        },
                        "choice_history": updated_session.choice_history,
                        "progress": updated_session.current_segment / updated_session.total_segments,
                        "educational_summary": next_data.get("educational_summary")
                    }
                    yield f"event: result\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            if run_id:
                try:
                    await tracker.fail_run(run_id, str(e))
                except Exception:
                    logger.warning("Failed to mark provenance run as failed", exc_info=True)
            error_data = {"error": str(e), "message": "Story branch generation failed"}
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


@router.post(
    "/{session_id}/choose",
    response_model=ChoiceResponse,
    summary="Choose story branch",
    description="Make a choice in the interactive story and get the next segment"
)
async def choose_story_branch(
    session_id: str = PathParam(..., description="Session ID"),
    request: ChoiceRequest = ...,
    user: UserData = Depends(get_current_user),
):
    """
    Choose a story branch (requires authentication + session ownership)
    """
    tracker = ProvenanceTracker(db_manager)
    run_id = None

    try:
        # 1. Get session and verify ownership
        session = await get_session_for_owner(session_id, user.user_id)

        # 2. Check session status
        if session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"会话状态为 {session.status}，无法继续"
            )

        # Get audio strategy for the age group
        audio_strategy = get_audio_strategy(session.age_group)

        # 3. Generate next segment (pass full session context)
        next_data = await generate_next_segment(
            session_id=session_id,
            choice_id=request.choice_id,
            session_data={
                "segments": session.segments,
                "choice_history": session.choice_history,
                "age_group": session.age_group,
                "interests": session.interests,
                "theme": session.theme,
                "story_title": session.story_title
            },
            enable_audio=session.enable_audio,
            voice=session.voice
        )

        # 4. Update session
        segment_data = next_data["segment"]
        is_ending = next_data.get("is_ending", False)

        # Handle audio URL from agent result
        audio_url = None
        if next_data.get("audio_path"):
            audio_filename = Path(next_data["audio_path"]).name
            audio_url = f"/data/audio/{audio_filename}"

        await session_repo.update_session(
            session_id=session_id,
            segment=segment_data,
            choice_id=request.choice_id,
            status="completed" if is_ending else "active",
            educational_summary=next_data.get("educational_summary"),
            audio_url=audio_url,
            segment_id=segment_data["segment_id"]
        )

        # --- Provenance tracking (Issue #138) ---
        segment_number = len(session.segments) + 1
        try:
            run_id = await tracker.start_run(
                session_id, WorkflowType.INTERACTIVE_STORY,
                session_id=session_id,
            )
            step_id = await tracker.start_step(
                run_id, f"segment_{segment_number}", 1,
                input_data={
                    "choice_id": request.choice_id,
                    "segment_number": segment_number,
                    "age_group": session.age_group,
                },
                model_name="claude-agent-sdk",
            )
            story_text = segment_data.get("text", "")
            text_artifact_id = await tracker.record_artifact(
                step_id, ArtifactType.TEXT, run_id=run_id,
                artifact_payload=story_text,
                description=f"Interactive story segment {segment_number}",
                safety_score=next_data.get("safety_score"),
                agent_name="interactive_story",
                metadata=ArtifactMetadata(
                    char_count=len(story_text),
                    word_count=count_words(story_text),
                ),
            )
            if audio_url and next_data.get("audio_path"):
                await tracker.record_artifact(
                    step_id, ArtifactType.AUDIO, run_id=run_id,
                    artifact_path=next_data["audio_path"],
                    artifact_url=audio_url,
                    description=f"TTS narration for segment {segment_number}",
                    mime_type="audio/mpeg",
                    agent_name="tts_generation",
                    input_artifact_ids=[text_artifact_id],
                )
            await tracker.complete_step(step_id, output_data={
                "segment_id": segment_data["segment_id"],
                "is_ending": is_ending,
            })
            await tracker.complete_run(run_id, result_summary={
                "segment_number": segment_number,
                "is_ending": is_ending,
            })
        except Exception:
            logger.warning("Provenance tracking failed for segment %d", segment_number, exc_info=True)

        # Update preferences on completion (Advanced Memory)
        if is_ending:
            try:
                await preference_repo.update_from_choices(
                    child_id=session.child_id,
                    choice_history=session.choice_history + [request.choice_id],
                    session_data={
                        "theme": session.theme,
                        "interests": session.interests,
                    },
                )
                if next_data.get("educational_summary"):
                    await preference_repo.update_from_story_result(
                        session.child_id, next_data["educational_summary"]
                    )
            except Exception:
                pass  # Non-critical

        # 5. Build response with age-based display settings
        next_segment = StorySegment(
            segment_id=segment_data["segment_id"],
            text=segment_data["text"],
            audio_url=audio_url,
            choices=[
                StoryChoice(**choice)
                for choice in segment_data.get("choices", [])
            ],
            is_ending=segment_data.get("is_ending", False),
            primary_mode=audio_strategy.primary_mode,
            optional_content_available=audio_strategy.optional_content_available,
            optional_content_type=audio_strategy.optional_content_type
        )

        # Updated session
        updated_session = await session_repo.get_session(session_id)

        response = ChoiceResponse(
            session_id=session_id,
            next_segment=next_segment,
            choice_history=updated_session.choice_history,
            progress=updated_session.current_segment / updated_session.total_segments
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        if run_id:
            try:
                await tracker.fail_run(run_id, str(e))
            except Exception:
                logger.warning("Failed to mark provenance run as failed", exc_info=True)
        print(f"Error choosing story branch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Story branch generation failed, please try again later"
        )


@router.get(
    "/{session_id}/resume",
    response_model=SessionResumeResponse,
    summary="Resume interactive story session",
    description="Fetch full session data including all segments for resuming a story"
)
async def resume_session(
    session_id: str = PathParam(..., description="Session ID"),
    user: UserData = Depends(get_current_user),
):
    """
    Resume an interactive story session — returns all segments so the
    frontend can restore the story view from a My Library card click.
    """
    try:
        session = await get_session_for_owner(session_id, user.user_id)

        # Reactivate expired sessions so the user can continue playing
        if session.status == "expired":
            new_expiry = (datetime.now() + timedelta(hours=24)).isoformat()
            await session_repo.update_session(session_id, status="active")
            await session_repo._db.execute(
                "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
                (new_expiry, session_id)
            )
            await session_repo._db.commit()
            session.status = "active"

        # Parse stored segments into StorySegment models
        segments = []
        for seg_data in session.segments:
            choices = [
                StoryChoice(**c) for c in seg_data.get("choices", [])
            ]
            segments.append(StorySegment(
                segment_id=seg_data.get("segment_id", 0),
                text=seg_data.get("text", ""),
                audio_url=seg_data.get("audio_url"),
                choices=choices,
                is_ending=seg_data.get("is_ending", False),
                primary_mode=seg_data.get("primary_mode", "both"),
                optional_content_available=seg_data.get("optional_content_available", False),
                optional_content_type=seg_data.get("optional_content_type"),
            ))

        educational_summary = None
        if session.educational_summary:
            educational_summary = EducationalValue(**session.educational_summary)

        progress = (
            session.current_segment / session.total_segments
            if session.total_segments > 0 else 0.0
        )

        return SessionResumeResponse(
            session_id=session.session_id,
            status=SessionStatusEnum(session.status),
            story_title=session.story_title,
            age_group=AgeGroup(session.age_group),
            segments=segments,
            choice_history=session.choice_history,
            progress=progress,
            total_segments=session.total_segments,
            educational_summary=educational_summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error resuming session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume session"
        )


@router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get session status",
    description="Query the current status of an interactive story session"
)
async def get_session_status(
    session_id: str = PathParam(..., description="Session ID"),
    user: UserData = Depends(get_current_user),
):
    """
    Get session status (requires authentication + session ownership)
    """
    try:
        # Get session and verify ownership
        session = await get_session_for_owner(session_id, user.user_id)

        # Build response
        educational_summary = None
        if session.educational_summary:
            educational_summary = EducationalValue(**session.educational_summary)

        response = SessionStatusResponse(
            session_id=session.session_id,
            status=SessionStatusEnum(session.status),
            child_id=session.child_id,
            story_title=session.story_title,
            current_segment=session.current_segment,
            total_segments=session.total_segments,
            choice_history=session.choice_history,
            educational_summary=educational_summary,
            created_at=datetime.fromisoformat(session.created_at),
            updated_at=datetime.fromisoformat(session.updated_at),
            expires_at=datetime.fromisoformat(session.expires_at)
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        print(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session status"
        )


@router.post(
    "/{session_id}/save",
    response_model=SaveInteractiveStoryResponse,
    summary="Save interactive story to My Library",
    description="Save a completed interactive story session as a story record"
)
async def save_interactive_story(
    session_id: str = PathParam(..., description="Session ID"),
    user: UserData = Depends(get_current_user),
):
    """
    Save a completed interactive story to the stories table.
    Requires authentication + session ownership.
    """
    try:
        # Get session and verify ownership
        session = await get_session_for_owner(session_id, user.user_id)

        if session.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only save completed stories"
            )

        # Concatenate all segment texts
        full_text = "\n\n".join(
            seg.get("text", "") for seg in session.segments if seg.get("text")
        )

        # Run safety check on the full story text
        safety_score = await _check_story_safety(full_text, session.age_group)
        if safety_score < 0.85:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Story content did not pass safety check "
                    f"(score={safety_score:.2f}, threshold=0.85)"
                ),
            )

        # Build story data
        story_id = str(uuid.uuid4())
        educational = session.educational_summary or {}

        story_data = {
            "story_id": story_id,
            "user_id": user.user_id,
            "child_id": session.child_id,
            "age_group": session.age_group,
            "story_type": "interactive",
            "story": {
                "text": full_text,
                "word_count": count_words(full_text),
                "age_adapted": True,
            },
            "educational_value": {
                "themes": educational.get("themes", []),
                "concepts": educational.get("concepts", []),
                "moral": educational.get("moral"),
            },
            "characters": [],
            "analysis": {
                "story_type": "interactive",
                "session_id": session_id,
                "choices_made": len(session.choice_history),
                "story_title": session.story_title,
            },
            "safety_score": safety_score,
            "created_at": session.created_at,
        }

        await story_repo.create(story_data)

        # Sync detected characters to characters table (#160)
        for char_data in story_data.get("characters", []):
            try:
                name = char_data.get("character_name") or char_data.get("name", "")
                if name:
                    await character_repo.upsert_character(
                        child_id=session.child_id,
                        name=name,
                        description=char_data.get("description", ""),
                    )
            except Exception:
                pass  # Non-critical

        # --- Provenance: record full story text + link to story (Issue #138) ---
        try:
            tracker = ProvenanceTracker(db_manager)
            run_id = await tracker.start_run(
                story_id, WorkflowType.INTERACTIVE_STORY,
                session_id=session_id,
            )
            step_id = await tracker.start_step(
                run_id, "save_story", 1,
                input_data={
                    "session_id": session_id,
                    "segments_count": len(session.segments),
                    "safety_score": safety_score,
                },
            )
            text_artifact_id = await tracker.record_artifact(
                step_id, ArtifactType.TEXT, run_id=run_id,
                artifact_payload=full_text,
                description="Complete interactive story text",
                safety_score=safety_score,
                agent_name="interactive_story",
                metadata=ArtifactMetadata(
                    char_count=len(full_text),
                    word_count=count_words(full_text),
                ),
            )
            # Promote and link
            art_repo = tracker._artifact_repo
            await art_repo.update_lifecycle_state(text_artifact_id, "candidate")
            await art_repo.update_lifecycle_state(text_artifact_id, "published")

            # Link audio artifacts from segments if available
            for seg in session.segments:
                audio_url = seg.get("audio_url")
                if audio_url:
                    audio_artifact_id = await tracker.record_artifact(
                        step_id, ArtifactType.AUDIO, run_id=run_id,
                        artifact_url=audio_url,
                        description="Segment TTS narration",
                        agent_name="tts_generation",
                        input_artifact_ids=[text_artifact_id],
                    )
                    await art_repo.update_lifecycle_state(audio_artifact_id, "candidate")
                    await tracker.publish_artifact(
                        audio_artifact_id, story_id, StoryArtifactRole.FINAL_AUDIO,
                    )

            await tracker.complete_step(step_id, output_data={
                "story_id": story_id,
                "text_artifact_id": text_artifact_id,
            })
            await tracker.complete_run(run_id, result_summary={
                "story_id": story_id,
                "safety_score": safety_score,
            })
        except Exception:
            logger.warning("Provenance tracking failed for save_interactive_story", exc_info=True)

        return SaveInteractiveStoryResponse(
            story_id=story_id,
            session_id=session_id,
            message="Interactive story saved successfully"
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f"Error saving interactive story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save interactive story"
        )


@router.delete(
    "/{session_id}",
    summary="Delete an interactive story session",
    description="Delete an interactive story session from the library"
)
async def delete_session(
    session_id: str = PathParam(..., description="Session ID"),
    user: UserData = Depends(get_current_user),
):
    """
    Delete an interactive story session (requires authentication + ownership).
    """
    # Verify ownership first
    await get_session_for_owner(session_id, user.user_id)

    deleted = await session_repo.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )

    return {"message": "Session deleted successfully", "session_id": session_id}
