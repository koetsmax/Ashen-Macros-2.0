"""Zip-based in-app updater with conditional elevation for protected install dirs."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import requests

GITHUB_DOWNLOAD_BASE = "https://github.com/koetsmax/Ashen-Macros-2.0/releases/download"


def install_dir() -> Path:
    """Directory that contains the frozen app (launcher.exe + _internal)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def app_executable() -> Path:
    if getattr(sys, "frozen", False):
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


def download_update_zip(
    online_version: str,
    dest_dir: Path | None = None,
    *,
    release_tag: str | None = None,
) -> Path:
    dest_root = dest_dir or Path(tempfile.gettempdir()) / "AshenMacrosUpdates"
    dest_root.mkdir(parents=True, exist_ok=True)
    zip_path = dest_root / zip_asset_name(online_version)
    # GitHub asset URLs use the git tag (often vYYYY.WW), not the release display name.
    tag = release_tag or online_version
    url = f"{GITHUB_DOWNLOAD_BASE}/{tag}/{zip_asset_name(online_version)}"
    response = requests.get(url, allow_redirects=True, timeout=120)
    response.raise_for_status()
    zip_path.write_bytes(response.content)
    return zip_path


UPDATE_HELPER_PS1 = r"""param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$AppExe
)

$ErrorActionPreference = "Stop"

# Wait for the main app to exit so files are unlocked.
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 120) {
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction Stop
        if ($null -eq $proc) { break }
        Start-Sleep -Milliseconds 250
    } catch {
        break
    }
}

$staging = Join-Path $env:TEMP ("AshenMacrosUpdate_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $staging -Force

    # Support zips that contain either flat contents or a single top-level folder.
    $payload = $staging
    $children = Get-ChildItem -LiteralPath $staging
    if (($children.Count -eq 1) -and $children[0].PSIsContainer) {
        $payload = $children[0].FullName
    }

    Copy-Item -Path (Join-Path $payload "*") -Destination $InstallDir -Recurse -Force
} finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $AppExe) {
    Start-Process -FilePath $AppExe
}
"""


def write_update_helper(dest_dir: Path | None = None) -> Path:
    dest_root = dest_dir or Path(tempfile.gettempdir()) / "AshenMacrosUpdates"
    dest_root.mkdir(parents=True, exist_ok=True)
    helper_path = dest_root / "apply_update.ps1"
    helper_path.write_text(UPDATE_HELPER_PS1, encoding="UTF-8")
    return helper_path


def _powershell_command(helper: Path, zip_path: Path, target_dir: Path, exe: Path) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(helper),
        "-ProcessId",
        str(os.getpid()),
        "-ZipPath",
        str(zip_path),
        "-InstallDir",
        str(target_dir),
        "-AppExe",
        str(exe),
    ]


def launch_update_helper(zip_path: Path, elevate: bool) -> None:
    helper = write_update_helper(zip_path.parent)
    target = install_dir()
    exe = app_executable()
    command = _powershell_command(helper, zip_path, target, exe)

    if elevate and os.name == "nt":
        # Elevate only the helper, not the whole app.
        ps_args = " ".join(
            [
                "-NoProfile",
                "-ExecutionPolicy Bypass",
                f'-File "{helper}"',
                f"-ProcessId {os.getpid()}",
                f'-ZipPath "{zip_path}"',
                f'-InstallDir "{target}"',
                f'-AppExe "{exe}"',
            ]
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f'Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList \'{ps_args}\'',
            ],
            close_fds=True,
        )
        return

    subprocess.Popen(command, close_fds=True)


def commence_zip_update(online_version: str, release_tag: str | None = None) -> None:
    """Download the release zip and apply it via helper (elevating only if needed)."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Zip updates are only supported for packaged builds.")

    zip_path = download_update_zip(online_version, release_tag=release_tag)
    elevate = not dir_is_writable(install_dir())
    launch_update_helper(zip_path, elevate=elevate)
