import hashlib
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


class S3Client(Protocol):
    def upload_file(
        self, filename: str, bucket: str, key: str, ExtraArgs: dict | None = None
    ) -> None: ...

    def download_file(self, bucket: str, key: str, filename: str) -> None: ...


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
    storage_prefix: str = "uploads",
) -> StoredUpload:
    original_filename = clean_filename(file.filename)
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    backend = normalized_storage_backend(settings)
    if backend not in {"local", "s3"}:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Unsupported upload storage backend: {settings.file_storage_backend}.",
        )
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    storage_key = build_storage_key(upload_id, extension, storage_prefix=storage_prefix)
    checksum = hashlib.sha256()
    file_size = 0
    preview_bytes = bytearray()

    if backend == "local":
        destination = Path(settings.local_upload_storage_dir) / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as output:
                while chunk := await file.read(CHUNK_SIZE_BYTES):
                    file_size = update_upload_digest_and_preview(
                        chunk=chunk,
                        file_size=file_size,
                        max_size_bytes=max_size_bytes,
                        checksum=checksum,
                        preview_bytes=preview_bytes,
                        extension=extension,
                    )
                    output.write(chunk)
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
    else:
        temp_path = write_upload_to_temp_path(extension)
        try:
            with temp_path.open("wb") as output:
                while chunk := await file.read(CHUNK_SIZE_BYTES):
                    file_size = update_upload_digest_and_preview(
                        chunk=chunk,
                        file_size=file_size,
                        max_size_bytes=max_size_bytes,
                        checksum=checksum,
                        preview_bytes=preview_bytes,
                        extension=extension,
                    )
                    output.write(chunk)
            if file_size > 0:
                upload_temp_file_to_s3(
                    temp_path=temp_path,
                    storage_key=storage_key,
                    content_type=file.content_type,
                    settings=settings,
                )
        except HTTPException:
            raise
        finally:
            temp_path.unlink(missing_ok=True)

    if file_size == 0:
        if backend == "local":
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
        storage_backend=backend,
        storage_key=storage_key,
        content_type=file.content_type,
        file_size_bytes=file_size,
        checksum_sha256=checksum.hexdigest(),
        processing_status=processing_status,
        text_preview=text_preview,
    )


def update_upload_digest_and_preview(
    *,
    chunk: bytes,
    file_size: int,
    max_size_bytes: int,
    checksum,
    preview_bytes: bytearray,
    extension: str,
) -> int:
    file_size += len(chunk)
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {max_size_bytes // (1024 * 1024)} MB limit.",
        )
    checksum.update(chunk)
    if extension in TEXT_PREVIEW_EXTENSIONS and len(preview_bytes) < PREVIEW_LIMIT_BYTES:
        preview_bytes.extend(chunk[: PREVIEW_LIMIT_BYTES - len(preview_bytes)])
    return file_size


def clean_filename(filename: str | None) -> str:
    cleaned = Path(filename or "").name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid filename is required.",
        )
    return cleaned


def build_storage_key(
    upload_id: uuid.UUID,
    extension: str,
    *,
    storage_prefix: str = "uploads",
) -> str:
    upload_id_text = str(upload_id)
    normalized_prefix = clean_storage_prefix(storage_prefix)
    return f"{normalized_prefix}/{upload_id_text[:2]}/{upload_id_text}{extension}"


def clean_storage_prefix(storage_prefix: str) -> str:
    parts = [
        part.strip().strip("/")
        for part in storage_prefix.split("/")
        if part.strip().strip("/")
    ]
    if not parts:
        return "uploads"
    return "/".join(parts)


def local_storage_path(settings: Settings, storage_key: str) -> Path:
    return Path(settings.local_upload_storage_dir) / storage_key


@contextmanager
def readable_upload_file(
    *,
    settings: Settings,
    storage_backend: str,
    storage_key: str,
    original_filename: str,
) -> Iterator[Path]:
    backend = storage_backend.strip().lower()
    if backend == "local":
        yield local_storage_path(settings, storage_key)
        return
    if backend != "s3":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Unsupported upload storage backend: {storage_backend}.",
        )
    extension = Path(original_filename).suffix.lower()
    temp_path = write_upload_to_temp_path(extension)
    try:
        download_s3_object_to_temp_file(
            temp_path=temp_path,
            storage_key=storage_key,
            settings=settings,
        )
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


def normalized_storage_backend(settings: Settings) -> str:
    return settings.file_storage_backend.strip().lower()


def write_upload_to_temp_path(extension: str) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
    path = Path(handle.name)
    handle.close()
    return path


def upload_temp_file_to_s3(
    *,
    temp_path: Path,
    storage_key: str,
    content_type: str | None,
    settings: Settings,
) -> None:
    extra_args = {"ContentType": content_type} if content_type else None
    try:
        get_s3_client(settings).upload_file(
            str(temp_path),
            settings.s3_bucket,
            storage_key,
            ExtraArgs=extra_args,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not store upload in S3.",
        ) from exc


def download_s3_object_to_temp_file(
    *,
    temp_path: Path,
    storage_key: str,
    settings: Settings,
) -> None:
    try:
        get_s3_client(settings).download_file(settings.s3_bucket, storage_key, str(temp_path))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not read upload from S3.",
        ) from exc


def get_s3_client(settings: Settings) -> S3Client:
    if not settings.s3_bucket.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3_BUCKET must be configured for S3 upload storage.",
        )
    try:
        import boto3
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 storage requires boto3 to be installed.",
        ) from exc
    return boto3.client("s3", region_name=settings.aws_region)


def extract_text_preview(preview_bytes: bytearray) -> str | None:
    try:
        decoded = bytes(preview_bytes).decode("utf-8")
    except UnicodeDecodeError:
        return None
    cleaned = decoded.replace("\x00", "").strip()
    if not cleaned:
        return None
    return cleaned[:PREVIEW_LIMIT_CHARS]
