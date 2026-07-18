import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SMTP_SERVER", "smtp.test.local")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USE_TLS", "true")
os.environ.setdefault("EMAIL_ADDRESS", "sender@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "test-password")
os.environ.setdefault("SENDER_NAME", "Test Sender")
os.environ.setdefault("LOG_LEVEL", "CRITICAL")

from services.template_engine import TemplateEngine  # noqa: E402


class TestTemplateEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.template_dir = Path(self.temp_dir.name)
        self.engine = TemplateEngine(self.template_dir)

    def _template(self, name: str, content: str) -> Path:
        path = self.template_dir / f"{name}.html"
        path.write_text(content, encoding="utf-8")
        return path

    def test_dynamic_template_discovery_is_sorted(self):
        self._template("welcome", "<p>Welcome</p>")
        self._template("custom", "<p>Custom</p>")
        (self.template_dir / "notes.txt").write_text("ignored", encoding="utf-8")

        self.assertEqual(self.engine.list_templates(), ["custom", "welcome"])

    def test_extracts_whitespace_placeholders_in_first_occurrence_order(self):
        self._template(
            "sample",
            "{{ name }} {{employee_id}} {{name}} {{ employee_id }} {{team}}",
        )

        self.assertEqual(
            self.engine.extract_placeholders("sample"),
            ["name", "employee_id", "team"],
        )

    def test_render_replaces_compact_and_spaced_placeholders(self):
        self._template("sample", "<p>{{ name }} - {{employee_id}}</p>")

        rendered = self.engine.render(
            "sample",
            {"name": "Alice", "employee_id": "EMP-1"},
        )

        self.assertEqual(rendered, "<p>Alice - EMP-1</p>")

    def test_render_escapes_untrusted_values(self):
        self._template("sample", '<a href="{{url}}">{{name}}</a>')

        rendered = self.engine.render(
            "sample",
            {"url": 'https://example.com/?a=1&b="2"', "name": "<Admin>"},
        )

        self.assertIn("&amp;", rendered)
        self.assertIn("&quot;", rendered)
        self.assertIn("&lt;Admin&gt;", rendered)

    def test_missing_placeholder_is_rejected(self):
        self._template("sample", "<p>{{name}} {{team}}</p>")

        with self.assertRaisesRegex(ValueError, "team"):
            self.engine.render("sample", {"name": "Alice"})

    def test_blank_placeholder_is_rejected(self):
        self._template("sample", "<p>{{name}}</p>")

        with self.assertRaisesRegex(ValueError, "Blank placeholder"):
            self.engine.render("sample", {"name": "   "})

    def test_extra_values_are_accepted(self):
        self._template("sample", "<p>{{name}}</p>")

        rendered = self.engine.render(
            "sample",
            {"name": "Alice", "unused": "value"},
        )

        self.assertEqual(rendered, "<p>Alice</p>")

    def test_html_to_plain_text_ignores_css_and_decodes_entities(self):
        rendered_html = """
        <html>
          <head><style>.hidden { color: red; }</style></head>
          <body>
            <h1>Hello &amp; welcome</h1>
            <p>First&nbsp;paragraph.</p>
            <ul><li>One</li><li>Two</li></ul>
          </body>
        </html>
        """

        text = self.engine.html_to_plain_text(rendered_html)

        self.assertIn("Hello & welcome", text)
        self.assertIn("First paragraph.", text)
        self.assertIn("- One", text)
        self.assertNotIn("color: red", text)

    def test_html_to_plain_text_rejects_invisible_content(self):
        with self.assertRaisesRegex(ValueError, "visible text"):
            self.engine.html_to_plain_text("<style>body { color: red; }</style>")

    def test_placeholder_labels_handle_abbreviations(self):
        self.assertEqual(
            self.engine.placeholder_label("employee_id"),
            "Employee ID",
        )
        self.assertEqual(
            self.engine.placeholder_label("login_url"),
            "Login URL",
        )

    def test_template_name_with_html_extension_is_supported(self):
        self._template("welcome", "<p>Welcome</p>")
        self.assertEqual(
            self.engine.load_template("welcome.html"),
            "<p>Welcome</p>",
        )

    def test_unsafe_template_names_are_rejected(self):
        for unsafe_name in ("../secret", "folder/template", "folder\\template"):
            with self.subTest(unsafe_name=unsafe_name):
                with self.assertRaises(ValueError):
                    self.engine.load_template(unsafe_name)

    def test_missing_template_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            self.engine.load_template("missing")


if __name__ == "__main__":
    unittest.main()
