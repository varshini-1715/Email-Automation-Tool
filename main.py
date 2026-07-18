"""
Email Automation Tool
"""

from pathlib import Path

from email_service.attachment_handler import add_attachment
from email_service.email_builder import build_email
from email_service.smtp_client import SMTPClient
from services.bulk_sender import BulkEmailSender
from services.template_engine import TemplateEngine
from utils.logger import get_logger


logger = get_logger(__name__)


def get_multiline_input(prompt: str) -> str:
    """
    Read multiline input until a blank line is entered.
    """

    print(prompt)
    print("(Press Enter on an empty line to finish)\n")

    lines: list[str] = []

    while True:
        line = input()

        if line == "":
            break

        lines.append(line)

    return "\n".join(lines)


def ask_attachment() -> str | None:
    """
    Ask the user whether an attachment should be included.
    """

    choice = input(
        "\nAttach a file? (y/n): "
    ).strip().lower()

    if choice != "y":
        return None

    path = input(
        "Attachment path: "
    ).strip()

    return path or None


def send_plain_email() -> None:

    recipient = input(
        "\nRecipient Email: "
    ).strip()

    subject = input(
        "Subject: "
    ).strip()

    body = get_multiline_input(
        "Email Body"
    )

    attachment = ask_attachment()

    try:

        message = build_email(
            recipient=recipient,
            subject=subject,
            body=body,
        )

        if attachment:
            add_attachment(
                message,
                attachment,
            )

        with SMTPClient() as client:
            client.send(message)

        print("\nEmail sent successfully.")

    except Exception as exc:

        logger.exception(
            "Failed to send email."
        )

        print(f"\nError: {exc}")


def send_template_email() -> None:

    engine = TemplateEngine()

    templates = engine.list_templates()

    if not templates:
        print("\nNo templates available.")
        return

    print("\nAvailable Templates:\n")

    for index, template in enumerate(
        templates,
        start=1,
    ):
        print(f"{index}. {template}")

    try:

        choice = int(
            input("\nChoose template: ")
        )

        template_name = templates[
            choice - 1
        ]

    except (ValueError, IndexError):

        print("\nInvalid selection.")
        return

    recipient = input(
        "\nRecipient Email: "
    ).strip()

    subject = input(
        "Subject: "
    ).strip()

    placeholders: dict[str, str] = {}

    print(
        "\nEnter placeholder values."
    )

    while True:

        key = input(
            "Placeholder name (blank to finish): "
        ).strip()

        if not key:
            break

        value = input(
            f"{key}: "
        )

        placeholders[key] = value

    plain_body = get_multiline_input(
        "\nPlain text fallback"
    )

    attachment = ask_attachment()

    try:

        html = engine.render(
            template_name,
            placeholders,
        )

        message = build_email(
            recipient=recipient,
            subject=subject,
            body=plain_body,
            html_body=html,
        )

        if attachment:
            add_attachment(
                message,
                attachment,
            )

        with SMTPClient() as client:
            client.send(message)

        print("\nTemplate email sent successfully.")

    except Exception as exc:

        logger.exception(
            "Template email failed."
        )

        print(f"\nError: {exc}")


def send_bulk_email() -> None:

    csv_path = input(
        "\nCSV file path: "
    ).strip()

    subject = input(
        "Subject: "
    ).strip()

    body = get_multiline_input(
        "Email Body"
    )

    attachment = ask_attachment()

    use_template = (
        input(
            "\nUse HTML template? (y/n): "
        )
        .strip()
        .lower()
    ) == "y"

    template_name = None
    placeholders = None

    if use_template:

        engine = TemplateEngine()

        templates = engine.list_templates()

        if not templates:

            print(
                "\nNo templates available."
            )

            return

        print()

        for index, template in enumerate(
            templates,
            start=1,
        ):
            print(
                f"{index}. {template}"
            )

        try:

            selection = int(
                input(
                    "\nChoose template: "
                )
            )

            template_name = templates[
                selection - 1
            ]

        except (ValueError, IndexError):

            print(
                "\nInvalid template."
            )

            return

        placeholders = {}

        print(
            "\nEnter placeholder values."
        )

        while True:

            key = input(
                "Placeholder (blank to finish): "
            ).strip()

            if not key:
                break

            placeholders[key] = input(
                f"{key}: "
            )

    sender = BulkEmailSender()

    try:

        summary = sender.send(
            csv_file=Path(csv_path),
            subject=subject,
            body=body,
            attachment=attachment,
            template_name=template_name,
            template_placeholders=placeholders,
        )

        print("\nBulk email completed.\n")

        print(
            f"Total Rows      : {summary['total_rows']}"
        )

        print(
            f"Successful      : {summary['successful']}"
        )

        print(
            f"Failed          : {summary['failed']}"
        )

        print(
            f"Invalid Rows    : {summary['invalid_rows']}"
        )

        print(
            f"Duplicate Rows  : {summary['duplicate_rows']}"
        )

        report_file = summary.get("report_file")

        print(
            f"Report          : {report_file or 'Not generated'}"
        )

        if summary["failure_details"]:

            print(
                "\nFailure Details:\n"
            )

            for failure in summary[
                "failure_details"
            ]:

                print(
                    f"- {failure['recipient']} -> {failure['error']}"
                )

    except Exception as exc:

        logger.exception(
            "Bulk email failed."
        )

        print(f"\nError: {exc}")


def main() -> None:

    while True:

        print(
            """
==============================
Email Automation Tool
==============================

1. Plain Text Email
2. Template Email
3. Bulk Email
4. Exit
"""
        )

        choice = input(
            "Choose an option: "
        ).strip()

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
            print(
                "\nInvalid option."
            )


if __name__ == "__main__":
    main()