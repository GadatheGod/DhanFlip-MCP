# Reference Pine v6 → Python mapping

Original uploaded file: `original_strategy/user_uploaded_original.md` (unchanged). Extracted reference file: `original_strategy/Nifty_Sensex_Flip_2026_reference.pine`. This was supplied by the user and remains the master specification.

| Pine section / identifiers | Python implementation | Notes |
|---|---|---|
| `ta.ema(close,50/200)` | `indicators.ema`, `enrich` | EMA seeded from first close |
| `ta.vwap(hlc3)` | `indicators.enrich` | Session-anchored volume VWAP; zero-volume reports `NaN` |
| `ta.atr(10)` | `indicators.atr`, `rma` | Wilder RMA seeded from SMA of first 10 true ranges |
| `ta.supertrend(factor,atrPeriod)` | `indicators.supertrend` | Trailing final bands / Pine direction sign: green < 0 |
| previous ST / EMA200 proximity | `strategy.evaluate` | Reference to previous red/green ST band; default 1.5 ATR gate |
| `ta.sma(volume,21)` + VCB | `indicators.enrich` | Average and colored-volume flags; optional directional filters |
| session cutoff / skip first bar | `strategy.evaluate` | IST 09:15 anchored; blocks new entries from 15:00 |
| `flipToGreen` primary | `strategy.evaluate` | Identical filter ordering / wait cancellation branches |
| `waitingForBreakLong` extended | `strategy.evaluate` | Replays state across full contract candle history; max 15 eligible bars |
| short filter logic | `strategy.evaluate` | Preserved but disabled by `enable_short:false` |
| target modes | `strategy.target` | Default NIFTY +20, SENSEX +50 option premium points |
| structural SL / cap | `strategy.stop` | VWAP / EMA50, maximum structural gap of 40 points |
| `strategy.entry` and `strategy.exit` | theoretical replay; local journal | **Different execution model:** no TradingView broker emulator and no automatic broker execution |
| `strategy.close_all` at 15:20 | `strategy.evaluate`, `scanner.position_advisories` | EOD **reminder** at live wall clock 15:20; no auto exit. Replay uses bar timestamps |
| `alert(msg)` webhook | `mcp_server.active_signals` | No TradingView alert or webhook; robust structured JSON with contract ID |

## Known unavoidable differences and review items

1. **Pine execution**: `process_orders_on_close=false` generally fills the strategy order next bar in replay. Here replay takes next available bar open, and if target+stop appear within the same bar, **SL is assumed first** (conservative, but cannot prove intrabar sequence).
2. **Indicator warmup**: the reference `ta.ema` makes values available early and uses the explicit `ema200NaPasses` switch for filters. A real derivative contract may have fewer bars than 200 and will be processed using whatever history is available. The engine rejects contracts that do not satisfy minimum ATR/VCB samples.
3. **Gap/volume quality**: Dhan 1m bars are resampled into 3m; missing 1m bars discard the entire 3m candle. A Dhan bar timestamp is assumed to indicate the start of the interval; verify this against actual Dhan data on first authentication.
4. **15:20 EOD**: Original 3m Pine only evaluates when its bar starts at 15:21, so exact 15:20 is impossible on completed candles. The live tool issues a wall-clock reminder from 15:20 even without a completed 3m bar. The theoretical replay closes from a later recorded bar. **You remain responsible for actually exiting in Dhan**.
5. **The original reference has a `storedTarget` / `storedSL` order-of-assignments issue**: it records them before calculating them at fill. The port uses explicit computed values rather than replicating that mistake.
6. **Pine stop uses original entry fill**. Local `record_manual_fill` recalculates target and stop from the *actual user-reported* premium, with signal-time ATR/VWAP/EMA snapshots.
7. **Short side**: original enables only LONG; both CE and PE are separately bought when they generate LONG signals. Original SHORT math exists in the port for parity but is disabled by default.
8. **Feed**: REST 1m candles remain authoritative for signals. Optional WebSocket only updates live quote snapshots. Resampling tick packets alone risks missing print volumes.
9. **Overlap**: backtest runs *each contract independently*. Results from multiple contracts can overlap and must not be summed as a realistic single-portfolio performance report.
10. **Pine `strategy.percent_of_equity=100`** is NOT copied into live lot sizing for safety. YAML max risk, max lots and one open manual position are separate post-signal controls.

## Signal quality gates

Pine signals are always recorded separately from post-signal eligibility. `CANDIDATE` means raw strategy signal occurred on the most recent complete bar, in a fresh 90s window; `MANUAL_REVIEW` additionally requires a valid quote, acceptable spread, premium bounds, available risk budget and no outstanding reported position. Otherwise `WATCHLIST_ONLY` with explicit risk flags. Older signals are `HISTORICAL`.

**Validation status:** unit tests and deterministic demo scan pass. Exact parity with TradingView's private implementation is NOT asserted (and TradingView is not a dependency). Live Dhan candle content and subscribed market entitlements require validation on the user's authenticated machine.
