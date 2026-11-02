#!/usr/bin/env bash
# Remove the per-user Ashen Macros install. Settings (~/.config/ashen-macros)
# and logs (~/.local/state/ashen-macros) are kept; delete them by hand if wanted.
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

rm -rf "$DATA_HOME/ashen-macros"
rm -f "$HOME/.local/bin/ashen-macros"
rm -f "$DATA_HOME/applications/ashen-macros.desktop"
rm -f "$DATA_HOME/icons/hicolor/256x256/apps/ashen-macros.png"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DATA_HOME/applications" || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true

echo "Ashen Macros removed. Settings and logs were kept."
