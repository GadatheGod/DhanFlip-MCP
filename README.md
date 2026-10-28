CAUTION / DISCLAIMER : USE AT YOUR OWN RISK . I AM NOT RESPONSIBLE FOR ANY TRADING LOSSES ARISING OUT OF IT. THIS IS FOR EDUCATIONAL PURPOSE ONLY. 

# DhanFlip V3 — NIFTY/SENSEX Options Scanner + Optional ChatGPT MCP

**Windows + Linux · one-click desktop launch after initial setup · 3-minute option-premium charts · DhanHQ paid data · local SQLite cache · manual execution only.**

This software is an **advisory scanner, NOT an order execution engine**. There are **no Dhan order, modify, cancel or automated stop-loss submission functions** in this project. The strategy can generate a BUY signal on a CE or a PE premium chart; SHORT is disabled by default, exactly as in the user-supplied Pine settings. TradingView is not used.

The original `Nifty/Sensex Flip 2026` Pine Script v6 is retained in `original_strategy/`. The Python implementation in `dhanflip/strategy.py` reproduces the rule structure, but live-equivalence to every Pine/TradingView numerical and backtest detail is **not guaranteed**; see `docs/VERIFICATION.md`.

## QUICK INSTALL

### Windows 10/11 (64-bit)

1. Install **Python 3.11 or 3.12 (64-bit)** and enable Python launcher (`py`). Internet is needed on first setup.
2. Extract the release ZIP into a **permanent** folder, e.g. `C:\DhanFlip_V3` (do not move it after creating shortcuts).
3. **Double-click `INSTALL_WINDOWS.cmd` once.** It creates a local `.venv`, installs Python requirements, tests imports and creates **Desktop + Start Menu shortcuts** in your current user account (no administrator rights required).
4. Thereafter double-click **DhanFlip V3** on Desktop (or in Start Menu).
5. Alternative: run `START_WINDOWS.bat`; tests: `RUN_TESTS.bat`.

The installer is a **source/venv installer** (Python remains required), not a compiled `.exe` or an MSI. It creates shortcuts but does not install to Program Files.

### Ubuntu / Linux Mint / Debian (X11 or desktop environment with Tk support)

```bash
sudo apt install python3-tk python3-venv
cd /path/to/DhanFlip_MCP_V3
bash INSTALL_LINUX.sh
```

Then open **DhanFlip V3 - Options Terminal** from your Applications menu. Alternative: `bash START_LINUX.sh`.

On Wayland, Tk works if the desktop provides the necessary GUI compatibility; headless servers cannot show the GUI.

### First launch: DEMO vs LIVE

- **DEMO** is the safe default. It uses deterministic synthetic options (clearly labeled) and never represents the current exchange market.
- **LIVE**: click **Dhan Credentials**, enter Client ID + DhanHQ access token (stored in `.env` locally), click **Test Dhan API**, choose `live` in **Data**, then **Apply**. An active paid market-data subscription is needed for Dhan API historical/options data.
- Check the actual instruments, timestamps, expiry/lot sizes, quote spread and risk flags. The first live scan needs historical 1-minute data for indicator warm-up and can take longer than cached scans.
- Access tokens may expire; update credentials and restart DhanFlip after changing them.

## INTEGRATED GUI CONTROLS

| Button/tab | Behavior |
|---|---|
| Start/Stop Scanner | Owns Dhan REST/WebSocket connection and computes the signals (no broker writes) |
| Refresh | One-off scan, skipping overlapping requests |
| Dhan Credentials / Test Dhan API | Save token locally / read `GET /profile` |
| Start/Stop MCP | Starts/stops **cache-only** read-only HTTP server on `127.0.0.1:8766/mcp` |
| Configure Tunnel | Choose existing `tunnel-client` binary, **dedicated DhanFlip** YAML profile, local control-plane key |
| Connect ChatGPT | Starts local MCP, then your configured tunnel-client; displays launch/health status |
| Stop Tunnel | Stops only tunnel started by this instance |
| Signals | Contracts, data freshness, latest indicator values, rejection reasons, proposal details |
| 3-minute option chart | Locally cached OHLCV, EMA50/200, VWAP, SuperTrend; charts drawn off UI thread |
| Manual trade journal | User-reported entries/exits and *pre-cost* P&L, does not verify Dhan broker fills |
| Strategy & Risk Settings | Editable original indicator inputs and scanner risk constraints (restart to apply) |
| Diagnostics | Process status, cache state, request counters, local logs/health checks |

Signals trigger the built-in desktop bell only in LIVE mode when a newly eligible `MANUAL_REVIEW` signal appears.

## 3-MINUTE INDICATOR AND Dhan RATE-LIMIT DESIGN

- Source: individual CE/PE **option-premium** OHLCV, not NIFTY/SENSEX underlying price.
- Dhan v2 provides 1-minute (not native 3-minute) intraday bars; we aggregate **exactly three contiguous complete 1-minute bars** anchored at 09:15 IST, discarding incomplete buckets. No lookahead or fabricated candles.
- EMA50/EMA200, SuperTrend ATR10 x4, session HLC3 VWAP, 21-volume VCB, primary green-flip/extended 15-bar logic, EMA200/ST proximity gates and structural stops follow original rule design.
- NIFTY +20, SENSEX +50 **premium points** auto targets; structural SL capped at max 40 points; longs enabled/shorts disabled, entry cutoff 15:00, EOD 15:20 advisory.
- Recommendation gate is separate from the raw Pine rules: suppress stale quotes, wide spreads, risk excess, duplicate open manual positions and **new recommendations after the cutoff**.
- Cached SQLite 1-minute OHLCV and fetch watermarks avoid re-downloading historical data on every scan/restart. Only newly completed bar data is requested; scanner workers share one limiter.
- Conservative REST throttle: data ≥0.27 sec spacing, quote ≥1.15 sec, option-chain ≥3.25 sec, bounded retries/backoff, max 95,000 calls per process-day. Dhan's published API limits and terms may change; check live usage.
- For **20 contracts**, the initial historical download is significantly slower; subsequent unchanged-bar scans are cached, but API latency varies. Do not run another independent Dhan client that shares the account's rate quota without coordinating limits.

## CHATGPT MCP / TUNNEL (OPTIONAL)

The **local MCP is not a Dhan connector**: it reads the GUI-owned scanner's SQLite snapshots; this avoids a second API client fetching duplicate market data. The tunnel only transports those MCP outputs to a connected, authorized ChatGPT app. **Tunnel health does not establish that ChatGPT has installed/authorized the connector**.

1. Obtain an actual OpenAI `tunnel-client` compatible binary and your separately provisioned tunnel ID/runtime key.
2. Copy `config/tunnel.example.yaml` to `config/tunnel.local.yaml`, replace `REPLACE_WITH_YOUR_TUNNEL_ID`, and keep the main MCP address `http://127.0.0.1:8766/mcp`.
3. GUI → **Configure Tunnel** → choose your tunnel-client executable, local YAML profile, enter the **control-plane runtime key**. It is saved only in ignored local `.env.tunnel` (never enter your Dhan token there).
4. GUI → **Connect ChatGPT**. This launches MCP then tunnel. Open tunnel admin UI at `http://127.0.0.1:8082/ui` if your example YAML is used. Check `/readyz`. Complete the connector authorization within ChatGPT; this is a separate manual account step.
5. Once authorized, ask ChatGPT for scanner status, qualifying signals, rejection reasons or the manual trade journal. **No MCP tool can place any Dhan order.**

If you already use `tunnel-client` for CraftApps, do not reuse the same main MCP profile as-is. V3 checks the chosen YAML routes `main` **exactly** to `127.0.0.1:8766/mcp` and blocks misdirected profiles. Use a **separate tunnel registration and admin port** when operating both simultaneously. See `docs/MCP_SETUP.md`.

## TESTING

```bash
python -m pytest -q             # after activating .venv
python -m dhanflip scan-once     # do NOT run a second live scanner alongside the GUI
python -m dhanflip status
python -m dhanflip backtest      # theoretical replay, NOT proven real-market performance
```

Tests are offline (mock/synthetic). The GUI also has an Xvfb/Linux headless smoke-test verification in the delivery report. **Authenticated live Dhan API behavior and actual ChatGPT tunnel registration cannot be validated without your account/desktop.** Do not interpret offline green tests as first-time-right live certification.

## SOURCE TREE

```text
DhanFlip_MCP_V3/
  INSTALL_WINDOWS.cmd / INSTALL_WINDOWS.ps1 / START_WINDOWS.bat
  INSTALL_LINUX.sh / START_LINUX.sh
  PUBLISH_GITHUB.sh / PUBLISH_GITHUB_WINDOWS.ps1
  .github/workflows/ci.yml
  .env.example / requirements.txt / .gitignore
  config/settings.yaml / config/tunnel.example.yaml
  dhanflip/{gui,tunnel,scanner,dhan,feed,bars,indicators,strategy,store,mcp_server,...}.py
  original_strategy/ (original user Pine file, no TradingView connection)
  docs/MCP_SETUP.md / docs/VERIFICATION.md / docs/STRATEGY_MAP.md
  tests/
```

## SAFETY / DISCLAIMERS

- This software is **not investment advice**, a broker order manager or a guaranteed stop-loss system. Dhan orders and exits are exclusively manual and must be confirmed in the Dhan app.
- Long option buying can lose the entire premium. Prices may gap; spreads and fills can differ materially from signals. Manual journal estimates exclude fees/slippage unless explicitly recorded separately.
- No guaranteed uninterrupted scanner service; your PC, internet, market feed and API credentials must be operational. No guaranteed signal speed or trading performance.

### Official references

- [Dhan API + limits](https://dhanhq.co/docs/v2/)
- [Dhan historical 1-minute API](https://dhanhq.co/docs/v2/historical-data/)
- [Dhan option chain + expiry](https://dhanhq.co/docs/v2/option-chain/)
- [Dhan instrument master](https://dhanhq.co/docs/v2/instruments/)
- [Dhan market feed](https://dhanhq.co/docs/v2/live-market-feed/)
- [OpenAI tunnel-client YAML schema](https://github.com/openai/tunnel-client/blob/master/docs/configuration.md)
- 
CAUTION / DISCLAIMER : USE AT YOUR OWN RISK . I AM NOT RESPONSIBLE FOR ANY TRADING LOSSES ARISING OUT OF IT. THIS IS FOR EDUCATIONAL PURPOSE ONLY.
BE CAREFUL WITH YOUR API KEYS, PASSWORDS ETC . 
