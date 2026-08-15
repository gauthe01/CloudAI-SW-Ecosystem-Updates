from pathlib import Path

import pytest

from app.agents.rulebooks import RULEBOOK_MANIFEST, RulebookLoader
from app.agents.rulebooks.loader import (
    RulebookFormatError,
    RulebookNotFoundError,
    hash_rulebook_content,
)

PRODUCTION_SOURCE_EVENT_RULEBOOKS = {
    "source_event.confluence",
    "source_event.github",
    "source_event.jira",
    "source_event.sharepoint",
    "source_event.slack",
}

ACTIVE_ADMIN_RULEBOOKS = {
    "admin_knowledge_upload",
    "admin_knowledge_upload.google_workstreams_ppt",
    "admin_knowledge_upload.microsoft_workstreams_ppt",
}


def test_registered_rulebooks_load_from_default_directory() -> None:
    loader = RulebookLoader()

    assert loader.list_rulebooks() == sorted(RULEBOOK_MANIFEST)

    for name in loader.list_rulebooks():
        rulebook = loader.load(name)

        assert rulebook.name == name
        if name in PRODUCTION_SOURCE_EVENT_RULEBOOKS:
            assert rulebook.status == "production"
            assert rulebook.version.startswith("production-")
            assert "Do not invent facts" in rulebook.body
            assert "Preserve relevant quantitative information" in rulebook.body
            assert "Preserve relevant links" in rulebook.body
            assert "own timestamp determines the update month" in rulebook.body
            assert "Extract only net-new facts" in rulebook.body
            assert "same-month facts" in rulebook.body
            assert "Acknowledgements" in rulebook.body
            assert "Do not join update clauses with semicolons" in rulebook.body
            assert "All generated updates enter Pending Updates first" in rulebook.body
            if name == "source_event.jira":
                assert (
                    "Do not ignore a Jira comment solely because it is "
                    "phrased as a request" in rulebook.body
                )
        elif name in ACTIVE_ADMIN_RULEBOOKS:
            assert rulebook.status == "active"
            assert rulebook.version
            assert "invent" in rulebook.body.lower()
        else:
            assert rulebook.status == "placeholder"
            assert rulebook.version.startswith("placeholder-")
        assert len(rulebook.content_hash) == 64
        assert rulebook.trace_version == f"{rulebook.version}:{rulebook.content_hash[:12]}"
        assert "## Purpose" in rulebook.body
        if name not in {
            "admin_knowledge_upload.google_workstreams_ppt",
            "admin_knowledge_upload.microsoft_workstreams_ppt",
        }:
            assert "## Input Contract" in rulebook.body
        assert "## Output Contract" in rulebook.body


def test_rulebook_loader_rejects_unregistered_names() -> None:
    loader = RulebookLoader()

    with pytest.raises(RulebookNotFoundError, match="not registered"):
        loader.load("source_event.unknown")


def test_rulebook_loader_rejects_path_traversal_names() -> None:
    loader = RulebookLoader()

    with pytest.raises(RulebookFormatError, match="Invalid rulebook name"):
        loader.load("../source_event.jira")


def test_rulebook_loader_reports_registered_missing_file(tmp_path: Path) -> None:
    loader = RulebookLoader(rulebook_dir=tmp_path)

    with pytest.raises(RulebookNotFoundError, match="registered but not found"):
        loader.load("source_event.jira")


def test_rulebook_loader_rejects_metadata_name_mismatch(tmp_path: Path) -> None:
    write_rulebook(
        tmp_path / "source_event.jira.md",
        name="source_event.slack",
    )
    loader = RulebookLoader(rulebook_dir=tmp_path)

    with pytest.raises(RulebookFormatError, match="does not match"):
        loader.load("source_event.jira")


def test_rulebook_loader_rejects_missing_required_sections(tmp_path: Path) -> None:
    (tmp_path / "source_event.jira.md").write_text(
        "\n".join(
            [
                "---",
                "name: source_event.jira",
                "version: test",
                "status: placeholder",
                "---",
                "",
                "# Jira",
                "",
                "## Purpose",
                "",
                "No output contract here.",
            ]
        ),
        encoding="utf-8",
    )
    loader = RulebookLoader(rulebook_dir=tmp_path)

    with pytest.raises(RulebookFormatError, match="missing required sections"):
        loader.load("source_event.jira")


def test_rulebook_hash_uses_full_content() -> None:
    content = "---\nname: update_quality\n---\nbody"

    assert hash_rulebook_content(content) != hash_rulebook_content(content + "\n")


def write_rulebook(path: Path, *, name: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "version: test",
                "status: placeholder",
                "---",
                "",
                "# Test Rulebook",
                "",
                "## Purpose",
                "",
                "Test purpose.",
                "",
                "## Input Contract",
                "",
                "Test input.",
                "",
                "## Output Contract",
                "",
                "Test output.",
            ]
        ),
        encoding="utf-8",
    )
