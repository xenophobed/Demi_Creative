# Vector Search MCP Server

**Source**: `backend/src/mcp_servers/vector_search_server.py`

## What This File Does

**Explorer**: This helper remembers all the drawings kids have uploaded before. When a new drawing arrives, it can find similar past drawings — like a librarian who says "Oh, you drew a dragon? Here are three other dragon drawings from last week!"

**Maker**: This MCP server provides embedding-based similarity search. It stores vector representations of drawings and stories, then retrieves the most similar items using cosine distance. Supports two backends: ChromaDB (local dev) and pgvector (PostgreSQL production via `VectorRepository`).

## How It Works

1. **Storing**: When a drawing is analyzed, `store_drawing_embedding` saves:
   - The drawing's text description (from vision analysis)
   - Metadata (child_id, age_group, themes, timestamp)
   - An embedding vector computed from the description
2. **Searching**: `search_similar_drawings` takes a query (text or drawing description) and returns the top-N most similar items by vector distance
3. **Backend selection**: `_use_pgvector()` checks if the database is PostgreSQL — if yes, uses pgvector; otherwise falls back to ChromaDB

### Dual Backend Architecture

```
vector_search_server.py
  │
  ├─ PostgreSQL detected? → VectorRepository (pgvector)
  │     Uses SQL: SELECT ... ORDER BY embedding <=> query_vector
  │
  └─ Otherwise → ChromaDB (local)
        Uses chromadb.PersistentClient at CHROMA_PATH
```

## Key Concepts

**Embedding**: A list of numbers (a vector) that represents the "meaning" of text or an image. Similar items have vectors that point in similar directions. Think of it as converting words into coordinates on a map — things that mean similar things are close together on the map.

**Cosine Similarity**: A way to measure how similar two vectors are by checking the angle between them. Angle near 0 = very similar. Angle near 90 = unrelated.

**pgvector**: A PostgreSQL extension that adds vector column types and efficient similarity search operators (`<=>` for cosine distance). Used in production because it lives inside the same database as all other data.

**ChromaDB**: A lightweight local vector database. Used in development because it requires no external database setup — just a folder on disk.

## Connections

- **Upstream**: Called by `image_to_story_agent.py` to find similar past drawings and avoid duplicate stories
- **Downstream (prod)**: `services/database/vector_repository.py` → PostgreSQL with pgvector
- **Downstream (dev)**: ChromaDB via `CHROMA_PATH` environment variable
- **Related**: `story_memory.py` uses vector search for cross-story references

## Thinking Question

Why maintain two vector backends (ChromaDB + pgvector) instead of using pgvector everywhere? Think about developer experience: what happens when a new contributor clones the repo and wants to run it locally without installing PostgreSQL?
