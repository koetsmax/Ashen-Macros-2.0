#!/usr/bin/env bash
# Ashen Macros per-user install for Linux (no sudo).
#
# Run from the extracted release tarball:
#   tar xzf Ashen-Macros-<version>-linux-x86_64.tar.gz
#   ./ashen-macros/install.sh
#
# Installs to ~/.local/share/ashen-macros/app, which the user owns, so in-app
# updates can swap it without a password. The launcher symlink and .desktop
# file point at that stable path and keep working after every update.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ROOT="$DATA_HOME/ashen-macros"
APP="$ROOT/app"
BIN_DIR="$HOME/.local/bin"
EXE_NAME="ashen-macros"

if [ ! -x "$SRC/$EXE_NAME" ] && [ ! -f "$SRC/$EXE_NAME" ]; then
    echo "error: $SRC/$EXE_NAME not found; run install.sh from the extracted tarball" >&2
    exit 1
fi

if [ "$SRC" != "$APP" ]; then
    echo "Installing to $APP"
    mkdir -p "$ROOT"
    rm -rf "$APP.new"
    cp -a "$SRC" "$APP.new"
    rm -rf "$APP" "$APP.old"
    mv "$APP.new" "$APP"
fi
chmod +x "$APP/$EXE_NAME"

mkdir -p "$BIN_DIR"
ln -sfn "$APP/$EXE_NAME" "$BIN_DIR/$EXE_NAME"

ICON_SRC="$APP/_internal/images/ashen-macros-256.png"
if [ -f "$ICON_SRC" ]; then
    install -Dm644 "$ICON_SRC" "$DATA_HOME/icons/hicolor/256x256/apps/ashen-macros.png"
fi

DESKTOP="$DATA_HOME/applications/ashen-macros.desktop"
mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Ashen Macros
Comment=Ashen Alliance staff tools
Exec="$APP/$EXE_NAME"
Icon=ashen-macros
Terminal=false
Categories=Utility;Network;
StartupWMClass=ashen-macros
DESKTOP_EOF

# Refresh menus / icon caches when the tools exist (KDE, GNOME, others).
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DATA_HOME/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$DATA_HOME/icons/hicolor" || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true

echo "Installed Ashen Macros. Start it from the app menu or run: $EXE_NAME"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "note: $BIN_DIR is not on your PATH; add it to run '$EXE_NAME' from a terminal." ;;
esac
