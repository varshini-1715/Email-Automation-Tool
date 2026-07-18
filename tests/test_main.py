import os
import unittest
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

os.environ.setdefault("SMTP_SERVER", "smtp.test.local")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USE_TLS", "true")
os.environ.setdefault("EMAIL_ADDRESS", "sender@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "test-password")
os.environ.setdefault("SENDER_NAME", "Test Sender")
os.environ.setdefault("LOG_LEVEL", "CRITICAL")

import main  # noqa: E402


class TestMainTemplateWorkflow(unittest.TestCase):
    @patch("builtins.input", side_effect=["Alice"])
    def test_collect_template_values_prompts_only_for_missing_values(
        self, mocked_input
    ):
        engine = MagicMock()
        engine.extract_placeholders.return_value = [
            "recipient_email",
            "recipient_name",
        ]
        engine.placeholder_label.return_value = "Recipient name"

        values = main.collect_template_values(
            engine,
            "welcome",
            initial_values={"recipient_email": "alice@example.com"},
        )

        self.assertEqual(values["recipient_email"], "alice@example.com")
        self.assertEqual(values["recipient_name"], "Alice")
        mocked_input.assert_called_once_with("Recipient name: ")

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["", "Alice"])
    def test_required_value_reprompts_after_blank(self, mocked_input, _mocked_print):
        self.assertEqual(main.ask_required_value("Recipient name"), "Alice")
        self.assertEqual(mocked_input.call_count, 2)

    @patch("main.SMTPClient")
    @patch("main.build_email")
    @patch("main.ask_yes_no", return_value=False)
    @patch("main.show_preview")
    @patch("main.ask_attachment", return_value=None)
    @patch("main.collect_template_values", return_value={"recipient_name": "Alice"})
    @patch("main.select_template", return_value="welcome")
    @patch("main.TemplateEngine")
    @patch("builtins.input", side_effect=["alice@example.com", "Welcome"])
    def test_cancelled_template_email_never_connects_to_smtp(
        self,
        _input,
        template_engine,
        _select_template,
        _collect_values,
        _ask_attachment,
        _show_preview,
        _ask_yes_no,
        build_email,
        smtp_client,
    ):
        engine = template_engine.return_value
        engine.render.return_value = "<p>Hello Alice</p>"
        engine.html_to_plain_text.return_value = "Hello Alice"

        main.send_template_email()

        build_email.assert_not_called()
        smtp_client.assert_not_called()

    @patch("main.SMTPClient")
    @patch("main.build_email")
    @patch("main.ask_yes_no", return_value=True)
    @patch("main.show_preview")
    @patch("main.ask_attachment", return_value=None)
    @patch("main.collect_template_values", return_value={"recipient_name": "Alice"})
    @patch("main.select_template", return_value="welcome")
    @patch("main.TemplateEngine")
    @patch("builtins.input", side_effect=["alice@example.com", "Welcome"])
    def test_confirmed_template_email_uses_generated_fallback(
        self,
        _input,
        template_engine,
        _select_template,
        _collect_values,
        _ask_attachment,
        _show_preview,
        _ask_yes_no,
        build_email,
        smtp_client,
    ):
        engine = template_engine.return_value
        engine.render.return_value = "<p>Hello Alice</p>"
        engine.html_to_plain_text.return_value = "Hello Alice"
        message = EmailMessage()
        message["To"] = "alice@example.com"
        build_email.return_value = message
        client = smtp_client.return_value.__enter__.return_value

        main.send_template_email()

        build_email.assert_called_once_with(
            recipient="alice@example.com",
            subject="Welcome",
            body="Hello Alice",
            html_body="<p>Hello Alice</p>",
        )
        client.send.assert_called_once_with(message)


if __name__ == "__main__":
    unittest.main()
