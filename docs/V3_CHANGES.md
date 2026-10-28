# V3 changes over V2

- Full unified Tk GUI with Strategy & Risk Settings / Diagnostics tabs.
- Start/Stop local MCP remains separate from Dhan connection.
- Dedicated Configure Tunnel / Connect ChatGPT / Stop Tunnel controls; the tunnel uses an existing OpenAI `tunnel-client` binary/profile.
- `tunnel.py` manages local runtime key without putting it in YAML/command arguments and refuses misrouted MCP main targets.
- Local tunnel admin health/readyz checks; no incorrect claim that a tunnel proves ChatGPT authorization.
- Per-user Windows PowerShell installer (Python venv, dependencies, Start Menu & Desktop shortcuts) and Linux graphical menu installer.
- Conservative 3m candle cache and global process rate limiter retained from V2.
- Separate new-entry cutoff safety check for live recommendations while original raw signals remain preserved.
- GitHub CI for 2 operating systems and 2 Python versions, no secrets in repo.
- Publication scripts for GitHub CLI (not automatically run).
- Read-only Dhan instrument scanner, manual journal, cached MCP remain unchanged in design.
