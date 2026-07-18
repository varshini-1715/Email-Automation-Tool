from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

from email_service.attachment_handler import add_attachment
from email_service.email_builder import build_email
from email_service.smtp_client import SMTPClient
from services.template_engine import TemplateEngine
from services.validator import (
    validate_attachment,
    validate_csv_file,
    validate_email,
    validate_subject,
    validate_body,
)
from utils.logger import get_logger
from utils.report import DeliveryReport

logger = get_logger(__name__)


class BulkEmailSender:
    """
    Send emails to multiple recipients loaded from a CSV file.

    Expected CSV format:

        email
        user1@example.com
        user2@example.com
    """

    def send(
        self,
        csv_file: str | Path,
        subject: str,
        body: str,
        *,
        attachment: str | Path | None = None,
        template_name: str | None = None,
        template_placeholders: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send emails to all valid recipients found in a CSV file.

        Returns a summary dictionary.
        """
        report = DeliveryReport()

        subject = validate_subject(subject)
        body = validate_body(body)

        csv_path = validate_csv_file(csv_file)

        attachment_path: Path | None = None
        if attachment:
            attachment_path = validate_attachment(attachment)

        html_body: str | None = None

        if template_name:
            engine = TemplateEngine()
            html_body = engine.render(
                template_name,
                template_placeholders or {},
            )

        recipients, total_rows, invalid_rows, duplicate_rows = self._load_recipients(
            csv_path
        )

        failure_details: list[dict[str, str]] = []

        if not recipients:
            logger.warning("No valid recipients found.")

            return {
                "total_rows": total_rows,
                "successful": 0,
                "failed": 0,
                "invalid_rows": invalid_rows,
                "duplicate_rows": duplicate_rows,
                "failure_details": failure_details,
                "report_file": None,
            }

        logger.info(
            "Starting bulk email delivery to %d recipients.",
            len(recipients),
        )

        with SMTPClient() as client:

            for recipient in recipients:

                try:

                    message = build_email(
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                    )

                    if attachment_path is not None:
                        add_attachment(
                            message,
                            attachment_path,
                        )

                    client.send(message)

                    report.add_success(
                        recipient,
                        subject,
                    )

                except Exception as exc:

                    logger.exception(
                        "Failed to send email to %s.",
                        recipient,
                    )

                    report.add_failure(
                        recipient,
                        subject,
                        exc,
                    )

                    failure_details.append(
                        {
                            "recipient": recipient,
                            "error": str(exc),
                        }
                    )

        report_file = Path("logs") / "delivery_report.csv"

        report.export_csv(report_file)

        summary = report.summary()

        return {
            "total_rows": total_rows,
            "successful": summary["successful"],
            "failed": summary["failed"],
            "invalid_rows": invalid_rows,
            "duplicate_rows": duplicate_rows,
            "failure_details": failure_details,
            "report_file": str(report_file),
        }

    def _load_recipients(
        self,
        csv_path: Path,
    ) -> tuple[list[str], int, int, int]:
        """
        Read recipients from a CSV file.

        Returns:
            (
                valid_recipients,
                invalid_row_count,
                duplicate_row_count,
            )
        """

        recipients: list[str] = []

        seen: set[str] = set()

        total_rows = 0
        invalid_rows = 0
        duplicate_rows = 0

        try:

            with csv_path.open(
                newline="",
                encoding="utf-8-sig",
            ) as file:

                reader = csv.DictReader(file)

                if reader.fieldnames is None:
                    raise ValueError("CSV file is empty.")

                columns = {
                    column.strip().lower() for column in reader.fieldnames if column
                }

                if "email" not in columns:
                    raise ValueError("CSV must contain an 'email' column.")

                for row in reader:

                    total_rows += 1

                    raw_email = (
                        row.get("email") or row.get("Email") or row.get("EMAIL") or ""
                    ).strip()

                    if not raw_email:
                        invalid_rows += 1
                        logger.warning("Skipping row with empty email.")
                        continue

                    try:
                        email = validate_email(raw_email)

                    except ValueError:

                        invalid_rows += 1

                        logger.warning(
                            "Skipping invalid email: %s",
                            raw_email,
                        )

                        continue

                    normalized = email.casefold()

                    if normalized in seen:

                        duplicate_rows += 1

                        logger.info(
                            "Skipping duplicate recipient: %s",
                            email,
                        )

                        continue

                    seen.add(normalized)
                    recipients.append(email)

        except FileNotFoundError:
            raise

        except csv.Error as exc:
            raise ValueError(f"Invalid CSV format: {exc}") from exc

        except Exception:
            logger.exception("Failed to load CSV file.")
            raise

        return (
            recipients,
            total_rows,
            invalid_rows,
            duplicate_rows,
        )
