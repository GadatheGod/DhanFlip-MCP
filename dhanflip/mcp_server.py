"""Cache-only MCP service. It NEVER connects to Dhan or starts a scanner.

This prevents two MCP/GUI processes from fetching identical market data or
bypassing the scanner's rate limits. Signals remain explicitly advisory.
"""
from __future__ import annotations
from .config import ROOT
from .store import Store

class CacheReader:
    def __init__(self,db=None):self.db=db or Store(ROOT/'data/market_data.sqlite')
    def status(self):return self.db.get_state('scanner') or {'running':False,'message':'Start scanner from the GUI first'}
    def snapshot(self):return self.db.get_state('snapshot') or {}
    def latest(self):return [s for r in self.snapshot().values() for s in r.get('signals',[])]
    def contracts(self):return [r['contract'] for r in self.snapshot().values() if r.get('contract')]


def build_server(host='127.0.0.1',port=8766):
    from mcp.server.fastmcp import FastMCP
    reader=CacheReader()
    server=FastMCP('DhanFlip NIFTY SENSEX 3m',host=host,port=int(port),instructions=(
        'DhanFlip is advisory-only. This MCP server reads local SQLite results written by the GUI scanner. '
        'No order placement, broker position management, or auto-exit tools. '
        'Always state the data mode, candle timestamp, freshness, premium units and all risk flags. '
        'Historical/demo/stale signals are not current trade recommendations.'))
    @server.tool()
    def connection_status()->dict:
        """Snapshot of GUI-owned scanner, data freshness, and Dhan call counters."""
        return reader.status()
    @server.tool()
    def monitored_contracts()->list[dict]:
        """List option contracts scanned by the GUI's single data-fetching process."""
        return reader.contracts()
    @server.tool()
    def active_signals()->list[dict]:
        """Signals from most recent completed 3-minute candles; check freshness."""
        return reader.latest()
    @server.tool()
    def all_contract_status()->dict:
        """Indicators, last signal, rejected conditions, and stale/error flags."""
        return reader.snapshot()
    @server.tool()
    def analyze_contract(contract_key:str)->dict:
        """Inspect single option contract by exact monitored_contracts key."""
        return reader.snapshot().get(contract_key,{'error':'Unknown contract'})
    @server.tool()
    def recent_signal_history(limit:int=30)->list[dict]:
        """Historical signal journal. Not live alerts or broker orders."""
        return reader.db.signals(min(100,max(1,int(limit))))
    @server.tool()
    def manual_trade_journal()->list[dict]:
        """User-reported local entries/exits; no Dhan order data."""
        return reader.db.trades()
    @server.tool()
    def request_scan_info()->dict:
        """Explain how to trigger refresh without starting duplicate data collection."""
        return {'action':'Click Refresh in the DhanFlip GUI','network_calls_from_mcp':0,
                'reason':'Only GUI process may fetch Dhan data; MCP reads shared cache'}
    return server


def run_server(transport='stdio',host='127.0.0.1',port=8766):
    server=build_server(host,port)
    if transport=='http':server.run(transport='streamable-http')
    else:server.run(transport='stdio')
