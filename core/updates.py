import logging
import os
import subprocess

import requests
from packaging import version

from core.settings import read_config

logger = logging.getLogger(__name__)

GITHUB_RELEASES_LATEST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"
)
GITHUB_RELEASES_LIST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases"
)

# Process names used by the installed / built launcher (without .exe for Stop-Process).
LAUNCHER_PROCESS_BASENAMES = (
    "launcher",
    "Ashen Macros",
)

# Survive parent exit when the launcher is in a Windows job object (common with PyInstaller).
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


def read_local_version() -> str:
    for path in ("_internal/version", "version"):
        try:
            with open(path, "r", encoding="UTF-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "0.0.0"


def prefer_prerelease_enabled() -> bool:
    config = read_config()
    return str(config.get("prefer_prerelease", "false")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _release_version_name(release: dict) -> str:
    name = str(release.get("name") or "").strip()
    if name:
        return name
    tag = str(release.get("tag_name") or "").strip()
    if tag.lower().startswith("v"):
        return tag[1:]
    return tag


def _fetch_online_release(*, prefer_prerelease: bool) -> dict | None:
    headers = {"Accept": "application/vnd.github+json"}
    if prefer_prerelease:
        response = requests.get(GITHUB_RELEASES_LIST, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        releases = response.json()
        if not isinstance(releases, list) or not releases:
            return None
        prereleases = [r for r in releases if r.get("prerelease")]
        chosen = (prereleases or releases)[0]
        online = _release_version_name(chosen)
        if not online:
            return None
        return {
            "online_version": online,
            "tag_name": str(chosen.get("tag_name") or online),
            "prerelease": bool(chosen.get("prerelease")),
        }

    response = requests.get(GITHUB_RELEASES_LATEST, headers=headers, timeout=15)
    if response.status_code != 200:
        return None
    payload = response.json()
    online = _release_version_name(payload)
    if not online:
        return None
    return {
        "online_version": online,
        "tag_name": str(payload.get("tag_name") or online),
        "prerelease": bool(payload.get("prerelease")),
    }


def check_for_updates(silent: bool = True) -> dict:
    """Returns {kind, online_version?} where kind is one of: noop, outdated, current, dev."""
    try:
        prefer = prefer_prerelease_enabled()
        release = _fetch_online_release(prefer_prerelease=prefer)
        if release is None:
            return {"kind": "noop"}
        local = read_local_version()
        online = release["online_version"]
        if version.parse(local) < version.parse(online):
            return {
                "kind": "outdated",
                "online_version": online,
                "tag_name": release.get("tag_name") or online,
                "prerelease": release.get("prerelease"),
            }
        if version.parse(local) == version.parse(online) and not silent:
            return {"kind": "current", "prerelease": release.get("prerelease")}
        if version.parse(local) > version.parse(online) and not silent:
            return {"kind": "dev", "prerelease": release.get("prerelease")}
        return {"kind": "noop"}
    except Exception as e:
        logger.warning("Failed to check for updates: %s", e)
        return {"kind": "noop"}


def download_update(online_version: str, tag_name: str | None = None) -> str:
    """Download the installer to disk. Does not start it or exit the app.

    Returns the absolute path to the downloaded installer.
    """
    asset_ref = (tag_name or online_version or "").strip()
    logger.info("Downloading update v%s (tag %s)", online_version, asset_ref)
    url = (
        f"https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/"
        f"{asset_ref}/Ashen.Macro.installer.exe"
    )
    download = requests.get(url, allow_redirects=True, timeout=180)
    download.raise_for_status()
    path = os.path.abspath("Ashen.Macro.Installer.exe")
    with open(path, "wb") as out:
        out.write(download.content)
    logger.info("Update downloaded to %s (%s bytes)", path, len(download.content))
    return path


def launch_installer_after_exit(installer_path: str) -> None:
    """Start a breakaway helper that waits briefly, then runs the installer.

    Must be called before the launcher exits. Uses PowerShell so the helper is
    not killed with the PyInstaller job object, and so the installer UI can open.
    """
    installer = os.path.abspath(installer_path)
    if not os.path.isfile(installer):
        raise FileNotFoundError(installer)

    # Escape single quotes for PowerShell single-quoted string.
    installer_ps = installer.replace("'", "''")
    kill_lines = "; ".join(
        f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue"
        for name in LAUNCHER_PROCESS_BASENAMES
    )
    # Fixed short delay is enough: we quit immediately after scheduling this.
    # Then force-kill leftovers and Start-Process the setup UI.
    ps = (
        "Start-Sleep -Seconds 2; "
        f"{kill_lines}; "
        "Start-Sleep -Seconds 1; "
        f"Start-Process -FilePath '{installer_ps}'"
    )

    creationflags = (
        _CREATE_BREAKAWAY_FROM_JOB
        | _CREATE_NEW_PROCESS_GROUP
        | _CREATE_NO_WINDOW
    )
    proc = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps,
        ],
        creationflags=creationflags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(
        "Scheduled installer after exit: %s (helper pid %s)",
        installer,
        proc.pid,
    )
