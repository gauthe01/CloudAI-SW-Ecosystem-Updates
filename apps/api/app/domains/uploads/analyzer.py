from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape as html_escape
from pathlib import Path
from xml.etree import ElementTree

from app.db.models.knowledge_upload import KnowledgeUploadCandidate
from app.db.models.partner import Partner

MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
MONTH_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")(?=[\s_\-.,'/]|\d)(?:[\s_\-.,'/]+(?:\d{1,2})[\s_\-.,'/]+|[\s_\-.,'/]+)"
    r"(20\d{2}|'\d{2})",
    re.IGNORECASE,
)
MONTH_DAY_YEAR_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")[\s_\-.,'/]+(?:\d{1,2})(?:st|nd|rd|th)?[\s_\-.,'/]+(20\d{2}|'\d{2})",
    re.IGNORECASE,
)
MONTH_APOSTROPHE_YEAR_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")'(\d{2})\b",
    re.IGNORECASE,
)
ISO_MONTH_RE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
SPLIT_RE = re.compile(r"(?:\n+|(?:^|\s)[\u2022\-*]\s+)")
MIN_MEANINGFUL_WORDS = 4
MAX_BLOCKS = 120
GENERIC_LABELS = {
    "document",
    "general",
    "notes",
    "partner",
    "partner update table",
    "source block",
    "status",
    "text",
    "update",
    "updates",
    "uploaded file",
}
GENERAL_TOPIC_LABELS = {
    "ecosystem projects",
    "marketing",
    "upcoming conferences and events",
    "upcoming pto",
    "pto",
}
PARTNER_TYPE_GROUP_LABELS = {
    "isv",
    "isvs",
    "osv",
    "osvs",
    "partner",
    "partners",
}
STATIC_PARTNER_ALIASES = {
    "amazon web services": "AWS",
    "aws": "AWS",
    "azure": "Microsoft",
    "canonical": "Canonical",
    "chain guard": "Chainguard",
    "chainguard": "Chainguard",
    "databricks": "Databricks",
    "docker": "Docker",
    "elastic": "Elastic",
    "github": "GitHub",
    "git hub": "GitHub",
    "google": "Google",
    "google cloud": "Google",
    "gcp": "Google",
    "meta": "Meta",
    "microsoft": "Microsoft",
    "mongodb": "MongoDB",
    "msft": "Microsoft",
    "red hat": "Red Hat",
    "redhat": "Red Hat",
    "redis": "Redis",
    "sap": "SAP HANA Cloud",
    "sap hana": "SAP HANA Cloud",
    "sap hana cloud": "SAP HANA Cloud",
    "salesforce": "Salesforce",
    "suse": "SUSE",
    "tinkerblox": "Tinkerblox",
    "cohere": "Cohere",
    "uber": "Uber",
    "vmware": "VMware",
}


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    section_label: str
    links: list[str]
    raw_label: str | None = None
    outline_path: tuple[str, ...] = ()
    block_type: str = "paragraph"
    partner_labels: tuple[str, ...] = ()


@dataclass
class DocxOutlineNode:
    text: str
    level: int
    num_id: str | None
    links: list[str]
    children: list[DocxOutlineNode]


@dataclass(frozen=True)
class PptxParagraph:
    text: str
    level: int
    links: tuple[str, ...] = ()


@dataclass
class PptxListNode:
    paragraph: PptxParagraph
    children: list[PptxListNode]


def build_knowledge_upload_candidates(
    *,
    file_path: Path,
    original_filename: str,
    upload_id,
    session_id=None,
    selected_partner_id,
    active_partners: list[Partner],
    description: str | None,
) -> list[KnowledgeUploadCandidate]:
    blocks = parse_file_blocks(file_path=file_path, original_filename=original_filename)
    document_cycle = infer_cycle_month(" ".join([original_filename, description or ""]))
    if document_cycle is None:
        document_cycle = first_cycle_from_blocks(blocks)
    candidates: list[KnowledgeUploadCandidate] = []
    seen_candidates: set[str] = set()
    now = datetime.now(UTC)

    for block in blocks[:MAX_BLOCKS]:
        summaries = (
            [block.text.strip()]
            if is_structured_update_block(block)
            else split_candidate_summaries(block.text)
        )
        for summary in summaries:
            normalized = normalize_text(summary).lower()
            if not is_structured_update_block(block) and not (
                is_meaningful_update(summary)
                or is_contextual_list_update(
                    block,
                    summary,
                )
            ):
                continue
            for explicit_partner_label in block.partner_labels or (None,):
                dedupe_key = "|".join(
                    [normalized, normalize_for_match(explicit_partner_label or "")]
                )
                if dedupe_key in seen_candidates:
                    continue
                seen_candidates.add(dedupe_key)

                raw_label = explicit_partner_label or block.raw_label
                if block.block_type == "docx_topic_update":
                    inferred_partner_id = None
                    partner_confidence = "topic"
                    detected_partner_label = None
                else:
                    (
                        inferred_partner_id,
                        partner_confidence,
                        detected_partner_label,
                    ) = infer_partner_id(
                        text=summary,
                        section_label=block.section_label,
                        raw_label=raw_label,
                        selected_partner_id=selected_partner_id,
                        active_partners=active_partners,
                    )
                summary = strip_redundant_leading_partner_label(
                    summary,
                    active_partners=active_partners,
                )
                cycle_month = candidate_cycle_month(
                    block=block,
                    summary=summary,
                    document_cycle=document_cycle,
                )
                review_status = (
                    "ready"
                    if inferred_partner_id is not None and cycle_month is not None
                    else "needs_mapping"
                )
                links = sorted(set([*block.links, *URL_RE.findall(summary)]))
                evidence = summary
                if links:
                    evidence = f"{summary}\nSource links: {', '.join(links)}"

                candidate_created_at = now + timedelta(microseconds=len(candidates))
                candidates.append(
                    KnowledgeUploadCandidate(
                        session_id=session_id,
                        upload_id=upload_id,
                        partner_id=inferred_partner_id,
                        cycle_month=cycle_month,
                        raw_label=detected_partner_label or raw_label or block.section_label,
                        summary=summary,
                        evidence_snippet=evidence,
                        section_label=block.section_label[:300] if block.section_label else None,
                        source_filename=original_filename,
                        source_location=source_location_for_block(block),
                        source_url=links[0] if links else None,
                        confidence=candidate_confidence(
                            partner_confidence=partner_confidence,
                            cycle_month=cycle_month,
                            document_cycle=document_cycle,
                        ),
                        review_status=review_status,
                        status="pending",
                        parser_notes=candidate_parser_notes(
                            review_status=review_status,
                            partner_id=inferred_partner_id,
                            cycle_month=cycle_month,
                            detected_partner_label=detected_partner_label,
                            block=block,
                        ),
                        created_at=candidate_created_at,
                        updated_at=candidate_created_at,
                    )
                )
    return candidates


def parse_file_blocks(*, file_path: Path, original_filename: str) -> list[ParsedBlock]:
    extension = file_path.suffix.lower()
    try:
        if extension == ".docx":
            return parse_docx_blocks(file_path)
        if extension == ".pptx":
            return parse_pptx_blocks(file_path)
        if extension == ".xlsx":
            return parse_xlsx_blocks(file_path)
        if extension in {".csv", ".json", ".log", ".md", ".txt"}:
            return parse_text_blocks(file_path)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError):
        return []
    return [
        ParsedBlock(
            text=f"{original_filename} was uploaded for admin review.",
            section_label="Uploaded file",
            links=[],
        )
    ]


def is_structured_update_block(block: ParsedBlock) -> bool:
    return block.block_type.startswith(
        (
            "docx_outline",
            "docx_topic",
            "pptx_google_workstream",
            "pptx_microsoft_workstream",
        )
    )


def parse_text_blocks(file_path: Path) -> list[ParsedBlock]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    return parse_plaintext_blocks(text)


def parse_plaintext_blocks(text: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    current_heading = "Text"
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        block_text = normalize_text("\n".join(buffer))
        if block_text:
            blocks.append(
                ParsedBlock(
                    text=block_text,
                    section_label=current_heading,
                    links=URL_RE.findall(block_text),
                    raw_label=current_heading,
                    outline_path=(current_heading,),
                )
            )
        buffer.clear()

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = normalize_text(raw_line)
        if not line:
            flush_buffer()
            continue
        if looks_like_heading(line):
            flush_buffer()
            current_heading = line
            continue
        buffer.append(line)
    flush_buffer()
    return blocks


def parse_docx_blocks(file_path: Path) -> list[ParsedBlock]:
    with zipfile.ZipFile(file_path) as package:
        rels = read_docx_relationships(package)
        root = ElementTree.fromstring(package.read("word/document.xml"))
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    blocks: list[ParsedBlock] = []
    current_heading = "Document"
    context_kind: str | None = None
    context_label: str | None = None
    context_base_level: int | None = None
    context_num_id: str | None = None
    context_partner_labels: tuple[str, ...] = ()
    active_partner_label: str | None = None
    active_partner_level: int | None = None
    update_level: int | None = None
    update_num_id: str | None = None
    current_update: DocxOutlineNode | None = None
    update_stack: list[DocxOutlineNode] = []

    def reset_context() -> None:
        nonlocal context_kind
        nonlocal context_label
        nonlocal context_base_level
        nonlocal context_num_id
        nonlocal context_partner_labels
        nonlocal active_partner_label
        nonlocal active_partner_level
        nonlocal update_level
        nonlocal update_num_id
        nonlocal current_update
        nonlocal update_stack
        flush_current_update()
        context_kind = None
        context_label = None
        context_base_level = None
        context_num_id = None
        context_partner_labels = ()
        active_partner_label = None
        active_partner_level = None
        update_level = None
        update_num_id = None
        current_update = None
        update_stack = []

    def flush_current_update() -> None:
        nonlocal current_update
        nonlocal update_stack
        if current_update is None:
            return
        labels = current_partner_labels(
            context_kind=context_kind,
            context_partner_labels=context_partner_labels,
            active_partner_label=active_partner_label,
        )
        block_type = "docx_topic_update" if context_kind == "topic" else "docx_outline_update"
        section_parts = [
            current_heading,
            context_label,
            active_partner_label,
        ]
        section_label = " > ".join(dedupe_preserve_order(section_parts))
        blocks.append(
            ParsedBlock(
                text=render_outline_html(current_update),
                section_label=section_label or current_heading,
                links=collect_outline_links(current_update),
                raw_label=context_label if context_kind == "topic" else active_partner_label,
                outline_path=tuple(
                    dedupe_preserve_order(
                        [
                            current_heading,
                            context_label,
                            active_partner_label,
                            current_update.text,
                        ]
                    )
                ),
                block_type=block_type,
                partner_labels=labels,
            )
        )
        current_update = None
        update_stack = []

    def start_update(
        *,
        text: str,
        level: int,
        num_id: str | None,
        links: list[str],
    ) -> None:
        nonlocal current_update
        nonlocal update_stack
        flush_current_update()
        current_update = DocxOutlineNode(
            text=text,
            level=level,
            num_id=num_id,
            links=links,
            children=[],
        )
        update_stack = [current_update]

    def append_descendant(
        *,
        text: str,
        level: int,
        num_id: str | None,
        links: list[str],
    ) -> None:
        if current_update is None:
            start_update(text=text, level=level, num_id=num_id, links=links)
            return
        node = DocxOutlineNode(
            text=text,
            level=level,
            num_id=num_id,
            links=links,
            children=[],
        )
        parent = current_update
        for candidate in reversed(update_stack):
            if candidate.level < level:
                parent = candidate
                break
        parent.children.append(node)
        update_stack[:] = [item for item in update_stack if item.level < level]
        update_stack.append(node)

    def append_continuation(text: str, links: list[str]) -> None:
        target = update_stack[-1] if update_stack else current_update
        if target is None:
            return
        target.text = normalize_text(f"{target.text} {text}")
        target.links = sorted(set([*target.links, *links]))

    def is_nested_under_context(level: int) -> bool:
        return context_base_level is not None and level > context_base_level

    body = root.find("w:body", ns)
    if body is None:
        return blocks
    for element in body:
        if element.tag == f"{{{ns['w']}}}p":
            text = docx_paragraph_text(element, ns)
            if not text:
                continue
            style_value = docx_paragraph_style(element, ns)
            num_id, list_level = docx_numbering(element, ns)
            is_list_item = list_level is not None
            links = docx_links(element, rels, ns)
            if (
                not is_list_item
                and (style_value.lower().startswith("heading") or looks_like_heading(text))
                and len(text) <= 120
            ):
                reset_context()
                current_heading = text
                if is_general_topic_label(text):
                    context_kind = "topic"
                    context_label = clean_topic_label(text)
                    context_base_level = None
                    context_num_id = None
                continue

            if is_list_item:
                level = list_level if list_level is not None else 0
                group_labels = extract_partner_group_labels(text)
                is_category_label = is_partner_type_category_label(text)
                is_topic_label = is_general_topic_label(text)
                is_partner_label = is_partner_context_label(text)

                if group_labels:
                    reset_context()
                    context_kind = "fanout"
                    context_label = text
                    context_base_level = level
                    context_num_id = num_id
                    context_partner_labels = group_labels
                    continue

                if is_category_label and not group_labels:
                    reset_context()
                    context_kind = "category"
                    context_label = text
                    context_base_level = level
                    context_num_id = num_id
                    continue

                if is_topic_label and not (
                    context_kind == "partner" and is_nested_under_context(level)
                ):
                    reset_context()
                    context_kind = "topic"
                    context_label = clean_topic_label(text)
                    context_base_level = level
                    context_num_id = num_id
                    continue

                if should_close_context(
                    context_kind=context_kind,
                    context_base_level=context_base_level,
                    context_num_id=context_num_id,
                    update_level=update_level,
                    update_num_id=update_num_id,
                    level=level,
                    num_id=num_id,
                ):
                    reset_context()

                if context_kind is None and is_partner_label:
                    context_kind = "partner"
                    context_label = split_partner_label(text)
                    context_base_level = level
                    context_num_id = num_id
                    active_partner_label = split_partner_label(text)
                    active_partner_level = level
                    continue

                if context_kind == "category":
                    if active_partner_level is not None and level <= active_partner_level:
                        flush_current_update()
                        active_partner_label = None
                        active_partner_level = None
                        update_level = None
                        update_num_id = None
                    leading_partner = extract_leading_partner_label(text)
                    if leading_partner and level > (context_base_level or -1):
                        inline_text = strip_leading_partner_label(text)
                        active_partner_label = leading_partner
                        active_partner_level = level
                        start_update(
                            text=inline_text or text,
                            level=level,
                            num_id=num_id,
                            links=links,
                        )
                        update_level = level
                        update_num_id = num_id
                        continue
                    if is_partner_label and level > (context_base_level or -1):
                        flush_current_update()
                        active_partner_label = split_partner_label(text)
                        active_partner_level = level
                        update_level = None
                        update_num_id = None
                        continue

                if context_kind in {"partner", "category", "fanout", "topic"}:
                    if update_level is None:
                        update_level = level
                        update_num_id = num_id
                    if level <= update_level:
                        if (
                            context_kind == "category"
                            and active_partner_label is None
                            and is_partner_label
                        ):
                            active_partner_label = split_partner_label(text)
                            active_partner_level = level
                            update_level = None
                            update_num_id = None
                            continue
                        start_update(text=text, level=level, num_id=num_id, links=links)
                    else:
                        append_descendant(text=text, level=level, num_id=num_id, links=links)
                    continue

                if is_partner_label:
                    context_kind = "partner"
                    context_label = split_partner_label(text)
                    context_base_level = level
                    context_num_id = num_id
                    active_partner_label = split_partner_label(text)
                    active_partner_level = level
                    continue

                blocks.append(
                    ParsedBlock(
                        text=text,
                        section_label=current_heading,
                        links=links,
                        raw_label=current_heading,
                        outline_path=(current_heading, text),
                        block_type="list_item",
                    )
                )
                continue

            if current_update is not None:
                append_continuation(text, links)
                continue

            blocks.append(
                ParsedBlock(
                    text=text,
                    section_label=current_heading,
                    links=links,
                    raw_label=current_heading,
                    outline_path=(current_heading, text),
                )
            )
        elif element.tag == f"{{{ns['w']}}}tbl":
            reset_context()
            blocks.extend(docx_table_blocks(element, rels, ns, current_heading))
    reset_context()
    return blocks


def docx_paragraph_text(paragraph: ElementTree.Element, ns: dict[str, str]) -> str:
    return normalize_text("".join(node.text or "" for node in paragraph.findall(".//w:t", ns)))


def docx_paragraph_style(paragraph: ElementTree.Element, ns: dict[str, str]) -> str:
    style = paragraph.find(".//w:pStyle", ns)
    if style is None:
        return ""
    return style.attrib.get(f"{{{ns['w']}}}val", "")


def docx_numbering(
    paragraph: ElementTree.Element,
    ns: dict[str, str],
) -> tuple[str | None, int | None]:
    num_id = paragraph.find(".//w:numId", ns)
    level = paragraph.find(".//w:ilvl", ns)
    num_value = num_id.attrib.get(f"{{{ns['w']}}}val", "") if num_id is not None else ""
    level_value = level.attrib.get(f"{{{ns['w']}}}val", "") if level is not None else ""
    try:
        parsed_level = int(level_value) if level_value else None
    except ValueError:
        parsed_level = None
    return num_value or None, parsed_level


def docx_links(
    element: ElementTree.Element,
    rels: dict[str, str],
    ns: dict[str, str],
) -> list[str]:
    links: list[str] = []
    for hyperlink in element.findall(".//w:hyperlink", ns):
        rel_id = hyperlink.attrib.get(f"{{{ns['r']}}}id")
        if rel_id and rel_id in rels:
            links.append(rels[rel_id])
    text = docx_paragraph_text(element, ns)
    links.extend(URL_RE.findall(text))
    return sorted(set(links))


def docx_table_blocks(
    table: ElementTree.Element,
    rels: dict[str, str],
    ns: dict[str, str],
    current_heading: str,
) -> list[ParsedBlock]:
    rows: list[list[str]] = []
    row_links: list[list[str]] = []
    for row in table.findall("w:tr", ns):
        values: list[str] = []
        links: list[str] = []
        for cell in row.findall("w:tc", ns):
            cell_paragraphs = [
                docx_paragraph_text(paragraph, ns) for paragraph in cell.findall(".//w:p", ns)
            ]
            cell_text = normalize_text(
                "\n".join(paragraph for paragraph in cell_paragraphs if paragraph)
            )
            values.append(cell_text)
            links.extend(docx_links(cell, rels, ns))
        if any(values):
            rows.append(values)
            row_links.append(sorted(set(links)))
    return table_rows_to_blocks(rows, row_links, current_heading)


def read_docx_relationships(package: zipfile.ZipFile) -> dict[str, str]:
    if "word/_rels/document.xml.rels" not in package.namelist():
        return {}
    root = ElementTree.fromstring(package.read("word/_rels/document.xml.rels"))
    rels = {}
    for relationship in root:
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if rel_id and target and target.startswith(("http://", "https://", "mailto:")):
            rels[rel_id] = target
    return rels


def parse_pptx_blocks(file_path: Path) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    with zipfile.ZipFile(file_path) as package:
        slide_names = sorted(
            (
                name
                for name in package.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ),
            key=pptx_slide_sort_key,
        )
        google_workstream_blocks = parse_google_workstream_pptx_blocks(package, slide_names)
        if google_workstream_blocks:
            return google_workstream_blocks
        microsoft_workstream_blocks = parse_microsoft_workstream_pptx_blocks(
            package,
            slide_names,
        )
        if microsoft_workstream_blocks:
            return microsoft_workstream_blocks
        for index, slide_name in enumerate(slide_names, start=1):
            root = ElementTree.fromstring(package.read(slide_name))
            texts = [
                normalize_text(node.text or "")
                for node in root.iter()
                if node.tag.endswith("}t") and normalize_text(node.text or "")
            ]
            for block in paragraph_blocks("\n".join(texts)):
                blocks.append(
                    ParsedBlock(
                        text=block,
                        section_label=f"Slide {index}",
                        links=URL_RE.findall(block),
                    )
                )
    return blocks


def pptx_slide_sort_key(slide_name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", slide_name)
    return int(match.group(1)) if match else 0


def parse_google_workstream_pptx_blocks(
    package: zipfile.ZipFile,
    slide_names: list[str],
) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    for slide_index, slide_name in enumerate(slide_names, start=1):
        rels = read_pptx_slide_relationships(package, slide_name)
        root = ElementTree.fromstring(package.read(slide_name))
        for table in root.findall(".//a:tbl", ns):
            rows = table.findall("./a:tr", ns)
            if not rows:
                continue
            header = [
                normalize_for_match(
                    " ".join(paragraph.text for paragraph in pptx_cell_paragraphs(cell, rels, ns))
                )
                for cell in rows[0].findall("./a:tc", ns)
            ]
            if not is_google_workstream_table_header(header):
                continue
            for row in rows[1:]:
                cells = row.findall("./a:tc", ns)
                if len(cells) < 3:
                    continue
                workstream_paragraphs = pptx_cell_paragraphs(cells[0], rels, ns)
                target_paragraphs = pptx_cell_paragraphs(cells[1], rels, ns)
                update_paragraphs = pptx_cell_paragraphs(cells[2], rels, ns)
                workstream_name = first_non_metadata_pptx_paragraph(workstream_paragraphs)
                if not workstream_name or not update_paragraphs:
                    continue
                links = sorted(
                    {
                        link
                        for paragraph in [*target_paragraphs, *update_paragraphs]
                        for link in paragraph.links
                    }
                )
                blocks.append(
                    ParsedBlock(
                        text=render_google_workstream_summary(
                            workstream_name=workstream_name,
                            targets=target_paragraphs,
                            updates=update_paragraphs,
                        ),
                        section_label=f"Slide {slide_index} > {workstream_name}",
                        links=links,
                        raw_label="Google",
                        outline_path=(
                            f"Slide {slide_index}",
                            workstream_name,
                            "Google workstream update",
                        ),
                        block_type="pptx_google_workstream_update",
                        partner_labels=("Google",),
                    )
                )
    return blocks


def is_google_workstream_table_header(header: list[str]) -> bool:
    if len(header) < 3:
        return False
    return (
        "workstream" in header[0]
        and ("cy2026 targets" in header[1] or "cy 2026 targets" in header[1])
        and ("recent updates" in header[2] or header[2] == "updates")
    )


def parse_microsoft_workstream_pptx_blocks(
    package: zipfile.ZipFile,
    slide_names: list[str],
) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    for slide_index, slide_name in enumerate(slide_names, start=1):
        rels = read_pptx_slide_relationships(package, slide_name)
        root = ElementTree.fromstring(package.read(slide_name))
        for table in root.findall(".//a:tbl", ns):
            rows = table.findall("./a:tr", ns)
            if not rows:
                continue
            header = [
                normalize_for_match(
                    " ".join(paragraph.text for paragraph in pptx_cell_paragraphs(cell, rels, ns))
                )
                for cell in rows[0].findall("./a:tc", ns)
            ]
            if not is_microsoft_workstream_table_header(header):
                continue
            current_workstream: str | None = None
            for row in rows[1:]:
                cells = row.findall("./a:tc", ns)
                if len(cells) < 6:
                    continue
                workstream_paragraphs = pptx_cell_paragraphs(cells[0], rels, ns)
                row_workstream = first_non_metadata_pptx_paragraph(workstream_paragraphs)
                if row_workstream:
                    current_workstream = row_workstream
                if not current_workstream:
                    continue
                workload_paragraphs = pptx_cell_paragraphs(cells[1], rels, ns)
                objective_paragraphs = pptx_cell_paragraphs(cells[2], rels, ns)
                update_paragraphs = pptx_cell_paragraphs(cells[3], rels, ns)
                go_green_paragraphs = pptx_cell_paragraphs(cells[4], rels, ns)
                if not update_paragraphs:
                    continue
                current_status = pptx_rag_status(cells[5], ns)
                for split_workload, split_objective in split_microsoft_row_fields(
                    workload_paragraphs,
                    objective_paragraphs,
                ):
                    links = sorted(
                        {
                            link
                            for paragraph in [
                                *split_workload,
                                *split_objective,
                                *update_paragraphs,
                                *go_green_paragraphs,
                            ]
                            for link in paragraph.links
                        }
                    )
                    workload_label = first_non_metadata_pptx_paragraph(split_workload)
                    blocks.append(
                        ParsedBlock(
                            text=render_microsoft_workstream_summary(
                                workstream_name=current_workstream,
                                workload=split_workload,
                                objective=split_objective,
                                updates=update_paragraphs,
                                go_green=go_green_paragraphs,
                                current_status=current_status,
                            ),
                            section_label=" > ".join(
                                part
                                for part in [
                                    f"Slide {slide_index}",
                                    current_workstream,
                                    workload_label,
                                ]
                                if part
                            ),
                            links=links,
                            raw_label="Microsoft",
                            outline_path=tuple(
                                part
                                for part in [
                                    f"Slide {slide_index}",
                                    current_workstream,
                                    workload_label,
                                    "Microsoft workstream update",
                                ]
                                if part
                            ),
                            block_type="pptx_microsoft_workstream_update",
                            partner_labels=("Microsoft",),
                        )
                    )
    return blocks


def is_microsoft_workstream_table_header(header: list[str]) -> bool:
    if len(header) < 6:
        return False
    return (
        "workstream" in header[0]
        and "workload" in header[1]
        and "objective" in header[2]
        and "updates" in header[3]
        and "go to green" in header[4]
        and header[5] == "rag"
    )


def split_microsoft_row_fields(
    workload: list[PptxParagraph],
    objective: list[PptxParagraph],
) -> list[tuple[list[PptxParagraph], list[PptxParagraph]]]:
    if len(workload) > 1 and len(workload) == len(objective):
        return [
            ([workload_item], [objective_item])
            for workload_item, objective_item in zip(workload, objective, strict=True)
        ]
    return [(workload, objective)]


def pptx_rag_status(cell: ElementTree.Element, ns: dict[str, str]) -> str | None:
    tcpr = cell.find("./a:tcPr", ns)
    if tcpr is None:
        return None
    solid_fill = tcpr.find("./a:solidFill", ns)
    if solid_fill is None:
        return None
    rgb = solid_fill.find("./a:srgbClr", ns)
    if rgb is not None:
        return rag_status_from_color(rgb.attrib.get("val"))
    scheme = solid_fill.find("./a:schemeClr", ns)
    if scheme is not None:
        return rag_status_from_scheme_color(scheme.attrib.get("val"))
    return None


def rag_status_from_color(value: str | None) -> str | None:
    color = (value or "").upper()
    if color in {"00B050", "70AD47", "92D050"}:
        return "Green"
    if color in {"FFC000", "FCAB2A", "FFB833", "F4B183"}:
        return "Amber"
    if color in {"FF0000", "C00000"}:
        return "Red"
    if color in {"A5A5A5", "6F6F6F", "BFBFBF"}:
        return "Gray"
    return None


def rag_status_from_scheme_color(value: str | None) -> str | None:
    scheme = (value or "").lower()
    if scheme == "accent3":
        return "Amber"
    if scheme == "accent6":
        return "Gray"
    return None


def read_pptx_slide_relationships(
    package: zipfile.ZipFile,
    slide_name: str,
) -> dict[str, str]:
    relationship_name = slide_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    if relationship_name not in package.namelist():
        return {}
    root = ElementTree.fromstring(package.read(relationship_name))
    rels: dict[str, str] = {}
    for relationship in root:
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if rel_id and target and target.startswith(("http://", "https://", "mailto:")):
            rels[rel_id] = target
    return rels


def pptx_cell_paragraphs(
    cell: ElementTree.Element,
    rels: dict[str, str],
    ns: dict[str, str],
) -> list[PptxParagraph]:
    paragraphs: list[PptxParagraph] = []
    for paragraph in cell.findall(".//a:p", ns):
        runs: list[str] = []
        links: list[str] = []
        for run in paragraph.findall("./a:r", ns):
            text = "".join(node.text or "" for node in run.findall("./a:t", ns))
            if not normalize_text(text):
                continue
            runs.append(text)
            hyperlink = run.find(".//a:hlinkClick", ns)
            rel_id = hyperlink.attrib.get(f"{{{ns['r']}}}id") if hyperlink is not None else None
            if rel_id and rel_id in rels:
                links.append(rels[rel_id])
        text = normalize_text("".join(runs))
        if not text:
            continue
        paragraph_props = paragraph.find("./a:pPr", ns)
        level_value = paragraph_props.attrib.get("lvl") if paragraph_props is not None else None
        try:
            level = int(level_value) if level_value is not None else 0
        except ValueError:
            level = 0
        paragraphs.append(PptxParagraph(text=text, level=level, links=tuple(sorted(set(links)))))
    return paragraphs


def first_non_metadata_pptx_paragraph(paragraphs: list[PptxParagraph]) -> str | None:
    for paragraph in paragraphs:
        text = normalize_text(paragraph.text).strip(" :")
        if not text or normalize_for_match(text).startswith("leads"):
            continue
        if text.startswith("(") and text.endswith(")"):
            continue
        return text
    return None


def render_google_workstream_summary(
    *,
    workstream_name: str,
    targets: list[PptxParagraph],
    updates: list[PptxParagraph],
) -> str:
    return "".join(
        [
            f"<p><strong>{html_escape(workstream_name)} work stream</strong></p>",
            "<p><strong>CY2026 Targets:</strong></p>",
            render_pptx_paragraph_list(targets),
            "<p><strong>Recent Updates:</strong></p>",
            render_pptx_paragraph_list(updates),
        ]
    )


def render_microsoft_workstream_summary(
    *,
    workstream_name: str,
    workload: list[PptxParagraph],
    objective: list[PptxParagraph],
    updates: list[PptxParagraph],
    go_green: list[PptxParagraph],
    current_status: str | None,
) -> str:
    parts = [
        f"<p><strong>{html_escape(workstream_name)} Work Stream</strong></p>",
        render_pptx_field("Workload", workload),
        render_pptx_field("Objective", objective),
        "<p><strong>Updates &amp; Blockers:</strong></p>",
        render_pptx_paragraph_list(updates),
    ]
    if go_green:
        parts.append(render_pptx_field("Go to Green Action", go_green))
    if current_status:
        parts.append(f"<p><strong>Current Status:</strong> {html_escape(current_status)}</p>")
    return "".join(parts)


def render_pptx_field(label: str, paragraphs: list[PptxParagraph]) -> str:
    items = [
        paragraph
        for paragraph in paragraphs
        if paragraph.text and not normalize_for_match(paragraph.text).startswith("leads")
    ]
    if not items:
        return ""
    escaped_label = html_escape(label)
    if len(items) == 1:
        value = render_linked_text(items[0].text, list(items[0].links))
        return f"<p><strong>{escaped_label}:</strong> {value}</p>"
    return f"<p><strong>{escaped_label}:</strong></p>{render_pptx_paragraph_list(items)}"


def render_pptx_paragraph_list(paragraphs: list[PptxParagraph]) -> str:
    items = [
        paragraph
        for paragraph in paragraphs
        if paragraph.text and not normalize_for_match(paragraph.text).startswith("leads")
    ]
    if not items:
        return "<ul></ul>"
    base_level = min(paragraph.level for paragraph in items)
    roots: list[PptxListNode] = []
    stack: list[tuple[int, PptxListNode]] = []
    for paragraph in items:
        level = max(paragraph.level - base_level, 0)
        node = PptxListNode(paragraph=paragraph, children=[])
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)
        stack.append((level, node))
    return render_pptx_list_nodes(roots)


def render_pptx_list_nodes(nodes: list[PptxListNode]) -> str:
    items = []
    for node in nodes:
        body = render_linked_text(node.paragraph.text, list(node.paragraph.links))
        if node.children:
            body += render_pptx_list_nodes(node.children)
        items.append(f"<li>{body}</li>")
    return f"<ul>{''.join(items)}</ul>"


def parse_xlsx_blocks(file_path: Path) -> list[ParsedBlock]:
    rows_by_sheet: list[tuple[str, list[list[str]]]] = []
    with zipfile.ZipFile(file_path) as package:
        shared_strings = read_shared_strings(package)
        sheet_names = sorted(
            name
            for name in package.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for sheet_index, sheet_name in enumerate(sheet_names, start=1):
            root = ElementTree.fromstring(package.read(sheet_name))
            rows = root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")
            parsed_rows: list[list[str]] = []
            for row in rows:
                values = []
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    values.append(read_xlsx_cell_text(cell, shared_strings))
                if any(values):
                    parsed_rows.append(values)
            rows_by_sheet.append((f"Sheet {sheet_index}", parsed_rows))
    blocks: list[ParsedBlock] = []
    for sheet_label, rows in rows_by_sheet:
        sheet_blocks = table_rows_to_blocks(rows, [[] for _ in rows], sheet_label)
        blocks.extend(sheet_blocks)
        if not sheet_blocks:
            for index, values in enumerate(rows, start=1):
                text = normalize_text(" | ".join(value for value in values if value))
                if text:
                    section_label = f"{sheet_label} row {index}".strip()
                    blocks.append(
                        ParsedBlock(
                            text=text,
                            section_label=section_label,
                            links=URL_RE.findall(text),
                            raw_label=sheet_label,
                            outline_path=(section_label,),
                        )
                    )
    return blocks


def table_rows_to_blocks(
    rows: list[list[str]],
    row_links: list[list[str]],
    current_heading: str,
) -> list[ParsedBlock]:
    if not rows:
        return []
    header = [normalize_for_match(value) for value in rows[0]]
    partner_index = find_first_header_index(header, {"company", "partner", "customer"})
    update_index = find_first_header_index(header, {"update", "updates", "summary", "status"})
    category_index = find_first_header_index(header, {"category", "partner category", "workstream"})
    blocks: list[ParsedBlock] = []
    if partner_index is not None and update_index is not None:
        for index, values in enumerate(rows[1:], start=2):
            partner_label = value_at(values, partner_index)
            update_text = value_at(values, update_index)
            if not update_text:
                continue
            category = (
                value_at(values, category_index) if category_index is not None else current_heading
            )
            links = row_links[index - 1] if index - 1 < len(row_links) else []
            blocks.append(
                ParsedBlock(
                    text=update_text,
                    section_label=category or current_heading,
                    links=sorted(set([*links, *URL_RE.findall(update_text)])),
                    raw_label=split_partner_label(partner_label),
                    outline_path=tuple(
                        item
                        for item in [current_heading, category, partner_label, update_text[:120]]
                        if item
                    ),
                    block_type="table_row",
                )
            )
        return blocks
    for index, values in enumerate(rows, start=1):
        text = normalize_text(" | ".join(value for value in values if value))
        if text:
            blocks.append(
                ParsedBlock(
                    text=text,
                    section_label=f"{current_heading} row {index}",
                    links=URL_RE.findall(text),
                    raw_label=current_heading,
                    outline_path=(current_heading, f"row {index}"),
                    block_type="table_row",
                )
            )
    return blocks


def find_first_header_index(header: list[str], names: set[str]) -> int | None:
    for index, value in enumerate(header):
        if value in names:
            return index
    return None


def value_at(values: list[str], index: int | None) -> str:
    if index is None or index >= len(values):
        return ""
    return normalize_text(values[index])


def split_partner_label(label: str) -> str:
    clean = normalize_text(label)
    parts = re.split(r"\s+[–—-]\s+", clean, maxsplit=1)
    return normalize_text(parts[0]).strip(" :") if parts else clean.strip(" :")


def extract_partner_group_labels(label: str) -> tuple[str, ...]:
    clean = normalize_text(label).strip(" :-")
    prefix, _, remainder = clean.partition("(")
    if remainder and prefix:
        if normalize_for_match(prefix) not in PARTNER_TYPE_GROUP_LABELS:
            return ()
        inner = remainder.rsplit(")", maxsplit=1)[0]
    else:
        inner = clean
    has_group_separator = bool(re.search(r"[,/&]|\band\b", inner, re.IGNORECASE))
    if not has_group_separator:
        return ()
    labels = [
        split_partner_label(part)
        for part in re.split(r"\s*(?:,|/|&|\band\b)\s*", inner, flags=re.IGNORECASE)
    ]
    filtered = [
        label
        for label in labels
        if label and not is_general_topic_label(label) and canonical_known_partner_label(label)
    ]
    if len(filtered) < 2:
        return ()
    if not remainder and len(filtered) != len([label for label in labels if label]):
        return ()
    return tuple(dict.fromkeys(filtered))


def is_partner_type_category_label(label: str) -> bool:
    clean = normalize_text(label).strip(" :-")
    prefix = clean.partition("(")[0].strip(" :-")
    return normalize_for_match(prefix) in PARTNER_TYPE_GROUP_LABELS


def should_close_context(
    *,
    context_kind: str | None,
    context_base_level: int | None,
    context_num_id: str | None,
    update_level: int | None,
    update_num_id: str | None,
    level: int,
    num_id: str | None,
) -> bool:
    if context_kind is None or context_base_level is None:
        return False
    if context_kind == "fanout" and update_level is None:
        return False
    if context_kind == "fanout":
        return num_id == context_num_id and level <= context_base_level
    if context_kind == "topic":
        if update_level is None:
            return False
        if context_num_id is None:
            return False
        return num_id == context_num_id and level <= context_base_level
    if update_num_id and num_id and num_id != update_num_id and level <= context_base_level:
        return True
    return level <= context_base_level


def current_partner_labels(
    *,
    context_kind: str | None,
    context_partner_labels: tuple[str, ...],
    active_partner_label: str | None,
) -> tuple[str, ...]:
    if context_kind == "topic":
        return ()
    if context_partner_labels:
        return context_partner_labels
    if active_partner_label:
        return (active_partner_label,)
    return ()


def clean_topic_label(text: str) -> str:
    return normalize_text(text).strip(" :")


def strip_leading_partner_label(text: str) -> str:
    clean = normalize_text(text)
    match = re.match(r"^[A-Z][A-Za-z0-9&.+ /-]{1,60}:\s*(.+)$", clean)
    return normalize_text(match.group(1)) if match else clean


def strip_redundant_leading_partner_label(text: str, *, active_partners: list[Partner]) -> str:
    clean = normalize_text(text)
    match = re.match(r"^([A-Z][A-Za-z0-9&.+ /-]{1,60}):\s*(.+)$", clean)
    if not match:
        return text
    label = split_partner_label(match.group(1))
    lookup = build_partner_lookup(active_partners)
    if match_partner_label(label, lookup) is None and canonical_known_partner_label(label) is None:
        return text
    return normalize_text(match.group(2))


def collect_outline_links(node: DocxOutlineNode) -> list[str]:
    links = list(node.links)
    for child in node.children:
        links.extend(collect_outline_links(child))
    return sorted(set(links))


def render_outline_html(node: DocxOutlineNode) -> str:
    parts = [f"<p>{render_linked_text(node.text, node.links)}</p>"]
    if node.children:
        parts.append(render_outline_children_html(node.children))
    return "".join(parts)


def render_outline_children_html(nodes: list[DocxOutlineNode]) -> str:
    items = []
    for node in nodes:
        body = render_linked_text(node.text, node.links)
        if node.children:
            body += render_outline_children_html(node.children)
        items.append(f"<li>{body}</li>")
    return f"<ul>{''.join(items)}</ul>"


def render_linked_text(text: str, links: list[str]) -> str:
    escaped = html_escape(text)
    if not links:
        return escaped
    href = html_escape(links[0], quote=True)
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{escaped}</a>'


def is_partner_context_label(label: str) -> bool:
    clean = normalize_text(label).strip()
    normalized = normalize_for_match(clean.rstrip(":"))
    if not normalized or normalized in GENERIC_LABELS or normalized in GENERAL_TOPIC_LABELS:
        return False
    if clean.endswith(":"):
        return True
    if canonical_known_partner_label(clean):
        return True
    return False


def is_general_topic_label(label: str | None) -> bool:
    clean = normalize_for_match((label or "").strip(" :-"))
    return clean in GENERAL_TOPIC_LABELS


def compose_nested_list_summary(
    *,
    text: str,
    parents: list[str],
    partner_context: str | None,
    partner_group_label: str | None,
    general_topic_context: str | None,
) -> str:
    context_labels = {
        normalize_for_match(value)
        for value in [partner_context, partner_group_label, general_topic_context]
        if value
    }
    nested_parents = [
        parent
        for parent in parents
        if normalize_for_match(parent) not in context_labels
        and not is_partner_context_label(parent)
        and (not is_general_topic_label(parent) or partner_context or partner_group_label)
    ]
    if not nested_parents:
        return text
    parent = nested_parents[-1]
    if normalize_for_match(parent) in normalize_for_match(text):
        return text
    return f"{parent}:\n  - {text}"


def dedupe_preserve_order(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = normalize_text(value or "")
        key = normalize_for_match(clean)
        if not clean or not key or key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def read_shared_strings(package: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in package.namelist():
        return []
    root = ElementTree.fromstring(package.read("xl/sharedStrings.xml"))
    strings = []
    for item in root:
        text = normalize_text(
            " ".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
        )
        strings.append(text)
    return strings


def read_xlsx_cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    value = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    if value is None or value.text is None:
        inline_text = " ".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
        return normalize_text(inline_text)
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(value.text)]
        except (IndexError, ValueError):
            return normalize_text(value.text)
    return normalize_text(value.text)


def paragraph_blocks(text: str) -> list[str]:
    return [
        normalize_text(block)
        for block in re.split(r"\n{2,}", text.replace("\r\n", "\n"))
        if normalize_text(block)
    ]


def split_candidate_summaries(text: str) -> list[str]:
    if "\n  - " in text:
        return [text.strip()]
    pieces = [normalize_text(piece) for piece in SPLIT_RE.split(text) if normalize_text(piece)]
    if len(pieces) > 1:
        return pieces
    if len(text) <= 700:
        return [normalize_text(text)]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [normalize_text(sentence) for sentence in sentences if normalize_text(sentence)]


def is_meaningful_update(text: str) -> bool:
    normalized = normalize_text(text)
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if len(words) < MIN_MEANINGFUL_WORDS:
        return False
    lowered = normalized.lower().strip(" :-")
    if is_document_metadata_line(lowered):
        return False
    noise = {
        "partner",
        "status",
        "notes",
        "owner",
        "date",
        "action",
        "summary",
        "table of contents",
    }
    if lowered in noise:
        return False
    return bool(
        re.search(
            r"\b("
            r"approved|available|blocked|blocker|confirmed|created|delivered|dependency|"
            r"due|expected|in progress|launched|milestone|next step|priority|published|"
            r"review|risk|scheduled|shared|target|timeline|validated|will|needs"
            r")\b",
            normalized,
            re.IGNORECASE,
        )
        or any(char.isdigit() for char in normalized)
    )


def is_contextual_list_update(block: ParsedBlock, text: str) -> bool:
    if block.block_type != "list_item":
        return False
    if is_general_topic_label(block.raw_label):
        return False
    words = re.findall(r"[A-Za-z0-9]+", normalize_text(text))
    return len(words) >= 3


def is_document_metadata_line(text: str) -> bool:
    clean = normalize_text(text).lower().strip(" :-")
    title_prefix = r"(software ecosystem\s+)?monthly status report\s*[–—-]?\s*"
    if re.fullmatch(title_prefix + r"[a-z]{3,9}\s+\d{1,2}?\s*20\d{2}", clean):
        return True
    if re.fullmatch(title_prefix + r"[a-z]{3,9}\s+20\d{2}", clean):
        return True
    return False


def infer_partner_id(
    *,
    text: str,
    section_label: str | None,
    raw_label: str | None,
    selected_partner_id,
    active_partners: list[Partner],
) -> tuple[object | None, str, str | None]:
    if selected_partner_id is not None:
        selected_partner = next(
            (partner for partner in active_partners if partner.partner_id == selected_partner_id),
            None,
        )
        return selected_partner_id, "selected", selected_partner.name if selected_partner else None

    lookup = build_partner_lookup(active_partners)
    label_candidates = [
        raw_label,
        extract_leading_partner_label(text),
        section_label,
    ]
    for label in label_candidates:
        detected_label = clean_candidate_label(label)
        if not detected_label:
            continue
        match = match_partner_label(detected_label, lookup)
        if match is not None:
            return match.partner_id, "matched_label", match.name
        known_label = canonical_known_partner_label(detected_label)
        if known_label:
            return None, "detected_unconfigured", known_label

    normalized_text = f" {normalize_for_match(text)} "
    text_matches = [
        partner
        for alias, partner in lookup.items()
        if len(alias) >= 3 and f" {alias} " in normalized_text
    ]
    unique_matches = unique_partners(text_matches)
    if len(unique_matches) == 1:
        return unique_matches[0].partner_id, "matched_text", unique_matches[0].name

    detected_label = first_known_partner_in_text(text)
    if detected_label:
        return None, "detected_unconfigured", detected_label
    return None, "missing", None


def infer_cycle_month(text: str) -> date | None:
    apostrophe_match = MONTH_APOSTROPHE_YEAR_RE.search(text or "")
    if apostrophe_match:
        year = int(f"20{apostrophe_match.group(2)}")
        month_key = apostrophe_match.group(1).lower()
        return date(year, MONTH_NAMES[month_key], 1)
    match = MONTH_DAY_YEAR_RE.search(text or "") or MONTH_RE.search(text or "")
    if not match:
        iso_match = ISO_MONTH_RE.search(text or "")
        if iso_match:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), 1)
        return None
    year_text = match.group(2)
    year = int(year_text) if len(year_text) == 4 else int(f"20{year_text.lstrip("'")}")
    month_key = match.group(1).lower()
    return date(year, MONTH_NAMES[month_key], 1)


def candidate_parser_notes(
    *,
    review_status: str,
    partner_id,
    cycle_month: date | None,
    detected_partner_label: str | None,
    block: ParsedBlock,
) -> str | None:
    notes: list[str] = []
    if detected_partner_label and partner_id is None:
        notes.append(
            f"Detected partner label: {detected_partner_label}. "
            "Map to an active partner before staging."
        )
    elif partner_id is None:
        notes.append("Needs partner mapping before staging.")
    if cycle_month is None:
        notes.append("Needs reporting month before staging.")
    if block.block_type == "table_row":
        notes.append("Parsed from partner update table.")
    if review_status == "ready" and notes == ["Parsed from partner update table."]:
        return notes[0]
    if review_status == "ready":
        return None
    return " ".join(notes) if notes else None


def missing_mapping_note(*, partner_id, cycle_month: date | None) -> str:
    missing = []
    if partner_id is None:
        missing.append("partner")
    if cycle_month is None:
        missing.append("cycle month")
    return f"Needs mapping for {', '.join(missing)} before staging."


def candidate_confidence(
    *,
    partner_confidence: str,
    cycle_month: date | None,
    document_cycle: date | None,
) -> str:
    if partner_confidence == "selected":
        return "high" if cycle_month else "medium"
    if partner_confidence in {"matched_label", "matched_text"} and cycle_month:
        return "high" if document_cycle and cycle_month == document_cycle else "medium"
    if partner_confidence == "detected_unconfigured":
        return "medium"
    return "low"


def candidate_cycle_month(
    *,
    block: ParsedBlock,
    summary: str,
    document_cycle: date | None,
) -> date | None:
    if block.block_type.startswith("pptx_google_workstream"):
        return (
            document_cycle or infer_cycle_month(block.section_label) or infer_cycle_month(summary)
        )
    if block.block_type.startswith("pptx_microsoft_workstream"):
        return (
            document_cycle or infer_cycle_month(block.section_label) or infer_cycle_month(summary)
        )
    return infer_cycle_month(summary) or infer_cycle_month(block.section_label) or document_cycle


def first_cycle_from_blocks(blocks: list[ParsedBlock]) -> date | None:
    for block in blocks[:12]:
        cycle = infer_cycle_month(" ".join([block.section_label, block.text]))
        if cycle:
            return cycle
    return None


def source_location_for_block(block: ParsedBlock) -> str:
    if block.outline_path:
        return " > ".join(part for part in block.outline_path if part)[:500]
    return (block.section_label or block.block_type or "Uploaded file")[:500]


def looks_like_heading(text: str) -> bool:
    clean = normalize_text(text).strip(" :-")
    if not clean or len(clean) > 90:
        return False
    if clean.lower() in GENERIC_LABELS:
        return True
    if canonical_known_partner_label(clean):
        return True
    words = clean.split()
    if len(words) <= 5 and not re.search(r"[.!?]", clean):
        return not re.search(
            r"\b(approved|available|blocked|confirmed|created|delivered|expected|planned|published|review|will)\b",
            clean,
            re.IGNORECASE,
        )
    return False


def build_partner_lookup(active_partners: list[Partner]) -> dict[str, Partner]:
    lookup: dict[str, Partner] = {}
    active_by_name = {normalize_for_match(partner.name): partner for partner in active_partners}
    for partner in active_partners:
        keys = {normalize_for_match(partner.name)}
        canonical = canonical_known_partner_label(partner.name)
        if canonical:
            keys.add(normalize_for_match(canonical))
        for alias, target in STATIC_PARTNER_ALIASES.items():
            target_key = normalize_for_match(target)
            if target_key == normalize_for_match(partner.name) or target_key in active_by_name:
                mapped = active_by_name.get(target_key)
                if mapped and mapped.partner_id == partner.partner_id:
                    keys.add(normalize_for_match(alias))
        for key in keys:
            if key:
                lookup[key] = partner
    return lookup


def match_partner_label(label: str, lookup: dict[str, Partner]) -> Partner | None:
    key = normalize_for_match(label)
    if not key or key in GENERIC_LABELS:
        return None
    if key in lookup:
        return lookup[key]
    for alias, partner in sorted(lookup.items(), key=lambda item: len(item[0]), reverse=True):
        if len(alias) < 3:
            continue
        if alias in key or key in alias:
            return partner
    return None


def unique_partners(partners: list[Partner]) -> list[Partner]:
    seen = set()
    unique: list[Partner] = []
    for partner in partners:
        if partner.partner_id in seen:
            continue
        seen.add(partner.partner_id)
        unique.append(partner)
    return unique


def clean_candidate_label(label: str | None) -> str | None:
    clean = normalize_text(label or "").strip(" :-")
    if not clean or normalize_for_match(clean) in GENERIC_LABELS:
        return None
    return split_partner_label(clean)


def canonical_known_partner_label(label: str | None) -> str | None:
    key = normalize_for_match(label or "")
    if not key:
        return None
    if key in STATIC_PARTNER_ALIASES:
        return STATIC_PARTNER_ALIASES[key]
    return None


def extract_leading_partner_label(text: str) -> str | None:
    clean = normalize_text(text)
    leading_verbs = (
        "is|has|had|will|was|were|published|created|developed|confirmed|plans|planned|expects"
    )
    match = re.match(
        rf"^([A-Z][A-Za-z0-9&.+ /-]{{1,60}}?)(?:\s+(?:{leading_verbs})\b|:)",
        clean,
    )
    if not match:
        return None
    return split_partner_label(match.group(1))


def first_known_partner_in_text(text: str) -> str | None:
    normalized = f" {normalize_for_match(text)} "
    for alias, canonical in sorted(
        STATIC_PARTNER_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if len(alias) >= 3 and f" {alias} " in normalized:
            return canonical
    return None


def normalize_text(text: str) -> str:
    text = (text or "").replace("\x00", "")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text.strip())


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
