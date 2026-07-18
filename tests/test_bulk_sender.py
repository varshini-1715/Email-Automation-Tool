import csv
import os
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, call, patch

os.environ.setdefault("SMTP_SERVER", "smtp.test.local")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USE_TLS", "true")
os.environ.setdefault("EMAIL_ADDRESS", "sender@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "test-password")
os.environ.setdefault("SENDER_NAME", "Test Sender")
os.environ.setdefault("LOG_LEVEL", "CRITICAL")

from services.bulk_sender import BulkEmailSender  # noqa: E402


class TestBulkEmailSender(unittest.TestCase):
    SUBJECT = "Test Subject"
    BODY = "Test Body"

    def setUp(self) -> None:
        self.sender = BulkEmailSender()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)

    def _csv(self, rows, headers=("email",)) -> Path:
        path = self.base / "recipients.csv"

        with path.open("w", newline="", encoding="utf-8") as csv_handle:
            if rows and isinstance(rows[0], dict):
                writer = csv.DictWriter(csv_handle, fieldnames=list(headers))
                writer.writeheader()
                writer.writerows(rows)
            else:
                writer = csv.writer(csv_handle)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row if isinstance(row, (list, tuple)) else [row])

        return path

    @staticmethod
    def _message(recipient: str) -> EmailMessage:
        message = EmailMessage()
        message["To"] = recipient
        return message

    def _delivery_mocks(self, smtp_cls, build_email):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client
        build_email.side_effect = lambda **kwargs: self._message(kwargs["recipient"])
        return client

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_plain_email_one_valid_recipient(self, smtp_cls, build_email):
        client = self._delivery_mocks(smtp_cls, build_email)
        summary = self.sender.send(
            self._csv(["alice@example.com"]),
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 0)
        client.send.assert_called_once()
        build_email.assert_called_once_with(
            recipient="alice@example.com",
            subject=self.SUBJECT,
            body=self.BODY,
            html_body=None,
        )

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_multiple_plain_recipients(self, smtp_cls, build_email):
        client = self._delivery_mocks(smtp_cls, build_email)
        summary = self.sender.send(
            self._csv(["a@example.com", "b@example.com", "c@example.com"]),
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["successful"], 3)
        self.assertEqual(client.send.call_count, 3)

    def test_header_only_csv_returns_consistent_empty_summary(self):
        summary = self.sender.send(
            self._csv([]),
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(
            summary,
            {
                "total_rows": 0,
                "successful": 0,
                "failed": 0,
                "invalid_rows": 0,
                "duplicate_rows": 0,
                "failure_details": [],
                "report_file": None,
            },
        )

    def test_missing_csv_file(self):
        with self.assertRaises(FileNotFoundError):
            self.sender.send(
                self.base / "missing.csv",
                self.SUBJECT,
                self.BODY,
            )

    def test_missing_email_column(self):
        with self.assertRaisesRegex(ValueError, "email"):
            self.sender.send(
                self._csv([["Alice"]], headers=("name",)),
                self.SUBJECT,
                self.BODY,
            )

    def test_empty_and_invalid_emails_are_counted(self):
        summary = self.sender.send(
            self._csv(["", "invalid-email"]),
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 2)
        self.assertEqual(summary["invalid_rows"], 2)
        self.assertEqual(summary["successful"], 0)

    def test_duplicate_email_is_case_insensitive(self):
        recipients, total, invalid, duplicate = self.sender._load_recipients(
            self._csv(["User@example.com", "user@example.com"])
        )

        self.assertEqual(recipients, ["User@example.com"])
        self.assertEqual(total, 2)
        self.assertEqual(invalid, 0)
        self.assertEqual(duplicate, 1)

    def test_total_rows_includes_invalid_and_duplicate_rows(self):
        recipients, total, invalid, duplicate = self.sender._load_recipients(
            self._csv(
                [
                    "valid@example.com",
                    "",
                    "invalid-email",
                    "VALID@example.com",
                ]
            )
        )

        self.assertEqual(total, 4)
        self.assertEqual(recipients, ["valid@example.com"])
        self.assertEqual(invalid, 2)
        self.assertEqual(duplicate, 1)

    def test_csv_headers_are_normalized(self):
        csv_file = self._csv(
            [],
            headers=("Email", "Recipient Name", "Account-ID"),
        )
        self.assertEqual(
            self.sender.get_csv_headers(csv_file),
            ["email", "recipient_name", "account_id"],
        )

    def test_duplicate_normalized_headers_are_rejected(self):
        csv_file = self._csv([], headers=("email", "Recipient Name", "recipient-name"))
        with self.assertRaisesRegex(ValueError, "duplicate column"):
            self.sender.get_csv_headers(csv_file)

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_one_smtp_failure_does_not_stop_later_recipients(
        self,
        smtp_cls,
        build_email,
    ):
        client = self._delivery_mocks(smtp_cls, build_email)
        client.send.side_effect = [None, RuntimeError("SMTP failure"), None]

        summary = self.sender.send(
            self._csv(["a@example.com", "b@example.com", "c@example.com"]),
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(client.send.call_count, 3)
        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failure_details"][0]["recipient"], "b@example.com")
        self.assertEqual(summary["failure_details"][0]["row"], "3")

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_delivery_report_is_fresh_for_each_send(self, smtp_cls, build_email):
        self._delivery_mocks(smtp_cls, build_email)
        csv_file = self._csv(["fresh@example.com"])

        first = self.sender.send(csv_file, self.SUBJECT, self.BODY)
        second = self.sender.send(csv_file, self.SUBJECT, self.BODY)

        self.assertEqual(first["successful"], 1)
        self.assertEqual(second["successful"], 1)
        self.assertEqual(first["failed"], 0)
        self.assertEqual(second["failed"], 0)

    @patch("services.bulk_sender.add_attachment")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_attachment_is_added_for_each_recipient(
        self,
        smtp_cls,
        build_email,
        add_attachment,
    ):
        self._delivery_mocks(smtp_cls, build_email)
        attachment = self.base / "sample.txt"
        attachment.write_text("attachment", encoding="utf-8")

        self.sender.send(
            self._csv(["one@example.com", "two@example.com"]),
            self.SUBJECT,
            self.BODY,
            attachment=attachment,
        )

        self.assertEqual(add_attachment.call_count, 2)

    @patch("services.bulk_sender.TemplateEngine")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_bulk_template_merges_shared_and_csv_values_per_recipient(
        self,
        smtp_cls,
        build_email,
        template_engine,
    ):
        self._delivery_mocks(smtp_cls, build_email)
        engine = template_engine.return_value
        engine.extract_placeholders.return_value = ["recipient_name", "company_name"]
        engine.render.side_effect = ["<p>Alice</p>", "<p>Bob</p>"]
        engine.html_to_plain_text.side_effect = ["Alice", "Bob"]
        csv_file = self._csv(
            [
                {
                    "email": "alice@example.com",
                    "recipient_name": "Alice",
                    "company_name": "CSV Company",
                },
                {
                    "email": "bob@example.com",
                    "recipient_name": "Bob",
                    "company_name": "",
                },
            ],
            headers=("email", "recipient_name", "company_name"),
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            "",
            template_name="welcome",
            template_placeholders={"company_name": "Shared Company"},
        )

        self.assertEqual(summary["successful"], 2)
        first_values = engine.render.call_args_list[0].args[1]
        second_values = engine.render.call_args_list[1].args[1]
        self.assertEqual(first_values["recipient_name"], "Alice")
        self.assertEqual(first_values["company_name"], "CSV Company")
        # CSV fields intentionally override shared fields, including blank values.
        self.assertEqual(second_values["company_name"], "")
        self.assertEqual(first_values["recipient_email"], "alice@example.com")
        self.assertEqual(second_values["recipient_email"], "bob@example.com")

    @patch("services.bulk_sender.TemplateEngine")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_template_is_rendered_separately_for_every_recipient(
        self,
        smtp_cls,
        build_email,
        template_engine,
    ):
        self._delivery_mocks(smtp_cls, build_email)
        engine = template_engine.return_value
        engine.extract_placeholders.return_value = ["recipient_name"]
        engine.render.side_effect = ["<p>Alice</p>", "<p>Bob</p>"]
        engine.html_to_plain_text.side_effect = ["Alice", "Bob"]
        csv_file = self._csv(
            [
                {"email": "a@example.com", "recipient_name": "Alice"},
                {"email": "b@example.com", "recipient_name": "Bob"},
            ],
            headers=("email", "recipient_name"),
        )

        self.sender.send(
            csv_file,
            self.SUBJECT,
            "",
            template_name="welcome",
        )

        self.assertEqual(engine.render.call_count, 2)
        self.assertEqual(engine.html_to_plain_text.call_count, 2)
        self.assertEqual(
            [item.kwargs["body"] for item in build_email.call_args_list],
            ["Alice", "Bob"],
        )

    @patch("services.bulk_sender.TemplateEngine")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_template_row_failure_is_isolated(
        self,
        smtp_cls,
        build_email,
        template_engine,
    ):
        client = self._delivery_mocks(smtp_cls, build_email)
        engine = template_engine.return_value
        engine.extract_placeholders.return_value = ["recipient_name"]
        engine.render.side_effect = [
            ValueError("Blank placeholder value: 'recipient_name'."),
            "<p>Bob</p>",
        ]
        engine.html_to_plain_text.return_value = "Bob"
        csv_file = self._csv(
            [
                {"email": "a@example.com", "recipient_name": ""},
                {"email": "b@example.com", "recipient_name": "Bob"},
            ],
            headers=("email", "recipient_name"),
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            "",
            template_name="welcome",
        )

        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(client.send.call_count, 1)
        self.assertEqual(summary["failure_details"][0]["recipient"], "a@example.com")

    def test_non_template_empty_body_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "body"):
            self.sender.send(
                self._csv(["a@example.com"]),
                self.SUBJECT,
                "",
            )


if __name__ == "__main__":
    unittest.main()
