"""
Email delivery reporting utilities.
"""

from __future__ import annotations

from csv import DictWriter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class DeliveryRecord:
    """
    Represents the delivery result of a single email.
    """

    recipient: str
    subject: str
    status: str
    timestamp: str
    error: str = ""


class DeliveryReport:
    """
    Collect email delivery results and export reports.
    """

    def __init__(self) -> None:

        self._records: list[DeliveryRecord] = []

    def add_success(
        self,
        recipient: str,
        subject: str,
    ) -> None:
        """
        Record a successful email delivery.
        """

        self._records.append(
            DeliveryRecord(
                recipient=recipient,
                subject=subject,
                status="Success",
                timestamp=self._current_timestamp(),
            )
        )

    def add_failure(
        self,
        recipient: str,
        subject: str,
        error: Exception,
    ) -> None:
        """
        Record a failed email delivery.
        """

        self._records.append(
            DeliveryRecord(
                recipient=recipient,
                subject=subject,
                status="Failed",
                timestamp=self._current_timestamp(),
                error=str(error),
            )
        )

    @property
    def total(self) -> int:
        """
        Total processed emails.
        """

        return len(self._records)

    @property
    def successful(self) -> int:
        """
        Total successful deliveries.
        """

        return sum(
            record.status == "Success"
            for record in self._records
        )

    @property
    def failed(self) -> int:
        """
        Total failed deliveries.
        """

        return self.total - self.successful

    def summary(self) -> dict[str, int]:
        """
        Return delivery statistics.
        """

        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
        }

    def export_csv(
        self,
        output_path: str | Path,
    ) -> Path:
        """
        Export delivery results to a CSV file.
        """

        output_file = Path(output_path)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_file.open(
            mode="w",
            newline="",
            encoding="utf-8",
        ) as csv_file:

            writer = DictWriter(
                csv_file,
                fieldnames=[
                    "recipient",
                    "subject",
                    "status",
                    "timestamp",
                    "error",
                ],
            )

            writer.writeheader()

            for record in self._records:
                writer.writerow(
                    asdict(record)
                )

        return output_file

    @staticmethod
    def _current_timestamp() -> str:
        """
        Return current local timestamp.
        """

        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )