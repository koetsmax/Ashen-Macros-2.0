import logging
import os

import requests
from packaging import version
from pyuac import isUserAdmin, runAsAdmin

logger = logging.getLogger(__name__)

GITHUB_RELEASES = "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"


def read_local_version() -> str:
    for path in ("_internal/version", "version"):
        try:
            with open(path, "r", encoding="UTF-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "0.0.0"


def check_for_updates(silent: bool = True) -> dict:
    """Returns {kind, online_version?} where kind is one of: noop, outdated, elevate, current, dev."""
    try:
        request = requests.get(GITHUB_RELEASES, timeout=15)
        if request.status_code != 200:
            return {"kind": "noop"}
        local = read_local_version()
        online = request.json()["name"]
        if version.parse(local) < version.parse(online):
            if isUserAdmin():
                return {"kind": "outdated", "online_version": online}
            return {"kind": "elevate"}
        if version.parse(local) == version.parse(online) and not silent:
            return {"kind": "current"}
        if version.parse(local) > version.parse(online) and not silent:
            return {"kind": "dev"}
        return {"kind": "noop"}
    except Exception as e:
        logger.warning("Failed to check for updates: %s", e)
        return {"kind": "noop"}


def download_update(online_version: str):
    logger.info("Downloading update v%s", online_version)
    url = (
        f"https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/"
        f"{online_version}/Ashen.Macro.installer.exe"
    )
    download = requests.get(url, allow_redirects=True, timeout=30)
    open("Ashen.Macro.Installer.exe", "wb").write(download.content)
    os.startfile("Ashen.Macro.Installer.exe")
