import csv
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.bulk_sender import BulkEmailSender


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

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for row in rows:
                if isinstance(row, (list, tuple)):
                    writer.writerow(row)
                else:
                    writer.writerow([row])

        return path

    def _smtp(self):
        smtp_cls = MagicMock()
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client
        smtp_cls.return_value.__exit__.return_value = None
        return smtp_cls, client

    @staticmethod
    def _message(recipient: str) -> EmailMessage:
        msg = EmailMessage()
        msg["To"] = recipient
        return msg

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_one_valid_recipient(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            ["alice@example.com"]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["invalid_rows"], 0)
        self.assertEqual(summary["duplicate_rows"], 0)

        client.send.assert_called_once()
        self.assertTrue(
            summary["report_file"].endswith(
                "delivery_report.csv"
            )
        )

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_multiple_valid_recipients(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            [
                "a@example.com",
                "b@example.com",
                "c@example.com",
            ]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 3)
        self.assertEqual(summary["successful"], 3)
        self.assertEqual(client.send.call_count, 3)

    def test_header_only_csv_returns_empty_summary(self):
        csv_file = self._csv([])

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 0)
        self.assertEqual(summary["successful"], 0)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["invalid_rows"], 0)
        self.assertEqual(summary["duplicate_rows"], 0)
        self.assertEqual(summary["failure_details"], [])
        self.assertIsNone(summary["report_file"])

    def test_missing_csv_file(self):
        with self.assertRaises(FileNotFoundError):
            self.sender.send(
                self.base / "missing.csv",
                self.SUBJECT,
                self.BODY,
            )

    def test_missing_email_column(self):
        csv_file = self._csv(
            [["Alice"]],
            headers=("name",),
        )

        with self.assertRaises(ValueError):
            self.sender.send(
                csv_file,
                self.SUBJECT,
                self.BODY,
            )

    def test_empty_email_value(self):
        csv_file = self._csv(
            [""]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["invalid_rows"], 1)
        self.assertEqual(summary["successful"], 0)
        self.assertIsNone(summary["report_file"])

    def test_invalid_email_value(self):
        csv_file = self._csv(
            ["not-an-email"]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["invalid_rows"], 1)
        self.assertEqual(summary["successful"], 0)
        self.assertIsNone(summary["report_file"])

    def test_duplicate_email_casefolding(self):
        csv_file = self._csv(
            [
                "User@example.com",
                "user@example.com",
            ]
        )

        recipients, total, invalid, duplicate = (
            self.sender._load_recipients(
                csv_file
            )
        )

        self.assertEqual(
            recipients,
            ["User@example.com"],
        )
        self.assertEqual(total, 2)
        self.assertEqual(invalid, 0)
        self.assertEqual(duplicate, 1)
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_one_failure_does_not_stop_later_recipients(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        calls = {"count": 0}

        def send_side_effect(message):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("SMTP failure")

        client.send.side_effect = send_side_effect

        csv_file = self._csv(
            [
                "a@example.com",
                "b@example.com",
                "c@example.com",
            ]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(client.send.call_count, 3)
        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(len(summary["failure_details"]), 1)
        self.assertEqual(
            summary["failure_details"][0]["recipient"],
            "b@example.com",
        )

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_all_recipients_successfully_sent(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            [
                "one@example.com",
                "two@example.com",
            ]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["failure_details"], [])
        self.assertTrue(
            summary["report_file"].endswith(
                "delivery_report.csv"
            )
        )

    def test_total_rows_counts_all_processed_rows(self):
        csv_file = self._csv(
            [
                "valid@example.com",
                "",
                "invalid-email",
                "VALID@example.com",
            ]
        )

        (
            recipients,
            total_rows,
            invalid_rows,
            duplicate_rows,
        ) = self.sender._load_recipients(csv_file)

        self.assertEqual(total_rows, 4)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(invalid_rows, 2)
        self.assertEqual(duplicate_rows, 1)

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_delivery_report_is_fresh_for_each_send(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            ["fresh@example.com"]
        )

        first = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        second = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertEqual(first["successful"], 1)
        self.assertEqual(second["successful"], 1)
        self.assertEqual(first["failed"], 0)
        self.assertEqual(second["failed"], 0)

    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_success_summary_contains_report_path(
        self,
        smtp_cls,
        build_email,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            ["report@example.com"]
        )

        summary = self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
        )

        self.assertIsInstance(
            summary["report_file"],
            str,
        )
        self.assertTrue(
            summary["report_file"].endswith(
                "delivery_report.csv"
            )
        )

    @patch("services.bulk_sender.TemplateEngine")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_template_rendering_is_used(
        self,
        smtp_cls,
        build_email,
        template_engine,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        engine = template_engine.return_value
        engine.render.return_value = "<h1>Hello</h1>"

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        csv_file = self._csv(
            ["template@example.com"]
        )

        self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
            template_name="welcome",
            template_placeholders={"name": "Alice"},
        )

        engine.render.assert_called_once_with(
            "welcome",
            {"name": "Alice"},
        )

    @patch("services.bulk_sender.add_attachment")
    @patch("services.bulk_sender.build_email")
    @patch("services.bulk_sender.SMTPClient")
    def test_attachment_is_added_when_requested(
        self,
        smtp_cls,
        build_email,
        add_attachment,
    ):
        client = MagicMock()
        smtp_cls.return_value.__enter__.return_value = client

        build_email.side_effect = (
            lambda **kw: self._message(kw["recipient"])
        )

        attachment = self.base / "sample.txt"
        attachment.write_text(
            "attachment",
            encoding="utf-8",
        )

        csv_file = self._csv(
            ["attach@example.com"]
        )

        self.sender.send(
            csv_file,
            self.SUBJECT,
            self.BODY,
            attachment=attachment,
        )

        add_attachment.assert_called_once()


if __name__ == "__main__":
    unittest.main()        