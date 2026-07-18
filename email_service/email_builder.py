"""
Build email messages.
"""

from email.message import EmailMessage

from config.settings import EMAIL_ADDRESS, SENDER_NAME


def build_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> EmailMessage:
    """
    Build and return an email message.

    Args:
        recipient: Recipient email address.
        subject: Email subject.
        body: Plain text email body.
        html_body: Optional HTML email body.

    Returns:
        Configured EmailMessage instance.
    """

    recipient = recipient.strip()
    subject = subject.strip()
    body = body.strip()

    if not recipient:
        raise ValueError("Recipient email address cannot be empty.")

    if not subject:
        raise ValueError("Email subject cannot be empty.")

    if not body:
        raise ValueError("Email body cannot be empty.")

    message = EmailMessage()

    message["From"] = f"{SENDER_NAME} <{EMAIL_ADDRESS}>"
    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)

    if html_body:
        message.add_alternative(
            html_body,
            subtype="html",
        )

    return message
