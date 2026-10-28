#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
APPDIR="$(pwd)"
python3 -c 'import tkinter' || { echo 'Please install Python tkinter e.g. sudo apt install python3-tk'; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/dhanflip-v3.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=DhanFlip V3 - Options Terminal
Comment=NIFTY & SENSEX 3-minute options scanner (read-only)
Exec=/bin/bash "$APPDIR/START_LINUX.sh"
Path=$APPDIR
Terminal=false
Categories=Office;Finance;
StartupNotify=true
EOF
chmod +x "$HOME/.local/share/applications/dhanflip-v3.desktop" START_LINUX.sh
printf 'Installed DhanFlip V3. Launch it from the Applications menu.\n'
