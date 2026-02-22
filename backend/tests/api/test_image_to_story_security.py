from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from backend.src.api.routes import image_to_story as route


def test_validate_child_id_rejects_path_traversal() -> None:
    with pytest.raises(HTTPException):
        route.validate_child_id("../../tmp/pwn")

    with pytest.raises(HTTPException):
        route.validate_child_id("child/../evil")


def test_validate_child_id_accepts_safe_identifier() -> None:
    assert route.validate_child_id("child_001-safe") == "child_001-safe"


@pytest.mark.asyncio
async def test_save_upload_file_stays_within_upload_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(route, "UPLOAD_DIR", tmp_path)

    upload = UploadFile(filename="drawing.png", file=BytesIO(b"small image bytes"))
    saved_path = await route.save_upload_file(upload, "child_001")

    assert saved_path.exists()
    assert saved_path.parent.name == "child_001"
    assert tmp_path.resolve() in saved_path.resolve().parents


@pytest.mark.asyncio
async def test_save_upload_file_rejects_escaped_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(route, "UPLOAD_DIR", tmp_path)

    upload = UploadFile(filename="drawing.png", file=BytesIO(b"small image bytes"))
    with pytest.raises(HTTPException):
        await route.save_upload_file(upload, "../../tmp/pwn")
