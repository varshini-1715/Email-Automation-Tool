from pathlib import Path

from utils.logger import get_logger


logger = get_logger(__name__)


class TemplateEngine:
    """Load HTML templates and replace placeholders."""

    def __init__(self, template_directory: str = "templates") -> None:
        self.template_directory = Path(template_directory)

        if not self.template_directory.exists():
            raise FileNotFoundError(
                f"Template directory not found: {self.template_directory.resolve()}"
            )

    def list_templates(self) -> list[str]:
        """Return all available HTML templates."""

        return sorted(
            template.stem
            for template in self.template_directory.glob("*.html")
        )

    def load_template(self, template_name: str) -> str:
        """Load an HTML template."""

        template_file = self.template_directory / f"{template_name}.html"

        if not template_file.exists():
            raise FileNotFoundError(
                f"Template '{template_name}' does not exist."
            )

        logger.info("Loading template: %s", template_name)

        return template_file.read_text(
            encoding="utf-8"
        )

    def render(
        self,
        template_name: str,
        placeholders: dict[str, str],
    ) -> str:
        """
        Render an HTML template.

        Example placeholder:

            {{name}}

        becomes

            John
        """

        html = self.load_template(template_name)

        for key, value in placeholders.items():
            html = html.replace(
                f"{{{{{key}}}}}",
                str(value),
            )

        self._validate_placeholders(html)

        logger.info(
            "Template '%s' rendered successfully.",
            template_name,
        )

        return html

    @staticmethod
    def _validate_placeholders(html: str) -> None:
        """
        Raise an error if unresolved placeholders remain.
        """

        if "{{" in html or "}}" in html:
            raise ValueError(
                "Template contains unresolved placeholders."
            )