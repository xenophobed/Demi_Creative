"""
Vector Search MCP Server

Provides tools for storing and searching children's drawings in vector database (ChromaDB).
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib

import anyio
try:
    import chromadb
except Exception:  # pragma: no cover - import fallback for test env
    chromadb = None

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except Exception:  # pragma: no cover - import fallback for test env
    def tool(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs

# pgvector repository for production (#342)
from ..services.database.connection import db_manager
from ..services.database.vector_repository import VectorRepository, vector_repo


def _use_pgvector() -> bool:
    """Return True when the database backend is PostgreSQL (pgvector available)."""
    try:
        return db_manager.is_connected and db_manager.dialect == "postgresql"
    except Exception:
        return False


# Initialize ChromaDB client
def get_chroma_client():
    """Get ChromaDB client"""
    if chromadb is None:
        raise RuntimeError("ChromaDB SDK is unavailable in current environment")

    # Use persistent storage
    persist_directory = os.getenv("CHROMA_PATH", "./data/vectors")
    return chromadb.PersistentClient(path=persist_directory)


# Collection names
COLLECTION_NAME = "children_drawings"
STORY_COLLECTION_NAME = "story_embeddings"


def get_or_create_collection():
    """Get or create collection"""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Vector store for children's drawings"}
    )


def get_or_create_story_collection():
    """Get or create story embeddings collection (#161)."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=STORY_COLLECTION_NAME,
        metadata={"description": "Story text embeddings for deduplication"}
    )


@tool(
    "search_similar_drawings",
    """Search for historical drawings similar to the current drawing in the vector database.

    This tool is used to:
    1. Find similar content the child has drawn before
    2. Identify recurring characters (e.g. "Lightning Dog")
    3. Maintain story continuity

    Returns a list of similar drawings with similarity scores.""",
    {"drawing_description": str, "child_id": str, "top_k": int}
)
async def search_similar_drawings(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for similar historical drawings

    Args:
        args: Dictionary containing drawing_description, child_id, top_k

    Returns:
        Dictionary containing list of similar drawings
    """
    drawing_description = args["drawing_description"]
    child_id = args["child_id"]
    top_k = args.get("top_k", 5)

    try:
        # --- pgvector path (production) ---
        if _use_pgvector():
            # Hybrid (BM25 + cosine via RRF) replaces pure cosine here
            # so exact-name queries ("Lightning Dog") rank correctly even
            # when a different drawing is closer in vector space (#590).
            # Shape stays additive: the legacy fields are still present,
            # plus optional rrf_score / lex_rank / vec_rank for callers
            # that care about provenance.
            hits = await vector_repo.hybrid_search_drawings(
                query_text=drawing_description,
                child_id=child_id,
                top_k=top_k,
            )
            similar_drawings = [
                {
                    "id": h["id"],
                    "similarity_score": h.get("similarity_score") or 0.0,
                    "distance": (
                        round(1.0 / h["similarity_score"] - 1.0, 4)
                        if h.get("similarity_score") else 0.0
                    ),
                    "drawing_data": h.get("metadata") or {},
                    "description": h.get("document_text", ""),
                    "rrf_score": h.get("rrf_score"),
                    "lex_rank": h.get("lex_rank"),
                    "vec_rank": h.get("vec_rank"),
                }
                for h in hits
            ]
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "similar_drawings": similar_drawings,
                        "total_found": len(similar_drawings),
                        "query": {"child_id": child_id, "top_k": top_k}
                    }, ensure_ascii=False, indent=2)
                }]
            }

        # --- ChromaDB path (local dev) ---
        # Get collection (offload blocking ChromaDB call to thread)
        collection = await anyio.to_thread.run_sync(get_or_create_collection)

        # Use ChromaDB query functionality
        # ChromaDB automatically converts query text to vectors and searches
        results = await anyio.to_thread.run_sync(lambda: collection.query(
            query_texts=[drawing_description],
            n_results=top_k,
            where={"child_id": child_id}  # Filter this child's drawings
        ))

        # Format results
        similar_drawings = []
        if results and results['ids'] and len(results['ids']) > 0:
            ids = results['ids'][0]
            distances = results['distances'][0] if 'distances' in results else [0] * len(ids)
            metadatas = results['metadatas'][0] if 'metadatas' in results else [{}] * len(ids)
            documents = results['documents'][0] if 'documents' in results else [""] * len(ids)

            for i, doc_id in enumerate(ids):
                # ChromaDB returns distance, need to convert to similarity score
                # Smaller distance means higher similarity
                similarity_score = 1.0 / (1.0 + distances[i]) if i < len(distances) else 0.0

                similar_drawings.append({
                    "id": doc_id,
                    "similarity_score": round(similarity_score, 4),
                    "distance": round(distances[i], 4) if i < len(distances) else 0.0,
                    "drawing_data": metadatas[i] if i < len(metadatas) else {},
                    "description": documents[i] if i < len(documents) else ""
                })

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "similar_drawings": similar_drawings,
                    "total_found": len(similar_drawings),
                    "query": {
                        "child_id": child_id,
                        "top_k": top_k
                    }
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Vector search failed: {str(e)}",
                    "similar_drawings": [],
                    "total_found": 0
                }, ensure_ascii=False)
            }]
        }


@tool(
    "store_drawing_embedding",
    """Store children's drawing analysis results in the vector database.

    This tool is used to:
    1. Save the vector representation of drawings
    2. Store drawing metadata (objects, scenes, characters, etc.)
    3. Build a long-term memory system

    Call this tool after each new story creation.""",
    {"drawing_description": str, "child_id": str, "drawing_analysis": dict, "story_text": str, "image_path": str}
)
async def store_drawing_embedding(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store drawing in vector database

    Args:
        args: Dictionary containing drawing information

    Returns:
        Storage result
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[VectorStore] Received storage request, args: {json.dumps(args, ensure_ascii=False, default=str)[:500]}")

    drawing_description = args.get("drawing_description", "")
    child_id = args.get("child_id", "")
    drawing_analysis = args.get("drawing_analysis", {})
    story_text = args.get("story_text", "")
    image_path = args.get("image_path", "")

    # Parameter validation
    if not drawing_description:
        logger.warning("[VectorStore] drawing_description is empty")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "drawing_description cannot be empty"
                }, ensure_ascii=False)
            }]
        }

    if not child_id:
        logger.warning("[VectorStore] child_id is empty")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "child_id cannot be empty"
                }, ensure_ascii=False)
            }]
        }

    # If drawing_analysis is a string, try to parse it as dict
    if isinstance(drawing_analysis, str):
        try:
            drawing_analysis = json.loads(drawing_analysis)
        except json.JSONDecodeError:
            drawing_analysis = {}

    try:
        # Generate unique ID
        timestamp = datetime.now().isoformat()
        doc_id = hashlib.md5(
            f"{child_id}_{timestamp}".encode()
        ).hexdigest()

        # Prepare metadata
        metadata = {
            "child_id": child_id,
            "scene": drawing_analysis.get("scene", ""),
            "mood": drawing_analysis.get("mood", ""),
            "story_text": story_text[:500] if story_text else "",  # Limit length
            "image_path": image_path,
            "created_at": timestamp,
            # ChromaDB metadata only supports basic types, lists need to be converted to strings
            "objects": json.dumps(drawing_analysis.get("objects", []), ensure_ascii=False),
            "colors": json.dumps(drawing_analysis.get("colors", []), ensure_ascii=False),
            "recurring_characters": json.dumps(
                drawing_analysis.get("recurring_characters", []),
                ensure_ascii=False
            )
        }

        # --- pgvector path (production) ---
        if _use_pgvector():
            await vector_repo.add_drawing(
                doc_id=doc_id,
                child_id=child_id,
                document_text=drawing_description,
                metadata=metadata,
            )
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "document_id": doc_id,
                        "message": "Drawing successfully stored in vector database (pgvector)"
                    }, ensure_ascii=False, indent=2)
                }]
            }

        # --- ChromaDB path (local dev) ---
        # Get collection (offload blocking ChromaDB call to thread)
        collection = await anyio.to_thread.run_sync(get_or_create_collection)

        # Store in ChromaDB
        # ChromaDB automatically converts text to vectors
        await anyio.to_thread.run_sync(lambda: collection.add(
            ids=[doc_id],
            documents=[drawing_description],
            metadatas=[metadata]
        ))

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "document_id": doc_id,
                    "message": "Drawing successfully stored in vector database"
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Storage failed: {str(e)}"
                }, ensure_ascii=False)
            }]
        }


@tool(
    "store_story_embedding",
    """Store a story's text embedding for deduplication (#161).

    Called after story generation to enable semantic similarity checks
    before future generations. Prevents near-duplicate stories for the
    same child.""",
    {"child_id": str, "story_id": str, "story_text": str, "themes": str, "age_group": str}
)
async def store_story_embedding(args: Dict[str, Any]) -> Dict[str, Any]:
    """Store story text embedding in the story_embeddings collection."""
    child_id = args.get("child_id", "")
    story_id = args.get("story_id", "")
    story_text = args.get("story_text", "")

    if not child_id or not story_text:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"success": False, "error": "child_id and story_text are required"}, ensure_ascii=False)
            }]
        }

    try:
        doc_id = story_id or hashlib.md5(f"{child_id}_{datetime.now().isoformat()}".encode()).hexdigest()

        metadata = {
            "child_id": child_id,
            "story_id": story_id,
            "themes": args.get("themes", ""),
            "age_group": args.get("age_group", ""),
            "created_at": datetime.now().isoformat(),
        }

        # --- pgvector path (production) ---
        if _use_pgvector():
            await vector_repo.add_story_embedding(
                doc_id=doc_id,
                child_id=child_id,
                document_text=story_text[:2000],
                metadata=metadata,
            )
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({"success": True, "document_id": doc_id}, ensure_ascii=False)
                }]
            }

        # --- ChromaDB path (local dev) ---
        collection = await anyio.to_thread.run_sync(get_or_create_story_collection)

        await anyio.to_thread.run_sync(lambda: collection.upsert(
            ids=[doc_id],
            documents=[story_text[:2000]],
            metadatas=[metadata]
        ))

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"success": True, "document_id": doc_id}, ensure_ascii=False)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"success": False, "error": f"Failed to store story embedding: {e}"}, ensure_ascii=False)
            }]
        }


@tool(
    "search_similar_stories",
    """Search for semantically similar stories for a child (#161).

    Used before story generation to detect near-duplicates (similarity > 0.9)
    and inject variation nudges into the prompt.""",
    {"child_id": str, "story_description": str, "top_k": int}
)
async def search_similar_stories(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search for similar stories in the story_embeddings collection."""
    child_id = args.get("child_id", "")
    story_description = args.get("story_description", "")
    top_k = args.get("top_k", 5)

    if not child_id or not story_description:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"similar_stories": [], "total_found": 0}, ensure_ascii=False)
            }]
        }

    try:
        # --- pgvector path (production) ---
        if _use_pgvector():
            # Hybrid (BM25 + cosine via RRF) replaces pure cosine here so
            # exact-name dedup checks ("the Lightning Dog moon story") match
            # an existing story by literal name even when vector similarity
            # is close to a different one (#590). Shape stays additive.
            hits = await vector_repo.hybrid_search_stories(
                query_text=story_description,
                child_id=child_id,
                top_k=top_k,
            )
            similar_stories = []
            for h in hits:
                text = h.get("document_text", "")
                preview = (text[:200] + "...") if len(text) > 200 else text
                similar_stories.append({
                    "story_id": h["id"],
                    "similarity_score": h.get("similarity_score") or 0.0,
                    "story_text_preview": preview,
                    "metadata": h.get("metadata") or {},
                    "rrf_score": h.get("rrf_score"),
                    "lex_rank": h.get("lex_rank"),
                    "vec_rank": h.get("vec_rank"),
                })
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "similar_stories": similar_stories,
                        "total_found": len(similar_stories),
                        "query": {"child_id": child_id, "top_k": top_k}
                    }, ensure_ascii=False, indent=2)
                }]
            }

        # --- ChromaDB path (local dev) ---
        collection = await anyio.to_thread.run_sync(get_or_create_story_collection)

        results = await anyio.to_thread.run_sync(lambda: collection.query(
            query_texts=[story_description],
            n_results=top_k,
            where={"child_id": child_id}
        ))

        similar_stories = []
        if results and results['ids'] and len(results['ids']) > 0:
            ids = results['ids'][0]
            distances = results.get('distances', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            documents = results.get('documents', [[]])[0]

            for i, doc_id in enumerate(ids):
                similarity_score = 1.0 / (1.0 + distances[i]) if i < len(distances) else 0.0
                similar_stories.append({
                    "story_id": doc_id,
                    "similarity_score": round(similarity_score, 4),
                    "story_text_preview": (documents[i][:200] + "...") if i < len(documents) and len(documents[i]) > 200 else (documents[i] if i < len(documents) else ""),
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                })

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "similar_stories": similar_stories,
                    "total_found": len(similar_stories),
                    "query": {"child_id": child_id, "top_k": top_k}
                }, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"similar_stories": [], "total_found": 0, "error": str(e)}, ensure_ascii=False)
            }]
        }


@tool(
    "search_my_stories",
    """Find a child's previously generated stories by topic, character, or keyword.

    Use this when the child asks the buddy a recall question like:
      - "find my Lightning Dog story"
      - "what was that story about the moon"
      - "the one with the brave puppy"

    Returns a small list of matching stories (title preview + relative
    similarity). Hybrid retrieval (BM25 + cosine via RRF) — exact-name
    queries surface the named story even when a different story is
    closer in vector space. Always scoped by child_id (#288 / #590).

    Pure recall: this tool never launches a generation flow. Use the
    Agent tool to delegate generation to a specialist instead.""",
    {"query": str, "child_id": str, "top_k": int}
)
async def search_my_stories(args: Dict[str, Any]) -> Dict[str, Any]:
    """Hybrid story-recall tool for the buddy chat surface (#590)."""
    query = args.get("query") or ""
    child_id = args.get("child_id") or ""
    top_k = int(args.get("top_k") or 5)

    if not query or not child_id:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(
                    {"error": "query and child_id required", "stories": []},
                    ensure_ascii=False,
                )
            }]
        }

    if not _use_pgvector():
        # Falls back to nothing on local-dev SQLite + ChromaDB because
        # ChromaDB has no tsvector — hybrid only works on Postgres. The
        # buddy degrades gracefully (no recall hit, no error).
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(
                    {"stories": [], "total_found": 0, "backend": "chromadb-fallback"},
                    ensure_ascii=False,
                )
            }]
        }

    try:
        hits = await vector_repo.hybrid_search_stories(
            query_text=query, child_id=child_id, top_k=top_k,
        )
        stories = []
        for h in hits:
            text = h.get("document_text", "")
            preview = (text[:200] + "...") if len(text) > 200 else text
            meta = h.get("metadata") or {}
            stories.append({
                "story_id": h["id"],
                "title": meta.get("title", ""),
                "preview": preview,
                "themes": meta.get("themes", ""),
                "age_group": meta.get("age_group", ""),
                "similarity_score": h.get("similarity_score"),
                "rrf_score": h.get("rrf_score"),
            })
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(
                    {"stories": stories, "total_found": len(stories),
                     "query": {"q": query, "child_id": child_id, "top_k": top_k}},
                    ensure_ascii=False, indent=2,
                )
            }]
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(
                    {"stories": [], "total_found": 0, "error": str(exc)},
                    ensure_ascii=False,
                )
            }]
        }


# Create MCP Server
vector_server = create_sdk_mcp_server(
    name="vector-search",
    version="1.0.0",
    tools=[
        search_similar_drawings,
        store_drawing_embedding,
        store_story_embedding,
        search_similar_stories,
        search_my_stories,
    ]
)


if __name__ == "__main__":
    """Test tools"""
    import asyncio

    async def test():
        print("=== Test ChromaDB Vector Search ===\n")

        # Test storage
        print("1. Testing drawing storage...")
        store_result = await store_drawing_embedding({
            "drawing_description": "A puppy wearing blue clothes playing in the park, with trees and sun nearby",
            "child_id": "child_123",
            "drawing_analysis": {
                "objects": ["puppy", "trees", "sun", "grass"],
                "scene": "outdoor park",
                "mood": "happy",
                "colors": ["blue", "green", "yellow"],
                "recurring_characters": [{
                    "name": "Lightning",
                    "description": "A puppy wearing blue clothes",
                    "visual_features": ["blue clothes", "pointed ears"]
                }]
            },
            "story_text": "Lightning the puppy came to its favorite park today..."
        })
        print("Storage result:")
        print(json.loads(store_result["content"][0]["text"]))

        # Test search
        print("\n2. Testing similar drawing search...")
        search_result = await search_similar_drawings({
            "drawing_description": "A puppy outdoors",
            "child_id": "child_123",
            "top_k": 3
        })
        print("Search result:")
        print(json.loads(search_result["content"][0]["text"]))

    asyncio.run(test())
