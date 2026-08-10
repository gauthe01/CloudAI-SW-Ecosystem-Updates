import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.db.models.knowledge_upload import KnowledgeUploadProcessingStatus

CHUNK_SIZE_BYTES = 1024 * 1024
PREVIEW_LIMIT_BYTES = 12_000
PREVIEW_LIMIT_CHARS = 4_000

ALLOWED_UPLOAD_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".json",
    ".log",
    ".md",
    ".pdf",
    ".ppt",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsx",
}

TEXT_PREVIEW_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".txt",
}


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    storage_backend: str
    storage_key: str
    content_type: str | None
    file_size_bytes: int
    checksum_sha256: str
    processing_status: KnowledgeUploadProcessingStatus
    text_preview: str | None


async def store_upload_file(
    *,
    upload_id: uuid.UUID,
    file: UploadFile,
    settings: Settings,
) -> StoredUpload:
    original_filename = clean_filename(file.filename)
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    if settings.file_storage_backend != "local":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Only local upload storage is implemented in this build.",
        )

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    storage_key = build_storage_key(upload_id, extension)
    destination = Path(settings.local_upload_storage_dir) / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)

    checksum = hashlib.sha256()
    file_size = 0
    preview_bytes = bytearray()

    with destination.open("wb") as output:
        while chunk := await file.read(CHUNK_SIZE_BYTES):
            file_size += len(chunk)
            if file_size > max_size_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds {settings.max_upload_size_mb} MB limit.",
                )
            checksum.update(chunk)
            output.write(chunk)
            if extension in TEXT_PREVIEW_EXTENSIONS and len(preview_bytes) < PREVIEW_LIMIT_BYTES:
                preview_bytes.extend(chunk[: PREVIEW_LIMIT_BYTES - len(preview_bytes)])

    if file_size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    text_preview = extract_text_preview(preview_bytes) if preview_bytes else None
    processing_status = (
        KnowledgeUploadProcessingStatus.parsed
        if text_preview
        else KnowledgeUploadProcessingStatus.stored
    )

    return StoredUpload(
        original_filename=original_filename,
        storage_backend=settings.file_storage_backend,
        storage_key=storage_key,
        content_type=file.content_type,
        file_size_bytes=file_size,
        checksum_sha256=checksum.hexdigest(),
        processing_status=processing_status,
        text_preview=text_preview,
    )


def clean_filename(filename: str | None) -> str:
    cleaned = Path(filename or "").name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid filename is required.",
        )
    return cleaned


def build_storage_key(upload_id: uuid.UUID, extension: str) -> str:
    upload_id_text = str(upload_id)
    return f"uploads/{upload_id_text[:2]}/{upload_id_text}{extension}"


def extract_text_preview(preview_bytes: bytearray) -> str | None:
    try:
        decoded = bytes(preview_bytes).decode("utf-8")
    except UnicodeDecodeError:
        return None
    cleaned = decoded.replace("\x00", "").strip()
    if not cleaned:
        return None
    return cleaned[:PREVIEW_LIMIT_CHARS]
