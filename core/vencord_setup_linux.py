"""Linux port of scripts/vencord_setup/Install-AshenVencordBridge.ps1.

Same stages and JSON-style progress events as the PowerShell installer, so
VencordSetupDialog renders both. The last step depends on the Discord client:

- Official Discord (``/opt/discord`` from the Arch ``discord`` package, or the
  ``com.discordapp.Discord`` Flatpak): ``pnpm inject`` in a terminal. Both
  installs are root-owned, so the terminal asks for the sudo password. A
  package / Flatpak update removes the patch again; ``discord_patch_missing()``
  lets the hub offer a re-inject. The Flatpak sandbox also gets read access to
  ``<Vencord>/dist`` (``flatpak override``), or the patch cannot load it.
- Vesktop (package or Flatpak): point its Vencord location at ``<Vencord>/dist``.
  No root and nothing to redo after updates.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

VENCORD_REPO = "https://github.com/Vendicated/Vencord.git"
PLUGIN_REPO = "https://github.com/koetsmax/ashen-macros-vencord.git"
PLUGIN_FOLDER_NAME = "ashenMacrosBridge"

DISCORD_FLATPAK_ID = "com.discordapp.Discord"
OFFICIAL_DISCORD_DIRS = (
    "/opt/discord",
    "/usr/lib/discord",
    "/usr/share/discord",
    f"/var/lib/flatpak/app/{DISCORD_FLATPAK_ID}/current/active/files/discord",
    f"~/.local/share/flatpak/app/{DISCORD_FLATPAK_ID}/current/active/files/discord",
)
VESKTOP_FLATPAK_ID = "dev.vencord.Vesktop"

Emit = Callable[..., None]


class SetupError(RuntimeError):
    pass


# --- client detection -------------------------------------------------------


def official_discord_dir() -> Path | None:
    """Install dir of the official (system) Discord client, if present."""
    for raw in OFFICIAL_DISCORD_DIRS:
        path = Path(raw).expanduser()
        if (path / "resources").is_dir():
            return path
    return None


def _is_flatpak(discord_dir: Path) -> bool:
    return DISCORD_FLATPAK_ID in str(discord_dir)


def _grant_flatpak_dist_access(dist: Path, emit: Emit) -> None:
    """Let the Discord Flatpak sandbox read <Vencord>/dist (per-user override, no root)."""
    if shutil.which("flatpak") is None:
        emit("inject", "flatpak not found; could not give Discord access to the Vencord build.", ok=False)
        return
    proc = _run(
        ["flatpak", "override", "--user", DISCORD_FLATPAK_ID, f"--filesystem={dist}:ro"],
        timeout=30,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-300:]
        emit("inject", f"Could not give the Discord Flatpak access to {dist}: {detail}", ok=False)
        return
    emit("inject", f"Discord Flatpak can read {dist}.")


def discord_patch_missing() -> bool:
    """True when official Discord is installed but Vencord is not injected.

    The Vencord installer renames ``app.asar`` to ``_app.asar``; a ``discord``
    package update restores the original and drops the patch.
    """
    root = official_discord_dir()
    if root is None:
        return False
    return not (root / "resources" / "_app.asar").exists()


def _flatpak_vesktop_installed() -> bool:
    if shutil.which("flatpak") is None:
        return False
    try:
        proc = subprocess.run(
            ["flatpak", "info", VESKTOP_FLATPAK_ID],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except Exception:
        return False


def vesktop_settings_path() -> Path | None:
    """settings.json of an installed Vesktop (native first, then Flatpak)."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    if shutil.which("vesktop") is not None or (config_home / "vesktop").is_dir():
        return config_home / "vesktop" / "settings.json"
    if _flatpak_vesktop_installed():
        return (
            Path.home()
            / ".var"
            / "app"
            / VESKTOP_FLATPAK_ID
            / "config"
            / "vesktop"
            / "settings.json"
        )
    return None


def detected_clients() -> list[str]:
    """Human-readable list of Discord clients the setup will configure."""
    out: list[str] = []
    discord_dir = official_discord_dir()
    if discord_dir is not None:
        out.append("Discord (Flatpak)" if _is_flatpak(discord_dir) else "Discord")
    if vesktop_settings_path() is not None:
        out.append("Vesktop")
    return out


def _vesktop_running() -> bool:
    try:
        proc = subprocess.run(
            ["pgrep", "-if", "vesktop"], capture_output=True, text=True, timeout=5
        )
        return proc.returncode == 0
    except Exception:
        return False


# --- git / pnpm helpers -----------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None, timeout: float = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = _run(["git", "-C", str(path), *args])
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise SetupError(f"git {' '.join(args)} failed (exit {proc.returncode}) in {path}: {detail}")
    return proc


def _remote_ref(path: Path, fallbacks: tuple[str, ...]) -> str | None:
    up = _git(path, "rev-parse", "--abbrev-ref", "@{u}", check=False)
    if up.returncode == 0 and up.stdout.strip():
        return up.stdout.strip()
    for candidate in fallbacks:
        if _git(path, "rev-parse", "--verify", candidate, check=False).returncode == 0:
            return candidate
    return None


def _fast_forward(path: Path, ref: str, label: str, emit: Emit) -> None:
    # reset --hard only touches tracked files; nested userplugins clones survive.
    dirty = _git(path, "status", "--porcelain", check=False).stdout.strip()
    if dirty:
        count = len([line for line in dirty.splitlines() if line.strip()])
        emit(label, f"Discarding local changes in {count} tracked file(s) so update can proceed...")
        _git(path, "reset", "--hard", "HEAD")
    try:
        _git(path, "merge", "--ff-only", ref)
    except SetupError as exc:
        raise SetupError(
            f"Could not fast-forward {label} to {ref}. If this keeps failing, re-clone "
            f"or run Setup / Repair. Details: {exc}"
        ) from exc


def _clone(url: str, dest: Path, error: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(["git", "clone", url, str(dest)])
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[-300:]
        raise SetupError(f"{error} {detail}".strip())


def _ensure_vencord_repo(path: Path, pull: bool, emit: Emit) -> None:
    if not path.exists() or (path.is_dir() and not any(path.iterdir())):
        emit("vencord", f"Cloning Vencord into {path}...")
        _clone(VENCORD_REPO, path, "Failed to clone Vencord. Check your network and retry.")
        return
    if not (path / ".git").exists():
        raise SetupError(
            f"Path exists but is not a git repo: {path}. Choose an empty folder or an "
            "existing Vencord clone."
        )
    if not pull:
        emit("vencord", f"Using existing Vencord at {path}")
        return
    emit("vencord", "Updating Vencord (git fetch + pull)...")
    _git(path, "fetch", "--prune", "origin")
    ref = _remote_ref(path, ("origin/main", "origin/dev"))
    if ref:
        _fast_forward(path, ref, "vencord", emit)
    else:
        emit("vencord", "No remote tracking branch found; skipped pull.")
    branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
    sha = _git(path, "rev-parse", "--short", "HEAD", check=False).stdout.strip()
    emit("vencord", f"Vencord at {branch} ({sha})")


def _ensure_plugin_repo(vencord: Path, pull: bool, emit: Emit) -> Path:
    plugin = vencord / "src" / "userplugins" / PLUGIN_FOLDER_NAME
    if not plugin.exists():
        emit("plugin", f"Cloning AshenMacrosBridge into {plugin}...")
        _clone(
            PLUGIN_REPO,
            plugin,
            "Failed to clone the plugin repo. Sign in to GitHub (gh auth login or a git "
            "credential helper), make sure you can access koetsmax/ashen-macros-vencord, "
            "then retry.",
        )
        return plugin
    if not (plugin / ".git").exists():
        raise SetupError(
            f"Plugin folder exists but is not a git clone: {plugin}. Remove or rename it "
            "and re-run Setup so it can be cloned from GitHub."
        )
    if not pull:
        emit("plugin", f"Using existing plugin at {plugin}")
        return plugin
    emit("plugin", "Updating plugin (git fetch + pull)...")
    try:
        _git(plugin, "fetch", "--prune", "origin")
        ref = _remote_ref(plugin, ("origin/main", "origin/master"))
        if ref:
            _fast_forward(plugin, ref, "plugin", emit)
    except SetupError as exc:
        raise SetupError(
            "Failed to update the plugin repo. Sign in to GitHub (gh auth login) and "
            f"retry. {exc}"
        ) from exc
    return plugin


def _pnpm(path: Path, args: list[str], emit: Emit) -> None:
    emit("build", f"pnpm {' '.join(args)}...")
    proc = subprocess.Popen(
        ["pnpm", *args],
        cwd=str(path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    lines: list[str] = []
    for raw in proc.stdout:
        text = raw.strip()
        if not text:
            continue
        lines.append(text)
        emit("build", text)
    code = proc.wait()
    if code != 0:
        tail = " | ".join(lines[-12:]) or "(no output)"
        raise SetupError(f"pnpm {' '.join(args)} failed (exit {code}). Last output: {tail}")


def _plugin_version(plugin: Path) -> str | None:
    try:
        data = json.loads((plugin / "package.json").read_text(encoding="utf-8"))
        return str(data.get("version") or "").strip() or None
    except Exception:
        return None


# --- client hookup ----------------------------------------------------------


def _configure_vesktop(settings: Path, dist: Path, emit: Emit) -> None:
    if _vesktop_running():
        emit(
            "inject",
            "Vesktop is running. Close it, then in Vesktop Settings set the Vencord "
            f"location to {dist} (or re-run Setup with Vesktop closed).",
            ok=False,
        )
        return
    data: dict = {}
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8")) or {}
        except Exception:
            raise SetupError(f"Could not read Vesktop settings at {settings}") from None
    if data.get("vencordDir") == str(dist):
        emit("inject", f"Vesktop already loads Vencord from {dist}.")
        return
    data["vencordDir"] = str(dist)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=4), encoding="utf-8")
    emit("inject", f"Vesktop now loads Vencord from {dist}. Restart Vesktop to load it.")


def _terminal_command(script: Path) -> list[str] | None:
    """Command that runs *script* in a visible terminal and waits for it to close."""
    if shutil.which("konsole"):
        return ["konsole", "--nofork", "-e", "bash", str(script)]
    if shutil.which("gnome-terminal"):
        return ["gnome-terminal", "--wait", "--", "bash", str(script)]
    for term in ("x-terminal-emulator", "xterm", "alacritty", "kitty", "foot"):
        if shutil.which(term):
            return [term, "-e", "bash", str(script)]
    return None


def _inject_official(vencord: Path, discord_dir: Path, emit: Emit) -> None:
    resources = discord_dir / "resources"
    needs_root = not os.access(resources, os.W_OK)
    emit(
        "inject",
        "Opening a terminal for the Vencord Installer (arrow keys + Enter). "
        + ("It asks for your password because Discord is installed system-wide. " if needs_root else "")
        + (f"Pick the Flatpak install ({discord_dir}). " if _is_flatpak(discord_dir) else "")
        + "Patch Discord, then close that terminal when finished...",
    )
    inject = "pnpm inject"
    if needs_root:
        # Keep the user's PATH (pnpm/node) and HOME; SUDO_USER lets the installer
        # find the right user's Discord settings.
        inject = 'sudo env "PATH=$PATH" "HOME=$HOME" "SUDO_USER=$USER" pnpm inject'
    script_text = f"""#!/usr/bin/env bash
cd {shlex.quote(str(vencord))} || exit 1
echo
echo "Ashen Macros - Vencord Installer"
echo "Use arrow keys to select Discord, Enter to patch, then close this window."
echo
{inject}
code=$?
if [ "$code" -ne 0 ]; then
    echo
    echo "pnpm inject exited with code $code"
    read -r -p "Press Enter to close..." _
fi
exit "$code"
"""
    fd, tmp = tempfile.mkstemp(prefix="ashen-vencord-inject-", suffix=".sh")
    script = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(script_text)
        os.chmod(script, 0o700)
        cmd = _terminal_command(script)
        if cmd is None:
            raise SetupError(
                f"No terminal emulator found. Run 'sudo pnpm inject' in {vencord} yourself."
            )
        code = subprocess.call(cmd)
        if code != 0:
            emit(
                "inject",
                f"Vencord Installer exited with code {code}. If Discord was not patched, "
                "run Setup again.",
                ok=False,
            )
        elif discord_patch_missing():
            emit(
                "inject",
                "The terminal closed but Discord does not look patched yet. If you "
                "skipped it, run Setup again.",
                ok=False,
            )
        else:
            emit("inject", "Vencord Installer finished.")
    finally:
        try:
            script.unlink()
        except OSError:
            pass


# --- entry point ------------------------------------------------------------


def run(action: str, vencord_path: str, *, skip_inject: bool, emit: Emit) -> str | None:
    """Run install/update. Returns the plugin version; raises SetupError on failure."""
    path = Path(vencord_path).expanduser().resolve()
    emit("start", f"Action={action} path={path}")

    missing = [name for name in ("git", "node", "pnpm") if shutil.which(name) is None]
    if missing:
        raise SetupError(
            f"Missing: {', '.join(missing)}. Install them with "
            "'sudo pacman -S --needed git nodejs pnpm' (or your distro's packages), "
            "then retry."
        )

    if action in ("updatePlugin", "updateVencord") and not path.exists():
        raise SetupError(f"Vencord path not found: {path}. Run Setup / Repair first.")

    _ensure_vencord_repo(path, action in ("install", "update", "updateVencord"), emit)
    plugin = _ensure_plugin_repo(path, action in ("install", "update", "updatePlugin"), emit)

    _pnpm(path, ["install", "--frozen-lockfile"], emit)
    _pnpm(path, ["build"], emit)

    dist = path / "dist"
    vesktop = vesktop_settings_path()
    discord_dir = official_discord_dir()
    if vesktop is not None:
        _configure_vesktop(vesktop, dist, emit)

    do_inject = not skip_inject and discord_dir is not None
    if do_inject and action == "updatePlugin" and not discord_patch_missing():
        do_inject = False
        emit("inject", "Skipped inject (plugin-only update). Fully restart Discord to load the new build.")
    if do_inject and action == "update" and not discord_patch_missing():
        # Already patched: the patch loads <Vencord>/dist, so a rebuild is enough.
        do_inject = False
        emit("inject", "Discord is already patched. Fully restart Discord to load the new build.")
    if discord_dir is None and vesktop is None:
        raise SetupError(
            "No Discord client found (/opt/discord, the Discord Flatpak or Vesktop). "
            "Vencord was built but not installed into anything. Install a client, then "
            "run Setup again."
        )
    if discord_dir is not None and _is_flatpak(discord_dir):
        _grant_flatpak_dist_access(dist, emit)
    if do_inject:
        _inject_official(path, discord_dir, emit)

    emit("post", "next_steps")
    version = _plugin_version(plugin)
    emit("done", "Done.", action=action, vencord_path=str(path), plugin_version=version)
    return version
