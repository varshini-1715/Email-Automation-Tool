"""Bulk email delivery from CSV data."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from email_service.attachment_handler import add_attachment
from email_service.email_builder import build_email
from email_service.smtp_client import SMTPClient
from services.template_engine import TemplateEngine
from services.validator import (
    validate_attachment,
    validate_body,
    validate_csv_file,
    validate_email,
    validate_subject,
)
from utils.logger import get_logger
from utils.report import DeliveryReport

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _RecipientRow:
    recipient: str
    values: dict[str, str]
    row_number: int


class BulkEmailSender:
    """Send plain-text or personalized template emails from a CSV file."""

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
        """Send to all valid, unique CSV recipients and return a summary."""

        report = DeliveryReport()
        subject = validate_subject(subject)
        csv_path = validate_csv_file(csv_file)

        attachment_path: Path | None = None
        if attachment:
            attachment_path = validate_attachment(attachment)

        engine: TemplateEngine | None = None
        plain_body: str | None = None
        shared_placeholders = self._normalize_placeholder_values(
            template_placeholders or {}
        )

        if template_name:
            engine = TemplateEngine()
            # Validate the template name/file before opening SMTP. Individual
            # missing row values are still handled per recipient below.
            engine.extract_placeholders(template_name)
        else:
            plain_body = validate_body(body)

        (
            recipient_rows,
            total_rows,
            invalid_rows,
            duplicate_rows,
        ) = self._load_recipient_rows(csv_path)

        failure_details: list[dict[str, str]] = []

        if not recipient_rows:
            logger.warning("No valid recipients found.")
            return self._summary(
                total_rows=total_rows,
                successful=0,
                failed=0,
                invalid_rows=invalid_rows,
                duplicate_rows=duplicate_rows,
                failure_details=failure_details,
                report_file=None,
            )

        logger.info(
            "Starting bulk email delivery to %d recipients.",
            len(recipient_rows),
        )

        with SMTPClient() as client:
            for recipient_row in recipient_rows:
                try:
                    html_body: str | None = None
                    current_body = plain_body

                    if engine is not None and template_name is not None:
                        placeholders = dict(shared_placeholders)
                        placeholders.update(recipient_row.values)
                        # The actual delivery address is the source of truth.
                        placeholders["email"] = recipient_row.recipient
                        placeholders["recipient_email"] = recipient_row.recipient

                        html_body = engine.render(template_name, placeholders)
                        current_body = engine.html_to_plain_text(html_body)

                    if current_body is None:
                        raise RuntimeError("Email body was not generated.")

                    message = build_email(
                        recipient=recipient_row.recipient,
                        subject=subject,
                        body=current_body,
                        html_body=html_body,
                    )

                    if attachment_path is not None:
                        add_attachment(message, attachment_path)

                    client.send(message)
                    report.add_success(recipient_row.recipient, subject)

                except Exception as exc:
                    logger.exception(
                        "Failed to send email to %s.",
                        recipient_row.recipient,
                    )
                    report.add_failure(
                        recipient_row.recipient,
                        subject,
                        exc,
                    )
                    failure_details.append(
                        {
                            "recipient": recipient_row.recipient,
                            "row": str(recipient_row.row_number),
                            "error": str(exc),
                        }
                    )

        report_file = Path("logs") / "delivery_report.csv"
        report.export_csv(report_file)
        report_summary = report.summary()

        return self._summary(
            total_rows=total_rows,
            successful=report_summary["successful"],
            failed=report_summary["failed"],
            invalid_rows=invalid_rows,
            duplicate_rows=duplicate_rows,
            failure_details=failure_details,
            report_file=report_file,
        )

    def get_csv_headers(self, csv_file: str | Path) -> list[str]:
        """Return normalized CSV headers and verify that `email` exists."""

        csv_path = validate_csv_file(csv_file)

        with csv_path.open(newline="", encoding="utf-8-sig") as csv_handle:
            reader = csv.DictReader(csv_handle)
            return self._normalized_headers(reader.fieldnames)

    def _load_recipients(
        self,
        csv_path: Path,
    ) -> tuple[list[str], int, int, int]:
        """Preserved compatibility wrapper returning only email addresses."""

        rows, total_rows, invalid_rows, duplicate_rows = self._load_recipient_rows(
            csv_path
        )
        return (
            [row.recipient for row in rows],
            total_rows,
            invalid_rows,
            duplicate_rows,
        )

    def _load_recipient_rows(
        self,
        csv_path: Path,
    ) -> tuple[list[_RecipientRow], int, int, int]:
        """Read complete normalized CSV rows for valid unique recipients."""

        recipients: list[_RecipientRow] = []
        seen: set[str] = set()
        total_rows = 0
        invalid_rows = 0
        duplicate_rows = 0

        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as csv_handle:
                reader = csv.DictReader(csv_handle)
                normalized_headers = self._normalized_headers(reader.fieldnames)
                original_headers = list(reader.fieldnames or [])
                header_map = dict(zip(original_headers, normalized_headers))

                for row_number, raw_row in enumerate(reader, start=2):
                    total_rows += 1

                    extra_values = raw_row.get(None)
                    if extra_values and any(
                        str(value).strip() for value in extra_values
                    ):
                        invalid_rows += 1
                        logger.warning(
                            "Skipping malformed CSV row %d with extra values.",
                            row_number,
                        )
                        continue

                    values = {
                        normalized: self._clean_csv_value(raw_row.get(original))
                        for original, normalized in header_map.items()
                    }
                    raw_email = values.get("email", "")

                    if not raw_email:
                        invalid_rows += 1
                        logger.warning(
                            "Skipping row %d with empty email.",
                            row_number,
                        )
                        continue

                    try:
                        recipient = validate_email(raw_email)
                    except ValueError:
                        invalid_rows += 1
                        logger.warning(
                            "Skipping invalid email on row %d: %s",
                            row_number,
                            raw_email,
                        )
                        continue

                    normalized_email = recipient.casefold()
                    if normalized_email in seen:
                        duplicate_rows += 1
                        logger.info(
                            "Skipping duplicate recipient on row %d: %s",
                            row_number,
                            recipient,
                        )
                        continue

                    seen.add(normalized_email)
                    values["email"] = recipient
                    recipients.append(
                        _RecipientRow(
                            recipient=recipient,
                            values=values,
                            row_number=row_number,
                        )
                    )

        except FileNotFoundError:
            raise
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV format: {exc}") from exc
        except Exception:
            logger.exception("Failed to load CSV file.")
            raise

        return recipients, total_rows, invalid_rows, duplicate_rows

    @classmethod
    def _normalized_headers(cls, fieldnames: list[str] | None) -> list[str]:
        if fieldnames is None:
            raise ValueError("CSV file is empty.")

        normalized_headers = [cls._normalize_column_name(name) for name in fieldnames]

        if any(not header for header in normalized_headers):
            raise ValueError("CSV contains an empty column name.")

        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("CSV contains duplicate column names after normalization.")

        if "email" not in normalized_headers:
            raise ValueError("CSV must contain an 'email' column.")

        return normalized_headers

    @staticmethod
    def _normalize_column_name(column_name: str | None) -> str:
        if column_name is None:
            return ""

        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            column_name.strip().casefold(),
        )
        return normalized.strip("_")

    @staticmethod
    def _clean_csv_value(value: object) -> str:
        return "" if value is None else str(value).strip()

    @classmethod
    def _normalize_placeholder_values(
        cls,
        placeholders: Mapping[str, object],
    ) -> dict[str, str]:
        return {
            cls._normalize_column_name(str(key)): cls._clean_csv_value(value)
            for key, value in placeholders.items()
            if cls._normalize_column_name(str(key))
        }

    @staticmethod
    def _summary(
        *,
        total_rows: int,
        successful: int,
        failed: int,
        invalid_rows: int,
        duplicate_rows: int,
        failure_details: list[dict[str, str]],
        report_file: Path | None,
    ) -> dict[str, Any]:
        return {
            "total_rows": total_rows,
            "successful": successful,
            "failed": failed,
            "invalid_rows": invalid_rows,
            "duplicate_rows": duplicate_rows,
            "failure_details": failure_details,
            "report_file": str(report_file) if report_file is not None else None,
        }
