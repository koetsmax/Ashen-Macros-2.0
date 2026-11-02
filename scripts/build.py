"""Build the PyInstaller app and its update archive for this OS.

  python scripts/build.py [--clean] [--version 2026.43]

Windows: dist/Ashen Macros/ + dist/Ashen-Macros-<version>.zip (same output as
build.ps1 + build-zip.ps1, which CI still uses).
Linux:   dist/ashen-macros/ + dist/Ashen-Macros-<version>-linux-x86_64.tar.gz,
with install.sh / uninstall.sh at the top of the tarball's folder.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from get_version import read_version  # noqa: E402

IS_WINDOWS = sys.platform == "win32"
APP_NAME = "Ashen Macros" if IS_WINDOWS else "ashen-macros"
EXE_NAME = "Ashen Macros.exe" if IS_WINDOWS else "ashen-macros"


def run_pyinstaller(clean: bool) -> Path:
    dist_app = REPO_ROOT / "dist" / APP_NAME
    if clean:
        shutil.rmtree(REPO_ROOT / "build", ignore_errors=True)
        shutil.rmtree(dist_app, ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(REPO_ROOT / "launcher.spec"), "--noconfirm"],
        cwd=REPO_ROOT,
        check=True,
    )
    exe = dist_app / EXE_NAME
    if not exe.is_file():
        raise SystemExit(f"Expected PyInstaller output missing: {exe}")
    print(f"Built {exe}")
    return dist_app


def make_zip(dist_app: Path, version: str) -> Path:
    out = REPO_ROOT / "dist" / f"Ashen-Macros-{version}.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(dist_app.rglob("*")):
            zf.write(path, path.relative_to(dist_app))
    return out


def make_tarball(dist_app: Path, version: str) -> Path:
    for name in ("install.sh", "uninstall.sh"):
        target = dist_app / name
        shutil.copy2(REPO_ROOT / "installer" / "linux" / name, target)
        target.chmod(0o755)
    out = REPO_ROOT / "dist" / f"Ashen-Macros-{version}-linux-x86_64.tar.gz"
    out.unlink(missing_ok=True)
    with tarfile.open(out, "w:gz") as tf:
        tf.add(dist_app, arcname=dist_app.name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean", action="store_true", help="remove build/ and the old dist app first")
    parser.add_argument("--version", default="", help="defaults to the repo version file")
    args = parser.parse_args()

    version = args.version.strip() or read_version()
    print(f"Building version {version}")
    dist_app = run_pyinstaller(args.clean)
    archive = make_zip(dist_app, version) if IS_WINDOWS else make_tarball(dist_app, version)
    print(f"Created {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
