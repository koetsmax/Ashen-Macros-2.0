import logging
import os
import subprocess

import requests
from packaging import version

logger = logging.getLogger(__name__)

GITHUB_RELEASES = "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"

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


def check_for_updates(silent: bool = True) -> dict:
    """Returns {kind, online_version?} where kind is one of: noop, outdated, current, dev."""
    try:
        request = requests.get(GITHUB_RELEASES, timeout=15)
        if request.status_code != 200:
            return {"kind": "noop"}
        local = read_local_version()
        online = request.json()["name"]
        if version.parse(local) < version.parse(online):
            return {"kind": "outdated", "online_version": online}
        if version.parse(local) == version.parse(online) and not silent:
            return {"kind": "current"}
        if version.parse(local) > version.parse(online) and not silent:
            return {"kind": "dev"}
        return {"kind": "noop"}
    except Exception as e:
        logger.warning("Failed to check for updates: %s", e)
        return {"kind": "noop"}


def download_update(online_version: str) -> str:
    """Download the installer to disk. Does not start it or exit the app.

    Returns the absolute path to the downloaded installer.
    """
    logger.info("Downloading update v%s", online_version)
    url = (
        f"https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/"
        f"{online_version}/Ashen.Macro.installer.exe"
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
