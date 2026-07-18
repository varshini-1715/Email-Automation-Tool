"""
Validation utilities for the Email Automation Tool.
"""

from pathlib import Path
import re

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email(email: str) -> str:
    """
    Validate a single email address.

    Returns:
        Normalized email address.

    Raises:
        ValueError: If the email address is invalid.
    """

    email = email.strip()

    if not email:
        raise ValueError("Email address cannot be empty.")

    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError(f"Invalid email address: {email}")

    return email


def validate_email_list(emails: list[str]) -> list[str]:
    """
    Validate a list of email addresses.

    Removes duplicate email addresses while preserving order.
    """

    if not emails:
        raise ValueError("Recipient list cannot be empty.")

    validated = []
    seen = set()

    for email in emails:

        email = validate_email(email)

        key = email.casefold()

        if key in seen:
            continue

        seen.add(key)
        validated.append(email)

    return validated


def validate_subject(subject: str) -> str:
    """
    Validate email subject.
    """

    subject = subject.strip()

    if not subject:
        raise ValueError("Email subject cannot be empty.")

    return subject


def validate_body(body: str) -> str:
    """
    Validate plain text body.
    """

    body = body.strip()

    if not body:
        raise ValueError("Email body cannot be empty.")

    return body


def validate_attachment(path: str | Path) -> Path:
    """
    Validate attachment file.
    """

    file_path = Path(path).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Attachment not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Attachment is not a file: {file_path}")

    return file_path


def validate_template(
    template_name: str,
    template_directory: str | Path = "templates",
) -> Path:
    """
    Validate template availability.
    """

    template = Path(template_directory) / f"{template_name}.html"

    if not template.exists():
        raise FileNotFoundError(f"Template '{template_name}' not found.")

    return template


def validate_placeholders(
    placeholders: dict[str, str],
    required_fields: list[str],
) -> None:
    """
    Ensure all required placeholders exist and are not empty.
    """

    missing = []

    for field in required_fields:

        value = placeholders.get(field)

        if value is None or not str(value).strip():
            missing.append(field)

    if missing:

        raise ValueError("Missing placeholder values: " + ", ".join(missing))


def validate_menu_choice(
    choice: str,
    valid_choices: set[str],
) -> str:
    """
    Validate CLI menu selection.
    """

    choice = choice.strip()

    if choice not in valid_choices:
        raise ValueError("Invalid menu selection.")

    return choice


def validate_csv_file(path: str | Path) -> Path:
    """
    Validate CSV file.
    """

    file_path = validate_attachment(path)

    if file_path.suffix.lower() != ".csv":
        raise ValueError("Expected a CSV file.")

    return file_path


def validate_html(html: str) -> str:
    """
    Validate HTML content.
    """

    html = html.strip()

    if not html:
        raise ValueError("HTML content cannot be empty.")

    return html
