from pathlib import Path

import pytest

from app.agents.rulebooks import RULEBOOK_MANIFEST, RulebookLoader
from app.agents.rulebooks.loader import (
    RulebookFormatError,
    RulebookNotFoundError,
    hash_rulebook_content,
)


def test_registered_rulebooks_load_from_default_directory() -> None:
    loader = RulebookLoader()

    assert loader.list_rulebooks() == sorted(RULEBOOK_MANIFEST)

    for name in loader.list_rulebooks():
        rulebook = loader.load(name)

        assert rulebook.name == name
        assert rulebook.status == "placeholder"
        assert rulebook.version.startswith("placeholder-")
        assert len(rulebook.content_hash) == 64
        assert rulebook.trace_version == f"{rulebook.version}:{rulebook.content_hash[:12]}"
        assert "## Purpose" in rulebook.body
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
