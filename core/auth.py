import logging
import secrets

import keyring
import requests

from core.settings import read_config

logger = logging.getLogger(__name__)


def check_login(force_new_token: bool = False) -> tuple[bool, str | None, list[str]]:
    """Return (verified, username, permissions)."""
    try:
        if force_new_token:
            raise ValueError("Force new token")
        token = keyring.get_password("AshenMacros", "token")
        if token is None:
            raise ValueError("Token not found")
        if len(token) != 128:
            raise ValueError("Invalid token length")
    except ValueError:
        logger.info("Token not found or invalid; creating new token")
        token = secrets.token_hex(64)
        keyring.set_password("AshenMacros", "token", token)

    try:
        api_url = read_config()["api_url"]
        response = requests.post(
            f"{api_url}/auth/validate_token",
            json={"token": token},
            timeout=3,
        )

        if response.status_code != 200:
            logger.warning("Token validation failed with status %s", response.status_code)
            return False, None, []
        data = response.json()

        if data.get("error") == "invalid token format":
            logger.info("Invalid token format; regenerating token")
            return check_login(True)

        permissions = list(data.get("permissions") or [])
        valid = data.get("valid")
        if valid is True or valid == "true":
            return True, data.get("username"), permissions

        if valid is False or valid == "false":
            return False, None, []
    except Exception as e:
        logger.warning("Failed to validate token: %s", e)
        return False, None, []

    return False, None, []


def get_token() -> str | None:
    return keyring.get_password("AshenMacros", "token")


def check_connection() -> bool:
    api_url = read_config()["api_url"]
    try:
        response = requests.get(f"{api_url}/auth/connection", timeout=3)
        return response.status_code == 200
    except (
        requests.exceptions.ConnectionError,
        TypeError,
        requests.exceptions.ReadTimeout,
        requests.exceptions.InvalidSchema,
    ):
        return False
