"""Hybrid search contract — BM25 (Postgres tsvector) + pgvector cosine via RRF.

Locks the behavior that fixes the recall miss described in #590:
exact-name queries should rank the matching row first even when a
different row is closer in vector space; fuzzy queries should still
work when there's no exact match.

Skipped unless DATABASE_URL is a Postgres URL AND OPENAI_API_KEY is set.

Parent Epic: #42 (Memory System)
Issue: #590
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
        reason="requires DATABASE_URL=postgresql://... pointed at live Postgres+pgvector",
    ),
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="requires OPENAI_API_KEY for embedding generation",
    ),
]


def _new_child_id(prefix: str = "hs") -> str:
    """Per-test scope so cross-user isolation assertions can compare cleanly."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_tsvector_columns_and_gin_indexes_exist():
    """The migration must add a generated tsvector column + GIN index to
    both embedding tables."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema

    db = DatabaseManager()
    await db.connect()
    try:
        await init_schema(db)
        await init_vector_schema(db)

        # Columns
        for table in ("drawing_embeddings", "story_embeddings_pg"):
            rows = await db.fetchall(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ? AND column_name = 'text_search'",
                (table,),
            )
            assert rows, f"{table} is missing the text_search tsvector column"

        # GIN indexes
        idx_rows = await db.fetchall(
            "SELECT tablename, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename IN "
            "('drawing_embeddings', 'story_embeddings_pg')"
        )
        gin_tables = {
            r["tablename"]
            for r in idx_rows
            if "gin" in (r.get("indexdef") or "").lower()
            and "text_search" in (r.get("indexdef") or "")
        }
        assert "drawing_embeddings" in gin_tables
        assert "story_embeddings_pg" in gin_tables
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_hybrid_drawings_exact_name_beats_pure_vector_neighbor():
    """RRF must rank a stored drawing whose text literally contains
    'Lightning Dog' above a drawing that's closer in vector space but
    doesn't mention the name."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema
    from backend.src.services.database.vector_repository import VectorRepository

    db = DatabaseManager()
    await db.connect()
    try:
        await init_schema(db)
        await init_vector_schema(db)
        repo = VectorRepository(db)

        child_id = _new_child_id()

        # Two drawings for the SAME child:
        # A — literally names the character ("Lightning Dog")
        # B — vector-similar to typical "dog adventure" queries but no
        #     exact-name match (talks about a "puppy in a meadow")
        a_id = f"doc_a_{uuid.uuid4().hex[:8]}"
        b_id = f"doc_b_{uuid.uuid4().hex[:8]}"
        await repo.add_drawing(
            doc_id=a_id,
            child_id=child_id,
            document_text="Lightning Dog the brave hero flying through clouds",
            metadata={"child_id": child_id},
        )
        await repo.add_drawing(
            doc_id=b_id,
            child_id=child_id,
            document_text="A small fluffy puppy playing in a green meadow",
            metadata={"child_id": child_id},
        )

        hits = await repo.hybrid_search_drawings(
            query_text="Lightning Dog",
            child_id=child_id,
            top_k=5,
        )
        assert len(hits) >= 1, "hybrid search returned no hits at all"
        assert hits[0]["id"] == a_id, (
            "exact-name match must rank #1; "
            f"got {hits[0]['id']!r} (A is {a_id!r}, B is {b_id!r}); "
            f"hits={[h['id'] for h in hits]}"
        )


    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_hybrid_drawings_fuzzy_query_still_finds_relevant():
    """A query with no exact-name overlap should still find the most
    relevant drawing via the vector half of the fusion."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema
    from backend.src.services.database.vector_repository import VectorRepository

    db = DatabaseManager()
    await db.connect()
    try:
        await init_schema(db)
        await init_vector_schema(db)
        repo = VectorRepository(db)

        child_id = _new_child_id()
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        await repo.add_drawing(
            doc_id=doc_id,
            child_id=child_id,
            document_text="A brave young pup explores the deep dark forest at night",
            metadata={"child_id": child_id},
        )

        hits = await repo.hybrid_search_drawings(
            query_text="canine adventure in the wilderness",
            child_id=child_id,
            top_k=3,
        )
        assert len(hits) >= 1
        assert hits[0]["id"] == doc_id
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_hybrid_drawings_cross_user_isolation():
    """Another child's drawings must NEVER appear in this child's results."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema
    from backend.src.services.database.vector_repository import VectorRepository

    db = DatabaseManager()
    await db.connect()
    try:
        await init_schema(db)
        await init_vector_schema(db)
        repo = VectorRepository(db)

        child_a = _new_child_id("a")
        child_b = _new_child_id("b")
        doc_for_a = f"doc_{uuid.uuid4().hex[:8]}"
        await repo.add_drawing(
            doc_id=doc_for_a,
            child_id=child_a,
            document_text="Sparkle the Brave Lion roaring on a hill",
            metadata={"child_id": child_a},
        )

        hits = await repo.hybrid_search_drawings(
            query_text="Sparkle the Brave Lion",
            child_id=child_b,
            top_k=5,
        )
        ids = [h["id"] for h in hits]
        assert doc_for_a not in ids, (
            f"cross-user leakage: child A's drawing surfaced for child B (hits={ids})"
        )
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_hybrid_stories_exact_name_beats_vector_neighbor():
    """Same RRF guarantee as drawings, but for the story_embeddings_pg table."""
    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema
    from backend.src.services.database.vector_repository import VectorRepository

    db = DatabaseManager()
    await db.connect()
    try:
        await init_schema(db)
        await init_vector_schema(db)
        repo = VectorRepository(db)

        child_id = _new_child_id()
        a_id = f"story_a_{uuid.uuid4().hex[:8]}"
        b_id = f"story_b_{uuid.uuid4().hex[:8]}"

        await repo.add_story_embedding(
            doc_id=a_id,
            child_id=child_id,
            document_text=(
                "Lightning Dog soared above the moon, his cape glowing brightly."
            ),
            metadata={"story_id": a_id, "themes": "space, courage", "age_group": "6-8"},
        )
        await repo.add_story_embedding(
            doc_id=b_id,
            child_id=child_id,
            document_text="A tiny pup chased butterflies through a sunlit meadow.",
            metadata={"story_id": b_id, "themes": "nature, joy", "age_group": "6-8"},
        )

        hits = await repo.hybrid_search_stories(
            query_text="Lightning Dog story about the moon",
            child_id=child_id,
            top_k=5,
        )
        assert len(hits) >= 1
        assert hits[0]["id"] == a_id, (
            f"exact-name story query failed; hits={[h['id'] for h in hits]}"
        )
    finally:
        await db.disconnect()
