#!/usr/bin/env python3
"""
One-shot dev migration: SQLite + ChromaDB -> Postgres + pgvector.

Usage:
    # 1. bring up local postgres
    ./backend/scripts/dev_db.sh up

    # 2. export DATABASE_URL
    export DATABASE_URL=postgresql://creative:creative@localhost:54329/creative_agent_dev

    # 3. run this migration
    python -m backend.scripts.migrate_sqlite_to_postgres

    # 4. (optional) start the app with DATABASE_URL still exported
    python backend/scripts/start_server.py

What it does:
  Phase A — connect both adapters and run init_schema() against Postgres.
  Phase B — copy SQL tables in FK-topological order with ON CONFLICT DO
            NOTHING. Idempotent: a second run is a no-op.
  Phase C — bump each SERIAL sequence to MAX(id) so the next INSERT
            doesn't trip a duplicate-key error.
  Phase D — re-embed each ChromaDB document via the OpenAI embedder used
            by VectorRepository (chroma's default embedder is 384-dim;
            our pgvector schema is 1536-dim, so vectors are NOT copied
            raw — they are recomputed from the stored text).
  Phase E — print a reconciliation report.

Flags:
  --dry-run        : count source rows + chroma docs, do not write to PG.
  --skip-vectors   : do only the SQL copy, skip ChromaDB re-embed.
  --sqlite-path P  : override DB_PATH (default uses the same path the app uses).
  --chroma-path P  : override CHROMA_PATH (default reads env or ./data/vectors).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Lazy imports inside main() so --help works even when chromadb is absent.


# Tables in FK-topological order. Children appear after parents so
# INSERT ... ON CONFLICT respects the foreign keys.
TABLE_ORDER: List[str] = [
    "users",
    "tokens",
    "child_profiles",
    "child_preferences",
    "stories",
    "sessions",
    "story_segments",
    "characters",
    "cloned_voices",
    "daily_usage",
    "referrals",
    "topic_subscriptions",
    "user_agents",
    "agent_chat_sessions",
    "agent_chat_messages",
    "hub_groups",
    "hub_group_memberships",
    "hub_posts",
    "hub_post_reactions",
    "runs",
    "agent_steps",
    "artifacts",
    "artifact_relations",
    "story_artifact_links",
    "run_artifact_links",
    "artifact_character_links",
    "favorites",
    "child_achievements",
]

# Sequence resetting is handled generically in Phase C by introspecting
# each copied table for a serial/identity column (see _reset_sequence).
# A hand-maintained allow-list used to live here, but it silently omitted
# tables (topic_subscriptions, *_artifact_links, ...) whose sequences then
# never advanced past the bulk-copied MAX(id) — producing duplicate-key
# 500s on the first real INSERT. Introspection cannot drift out of sync.


@dataclass
class Report:
    tables_copied: Dict[str, int] = field(default_factory=dict)
    tables_skipped: List[str] = field(default_factory=list)
    vectors_replayed: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


async def _list_sqlite_tables(sqlite_db) -> set[str]:
    rows = await sqlite_db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    return {row["name"] for row in rows}


async def _copy_table(sqlite_db, pg_db, name: str) -> int:
    """Copy all rows of one table from SQLite to Postgres with ON CONFLICT."""
    rows = await sqlite_db.fetchall(f"SELECT * FROM {name}")
    if not rows:
        return 0
    cols = list(rows[0].keys())
    # Postgres uses $1..$N placeholders via asyncpg; we go through the
    # adapter's execute() which already translates ? -> $N.
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    sql = (
        f"INSERT INTO {name} ({col_list}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING"
    )
    inserted = 0
    for row in rows:
        params = tuple(row[c] for c in cols)
        try:
            result = await pg_db.execute(sql, params)
            # asyncpg returns INSERT 0 N status — count rows by parsing
            # rowcount on the CursorResult wrapper.
            if hasattr(result, "rowcount") and result.rowcount:
                inserted += result.rowcount
            else:
                inserted += 1  # best effort when adapter doesn't report
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"insert into {name} failed: {exc}") from exc
    await pg_db.commit()
    return inserted


async def _reset_sequence(pg_db, name: str) -> bool:
    """Bump <table>'s id sequence to MAX(id) so future INSERTs don't collide.

    Returns True if a sequence was found and reset. Tables with a TEXT
    primary key (no serial/identity column) have no sequence and are
    skipped without error.
    """
    try:
        seq = await pg_db.fetchone(
            f"SELECT pg_get_serial_sequence('{name}', 'id') AS seq"
        )
        seq_name = seq["seq"] if seq else None
        if not seq_name:
            return False  # TEXT PK or no serial id — nothing to reset.
        await pg_db.execute(
            f"SELECT setval('{seq_name}', "
            f"COALESCE((SELECT MAX(id) FROM {name}), 1))"
        )
        await pg_db.commit()
        return True
    except Exception:  # noqa: BLE001
        return False


async def _replay_chromadb(chroma_path: Path, pg_db, dry_run: bool) -> Dict[str, int]:
    """Re-embed each ChromaDB document via OpenAI and load into pgvector."""
    try:
        import chromadb
    except ImportError:
        print("  ! chromadb not installed; skipping vector replay")
        return {}

    if not chroma_path.exists():
        print(f"  ! no chroma data at {chroma_path}; skipping vector replay")
        return {}

    from backend.src.services.database.vector_repository import VectorRepository

    client = chromadb.PersistentClient(path=str(chroma_path))
    # Bind the repo to the SAME connected pg_db the migration opened.
    # (The global db_manager singleton is never connected in this script,
    # so VectorRepository() with no args would fail "not connected".)
    vector_repo = VectorRepository(db=pg_db)

    counts: Dict[str, int] = {}

    # Drawings
    try:
        drawings = client.get_collection("children_drawings")
        data = drawings.get(include=["documents", "metadatas"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        print(f"  - children_drawings: {len(ids)} docs")
        if not dry_run:
            for doc_id, text, meta in zip(ids, docs, metas):
                child_id = (meta or {}).get("child_id", "")
                if not child_id or not text:
                    continue
                await vector_repo.add_drawing(
                    doc_id=doc_id,
                    child_id=child_id,
                    document_text=text,
                    metadata=meta or {},
                )
        counts["children_drawings"] = len(ids)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! drawings replay failed: {exc}")

    # Stories
    try:
        stories = client.get_collection("story_embeddings")
        data = stories.get(include=["documents", "metadatas"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        print(f"  - story_embeddings: {len(ids)} docs")
        if not dry_run:
            for doc_id, text, meta in zip(ids, docs, metas):
                m = meta or {}
                child_id = m.get("child_id", "")
                story_id = m.get("story_id", doc_id)
                themes = m.get("themes", "")
                age_group = m.get("age_group", "")
                if not child_id or not text:
                    continue
                await vector_repo.add_story_embedding(
                    doc_id=story_id,
                    child_id=child_id,
                    document_text=text,
                    metadata={
                        "story_id": story_id,
                        "themes": themes if isinstance(themes, str) else json.dumps(themes),
                        "age_group": age_group,
                    },
                )
        counts["story_embeddings"] = len(ids)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! stories replay failed: {exc}")

    return counts


async def main_async(args: argparse.Namespace) -> int:
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        print(
            "ERROR: DATABASE_URL must point to a Postgres URL "
            "(postgresql://...) before running this migration.",
            file=sys.stderr,
        )
        return 2

    from backend.src.services.database.connection import DatabaseManager
    from backend.src.services.database.schema import init_schema
    from backend.src.services.database.schema_vectors import init_vector_schema
    from backend.src.paths import DB_PATH

    sqlite_path = Path(args.sqlite_path) if args.sqlite_path else DB_PATH
    chroma_path = Path(args.chroma_path or os.environ.get("CHROMA_PATH", "./data/vectors"))

    print(f"SQLite source:   {sqlite_path}")
    print(f"ChromaDB source: {chroma_path}")
    print(f"Postgres target: {os.environ['DATABASE_URL']}")
    print(f"Dry run:         {args.dry_run}")
    print()

    if not sqlite_path.exists():
        print(f"ERROR: SQLite file not found at {sqlite_path}", file=sys.stderr)
        return 2

    # --- Phase A: connect both, init Postgres schema ---
    sqlite_db = DatabaseManager(db_path=str(sqlite_path))
    pg_db = DatabaseManager()  # picks up DATABASE_URL
    await sqlite_db.connect()
    await pg_db.connect()
    print(f"Connected: sqlite={sqlite_db.dialect}, pg={pg_db.dialect}")

    if not args.dry_run:
        await init_schema(pg_db)
        await init_vector_schema(pg_db)
        print("Postgres schema initialized\n")

    report = Report()

    # --- Phase B: copy SQL tables ---
    print("Phase B: copying SQL tables")
    source_tables = await _list_sqlite_tables(sqlite_db)
    for name in TABLE_ORDER:
        if name not in source_tables:
            report.tables_skipped.append(name)
            print(f"  - {name:32s} skipped (not in source)")
            continue
        rows = await sqlite_db.fetchall(f"SELECT COUNT(*) AS c FROM {name}")
        source_count = rows[0]["c"] if rows else 0
        if args.dry_run:
            print(f"  - {name:32s} {source_count} rows (dry-run)")
            continue
        try:
            n = await _copy_table(sqlite_db, pg_db, name)
            report.tables_copied[name] = n
            print(f"  - {name:32s} copied {n}/{source_count}")
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{name}: {exc}")
            print(f"  ! {name:32s} ERROR: {exc}")

    # --- Phase C: bump sequences ---
    # Reset the sequence for EVERY copied table (introspected per table),
    # not a hand-maintained subset — a missed table leaves its sequence at
    # 1 and the first real INSERT collides with bulk-copied rows.
    if not args.dry_run:
        print("\nPhase C: resetting SERIAL sequences")
        reset = 0
        for name in report.tables_copied:
            if await _reset_sequence(pg_db, name):
                reset += 1
        print(f"  done ({reset} sequences reset)")

    # --- Phase D: ChromaDB -> pgvector ---
    if not args.skip_vectors:
        print("\nPhase D: replaying ChromaDB into pgvector")
        if not os.environ.get("OPENAI_API_KEY"):
            print("  ! OPENAI_API_KEY not set; skipping vector replay")
        else:
            report.vectors_replayed = await _replay_chromadb(
                chroma_path, pg_db, args.dry_run
            )

    # --- Phase E: reconciliation ---
    print("\n=== Summary ===")
    print(f"Tables copied: {len(report.tables_copied)}")
    print(f"Tables skipped (not in source): {len(report.tables_skipped)}")
    print(f"Vectors replayed: {sum(report.vectors_replayed.values())}")
    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e}")

    await sqlite_db.disconnect()
    await pg_db.disconnect()
    return 0 if not report.errors else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="don't write to Postgres")
    p.add_argument("--skip-vectors", action="store_true", help="skip ChromaDB replay")
    p.add_argument("--sqlite-path", default=None)
    p.add_argument("--chroma-path", default=None)
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
