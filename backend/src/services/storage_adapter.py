"""
Storage Adapter — abstraction for file uploads and media storage.

Supports two backends:
- **local** (default): writes to ``DATA_DIR/<bucket>/<filename>``, serves
  via FastAPI StaticFiles at ``/data/<bucket>/<filename>``.
- **supabase**: uploads to Supabase Storage buckets, returns public CDN URLs.

The active backend is selected by the ``STORAGE_BACKEND`` env var.
"""

import logging
import os
from pathlib import Path
from typing import Protocol

from ..paths import DATA_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Supabase SDK import (follows project convention for optional deps)
# ---------------------------------------------------------------------------
try:
    from supabase import create_client as _create_supabase_client
except Exception:  # pragma: no cover - import fallback for envs without SDK
    _create_supabase_client = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class StorageAdapter(Protocol):
    """Thin protocol every storage backend must satisfy."""

    async def upload(
        self,
        bucket: str,
        filename: str,
        data: bytes,
        content_type: str = "",
    ) -> str:
        """Upload *data* and return the public URL."""
        ...

    async def get_url(self, bucket: str, filename: str) -> str:
        """Return the public URL for an already-uploaded file."""
        ...

    async def delete(self, bucket: str, filename: str) -> bool:
        """Delete a file.  Return ``True`` on success."""
        ...


# ---------------------------------------------------------------------------
# Local (development) adapter
# ---------------------------------------------------------------------------


class LocalStorageAdapter:
    """Write files to ``DATA_DIR/<bucket>/`` and serve via StaticFiles."""

    async def upload(
        self,
        bucket: str,
        filename: str,
        data: bytes,
        content_type: str = "",
    ) -> str:
        bucket_dir = DATA_DIR / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        file_path = bucket_dir / filename
        file_path.write_bytes(data)
        return f"/data/{bucket}/{filename}"

    async def get_url(self, bucket: str, filename: str) -> str:
        return f"/data/{bucket}/{filename}"

    async def delete(self, bucket: str, filename: str) -> bool:
        file_path = DATA_DIR / bucket / filename
        try:
            file_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Supabase Storage adapter
# ---------------------------------------------------------------------------


class SupabaseStorageAdapter:
    """Upload files to Supabase Storage and return public CDN URLs."""

    def __init__(self) -> None:
        self._url = os.environ.get("SUPABASE_URL", "")
        self._key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self._url or not self._key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set "
                "when STORAGE_BACKEND=supabase"
            )
        if _create_supabase_client is None:
            raise RuntimeError(
                "supabase Python SDK is not installed. "
                "Run: pip install supabase>=2.0.0"
            )
        self._client = _create_supabase_client(self._url, self._key)

    async def upload(
        self,
        bucket: str,
        filename: str,
        data: bytes,
        content_type: str = "",
    ) -> str:
        file_options = {}
        if content_type:
            file_options["content-type"] = content_type

        self._client.storage.from_(bucket).upload(
            path=filename,
            file=data,
            file_options=file_options or None,
        )
        return self.get_url_sync(bucket, filename)

    async def get_url(self, bucket: str, filename: str) -> str:
        return self.get_url_sync(bucket, filename)

    def get_url_sync(self, bucket: str, filename: str) -> str:
        return f"{self._url}/storage/v1/object/public/{bucket}/{filename}"

    async def delete(self, bucket: str, filename: str) -> bool:
        try:
            self._client.storage.from_(bucket).remove([filename])
            return True
        except Exception:
            logger.exception("Failed to delete %s/%s from Supabase Storage", bucket, filename)
            return False


# ---------------------------------------------------------------------------
# Factory + module-level singleton
# ---------------------------------------------------------------------------


def create_storage_adapter() -> StorageAdapter:
    """Instantiate the storage adapter based on ``STORAGE_BACKEND`` env var."""
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend == "supabase":
        logger.info("Using Supabase Storage adapter")
        return SupabaseStorageAdapter()
    logger.info("Using local disk storage adapter")
    return LocalStorageAdapter()


storage: StorageAdapter = create_storage_adapter()
