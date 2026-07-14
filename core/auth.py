import secrets

import keyring
import requests

from core.settings import read_config


def check_login(force_new_token: bool = False) -> tuple[bool, str | None]:
    try:
        if force_new_token:
            raise ValueError("Force new token")
        token = keyring.get_password("AshenMacros", "token")
        if token is None:
            raise ValueError("Token not found")
        if len(token) != 128:
            raise ValueError("Invalid token length")
    except ValueError:
        print("Token not found or invalid. Creating new token...")
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
            print("Failed to validate token. Error code:", response.status_code)
            return True, "N/A"
        data = response.json()

        if data["error"] == "invalid token format":
            print("Invalid token format. Creating new token...")
            return check_login(True)

        if data["valid"] == "true":
            return True, data["username"]

        if data["valid"] == "false":
            return False, None
    except Exception as e:
        print(f"Failed to validate token: {e}")
        return True, "N/A"

    return True, "N/A"


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
