"""
SMTP client for sending email messages.
"""

import smtplib
from email.message import EmailMessage

from config.settings import (
    EMAIL_ADDRESS,
    EMAIL_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USE_TLS,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class SMTPClient:
    """
    Manage an SMTP connection and send email messages.
    """

    def __init__(self) -> None:
        self._smtp: smtplib.SMTP | None = None

    def __enter__(self) -> "SMTPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def connect(self) -> None:
        """
        Connect to the SMTP server and authenticate.
        """

        if self._smtp is not None:
            return

        try:
            logger.info("Connecting to SMTP server.")

            smtp = smtplib.SMTP(
                host=SMTP_SERVER,
                port=SMTP_PORT,
                timeout=30,
            )

            smtp.ehlo()

            if SMTP_USE_TLS:
                logger.info("Starting TLS session.")
                smtp.starttls()
                smtp.ehlo()

            logger.info("Authenticating with SMTP server.")
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            self._smtp = smtp

            logger.info("SMTP connection established.")

        except Exception:
            logger.exception("Failed to establish SMTP connection.")
            raise

    def send(self, message: EmailMessage) -> None:
        """
        Send an email message.

        Args:
            message: EmailMessage instance to send.
        """

        if self._smtp is None:
            raise RuntimeError(
                "SMTP connection is not established. Call connect() first."
            )

        try:
            recipients = message.get_all("To", [])

            logger.info(
                "Sending email to %s.",
                ", ".join(recipients),
            )

            self._smtp.send_message(message)

            logger.info("Email sent successfully.")

        except Exception:
            logger.exception("Failed to send email.")
            raise

    def close(self) -> None:
        """
        Close the SMTP connection.
        """

        if self._smtp is None:
            return

        try:
            self._smtp.quit()
            logger.info("SMTP connection closed.")

        except smtplib.SMTPException:
            logger.warning("SMTP connection closed with warnings.")

        finally:
            self._smtp = None
