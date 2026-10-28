#!/usr/bin/env bash
# User-initiated publishing. Never automatically uploads secrets or local market data.
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
REPO="${DHANFLIP_GITHUB_REPO:-GadatheGod/DhanFlip-MCP}"
command -v git >/dev/null || { echo 'Install git'; exit 1; }
command -v gh >/dev/null || { echo 'Install GitHub CLI (gh) and run gh auth login'; exit 1; }
[ ! -f .env ] || echo 'Local .env present: ignored by .gitignore.'
[ ! -f .env.tunnel ] || echo 'Local tunnel key present: ignored by .gitignore.'
if [ ! -d .git ]; then git init -b main; fi
# Explicit allowlist. Never git add -A with local files.
git add .github README.md LICENSE.txt .gitignore .env.example requirements.txt pytest.ini dhanflip config/settings.yaml config/tunnel.example.yaml \
  docs tests original_strategy START_WINDOWS.bat INSTALL_WINDOWS.cmd INSTALL_WINDOWS.ps1 INSTALL_LINUX.sh START_LINUX.sh RUN_TESTS.bat RUN_TESTS_LINUX.sh PUBLISH_GITHUB.sh PUBLISH_GITHUB_WINDOWS.ps1
if git diff --cached --quiet; then echo 'Nothing to commit.'; else git commit -m 'DhanFlip V3: unified read-only options terminal'; fi
if ! gh repo view "$REPO" >/dev/null 2>&1; then
    gh repo create "$REPO" --private --description 'DhanFlip V3: NIFTY/SENSEX 3-minute options trading signals (read-only)'
fi
if ! git remote get-url origin >/dev/null 2>&1; then git remote add origin "https://github.com/$REPO.git"; fi
git push -u origin main
printf 'Pushed to https://github.com/%s\n' "$REPO"
