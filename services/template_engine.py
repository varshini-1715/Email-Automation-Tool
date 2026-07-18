"""Dynamic HTML template discovery, rendering, and plain-text conversion."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Mapping

from utils.logger import get_logger

logger = get_logger(__name__)


class _HTMLToTextParser(HTMLParser):
    """Convert rendered HTML into readable plain text."""

    _IGNORED_TAGS = {"head", "script", "style", "template", "noscript"}
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "tr",
        "td",
        "th",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        normalized = tag.casefold()

        if normalized in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if normalized == "br":
            self._parts.append("\n")
        elif normalized == "li":
            self._parts.append("\n- ")
        elif normalized in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()

        if normalized in self._IGNORED_TAGS:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return

        if self._ignored_depth:
            return

        if normalized == "li" or normalized in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data:
            self._parts.append(data)

    def get_text(self) -> str:
        """Return normalized text while preserving useful line breaks."""

        raw_text = html.unescape("".join(self._parts)).replace("\xa0", " ")
        lines: list[str] = []
        previous_blank = False

        for raw_line in raw_text.splitlines():
            line = re.sub(r"[ \t\r\f\v]+", " ", raw_line).strip()

            if line:
                lines.append(line)
                previous_blank = False
            elif lines and not previous_blank:
                lines.append("")
                previous_blank = True

        return "\n".join(lines).strip()


class TemplateEngine:
    """Discover, inspect, safely render, and convert HTML templates."""

    _PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
    _SAFE_TEMPLATE_NAME = re.compile(r"^[A-Za-z0-9_-]+(?:\.html)?$")
    _ABBREVIATIONS = {
        "api": "API",
        "csv": "CSV",
        "dob": "DOB",
        "email": "Email",
        "html": "HTML",
        "http": "HTTP",
        "https": "HTTPS",
        "id": "ID",
        "ip": "IP",
        "otp": "OTP",
        "pdf": "PDF",
        "uri": "URI",
        "url": "URL",
    }

    def __init__(self, template_directory: str | Path = "templates") -> None:
        self.template_directory = Path(template_directory).expanduser().resolve()

        if not self.template_directory.exists():
            raise FileNotFoundError(
                f"Template directory not found: {self.template_directory}"
            )

        if not self.template_directory.is_dir():
            raise NotADirectoryError(
                f"Template path is not a directory: {self.template_directory}"
            )

    def list_templates(self) -> list[str]:
        """Return available HTML template names in stable sorted order."""

        return sorted(
            template.stem
            for template in self.template_directory.glob("*.html")
            if template.is_file()
        )

    def load_template(self, template_name: str) -> str:
        """Load one validated HTML template as UTF-8 text."""

        template_file = self._template_path(template_name)

        if not template_file.is_file():
            raise FileNotFoundError(
                f"Template '{self._normalize_template_name(template_name)}' "
                "does not exist."
            )

        logger.info("Loading template: %s", template_file.stem)
        return template_file.read_text(encoding="utf-8")

    def extract_placeholders(self, template_name: str) -> list[str]:
        """Return unique placeholders in first-occurrence order."""

        return self._extract_placeholders_from_html(self.load_template(template_name))

    @classmethod
    def placeholder_label(cls, placeholder: str) -> str:
        """Convert an internal placeholder key into a readable CLI label."""

        words: list[str] = []

        for word in placeholder.split("_"):
            normalized = word.casefold()
            words.append(cls._ABBREVIATIONS.get(normalized, word.capitalize()))

        if not words:
            return placeholder

        label = [words[0]]
        label.extend(word if word.isupper() else word.lower() for word in words[1:])
        return " ".join(label)

    def render(
        self,
        template_name: str,
        placeholders: Mapping[str, object],
    ) -> str:
        """
        Render a template with required, non-blank, HTML-escaped values.

        Extra values are accepted and ignored. Missing or blank required values
        raise a precise ValueError before any SMTP connection is attempted.
        """

        rendered_html = self.load_template(template_name)
        required = self._extract_placeholders_from_html(rendered_html)

        for placeholder in required:
            if placeholder not in placeholders:
                raise ValueError(f"Missing placeholder value: '{placeholder}'.")

            raw_value = placeholders[placeholder]
            value = "" if raw_value is None else str(raw_value).strip()

            if not value:
                raise ValueError(f"Blank placeholder value: '{placeholder}'.")

            safe_value = html.escape(value, quote=True)
            rendered_html = re.sub(
                rf"{{{{\s*{re.escape(placeholder)}\s*}}}}",
                lambda _match, replacement=safe_value: replacement,
                rendered_html,
            )

        self._validate_placeholders(rendered_html)
        logger.info("Template '%s' rendered successfully.", template_name)
        return rendered_html

    @staticmethod
    def html_to_plain_text(rendered_html: str) -> str:
        """Generate a non-empty readable fallback from rendered HTML."""

        parser = _HTMLToTextParser()
        parser.feed(rendered_html)
        parser.close()
        text = parser.get_text()

        if not text:
            raise ValueError("Rendered HTML does not contain visible text.")

        return text

    def _template_path(self, template_name: str) -> Path:
        normalized_name = self._normalize_template_name(template_name)
        template_file = (self.template_directory / f"{normalized_name}.html").resolve()

        if template_file.parent != self.template_directory:
            raise ValueError("Invalid template name.")

        return template_file

    @classmethod
    def _normalize_template_name(cls, template_name: str) -> str:
        name = str(template_name).strip()

        if not name or not cls._SAFE_TEMPLATE_NAME.fullmatch(name):
            raise ValueError("Invalid template name.")

        return name[:-5] if name.casefold().endswith(".html") else name

    @classmethod
    def _extract_placeholders_from_html(cls, html_template: str) -> list[str]:
        placeholders: list[str] = []
        seen: set[str] = set()

        for match in cls._PLACEHOLDER_PATTERN.finditer(html_template):
            placeholder = match.group(1)

            if placeholder not in seen:
                seen.add(placeholder)
                placeholders.append(placeholder)

        return placeholders

    @classmethod
    def _validate_placeholders(cls, rendered_html: str) -> None:
        if cls._PLACEHOLDER_PATTERN.search(rendered_html):
            raise ValueError("Template contains unresolved placeholders.")
