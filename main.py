"""Command-line entry point for the Email Automation Tool."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from email_service.attachment_handler import add_attachment
from email_service.email_builder import build_email
from email_service.smtp_client import SMTPClient
from services.bulk_sender import BulkEmailSender
from services.template_engine import TemplateEngine
from utils.logger import get_logger

logger = get_logger(__name__)


def get_multiline_input(prompt: str) -> str:
    """Read multiline input until a blank line is entered."""

    print(prompt)
    print("(Press Enter on an empty line to finish)\n")
    lines: list[str] = []

    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    return "\n".join(lines)


def ask_yes_no(prompt: str, *, default: bool = False) -> bool:
    """Read a reliable yes/no answer."""

    suffix = " [Y/n]: " if default else " [y/N]: "

    while True:
        answer = input(prompt + suffix).strip().casefold()

        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False

        print("Please enter y or n.")


def ask_attachment() -> str | None:
    """Return an optional attachment path with pasted quotes removed."""

    if not ask_yes_no("\nAttach a file?"):
        return None

    path = input("Attachment path: ").strip().strip('"').strip("'")
    return path or None


def select_template(engine: TemplateEngine) -> str | None:
    """Display dynamically discovered templates and return one selection."""

    templates = engine.list_templates()

    if not templates:
        print("\nNo templates available.")
        return None

    print("\nAvailable Templates:\n")
    for index, template in enumerate(templates, start=1):
        print(f"{index}. {template}")

    try:
        selection = int(input("\nChoose template: ").strip())
        return templates[selection - 1]
    except (ValueError, IndexError):
        print("\nInvalid template selection.")
        return None


def ask_required_value(label: str) -> str:
    """Prompt until a non-blank required value is entered."""

    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} cannot be blank.")


def collect_template_values(
    engine: TemplateEngine,
    template_name: str,
    *,
    initial_values: Mapping[str, str] | None = None,
    available_fields: Iterable[str] = (),
) -> dict[str, str]:
    """Prompt only for required placeholders not already supplied elsewhere."""

    values = dict(initial_values or {})
    available = {field.casefold() for field in available_fields}
    placeholders = engine.extract_placeholders(template_name)
    missing = [
        placeholder
        for placeholder in placeholders
        if placeholder.casefold() not in available
        and not str(values.get(placeholder, "")).strip()
    ]

    if missing:
        print("\nEnter template values:\n")

    for placeholder in missing:
        values[placeholder] = ask_required_value(engine.placeholder_label(placeholder))

    return values


def show_preview(
    *,
    mode: str,
    recipient: str | None = None,
    csv_file: str | None = None,
    subject: str,
    template_name: str | None,
    attachment: str | None,
) -> None:
    """Display the final non-secret delivery summary before SMTP use."""

    print("\nDelivery Preview")
    print("-" * 32)
    print(f"Mode       : {mode}")

    if recipient is not None:
        print(f"Recipient  : {recipient}")
    if csv_file is not None:
        print(f"CSV file   : {csv_file}")

    print(f"Subject    : {subject}")
    print(f"Template   : {template_name or 'None'}")
    print(f"Attachment : {attachment or 'None'}")


def send_plain_email() -> None:
    recipient = input("\nRecipient Email: ").strip()
    subject = input("Subject: ").strip()
    body = get_multiline_input("Email Body")
    attachment = ask_attachment()

    show_preview(
        mode="Plain text email",
        recipient=recipient,
        subject=subject,
        template_name=None,
        attachment=attachment,
    )

    if not ask_yes_no("\nSend email?"):
        print("\nEmail cancelled.")
        return

    try:
        message = build_email(
            recipient=recipient,
            subject=subject,
            body=body,
        )

        if attachment:
            add_attachment(message, attachment)

        with SMTPClient() as client:
            client.send(message)

        print("\nEmail sent successfully.")

    except Exception as exc:
        logger.exception("Failed to send email.")
        print(f"\nError: {exc}")


def send_template_email() -> None:
    try:
        engine = TemplateEngine()
        template_name = select_template(engine)

        if template_name is None:
            return

        recipient = input("\nRecipient Email: ").strip()
        subject = input("Subject: ").strip()
        placeholders = collect_template_values(
            engine,
            template_name,
            initial_values={
                "email": recipient,
                "recipient_email": recipient,
            },
        )
        html_body = engine.render(template_name, placeholders)
        plain_body = engine.html_to_plain_text(html_body)
        attachment = ask_attachment()

        show_preview(
            mode="Template email",
            recipient=recipient,
            subject=subject,
            template_name=template_name,
            attachment=attachment,
        )

        if not ask_yes_no("\nSend email?"):
            print("\nTemplate email cancelled.")
            return

        message = build_email(
            recipient=recipient,
            subject=subject,
            body=plain_body,
            html_body=html_body,
        )

        if attachment:
            add_attachment(message, attachment)

        with SMTPClient() as client:
            client.send(message)

        print("\nTemplate email sent successfully.")

    except Exception as exc:
        logger.exception("Template email failed.")
        print(f"\nError: {exc}")


def send_bulk_email() -> None:
    csv_path = input("\nCSV file path: ").strip().strip('"').strip("'")
    subject = input("Subject: ").strip()
    use_template = ask_yes_no("\nUse HTML template?")

    template_name: str | None = None
    shared_placeholders: dict[str, str] | None = None
    body = ""
    sender = BulkEmailSender()

    try:
        if use_template:
            engine = TemplateEngine()
            template_name = select_template(engine)

            if template_name is None:
                return

            headers = sender.get_csv_headers(csv_path)
            available_fields = set(headers)

            if "email" in available_fields:
                available_fields.add("recipient_email")

            shared_placeholders = collect_template_values(
                engine,
                template_name,
                available_fields=available_fields,
            )
        else:
            body = get_multiline_input("Email Body")

        attachment = ask_attachment()

        show_preview(
            mode="Bulk template email" if use_template else "Bulk plain email",
            csv_file=csv_path,
            subject=subject,
            template_name=template_name,
            attachment=attachment,
        )

        if not ask_yes_no("\nStart bulk delivery?"):
            print("\nBulk delivery cancelled.")
            return

        summary = sender.send(
            csv_file=Path(csv_path),
            subject=subject,
            body=body,
            attachment=attachment,
            template_name=template_name,
            template_placeholders=shared_placeholders,
        )

        print("\nBulk email completed.\n")
        print(f"Total Rows      : {summary['total_rows']}")
        print(f"Successful      : {summary['successful']}")
        print(f"Failed          : {summary['failed']}")
        print(f"Invalid Rows    : {summary['invalid_rows']}")
        print(f"Duplicate Rows  : {summary['duplicate_rows']}")
        print(f"Report          : {summary.get('report_file') or 'Not generated'}")

        if summary["failure_details"]:
            print("\nFailure Details:\n")
            for failure in summary["failure_details"]:
                row = failure.get("row")
                row_text = f" (CSV row {row})" if row else ""
                print(f"- {failure['recipient']}{row_text} -> " f"{failure['error']}")

    except Exception as exc:
        logger.exception("Bulk email failed.")
        print(f"\nError: {exc}")


def main() -> None:
    while True:
        print("""
==============================
Email Automation Tool
==============================

1. Plain Text Email
2. Template Email
3. Bulk Email
4. Exit
""")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            send_plain_email()
        elif choice == "2":
            send_template_email()
        elif choice == "3":
            send_bulk_email()
        elif choice == "4":
            print("\nGoodbye.")
            break
        else:
            print("\nInvalid option.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nGoodbye.")
