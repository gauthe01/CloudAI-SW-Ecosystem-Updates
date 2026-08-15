from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_INLINE_TAGS = {"b", "strong", "i", "em", "u"}
ALLOWED_BLOCK_TAGS = {"ol", "ul", "li", "br"}
ALLOWED_TAGS = ALLOWED_INLINE_TAGS | ALLOWED_BLOCK_TAGS | {"a"}
SKIPPED_TAGS = {"script", "style", "iframe", "object", "embed"}


class UpdateSummarySanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in SKIPPED_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if normalized not in ALLOWED_TAGS:
            return
        if normalized == "a":
            href = safe_href(dict(attrs).get("href"))
            if not href:
                return
            self.parts.append(
                f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
            )
            return
        if normalized == "br":
            self.parts.append("<br>")
            return
        self.parts.append(f"<{normalized}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in SKIPPED_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if normalized in ALLOWED_TAGS and normalized != "br":
            self.parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        if not self.skip_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.skip_depth:
            self.parts.append(f"&#{name};")

    def sanitized(self) -> str:
        return "".join(self.parts)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def sanitize_update_summary_html(value: str) -> str:
    parser = UpdateSummarySanitizer()
    parser.feed(value)
    parser.close()
    return parser.sanitized()


def update_summary_text(value: str) -> str:
    parser = TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def safe_href(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https", "mailto"}:
        return cleaned
    if not parsed.scheme and cleaned.startswith(("/", "#")):
        return cleaned
    return None
