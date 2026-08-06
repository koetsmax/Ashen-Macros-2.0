import logging
import secrets

import keyring
import requests

from core.settings import read_config, set_custom_value

logger = logging.getLogger(__name__)


def _sync_prefer_prerelease(enabled: bool) -> None:
    """Apply server/admin beta-channel force to local updater config."""
    set_custom_value(
        "UPDATES",
        "prefer_prerelease",
        "true" if enabled else "false",
    )


def check_login(force_new_token: bool = False) -> tuple[bool, str | None, list[str]]:
    """Return (verified, username, permissions).

    When verified, syncs local prefer_prerelease from the `prerelease` permission
    (or prefer_prerelease field) so Permissions can force users onto/off beta.
    """
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
            prefer = data.get("prefer_prerelease")
            if prefer is None:
                prefer = "prerelease" in permissions
            _sync_prefer_prerelease(bool(prefer))
            return True, data.get("username"), permissions

        if valid is False or valid == "false":
            return False, None, []
    except Exception as e:
        logger.warning("Failed to validate token: %s", e)
        return False, None, []

    return False, None, []


def get_token() -> str | None:
    return keyring.get_password("AshenMacros", "token")


def auth_headers() -> dict[str, str]:
    return {"Authorization": get_token() or ""}


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
