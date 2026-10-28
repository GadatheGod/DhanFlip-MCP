# DhanFlip V3: Cache-only MCP and OpenAI Tunnel

**These are separate processes.** GUI Scanner → SQLite cache → local MCP → tunnel-client → authorized ChatGPT connector. No Dhan REST calls originate from MCP and no broker order mutations exist.

## Setup

1. Open DhanFlip GUI and **Start Scanner** (DEMO at first). The scanner records results in `data/market_data.sqlite`.
2. Click **Start MCP**; endpoint is `http://127.0.0.1:8766/mcp` (loopback only). Check `logs/mcp.log` if not running.
3. Obtain your own [OpenAI tunnel-client](https://github.com/openai/tunnel-client) binary, tunnel registration ID, and runtime API key. The ChatGPT app/connector must also be installed/authorized in ChatGPT. Do not confuse this with the Dhan data API.
4. Copy `config/tunnel.example.yaml` to **`config/tunnel.local.yaml`**, replace the dummy tunnel ID with your own. Never put the actual API key in this YAML. If you have another existing tunnel-client instance running, choose an unused admin port (the sample uses 8082).
5. GUI → **Configure Tunnel** → select executable and `config/tunnel.local.yaml`. Enter the CONTROL_PLANE_API_KEY once; it is stored in ignored `.env.tunnel`, protected with chmod 600 on Linux.
6. Click **Connect ChatGPT**, which starts MCP then the tunnel-client subprocess. Examine diagnostics and `http://127.0.0.1:8082/readyz` or `/ui` (adjust if your YAML differs).
7. Go to ChatGPT Settings → Plugins/Apps and complete the specific MCP registration/authorization for this tunnel. Runtime readiness **does not guarantee** a registered or authorized ChatGPT app.

The GUI intentionally refuses any YAML profile whose `mcp.server_urls` has no `main` entry pointing to **exactly** `http://127.0.0.1:8766/mcp`. This prevents accidental rerouting of the user's existing ArtCraft/CraftApps tools.

**Security model:** `tunnel-client` receives only its own runtime key; MCP reads the SQLite cache; the Dhan token stays in the GUI scanner process. Do not expose the local endpoint to the internet directly or bind it to a public interface. Data from the scanner may be forwarded to ChatGPT after connector authorization; do not publish sensitive positions or account data through public repositories.

## Provided MCP tool names

- `connection_status` — scanner / mode / freshness / counters
- `monitored_contracts` — monitored option universe
- `active_signals` — recent qualifying completed-bar signals, always inspect risk flags
- `all_contract_status` — last indicator values, rejections, stale/errors
- `analyze_contract` — one contract by exact key
- `recent_signal_history` — journal of previously generated strategy signals
- `manual_trade_journal` — user-reported trades only, not Dhan verified fills
- `request_scan_info` — how to refresh safely from the GUI

## Diagnostics

- MCP process running only: confirms local service, not external ChatGPT access.
- `127.0.0.1:8766` busy and not owned by this GUI: do **not** automatically forward it; inspect/stop other service.
- Tunnel health 200 but readyz not 200: check YAML, runtime key, tunnel registration, control-plane and server logs.
- Tunnel readyz 200 but ChatGPT cannot call tools: complete ChatGPT connector authorization/permissions; examine tunnel admin UI.
- Dhan `429`: pause other scripts sharing the account API quota; DhanFlip rate-limits only its own process.

No installed app/tool access was verified against your personal account as part of producing this source distribution.
