#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
mkdir -p logs
if [ ! -x .venv/bin/python ]; then
  echo 'Install once using: bash INSTALL_LINUX.sh' >&2
  exit 1
fi
# Redirect fatal startup errors for desktop launches.
exec .venv/bin/python -m dhanflip gui 2>>logs/gui.log
