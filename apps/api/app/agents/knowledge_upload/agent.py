import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.agents.rulebooks import Rulebook, RulebookLoader
from app.db.models.knowledge_upload import KnowledgeUploadCandidate
from app.db.models.partner import Partner
from app.domains.uploads.analyzer import (
    build_knowledge_upload_candidates,
    infer_cycle_month,
    parse_file_blocks,
)

ADMIN_KNOWLEDGE_UPLOAD_RULEBOOK = "admin_knowledge_upload"


@dataclass(frozen=True)
class KnowledgeUploadAgentInput:
    file_path: Path
    original_filename: str
    upload_id: object
    session_id: object
    selected_partner_id: object | None
    active_partners: list[Partner]
    description: str | None
    checksum_sha256: str


@dataclass(frozen=True)
class KnowledgeUploadAgentResult:
    candidates: list[KnowledgeUploadCandidate]
    document_type: str
    inferred_cycle: date | None
    cycle_confidence: str
    warnings: list[str]
    rulebook: Rulebook
    input_fingerprint: str


class KnowledgeUploadAgent:
    """Rulebook-traced deterministic admin knowledge upload agent."""

    def __init__(self, *, rulebook_loader: RulebookLoader | None = None) -> None:
        self.rulebook_loader = rulebook_loader or RulebookLoader()

    def analyze(self, agent_input: KnowledgeUploadAgentInput) -> KnowledgeUploadAgentResult:
        rulebook = self.rulebook_loader.load(ADMIN_KNOWLEDGE_UPLOAD_RULEBOOK)
        blocks = parse_file_blocks(
            file_path=agent_input.file_path,
            original_filename=agent_input.original_filename,
        )
        document_context = " ".join([agent_input.original_filename, agent_input.description or ""])
        document_cycle = infer_cycle_month(document_context) or first_cycle_from_blocks_text(blocks)
        candidates = build_knowledge_upload_candidates(
            file_path=agent_input.file_path,
            original_filename=agent_input.original_filename,
            upload_id=agent_input.upload_id,
            session_id=agent_input.session_id,
            selected_partner_id=agent_input.selected_partner_id,
            active_partners=agent_input.active_partners,
            description=agent_input.description,
        )
        warnings: list[str] = []
        if not blocks:
            warnings.append(f"{agent_input.original_filename}: no readable content was found.")
        if not candidates:
            warnings.append(
                f"{agent_input.original_filename}: no meaningful partner updates were extracted."
            )
        if any(candidate.review_status == "needs_mapping" for candidate in candidates):
            warnings.append(
                f"{agent_input.original_filename}: some updates need partner or cycle mapping."
            )

        return KnowledgeUploadAgentResult(
            candidates=candidates,
            document_type=document_type_for_filename(agent_input.original_filename),
            inferred_cycle=document_cycle,
            cycle_confidence="high" if document_cycle else "low",
            warnings=warnings,
            rulebook=rulebook,
            input_fingerprint=knowledge_upload_input_fingerprint(agent_input),
        )


def document_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    normalized = filename.lower()
    if suffix == ".docx":
        return "Software Ecosystem Monthly Status Report"
    if suffix == ".pptx":
        if "google" in normalized and "workstream" in normalized:
            return "Google Software Workstreams Deck"
        if "microsoft" in normalized and "workstream" in normalized:
            return "Microsoft Software Workstreams Deck"
        return "Partner Highlights Deck"
    if suffix == ".xlsx":
        return "Partner Tracker Spreadsheet"
    return "Historical Partner Knowledge Document"


def first_cycle_from_blocks_text(blocks) -> date | None:
    for block in blocks[:12]:
        cycle = infer_cycle_month(" ".join([block.section_label, block.text]))
        if cycle:
            return cycle
    return None


def knowledge_upload_input_fingerprint(agent_input: KnowledgeUploadAgentInput) -> str:
    payload = "|".join(
        [
            agent_input.original_filename,
            agent_input.checksum_sha256,
            str(agent_input.selected_partner_id or ""),
            agent_input.description or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
