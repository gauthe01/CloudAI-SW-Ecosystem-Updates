import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from app.agents.rulebooks.manifest import RULEBOOK_MANIFEST
from app.core.config import Settings, get_settings

RULEBOOK_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
DEFAULT_RULEBOOK_DIR = "app/agents/rulebooks/content"


class RulebookNotFoundError(FileNotFoundError):
    """Raised when a requested rulebook is not present in the configured directory."""


class RulebookFormatError(ValueError):
    """Raised when a rulebook exists but does not follow the framework contract."""


@dataclass(frozen=True)
class Rulebook:
    name: str
    version: str
    status: str
    body: str
    content_hash: str
    path: Path
    metadata: MappingProxyType[str, str]

    @property
    def trace_version(self) -> str:
        return f"{self.version}:{self.content_hash[:12]}"


class RulebookLoader:
    def __init__(
        self,
        *,
        rulebook_dir: str | Path | None = None,
        settings: Settings | None = None,
    ) -> None:
        runtime_settings = settings or get_settings()
        self.root_dir = resolve_rulebook_dir(rulebook_dir or runtime_settings.rulebook_dir)

    def list_rulebooks(self) -> list[str]:
        return sorted(RULEBOOK_MANIFEST)

    def load(self, name: str) -> Rulebook:
        normalized_name = normalize_rulebook_name(name)
        manifest_entry = RULEBOOK_MANIFEST.get(normalized_name)
        if manifest_entry is None:
            raise RulebookNotFoundError(f"Rulebook {normalized_name!r} is not registered.")

        path = self.root_dir / manifest_entry.filename
        if not path.is_file():
            raise RulebookNotFoundError(
                f"Rulebook {normalized_name!r} was registered but not found at {path}.",
            )

        content = path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(content)
        rulebook = Rulebook(
            name=require_metadata(metadata, "name", path),
            version=require_metadata(metadata, "version", path),
            status=require_metadata(metadata, "status", path),
            body=body.strip(),
            content_hash=hash_rulebook_content(content),
            path=path,
            metadata=MappingProxyType(dict(metadata)),
        )
        validate_rulebook(rulebook, expected_name=normalized_name)
        return rulebook


def load_rulebook(name: str, *, settings: Settings | None = None) -> Rulebook:
    return RulebookLoader(settings=settings).load(name)


def normalize_rulebook_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "_")
    if not RULEBOOK_NAME_PATTERN.fullmatch(normalized):
        raise RulebookFormatError(f"Invalid rulebook name {name!r}.")
    return normalized


def resolve_rulebook_dir(rulebook_dir: str | Path) -> Path:
    configured = Path(rulebook_dir)
    if configured.is_absolute():
        return configured

    cwd_candidate = Path.cwd() / configured
    if cwd_candidate.exists():
        return cwd_candidate

    package_candidate = Path(__file__).resolve().parent / "content"
    if configured.as_posix() in {DEFAULT_RULEBOOK_DIR, "apps/api/app/agents/rulebooks/content"}:
        return package_candidate

    return cwd_candidate


def parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RulebookFormatError("Rulebook must start with front matter.")

    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return metadata, "\n".join(lines[index + 1 :])
        key, separator, value = line.partition(":")
        if not separator:
            raise RulebookFormatError(f"Invalid front matter line: {line!r}.")
        metadata[key.strip().lower()] = value.strip()

    raise RulebookFormatError("Rulebook front matter is not closed.")


def require_metadata(metadata: dict[str, str], key: str, path: Path) -> str:
    value = metadata.get(key, "").strip()
    if not value:
        raise RulebookFormatError(f"Rulebook {path} is missing required metadata {key!r}.")
    return value


def validate_rulebook(rulebook: Rulebook, *, expected_name: str) -> None:
    if rulebook.name != expected_name:
        raise RulebookFormatError(
            f"Rulebook metadata name {rulebook.name!r} does not match {expected_name!r}.",
        )
    if not rulebook.body:
        raise RulebookFormatError(f"Rulebook {rulebook.name!r} has no body.")

    required_sections = ("## Purpose", "## Input Contract", "## Output Contract")
    missing_sections = [section for section in required_sections if section not in rulebook.body]
    if missing_sections:
        joined_sections = ", ".join(missing_sections)
        raise RulebookFormatError(
            f"Rulebook {rulebook.name!r} is missing required sections: {joined_sections}.",
        )


def hash_rulebook_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
