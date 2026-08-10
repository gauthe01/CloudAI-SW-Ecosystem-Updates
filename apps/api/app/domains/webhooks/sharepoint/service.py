import base64
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.connected_source import (
    ConnectedSource,
    ConnectedSourceSharePointFile,
    ConnectedSourceStatus,
)
from app.db.models.integration import Integration, IntegrationStatus, IntegrationType
from app.db.models.partner_update import (
    PartnerUpdate,
    PartnerUpdateSourceType,
    PartnerUpdateStatus,
)
from app.db.models.source_event import SourceEvent, SourcePayload
from app.db.models.storage_object import StorageObject, StorageObjectSourceKind
from app.domains.admin.integrations.secrets import get_integration_secret_value
from app.domains.source_events.schemas import SourceEventIngestRequest
from app.domains.source_events.service import SourceEventQueueService

PREVIEW_LIMIT_CHARS = 4_000
TEXT_FILE_EXTENSIONS = {".csv", ".json", ".log", ".md", ".txt"}
SUPPORTED_SHAREPOINT_EXTENSIONS = {".docx", ".pdf", ".pptx", ".xlsx"} | TEXT_FILE_EXTENSIONS
MEANINGFUL_DOCUMENT_KEYWORDS = {
    "blocked",
    "blocker",
    "decision",
    "delay",
    "issue",
    "milestone",
    "priority",
    "release",
    "risk",
    "status",
    "update",
}


class SharePointWebhookService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def handle_event_payload(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        client_state = await self._get_enabled_client_state()
        notifications = payload.get("value") if isinstance(payload.get("value"), list) else []
        if not notifications:
            return {
                "status": "ignored",
                "reason": "SharePoint payload did not include notifications.",
            }

        results = []
        for notification in notifications:
            if not isinstance(notification, dict):
                continue
            results.append(await self._handle_notification(notification, client_state))

        processed_count = sum(1 for item in results if item.get("status") == "processed")
        duplicate_count = sum(1 for item in results if item.get("status") == "duplicate")
        ignored_count = sum(1 for item in results if item.get("status") == "ignored")
        return {
            "status": "processed" if processed_count else "ignored",
            "processed_count": processed_count,
            "duplicate_count": duplicate_count,
            "ignored_count": ignored_count,
            "results": results,
        }

    async def _handle_notification(
        self,
        notification: dict[str, Any],
        expected_client_state: str,
    ) -> dict[str, Any]:
        if clean_optional(notification.get("clientState")) != expected_client_state:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid SharePoint client state.",
            )

        file_url = sharepoint_file_url(notification)
        if file_url is None:
            return {
                "status": "ignored",
                "reason": "SharePoint notification did not include a file URL.",
            }

        source_context = await self._load_active_sharepoint_source(file_url)
        if source_context is None:
            return {
                "status": "ignored",
                "reason": "No active SharePoint connected source is mapped to this file.",
            }
        connected_source, sharepoint_file = source_context

        event_timestamp = datetime.now(UTC)
        event_id = sharepoint_event_id(notification, file_url)
        queued = await SourceEventQueueService(self.db).enqueue_event(
            SourceEventIngestRequest(
                connected_source_id=connected_source.connected_source_id,
                external_event_id=event_id,
                idempotency_key=f"sharepoint:{event_id}",
                source_url=sharepoint_file.file_url,
                source_event_timestamp=event_timestamp,
                technical_metadata=sharepoint_technical_metadata(notification, file_url),
                raw_payload_json=None,
                raw_text_encrypted=None,
                retention_policy="technical_metadata_only",
            )
        )

        if queued.is_duplicate:
            return {
                "status": "duplicate",
                "source_event_id": str(queued.source_event.source_event_id),
            }

        storage_object = await self._store_file_copy_if_available(
            notification=notification,
            connected_source=connected_source,
            sharepoint_file=sharepoint_file,
        )
        if storage_object is not None:
            await self._link_storage_object(
                queued.source_event.source_event_id,
                storage_object.storage_object_id,
            )

        processing = await SourceEventQueueService(self.db).process_event(
            queued.source_event.source_event_id,
            handler=SharePointSourceEventProcessor(
                db=self.db,
                sharepoint_file=sharepoint_file,
                storage_object=storage_object,
            ).process,
        )
        return {
            "status": "processed",
            "source_event_id": str(queued.source_event.source_event_id),
            "processing_status": processing.status.value if processing.status is not None else None,
            "message": processing.message,
            "storage_object_id": (
                str(storage_object.storage_object_id) if storage_object is not None else None
            ),
        }

    async def _get_enabled_client_state(self) -> str:
        result = await self.db.execute(
            select(Integration).where(
                Integration.integration_type == IntegrationType.sharepoint.value
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None or integration.status != IntegrationStatus.enabled.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SharePoint global integration is not enabled.",
            )

        client_state = await get_integration_secret_value(
            self.db,
            self.settings,
            integration_type=IntegrationType.sharepoint,
            secret_name="client_state",
        )
        if client_state is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SharePoint client state is not configured.",
            )
        return client_state

    async def _load_active_sharepoint_source(
        self,
        file_url: str,
    ) -> tuple[ConnectedSource, ConnectedSourceSharePointFile] | None:
        result = await self.db.execute(
            select(ConnectedSource, ConnectedSourceSharePointFile)
            .join(
                ConnectedSourceSharePointFile,
                ConnectedSourceSharePointFile.connected_source_id
                == ConnectedSource.connected_source_id,
            )
            .where(func.lower(ConnectedSourceSharePointFile.file_url) == file_url.lower())
            .where(ConnectedSource.status == ConnectedSourceStatus.active.value)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def _store_file_copy_if_available(
        self,
        *,
        notification: dict[str, Any],
        connected_source: ConnectedSource,
        sharepoint_file: ConnectedSourceSharePointFile,
    ) -> StorageObject | None:
        downloaded_file = notification.get("downloadedFile")
        if not isinstance(downloaded_file, dict):
            return None

        original_filename = (
            clean_optional(downloaded_file.get("name"))
            or sharepoint_file.file_name
            or file_name_from_url(sharepoint_file.file_url)
            or "sharepoint-file"
        )
        extension = Path(original_filename).suffix.lower()
        if extension and extension not in SUPPORTED_SHAREPOINT_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported SharePoint file type.",
            )

        encoded_content = clean_optional(downloaded_file.get("contentBase64"))
        if encoded_content is None:
            return None
        try:
            file_bytes = base64.b64decode(encoded_content, validate=True)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SharePoint downloaded file content.",
            ) from exc
        if not file_bytes:
            return None

        if self.settings.file_storage_backend != "local":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Only local SharePoint file storage is implemented in this build.",
            )

        storage_object_id = uuid.uuid4()
        storage_key = sharepoint_storage_key(storage_object_id, extension)
        destination = Path(self.settings.local_upload_storage_dir) / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_bytes)

        text_preview = clean_optional(downloaded_file.get("extractedText"))
        if text_preview is None and extension in TEXT_FILE_EXTENSIONS:
            text_preview = decode_text_preview(file_bytes)

        storage_object = StorageObject(
            storage_object_id=storage_object_id,
            partner_id=connected_source.partner_id,
            connected_source_id=connected_source.connected_source_id,
            source_kind=StorageObjectSourceKind.sharepoint_file_copy.value,
            original_filename=original_filename,
            content_type=clean_optional(downloaded_file.get("contentType")),
            file_size_bytes=len(file_bytes),
            checksum_sha256=hashlib.sha256(file_bytes).hexdigest(),
            storage_backend=self.settings.file_storage_backend,
            storage_key=storage_key,
            text_preview=text_preview[:PREVIEW_LIMIT_CHARS] if text_preview else None,
            created_at=datetime.now(UTC),
        )
        self.db.add(storage_object)
        await self.db.flush()
        return storage_object

    async def _link_storage_object(
        self,
        source_event_id: uuid.UUID,
        storage_object_id: uuid.UUID,
    ) -> None:
        result = await self.db.execute(
            select(SourcePayload).where(SourcePayload.source_event_id == source_event_id)
        )
        source_payload = result.scalar_one_or_none()
        if source_payload is not None:
            source_payload.storage_object_id = storage_object_id
            await self.db.flush()


class SharePointSourceEventProcessor:
    def __init__(
        self,
        *,
        db: AsyncSession,
        sharepoint_file: ConnectedSourceSharePointFile,
        storage_object: StorageObject | None,
    ) -> None:
        self.db = db
        self.sharepoint_file = sharepoint_file
        self.storage_object = storage_object

    async def process(
        self,
        source_event: SourceEvent,
        _payload: SourcePayload | None,
    ) -> dict[str, Any]:
        text = clean_optional(self.storage_object.text_preview if self.storage_object else None)
        if text is None:
            return {
                "pending_updates_created": 0,
                "reason": "SharePoint file copy is not available for extraction yet.",
            }
        if not is_meaningful_sharepoint_text(text):
            return {
                "pending_updates_created": 0,
                "reason": "SharePoint document did not meet the developer-owned rule.",
            }

        existing_update = await self._find_existing_update(source_event.idempotency_key)
        if existing_update is not None:
            return {
                "pending_updates_created": 0,
                "reason": "Pending update already exists for this SharePoint event.",
                "update_id": str(existing_update.update_id),
            }

        file_name = self.sharepoint_file.file_name or file_name_from_url(
            self.sharepoint_file.file_url
        )
        update = PartnerUpdate(
            partner_id=source_event.partner_id,
            cycle_month=source_event.source_event_timestamp.date().replace(day=1),
            title=sharepoint_update_title(file_name, text),
            summary=sharepoint_update_summary(file_name, text),
            source_type=PartnerUpdateSourceType.sharepoint.value,
            source_label=file_name or "SharePoint file",
            source_url=source_event.source_url,
            source_event_key=source_event.idempotency_key,
            connected_source_id=source_event.connected_source_id,
            source_event_id=source_event.source_event_id,
            status=PartnerUpdateStatus.pending.value,
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.db.add(update)
        await self.db.flush()
        return {
            "pending_updates_created": 1,
            "update_id": str(update.update_id),
        }

    async def _find_existing_update(self, source_event_key: str) -> PartnerUpdate | None:
        result = await self.db.execute(
            select(PartnerUpdate).where(PartnerUpdate.source_event_key == source_event_key)
        )
        return result.scalar_one_or_none()


def sharepoint_file_url(notification: dict[str, Any]) -> str | None:
    resource_data = (
        notification.get("resourceData")
        if isinstance(notification.get("resourceData"), dict)
        else {}
    )
    downloaded_file = (
        notification.get("downloadedFile")
        if isinstance(notification.get("downloadedFile"), dict)
        else {}
    )
    return (
        clean_optional(resource_data.get("webUrl"))
        or clean_optional(notification.get("webUrl"))
        or clean_optional(notification.get("fileUrl"))
        or clean_optional(downloaded_file.get("webUrl"))
    )


def sharepoint_event_id(notification: dict[str, Any], file_url: str) -> str:
    resource_data = (
        notification.get("resourceData")
        if isinstance(notification.get("resourceData"), dict)
        else {}
    )
    components = [
        clean_optional(notification.get("subscriptionId")),
        clean_optional(notification.get("resource")),
        clean_optional(resource_data.get("id")),
        clean_optional(notification.get("changeType")),
        file_checksum(notification),
    ]
    raw_identity = (
        "|".join(component or "none" for component in components)
        if any(components)
        else file_url
    )
    return hashlib.sha256(raw_identity.encode()).hexdigest()


def sharepoint_technical_metadata(notification: dict[str, Any], file_url: str) -> dict[str, Any]:
    resource_data = (
        notification.get("resourceData")
        if isinstance(notification.get("resourceData"), dict)
        else {}
    )
    return {
        "subscription_id": clean_optional(notification.get("subscriptionId")),
        "change_type": clean_optional(notification.get("changeType")),
        "resource": clean_optional(notification.get("resource")),
        "resource_id": clean_optional(resource_data.get("id")),
        "resource_odata_type": clean_optional(resource_data.get("@odata.type")),
        "tenant_id": clean_optional(notification.get("tenantId")),
        "file_url_hash": hashlib.sha256(file_url.lower().encode()).hexdigest(),
    }


def file_checksum(notification: dict[str, Any]) -> str | None:
    downloaded_file = (
        notification.get("downloadedFile")
        if isinstance(notification.get("downloadedFile"), dict)
        else {}
    )
    encoded_content = clean_optional(downloaded_file.get("contentBase64"))
    if encoded_content is None:
        return None
    return hashlib.sha256(encoded_content.encode()).hexdigest()


def is_meaningful_sharepoint_text(text: str) -> bool:
    if len(text) >= 40:
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in MEANINGFUL_DOCUMENT_KEYWORDS)


def sharepoint_update_title(file_name: str | None, text: str) -> str:
    label = file_name or "SharePoint file"
    trimmed = " ".join(text.split())[:160].rstrip()
    if len(text) > 160:
        trimmed = f"{trimmed}..."
    return f"SharePoint update from {label}: {trimmed}"[:300]


def sharepoint_update_summary(file_name: str | None, text: str) -> str:
    label = file_name or "SharePoint file"
    trimmed = " ".join(text.split())[:900].rstrip()
    if len(text) > 900:
        trimmed = f"{trimmed}..."
    return f"{label} was updated and surfaced a potential partner update: {trimmed}"


def sharepoint_storage_key(storage_object_id: uuid.UUID, extension: str) -> str:
    object_id_text = str(storage_object_id)
    suffix = extension or ".bin"
    return f"sharepoint/{object_id_text[:2]}/{object_id_text}{suffix}"


def file_name_from_url(file_url: str) -> str | None:
    path = Path(file_url.split("?", 1)[0])
    name = path.name.strip()
    return name or None


def decode_text_preview(file_bytes: bytes) -> str | None:
    try:
        decoded = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    cleaned = decoded.replace("\x00", "").strip()
    return cleaned[:PREVIEW_LIMIT_CHARS] if cleaned else None


def clean_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
