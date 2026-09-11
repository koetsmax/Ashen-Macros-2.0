"""Vencord + AshenMacrosBridge install/update helpers for Ashen Macros."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests
from packaging import version as pkg_version

from core.settings import config_bool, read_config, set_custom_value

logger = logging.getLogger(__name__)

PLUGIN_GITHUB_REPO = "koetsmax/ashen-macros-vencord"
PLUGIN_FOLDER_NAME = "ashenMacrosBridge"
PLUGIN_PACKAGE_URL = (
    f"https://api.github.com/repos/{PLUGIN_GITHUB_REPO}/contents/package.json"
)
VENCORD_DOCS_URL = "https://docs.vencord.dev/installing/"
DEFAULT_PORT = 47832
# Permission key for Setup / Repair / Update (also unlocked by administrator).
VENCORD_SETUP_PERMISSION = "vencord_setup"
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

ProgressCallback = Callable[[dict], None]


def can_manage_vencord_setup(permissions: list[str] | None) -> bool:
    """True if the user may run Vencord install / update from macros."""
    perms = set(permissions or [])
    return VENCORD_SETUP_PERMISSION in perms or "administrator" in perms


def default_vencord_path() -> str:
    return str(Path.home() / "Documents" / "Vencord")


def vencord_install_path() -> str:
    raw = (read_config().get("vencord_install_path") or "").strip()
    if raw:
        return os.path.normpath(raw)
    return default_vencord_path()


def set_vencord_install_path(path: str) -> None:
    set_custom_value("EXPERIMENTAL", "vencord_install_path", os.path.normpath(path))


def auto_update_check_enabled() -> bool:
    """Default on when unset; respect explicit false."""
    cfg = read_config()
    if "vencord_auto_update_check" not in cfg:
        return True
    return config_bool("vencord_auto_update_check", "true")


def script_path() -> Path:
    """Resolve Install-AshenVencordBridge.ps1 for dev and frozen builds."""
    name = "Install-AshenVencordBridge.ps1"
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "scripts" / "vencord_setup" / name)
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "scripts" / "vencord_setup" / name)
        candidates.append(exe_dir / "_internal" / "scripts" / "vencord_setup" / name)
    # Dev: repo root / scripts / …
    here = Path(__file__).resolve()
    candidates.append(here.parent.parent / "scripts" / "vencord_setup" / name)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Install-AshenVencordBridge.ps1 not found. Reinstall Ashen Macros or run from the repo."
    )


def plugin_dir(vencord_path: str | None = None) -> Path:
    root = Path(vencord_path or vencord_install_path())
    return root / "src" / "userplugins" / PLUGIN_FOLDER_NAME


def read_local_plugin_version(vencord_path: str | None = None) -> str | None:
    pkg = plugin_dir(vencord_path) / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        ver = str(data.get("version") or "").strip()
        return ver or None
    except Exception:
        logger.exception("Failed reading local plugin package.json")
        return None


def _parse_version(value: str | None) -> pkg_version.Version | None:
    if not value:
        return None
    try:
        return pkg_version.parse(str(value).strip())
    except Exception:
        return None


def _version_outdated(current: str | None, latest: str | None) -> bool:
    cur = _parse_version(current)
    lat = _parse_version(latest)
    if cur is None or lat is None:
        return bool(latest and current and latest != current)
    return lat > cur


def fetch_remote_plugin_version(
    timeout: float = 12.0,
    *,
    vencord_path: str | None = None,
) -> str | None:
    """Latest plugin version from GitHub package.json (main), or local git remote."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Ashen-Macros-Vencord-Setup",
    }
    try:
        resp = requests.get(PLUGIN_PACKAGE_URL, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            body = resp.json()
            content = body.get("content")
            if content:
                raw = base64.b64decode(content).decode("utf-8")
                data = json.loads(raw)
                ver = str(data.get("version") or "").strip()
                if ver:
                    return ver
        else:
            logger.info(
                "GitHub package.json fetch status=%s (private repo may need git fallback)",
                resp.status_code,
            )
    except Exception:
        logger.debug("GitHub API plugin version fetch failed", exc_info=True)

    # Fallback: git show origin/main:package.json in local plugin clone
    pdir = plugin_dir(vencord_path)
    if not (pdir / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(pdir), "fetch", "--prune", "origin"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=_CREATE_NO_WINDOW,
        )
        if proc.returncode != 0:
            logger.debug("git fetch plugin failed: %s", (proc.stderr or "")[-400:])
    except Exception:
        logger.debug("git fetch plugin failed", exc_info=True)
    for ref in ("origin/main", "origin/master"):
        try:
            show = subprocess.run(
                ["git", "-C", str(pdir), "show", f"{ref}:package.json"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=_CREATE_NO_WINDOW,
            )
            if show.returncode == 0 and show.stdout.strip():
                data = json.loads(show.stdout)
                ver = str(data.get("version") or "").strip()
                if ver:
                    return ver
        except Exception:
            logger.debug("git show plugin package.json failed for %s", ref, exc_info=True)
    return None


def _git_vencord_behind(vencord_path: str, timeout: float = 90.0) -> tuple[int | None, str | None]:
    """Return (commits_behind, short_sha)."""
    root = Path(vencord_path)
    if not (root / ".git").is_dir():
        return None, None
    try:
        sha_p = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )
        sha = sha_p.stdout.strip() if sha_p.returncode == 0 else None
        subprocess.run(
            ["git", "-C", str(root), "fetch", "--prune", "origin"],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        ref = None
        up = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "@{u}"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )
        if up.returncode == 0 and up.stdout.strip():
            ref = up.stdout.strip()
        else:
            for candidate in ("origin/main", "origin/dev"):
                chk = subprocess.run(
                    ["git", "-C", str(root), "rev-parse", "--verify", candidate],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=_CREATE_NO_WINDOW,
                )
                if chk.returncode == 0:
                    ref = candidate
                    break
        if not ref:
            return None, sha
        behind_p = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", f"HEAD..{ref}"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=_CREATE_NO_WINDOW,
        )
        if behind_p.returncode == 0 and re.fullmatch(r"\d+", behind_p.stdout.strip()):
            return int(behind_p.stdout.strip()), sha
        return None, sha
    except Exception:
        logger.debug("Vencord git behind check failed", exc_info=True)
        return None, None


@dataclass
class UpdateCheckResult:
    plugin_update_available: bool = False
    vencord_update_available: bool = False
    local_plugin_version: str | None = None
    remote_plugin_version: str | None = None
    connected_plugin_version: str | None = None
    vencord_sha: str | None = None
    vencord_behind: int | None = None
    vencord_path: str = ""
    installed: bool = False
    error: str | None = None
    message: str = ""

    @property
    def any_update(self) -> bool:
        return self.plugin_update_available or self.vencord_update_available


def check_updates(*, vencord_path: str | None = None) -> UpdateCheckResult:
    """Compare local/connected plugin + Vencord git vs remotes (no install)."""
    path = os.path.normpath(vencord_path or vencord_install_path())
    result = UpdateCheckResult(vencord_path=path)
    result.installed = Path(path).is_dir() and (Path(path) / "src").is_dir()

    try:
        from core.discord_bridge import bridge_plugin_version, is_connected, is_enabled

        if is_enabled() and is_connected():
            result.connected_plugin_version = bridge_plugin_version() or None
    except Exception:
        logger.debug("Could not read connected bridge version", exc_info=True)

    result.local_plugin_version = read_local_plugin_version(path)
    current_plugin = result.connected_plugin_version or result.local_plugin_version

    try:
        result.remote_plugin_version = fetch_remote_plugin_version(vencord_path=path)
    except Exception as exc:
        logger.debug("Remote plugin version failed: %s", exc)

    plugin_pkg = plugin_dir(path) / "package.json"
    if result.remote_plugin_version and current_plugin:
        result.plugin_update_available = _version_outdated(
            current_plugin, result.remote_plugin_version
        )
    elif (
        result.installed
        and result.remote_plugin_version
        and not current_plugin
        and not plugin_pkg.is_file()
    ):
        # Tree exists but plugin is missing — treat as needs install/update.
        result.plugin_update_available = True

    behind, sha = _git_vencord_behind(path)
    result.vencord_behind = behind
    result.vencord_sha = sha
    if behind is not None and behind > 0:
        result.vencord_update_available = True

    parts: list[str] = []
    if not result.installed:
        parts.append("Vencord not installed at this path - use Setup / Repair.")
    else:
        if result.plugin_update_available:
            if not current_plugin and not plugin_pkg.is_file():
                parts.append(
                    f"Plugin missing (remote {result.remote_plugin_version}) - run Setup"
                )
            else:
                parts.append(
                    f"Plugin update: {current_plugin or '?'} -> {result.remote_plugin_version}"
                )
        elif current_plugin:
            parts.append(f"Plugin up to date ({current_plugin})")
        if result.vencord_update_available:
            parts.append(f"Vencord behind by {result.vencord_behind} commit(s)")
        elif result.vencord_sha:
            parts.append(f"Vencord current ({result.vencord_sha})")
    result.message = " | ".join(parts) if parts else "Status unknown"
    return result


@dataclass
class RunResult:
    ok: bool
    returncode: int
    events: list[dict] = field(default_factory=list)
    error: str | None = None
    plugin_version: str | None = None


def run_action(
    action: str,
    *,
    vencord_path: str | None = None,
    skip_inject: bool = False,
    on_event: ProgressCallback | None = None,
    timeout: float | None = None,
) -> RunResult:
    """Run the PowerShell installer. Streams JSON progress lines to on_event."""
    if sys.platform != "win32":
        return RunResult(
            ok=False,
            returncode=1,
            error="Vencord setup is only supported on Windows.",
        )

    try:
        ps1 = script_path()
    except FileNotFoundError as exc:
        return RunResult(ok=False, returncode=1, error=str(exc))

    path = os.path.normpath(vencord_path or vencord_install_path())
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-Action",
        action,
        "-VencordPath",
        path,
    ]
    if skip_inject:
        cmd.append("-SkipInject")

    logger.info("Running Vencord setup: action=%s path=%s", action, path)
    events: list[dict] = []
    error_msg: str | None = None
    plugin_ver: str | None = None

    # Avoid CREATE_NO_WINDOW / CREATE_NEW_CONSOLE with a piped stdout: the former
    # can block winget/inject UI on some setups; the latter can send output to a
    # detached console instead of our pipe. Default flags + PIPE keeps JSON
    # streaming to the Qt dialog while child GUIs (inject) still appear.
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        logger.exception("Failed to start PowerShell installer")
        return RunResult(ok=False, returncode=1, error=str(exc))

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        event: dict | None = None
        if line.startswith("{") and line.endswith("}"):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"stage": "log", "message": line, "ok": True}
        else:
            event = {"stage": "log", "message": line, "ok": True}
        events.append(event)
        if event.get("stage") == "error":
            error_msg = str(event.get("message") or error_msg)
        if event.get("plugin_version"):
            plugin_ver = str(event.get("plugin_version"))
        if on_event is not None:
            try:
                on_event(event)
            except Exception:
                logger.debug("on_event callback failed", exc_info=True)

    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return RunResult(
            ok=False,
            returncode=1,
            events=events,
            error="Installer timed out.",
            plugin_version=plugin_ver,
        )

    ok = code == 0
    if code != 0 and not error_msg:
        error_msg = f"Installer exited with code {code}"
        for e in reversed(events):
            if e.get("stage") == "error":
                error_msg = str(e.get("message") or error_msg)
                break

    return RunResult(
        ok=ok,
        returncode=code,
        events=events,
        error=None if ok else error_msg,
        plugin_version=plugin_ver or read_local_plugin_version(path),
    )


def run_action_async(
    action: str,
    *,
    vencord_path: str | None = None,
    skip_inject: bool = False,
    on_event: ProgressCallback | None = None,
    on_done: Callable[[RunResult], None] | None = None,
) -> threading.Thread:
    def _worker() -> None:
        try:
            result = run_action(
                action,
                vencord_path=vencord_path,
                skip_inject=skip_inject,
                on_event=on_event,
            )
        except Exception as exc:
            logger.exception("Vencord setup worker crashed")
            result = RunResult(ok=False, returncode=1, error=str(exc))
        if on_done is not None:
            try:
                on_done(result)
            except Exception:
                logger.exception("Vencord setup on_done failed")

    thread = threading.Thread(target=_worker, name=f"vencord-setup-{action}", daemon=True)
    thread.start()
    return thread
