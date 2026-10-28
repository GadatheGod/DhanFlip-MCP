# V2 improvements over V1

* One-click Linux application-menu installer and Windows launcher.
* Unified Tk desktop controls for Start/Stop Scanner, Refresh, Start/Stop MCP, credentials, Dhan token/data-plan check, Demo/Live.
* Fixed expensive shared scanner lock preventing Tk updates during full scans.
* Concurrent contract calculations (four workers) with a conservative shared data/quote/chain API limiter.
* SQLite candle cache and persistent per-contract download watermarks; only newly completed 3-minute data requested.
* Never refetch full historical lookback every 30 seconds; warm-up stored locally.
* Option-chain refresh 15 minutes and retains unchanged contract calculation caches.
* Cache-only MCP server reads GUI results from SQLite; no independent market requests.
* Chart calculations off the Tk thread, reuse unchanged chart on repeated selection.
* Additional offline limiter/cache safety tests.

## Still requires live validation

Actual Dhan API credentials, account data entitlements, market feed packets, Linux desktop driver/font behavior, and exact Pine equivalence cannot be verified offline. All broker orders are deliberately unavailable.
