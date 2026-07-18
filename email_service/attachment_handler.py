"""
Attach files to email messages.
"""

from email.message import EmailMessage
from mimetypes import guess_type
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


def add_attachment(
    message: EmailMessage,
    file_path: str | Path,
) -> None:
    """
    Attach a file to an EmailMessage.

    Args:
        message: EmailMessage instance.
        file_path: Path to the attachment.

    Raises:
        FileNotFoundError:
            If the file does not exist.

        IsADirectoryError:
            If the path points to a directory.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Attachment not found: {path}")

    if not path.is_file():
        raise IsADirectoryError(f"Expected a file but received: {path}")

    mime_type, _ = guess_type(path)

    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype = "application"
        subtype = "octet-stream"

    logger.info("Attaching file: %s", path.name)

    with path.open("rb") as file:
        message.add_attachment(
            file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )

    logger.info("Attachment added successfully.")
