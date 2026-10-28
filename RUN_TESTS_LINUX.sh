#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
. .venv/bin/activate
python -m pytest -q
