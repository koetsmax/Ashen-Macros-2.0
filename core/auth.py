import logging
import os
import secrets

import keyring
import requests

from core.settings import DATA_DIR, read_config

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "AshenMacros"
_KEYRING_USER = "token"
# Used only when no keyring backend works (e.g. no Secret Service / KWallet daemon).
_TOKEN_FALLBACK_PATH = os.path.join(DATA_DIR, "token")


def _read_fallback_token() -> str | None:
    try:
        with open(_TOKEN_FALLBACK_PATH, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Could not read token fallback file: %s", exc)
        return None


def _write_fallback_token(token: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(_TOKEN_FALLBACK_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token)
    try:
        os.chmod(_TOKEN_FALLBACK_PATH, 0o600)
    except OSError:
        pass


_keyring_failed = False


def _note_keyring_failure(exc: Exception) -> None:
    global _keyring_failed
    if not _keyring_failed:
        logger.warning(
            "Keyring unavailable (%s); using token file %s (0600)",
            exc,
            _TOKEN_FALLBACK_PATH,
        )
    _keyring_failed = True


def _load_token() -> str | None:
    if _keyring_failed:
        return _read_fallback_token()
    try:
        token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception as exc:  # KeyringError, or a D-Bus error from Secret Service
        _note_keyring_failure(exc)
        return _read_fallback_token()
    if token is None and os.path.exists(_TOKEN_FALLBACK_PATH):
        return _read_fallback_token()
    return token


def _store_token(token: str) -> None:
    if not _keyring_failed:
        try:
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, token)
            return
        except Exception as exc:  # KeyringError, or a D-Bus error from Secret Service
            _note_keyring_failure(exc)
    _write_fallback_token(token)


def check_login(force_new_token: bool = False) -> tuple[bool, str | None, list[str]]:
    """Return (verified, username, permissions).

    Pre-release updates are a local user preference (Ctrl+Shift+P) only.
    """
    try:
        if force_new_token:
            raise ValueError("Force new token")
        token = _load_token()
        if token is None:
            raise ValueError("Token not found")
        if len(token) != 128:
            raise ValueError("Invalid token length")
    except ValueError:
        logger.info("Token not found or invalid; creating new token")
        token = secrets.token_hex(64)
        _store_token(token)

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
    return _load_token()


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
