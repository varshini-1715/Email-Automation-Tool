"""
Application configuration.

Loads environment variables from the .env file,
validates required settings, and exposes them
to the rest of the application.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables.

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Local development may use .env. Deployed environments may provide the
# same values directly through operating-system or platform variables.
if ENV_FILE.is_file():
    load_dotenv(ENV_FILE)


# Read and validate environment variables.


def _get_required_env(variable_name: str) -> str:
    """
    Return a required environment variable.

    Raises:
        ValueError:
            If the environment variable is missing or empty.
    """

    value = os.getenv(variable_name)

    if value is None:
        raise ValueError(f"Required environment variable '{variable_name}' is missing.")

    value = value.strip()

    if not value:
        raise ValueError(f"Environment variable '{variable_name}' cannot be empty.")

    return value


# Convert environment variables to boolean values.


def _get_bool(variable_name: str, default: bool = False) -> bool:
    """
    Return an environment variable as a boolean.
    """

    value = os.getenv(variable_name)

    if value is None:
        return default

    value = value.strip().lower()

    true_values = {"true", "1", "yes", "y", "on"}
    false_values = {"false", "0", "no", "n", "off"}

    if value in true_values:
        return True

    if value in false_values:
        return False

    raise ValueError(f"Invalid boolean value for '{variable_name}': '{value}'.")


# Convert environment variables to integers.


def _get_int(variable_name: str) -> int:
    """
    Return an environment variable as an integer.
    """

    value = _get_required_env(variable_name)

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable '{variable_name}' must be an integer."
        ) from exc


# SMTP configuration.

SMTP_SERVER = _get_required_env("SMTP_SERVER")
SMTP_PORT = _get_int("SMTP_PORT")
SMTP_USE_TLS = _get_bool("SMTP_USE_TLS", default=True)


# Email configuration.

EMAIL_ADDRESS = _get_required_env("EMAIL_ADDRESS")
EMAIL_PASSWORD = _get_required_env("EMAIL_PASSWORD")
SENDER_NAME = _get_required_env("SENDER_NAME")


# Logging configuration.

LOG_LEVEL = _get_required_env("LOG_LEVEL").upper()

VALID_LOG_LEVELS = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}

if LOG_LEVEL not in VALID_LOG_LEVELS:
    raise ValueError(
        "LOG_LEVEL must be one of: " f"{', '.join(sorted(VALID_LOG_LEVELS))}."
    )
