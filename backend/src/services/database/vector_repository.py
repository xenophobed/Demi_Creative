"""
Vector Repository — pgvector-backed similarity search for production.

Uses OpenAI text-embedding-3-small (1536 dims) for embedding generation
and PostgreSQL pgvector for storage and cosine similarity search.

Issue: #342 | Parent Epic: #313
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .connection import db_manager

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment, misc]


class VectorRepository:
    """pgvector-backed vector storage and similarity search.

    Embedding client is created lazily on first use. Uses OpenAI
    text-embedding-3-small which produces 1536-dimensional vectors.
    """

    MODEL_NAME = "text-embedding-3-small"
    DIMENSIONS = 1536

    def __init__(self, db: "Any" = None):
        # Default to the global singleton — production callers pass nothing.
        # Tests can inject a fresh DatabaseManager so a per-function event
        # loop owns the asyncpg pool (avoids "attached to a different loop").
        self._db = db if db is not None else db_manager
        self._client = None

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-init OpenAI client."""
        if self._client is None:
            if OpenAI is None:
                raise RuntimeError(
                    "openai package is not installed. "
                    "Install it with: pip install openai"
                )
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def _embed(self, text: str) -> List[float]:
        """Generate embedding vector for a text string via OpenAI API."""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.MODEL_NAME,
            input=text,
        )
        return response.data[0].embedding

    @staticmethod
    def _vector_literal(vec: List[float]) -> str:
        """Format a vector as a pgvector literal string: '[0.1,0.2,...]'."""
        return "[" + ",".join(str(v) for v in vec) + "]"

    # ------------------------------------------------------------------
    # Drawing embeddings
    # ------------------------------------------------------------------

    async def add_drawing(
        self,
        doc_id: str,
        child_id: str,
        document_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a drawing description with its embedding vector."""
        embedding = self._embed(document_text)
        vec_literal = self._vector_literal(embedding)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        from datetime import datetime
        now = datetime.now().isoformat()

        await self._db.execute(
            """
            INSERT INTO drawing_embeddings (doc_id, child_id, document_text, embedding, metadata_json, created_at)
            VALUES (?, ?, ?, ?::vector, ?, ?)
            ON CONFLICT (doc_id) DO UPDATE SET
                document_text = EXCLUDED.document_text,
                embedding = EXCLUDED.embedding,
                metadata_json = EXCLUDED.metadata_json
            """,
            (doc_id, child_id, document_text, vec_literal, metadata_json, now),
        )
        await self._db.commit()

    async def search_similar_drawings(
        self,
        query_text: str,
        child_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find the most similar drawings for a child using cosine distance."""
        embedding = self._embed(query_text)
        vec_literal = self._vector_literal(embedding)

        rows = await self._db.fetchall(
            """
            SELECT doc_id, child_id, document_text, metadata_json,
                   embedding <=> ?::vector AS distance
            FROM drawing_embeddings
            WHERE child_id = ?
            ORDER BY distance ASC
            LIMIT ?
            """,
            (vec_literal, child_id, top_k),
        )

        results = []
        for row in rows:
            distance = row.get("distance", 0.0)
            similarity = 1.0 / (1.0 + distance)
            meta = {}
            if row.get("metadata_json"):
                try:
                    meta = json.loads(row["metadata_json"])
                except json.JSONDecodeError:
                    pass
            results.append({
                "id": row["doc_id"],
                "similarity_score": round(similarity, 4),
                "distance": round(distance, 4),
                "drawing_data": meta,
                "description": row.get("document_text", ""),
            })
        return results

    async def get_drawings_by_child(self, child_id: str) -> List[Dict[str, Any]]:
        """Return all drawing embeddings for a child (no similarity search)."""
        rows = await self._db.fetchall(
            "SELECT doc_id, child_id, document_text, metadata_json, created_at "
            "FROM drawing_embeddings WHERE child_id = ?",
            (child_id,),
        )
        results = []
        for row in rows:
            meta = {}
            if row.get("metadata_json"):
                try:
                    meta = json.loads(row["metadata_json"])
                except json.JSONDecodeError:
                    pass
            results.append({
                "id": row["doc_id"],
                "child_id": row["child_id"],
                "document_text": row.get("document_text", ""),
                "metadata": meta,
                "created_at": row.get("created_at", ""),
            })
        return results

    # ------------------------------------------------------------------
    # Story embeddings
    # ------------------------------------------------------------------

    async def add_story_embedding(
        self,
        doc_id: str,
        child_id: str,
        document_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a story text with its embedding vector for deduplication."""
        embedding = self._embed(document_text)
        vec_literal = self._vector_literal(embedding)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        from datetime import datetime
        now = datetime.now().isoformat()

        await self._db.execute(
            """
            INSERT INTO story_embeddings_pg (doc_id, child_id, document_text, embedding, metadata_json, created_at)
            VALUES (?, ?, ?, ?::vector, ?, ?)
            ON CONFLICT (doc_id) DO UPDATE SET
                document_text = EXCLUDED.document_text,
                embedding = EXCLUDED.embedding,
                metadata_json = EXCLUDED.metadata_json
            """,
            (doc_id, child_id, document_text, vec_literal, metadata_json, now),
        )
        await self._db.commit()

    async def search_similar_stories(
        self,
        query_text: str,
        child_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find semantically similar stories for a child."""
        embedding = self._embed(query_text)
        vec_literal = self._vector_literal(embedding)

        rows = await self._db.fetchall(
            """
            SELECT doc_id, child_id, document_text, metadata_json,
                   embedding <=> ?::vector AS distance
            FROM story_embeddings_pg
            WHERE child_id = ?
            ORDER BY distance ASC
            LIMIT ?
            """,
            (vec_literal, child_id, top_k),
        )

        results = []
        for row in rows:
            distance = row.get("distance", 0.0)
            similarity = 1.0 / (1.0 + distance)
            meta = {}
            if row.get("metadata_json"):
                try:
                    meta = json.loads(row["metadata_json"])
                except json.JSONDecodeError:
                    pass
            text = row.get("document_text", "")
            preview = (text[:200] + "...") if len(text) > 200 else text
            results.append({
                "story_id": row["doc_id"],
                "similarity_score": round(similarity, 4),
                "story_text_preview": preview,
                "metadata": meta,
            })
        return results

    # ------------------------------------------------------------------
    # Hybrid search — BM25 (Postgres tsvector) + pgvector cosine via RRF
    # ------------------------------------------------------------------
    #
    # Why RRF and not weighted score blending?
    #   The two scoring functions are incomparable: BM25 raw scores
    #   range with corpus, cosine distance is bounded [0, 2]. Rank-based
    #   fusion sidesteps normalization. We use the standard k=60 dampener
    #   so neither side's #1 always dominates.
    # See PRD §3.5 "Hybrid Retrieval Approach".

    _RRF_K = 60   # standard dampener; lower = top hits dominate more.
    _LIMIT = 50   # how many candidates each subquery contributes to the fusion.

    async def _hybrid_search(
        self,
        *,
        table: str,
        query_text: str,
        child_id: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """RRF over BM25 (tsvector) + cosine on the given embedding table.

        Returns rows with id, similarity_score (cosine for the picked
        doc — useful for callers that still want a score), rrf_score,
        lex_rank, vec_rank, plus the full row payload.
        """
        embedding = self._embed(query_text)
        vec_literal = self._vector_literal(embedding)
        rrf_k = self._RRF_K
        candidate_limit = self._LIMIT

        # Two CTEs, one per subquery, plus a third that fuses by RRF.
        # COALESCE handles candidates that appear in only one list.
        # `plainto_tsquery` is forgiving (no syntax errors on raw user text).
        # If the lexical query has zero matches the lex side simply
        # contributes nothing, which is exactly the desired behavior.
        rows = await self._db.fetchall(
            f"""
            WITH
            lex AS (
                SELECT doc_id,
                       ROW_NUMBER() OVER (ORDER BY ts_rank(text_search, plainto_tsquery('english', ?)) DESC) AS rnk
                FROM {table}
                WHERE child_id = ?
                  AND text_search @@ plainto_tsquery('english', ?)
                LIMIT ?
            ),
            vec AS (
                SELECT doc_id,
                       ROW_NUMBER() OVER (ORDER BY embedding <=> ?::vector ASC) AS rnk,
                       embedding <=> ?::vector AS distance
                FROM {table}
                WHERE child_id = ?
                ORDER BY embedding <=> ?::vector
                LIMIT ?
            ),
            fused AS (
                SELECT
                    COALESCE(lex.doc_id, vec.doc_id) AS doc_id,
                    lex.rnk AS lex_rank,
                    vec.rnk AS vec_rank,
                    vec.distance AS distance,
                    COALESCE(1.0 / (? + lex.rnk), 0) + COALESCE(1.0 / (? + vec.rnk), 0) AS rrf_score
                FROM lex
                FULL OUTER JOIN vec ON lex.doc_id = vec.doc_id
            )
            SELECT t.doc_id, t.child_id, t.document_text, t.metadata_json,
                   t.created_at,
                   f.lex_rank, f.vec_rank, f.distance, f.rrf_score
            FROM fused f
            JOIN {table} t ON t.doc_id = f.doc_id
            ORDER BY f.rrf_score DESC
            LIMIT ?
            """,
            (
                query_text, child_id, query_text, candidate_limit,
                vec_literal, vec_literal, child_id, vec_literal, candidate_limit,
                rrf_k, rrf_k,
                top_k,
            ),
        )

        results: List[Dict[str, Any]] = []
        for row in rows:
            distance = row.get("distance")
            similarity = (
                round(1.0 / (1.0 + float(distance)), 4)
                if distance is not None else None
            )
            meta = {}
            if row.get("metadata_json"):
                try:
                    meta = json.loads(row["metadata_json"])
                except json.JSONDecodeError:
                    pass
            results.append({
                "id": row["doc_id"],
                "child_id": row["child_id"],
                "document_text": row.get("document_text", ""),
                "metadata": meta,
                "similarity_score": similarity,
                "rrf_score": float(row["rrf_score"]),
                "lex_rank": int(row["lex_rank"]) if row.get("lex_rank") is not None else None,
                "vec_rank": int(row["vec_rank"]) if row.get("vec_rank") is not None else None,
                "created_at": row.get("created_at", ""),
            })
        return results

    async def hybrid_search_drawings(
        self,
        query_text: str,
        child_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Hybrid (BM25 + cosine via RRF) over drawing_embeddings (#590)."""
        return await self._hybrid_search(
            table="drawing_embeddings",
            query_text=query_text,
            child_id=child_id,
            top_k=top_k,
        )

    async def hybrid_search_stories(
        self,
        query_text: str,
        child_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Hybrid (BM25 + cosine via RRF) over story_embeddings_pg (#590)."""
        return await self._hybrid_search(
            table="story_embeddings_pg",
            query_text=query_text,
            child_id=child_id,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    async def delete_by_child(self, child_id: str) -> int:
        """Delete all vector data for a child. Returns total rows deleted."""
        r1 = await self._db.execute(
            "DELETE FROM drawing_embeddings WHERE child_id = ?",
            (child_id,),
        )
        r2 = await self._db.execute(
            "DELETE FROM story_embeddings_pg WHERE child_id = ?",
            (child_id,),
        )
        await self._db.commit()
        deleted = (r1.rowcount if r1 else 0) + (r2.rowcount if r2 else 0)
        return deleted


# Module-level singleton (follows the same pattern as other repositories)
vector_repo = VectorRepository()
