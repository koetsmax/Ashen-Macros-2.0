"""Release checks and zip-based in-app updates."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

import requests
from packaging import version

logger = logging.getLogger(__name__)

GITHUB_RELEASES_LATEST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"
)
GITHUB_RELEASES_LIST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases"
)
GITHUB_DOWNLOAD_BASE = (
    "https://github.com/koetsmax/Ashen-Macros-2.0/releases/download"
)

# Survive parent exit when the launcher is in a Windows job object (common with PyInstaller).
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NEW_CONSOLE = 0x00000010
_DETACHED_PROCESS = 0x00000008

# cmd.exe helper — no PowerShell (avoids execution-policy / Constrained Language failures).
# Wait uses ping (not timeout): timeout fails when stdin is redirected and can stall/abort.
UPDATE_HELPER_CMD = r"""@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Installing Ashen Macros
set "LOG=%TEMP%\AshenMacrosUpdateApply.log"
set "PID=%~1"
set "STAGING=%~2"
set "INSTALL=%~3"
set "APPEXE=%~4"

echo.>>"%LOG%"
echo [%date% %time%] apply_update start PID=!PID!>>"%LOG%"
echo [%date% %time%] staging=!STAGING!>>"%LOG%"
echo [%date% %time%] install=!INSTALL!>>"%LOG%"
echo [%date% %time%] appexe=!APPEXE!>>"%LOG%"

if not defined PID (
  echo [%date% %time%] ERROR: missing PID>>"%LOG%"
  exit /b 1
)
if not exist "!STAGING!\" (
  echo [%date% %time%] staging missing - nothing to apply>>"%LOG%"
  exit /b 0
)

echo Waiting for Ashen Macros to exit...
set /a WAITED=0
:wait_loop
tasklist /FI "PID eq !PID!" /NH 2>NUL | find /I ".exe" >NUL
if errorlevel 1 goto wait_done
rem ~1s sleep without timeout.exe (stdin-safe)
ping -n 2 127.0.0.1 >NUL
set /a WAITED+=1
if !WAITED! EQU 1 echo [%date% %time%] waiting for PID !PID! ...>>"%LOG%"
if !WAITED! EQU 10 echo [%date% %time%] still waiting ^(!WAITED!s^)>>"%LOG%"
if !WAITED! EQU 30 echo [%date% %time%] still waiting ^(!WAITED!s^)>>"%LOG%"
if !WAITED! LSS 120 goto wait_loop
echo [%date% %time%] PID !PID! still alive after 120s - forcing stop>>"%LOG%"
taskkill /PID !PID! /F >NUL 2>&1
:wait_done
echo [%date% %time%] process gone ^(waited !WAITED!s^)>>"%LOG%"
ping -n 2 127.0.0.1 >NUL

set "PAYLOAD=!STAGING!"
set /a DIR_COUNT=0
set /a FILE_COUNT=0
set "ONLY_DIR="
for /d %%D in ("!STAGING!\*") do (
  set /a DIR_COUNT+=1
  set "ONLY_DIR=%%~fD"
)
for %%F in ("!STAGING!\*") do (
  if not exist "%%~fF\" set /a FILE_COUNT+=1
)
rem Onedir zips are flat: Ashen Macros.exe + _internal\. Only unwrap when the
rem staging root is a single wrapper folder (no sibling files). Never treat
rem _internal alone as the payload — that copies DLLs over the install root
rem and skips the exe (version becomes 0.0.0 / stale).
if !DIR_COUNT! EQU 1 if !FILE_COUNT! EQU 0 if defined ONLY_DIR (
  for %%I in ("!ONLY_DIR!") do (
    if /I not "%%~nxI"=="_internal" set "PAYLOAD=!ONLY_DIR!"
  )
)
echo [%date% %time%] payload=!PAYLOAD! dirs=!DIR_COUNT! files=!FILE_COUNT!>>"%LOG%"

for %%I in ("!APPEXE!") do set "EXENAME=%%~nxI"
for %%I in ("!PAYLOAD!") do set "PAYLOAD_NAME=%%~nxI"
if /I "!PAYLOAD_NAME!"=="_internal" (
  echo [%date% %time%] ERROR: refusing bare _internal payload>>"%LOG%"
  echo Refusing to install from bare _internal folder. See:
  echo   !LOG!
  pause
  exit /b 1
)
if not exist "!PAYLOAD!\!EXENAME!" (
  echo [%date% %time%] ERROR: payload missing !EXENAME!>>"%LOG%"
  echo Update payload is missing !EXENAME!. See:
  echo   !LOG!
  pause
  exit /b 1
)
if not exist "!PAYLOAD!\_internal\version" (
  echo [%date% %time%] ERROR: payload missing _internal\version>>"%LOG%"
  echo Update payload is missing _internal\version. See:
  echo   !LOG!
  pause
  exit /b 1
)

echo.
echo Installing update into:
echo   !INSTALL!
echo.

if not exist "!INSTALL!\" mkdir "!INSTALL!" >NUL 2>&1

robocopy "!PAYLOAD!" "!INSTALL!" /E /IS /IT /R:2 /W:1
set "RC=!ERRORLEVEL!"
echo [%date% %time%] robocopy exit=!RC!>>"%LOG%"
rem robocopy: 0-7 = success / partial copy; 8+ = failure
if !RC! GEQ 8 (
  echo.
  echo Update copy failed ^(robocopy !RC!^). See:
  echo   !LOG!
  echo [%date% %time%] ERROR: robocopy failed>>"%LOG%"
  pause
  exit /b 1
)

if exist "!INSTALL!\_internal\version" (
  set /p INSTALLED_VER=<"!INSTALL!\_internal\version"
  echo [%date% %time%] installed version=!INSTALLED_VER!>>"%LOG%"
) else (
  echo [%date% %time%] ERROR: _internal\version missing after copy>>"%LOG%"
  echo Update copy finished but version file is missing. See:
  echo   !LOG!
  pause
  exit /b 1
)
if not exist "!INSTALL!\!EXENAME!" (
  echo [%date% %time%] ERROR: !EXENAME! missing after copy>>"%LOG%"
  echo Update copy finished but !EXENAME! is missing. See:
  echo   !LOG!
  pause
  exit /b 1
)

echo [%date% %time%] cleaning staging>>"%LOG%"
rmdir /s /q "!STAGING!" >NUL 2>&1

if exist "!APPEXE!" (
  echo [%date% %time%] starting !APPEXE! ^(cwd=!INSTALL!^)>>"%LOG%"
  echo.
  echo Install complete. Starting Ashen Macros...
  start "" /D "!INSTALL!" "!APPEXE!"
) else (
  echo [%date% %time%] ERROR: AppExe missing: !APPEXE!>>"%LOG%"
  echo.
  echo Update copied but could not find:
  echo   !APPEXE!
  pause
  exit /b 1
)

echo [%date% %time%] apply_update done>>"%LOG%"
ping -n 3 127.0.0.1 >NUL
exit /b 0
"""


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def read_local_version() -> str:
    """Read the packaged or repo version file.

    Frozen builds resolve paths from the install directory (next to the exe),
    not the process cwd — after an in-app update the helper may relaunch with
    cwd still in %TEMP%, which made the badge show v0.0.0 until a normal restart.
    """
    bases: list[Path] = []
    if is_frozen():
        bases.append(Path(sys.executable).resolve().parent)
    bases.append(Path.cwd())
    for base in bases:
        for name in ("_internal/version", "version"):
            path = base / name
            try:
                return path.read_text(encoding="UTF-8").strip()
            except FileNotFoundError:
                continue
            except OSError:
                continue
    return "0.0.0"


def display_version(plain: str | None = None) -> str:
    """UI version string. Appends ' (dev)' when running from source."""
    value = plain if plain is not None else read_local_version()
    if is_frozen():
        return value
    return f"{value} (dev)"


def prefer_prerelease_enabled() -> bool:
    from core.settings import config_bool

    return config_bool("prefer_prerelease", "false")


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def app_executable() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def dir_is_writable(path: Path) -> bool:
    """Probe real create/delete rights instead of trusting os.access alone."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".ashen_write_probe_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="UTF-8")
        probe.unlink()
        return True
    except OSError:
        return False


def zip_asset_name(online_version: str) -> str:
    return f"Ashen-Macros-{online_version}.zip"


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
        if not is_frozen() and silent:
            return {"kind": "noop"}

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
        if (version.parse(local) > version.parse(online) or not is_frozen()) and not silent:
            return {"kind": "dev", "prerelease": release.get("prerelease")}
        return {"kind": "noop"}
    except Exception as e:
        logger.warning("Failed to check for updates: %s", e)
        return {"kind": "noop"}


def download_update(
    online_version: str,
    tag_name: str | None = None,
    progress_callback=None,
) -> str:
    """Download the release zip to a user-writable temp path.

    When ``progress_callback`` is provided it is called as
    ``progress_callback(received_bytes, total_bytes)`` during the download.
    ``total_bytes`` may be 0 if Content-Length is missing.

    Returns the absolute path to the downloaded zip.
    """
    if not is_frozen():
        raise RuntimeError("Zip updates are only supported for packaged builds.")

    asset_ref = (tag_name or online_version or "").strip()
    asset = zip_asset_name(online_version)
    logger.info("Downloading update v%s (tag %s, asset %s)", online_version, asset_ref, asset)
    url = f"{GITHUB_DOWNLOAD_BASE}/{asset_ref}/{asset}"

    dest_root = Path(tempfile.gettempdir()) / "AshenMacrosUpdates"
    dest_root.mkdir(parents=True, exist_ok=True)
    path = dest_root / asset
    chunk_size = 256 * 1024

    with requests.get(url, allow_redirects=True, timeout=180, stream=True) as download:
        download.raise_for_status()
        total = int(download.headers.get("Content-Length") or 0)
        received = 0
        with open(path, "wb") as out:
            for chunk in download.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                out.write(chunk)
                received += len(chunk)
                if progress_callback is not None:
                    progress_callback(received, total)

    logger.info("Update downloaded to %s (%s bytes)", path, received)
    return str(path.resolve())


def extract_update(zip_path: str, progress_callback=None) -> str:
    """Extract the release zip to a temp staging directory.

    When ``progress_callback`` is provided it is called as
    ``progress_callback(extracted_bytes, total_uncompressed_bytes)``.
    ``total_uncompressed_bytes`` may be 0 if sizes are unavailable.

    Returns the absolute path to the staging root (helper unwraps a single
    top-level folder). Deletes the zip after a successful extract.
    """
    zip_file = Path(zip_path).resolve()
    if not zip_file.is_file():
        raise FileNotFoundError(zip_file)

    staging = Path(tempfile.gettempdir()) / f"AshenMacrosUpdate_{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            members = zf.infolist()
            total = sum(info.file_size for info in members if not info.is_dir())
            extracted = 0
            for info in members:
                # Guard against zip-slip into paths outside staging.
                target = (staging / info.filename).resolve()
                if not str(target).startswith(str(staging.resolve())):
                    raise RuntimeError(f"Unsafe path in update zip: {info.filename}")
                zf.extract(info, staging)
                if not info.is_dir():
                    extracted += info.file_size
                    if progress_callback is not None:
                        progress_callback(extracted, total)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    try:
        zip_file.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete update zip after extract: %s", zip_file)

    logger.info("Update extracted to %s", staging)
    return str(staging.resolve())


def apply_helper_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "AshenMacrosUpdateApply.log"


def _write_update_helper(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    helper_path = dest_dir / "apply_update.cmd"
    # cmd scripts are ANSI/OEM on many systems; ASCII-only body is safe as UTF-8.
    helper_path.write_text(UPDATE_HELPER_CMD, encoding="utf-8", newline="\r\n")
    return helper_path


def _helper_params(staging: Path, target: Path, exe: Path) -> str:
    """Argument string for apply_update.cmd (ShellExecute lpParameters)."""
    return f'{os.getpid()} "{staging}" "{target}" "{exe}"'


def _shell_execute_helper(
    helper: Path,
    staging: Path,
    target: Path,
    exe: Path,
    *,
    elevate: bool,
) -> int:
    """Launch helper detached via ShellExecuteW (survives PyInstaller job exit).

    Returns ShellExecute result (>32 = success).
    """
    import ctypes

    verb = "runas" if elevate else "open"
    # open/runas on the .cmd file — Explorer/Shell starts an independent process
    # tree, unlike Popen which often stays in the frozen app's job object and
    # dies when the app quits (log truncates right after "apply_update start").
    return int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            verb,
            str(helper),
            _helper_params(staging, target, exe),
            str(helper.parent),
            1,  # SW_SHOWNORMAL
        )
    )


def launch_update_after_exit(staging_dir: str) -> None:
    """Start a breakaway cmd helper that waits for exit, copies staging, relaunches.

    Elevates the helper only when the install directory is not writable
    (e.g. custom install under Program Files). Does not use PowerShell.
    """
    staging = Path(staging_dir).resolve()
    if not staging.is_dir():
        raise FileNotFoundError(staging)

    target = install_dir()
    exe = app_executable()
    elevate = not dir_is_writable(target)
    helper = _write_update_helper(staging.parent)
    log_path = apply_helper_log_path()

    if elevate:
        logger.info(
            "Install dir %s is not writable; elevating update helper",
            target,
        )

    ret = _shell_execute_helper(
        helper, staging, target, exe, elevate=elevate
    )
    if ret <= 32:
        # Fallback: Popen with every detach flag we have (less reliable under jobs).
        logger.warning(
            "ShellExecute helper failed (%s); falling back to detached Popen",
            ret,
        )
        creationflags = (
            _CREATE_BREAKAWAY_FROM_JOB
            | _CREATE_NEW_PROCESS_GROUP
            | _CREATE_NEW_CONSOLE
            | _DETACHED_PROCESS
        )
        proc = subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                str(helper),
                str(os.getpid()),
                str(staging),
                str(target),
                str(exe),
            ],
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(helper.parent),
            start_new_session=True,
        )
        helper_ref: int | str = proc.pid
    else:
        helper_ref = ret

    logger.info(
        "Scheduled staging update after exit: %s -> %s (elevate=%s helper=%s log=%s)",
        staging,
        target,
        elevate,
        helper_ref,
        log_path,
    )
