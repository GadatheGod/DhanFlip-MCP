# Verification and limits — DhanFlip V3

## Automated offline tests — 31 passing on Linux

Run `python -m pytest -q` from project root after dependency install. Includes:

- 1-minute → 3-minute candle alignment, missing-minute discard, freshness
- EMA/Wilder ATR/SuperTrend, primary and extended entry, target/SL, session logic
- Dhan REST endpoint allowlist (no order endpoints), Dhan rate-limit contract
- Persistent local candle cache/scan revisions, scanner single-instance locking
- Local tunnel settings and separate secrets; rejects profiles pointing at a different MCP main URL
- GUI construction under a virtual display (`xvfb-run`) where available

**No external API credentials were used in tests.** The offline demo scan is synthetic and not evidence of historical profitability. Tests cannot prove perfect numerical equivalence to TradingView's broker emulator or Dhan real-world fills.

## In-person live acceptance checklist

- Dhan Client ID/token are valid and paid Data API is active
- `/profile`, instrument master and NIFTY/SENSEX option expiries load
- Source 1-minute OHLCV aligns to actual exchange times and option contract IDs
- No partial/missing 3-minute candle generates an entry
- Static quote and option spread are timely; market data freshness displayed correctly
- API 429 backoff and cumulative account quota observed during market hours
- Cache reuse works after restart with no old history re-fetch
- 3-minute strategy comparison against independent OHLCV fixtures and manual calculations, including edge cases
- No recommendations outside cutoff; 15:20 exit advisory works but is not an order
- No Dhan order endpoint is ever called
- Local MCP and existing OpenAI tunnel-client check passes on user's machine
- ChatGPT app/tool authorization is separately confirmed in ChatGPT

The application is strictly manual-trade advisory; risk is uncontrolled if the user fails to place a protective order in the broker application.

## Environment limitation in this delivery

The build container had no `mcp` Python package and could not reach package repositories to install it. Therefore the actual FastMCP HTTP handshake and OpenAI tunnel connectivity **were not tested** in this environment. Installing `requirements.txt` on an internet-connected Windows/Linux machine is required before using MCP. Python source compiles and the scanner, GUI, and other offline tests passed.
