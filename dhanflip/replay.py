"""Illustrative theoretical OHLC replay. Not live, no guarantee or proof of profitability."""
from __future__ import annotations
import csv,math
from datetime import datetime
from pathlib import Path
from .bars import aggregate_3m, IST
from .strategy import evaluate

def backtest_all(svc,now=None):
    now=now or datetime.now(IST)
    if not svc.contracts:svc.discover(now)
    rows=[];skipped=[]
    for co in svc.contracts:
        df=aggregate_3m(svc.db.candles(co['key']),now)
        if df.empty:skipped.append(co['key']);continue
        result=evaluate(df,svc.c['strategy'],co['index'],co['tick_size'])
        for t in result['trades']:
            # next open + pessimistic 2-tick slippage on entry and exit. Value is per 1 lot.
            s=svc.c['slippage_ticks']*co['tick_size']
            gain=t['pnl_points']-2*s
            commission=2*svc.c['commission_per_order_rupees']
            gross=gain*co['lot_size']
            net=gross-commission
            rows.append({'contract':co['key'],'symbol':co['symbol'],'index':co['index'],'expiry':co['expiry'],
                         'open_time':t['open_time'],'exit_time':t['exit_time'],'entry':t['entry'],
                         'exit':t['exit'],'exit_reason':t['reason'],'gross_one_lot_rupees':round(gross,2),
                         'net_one_lot_rupees':round(net,2)})
    total=sum(r['net_one_lot_rupees'] for r in rows)
    # This is NOT a valid portfolio-level P&L. Contract simulations overlap and share risk.
    wins=sum(1 for r in rows if r['net_one_lot_rupees']>0)
    return {'trades':rows,'summary':{'number_of_theoretical_trades':len(rows),
            'positive_trade_fraction':wins/len(rows) if rows else None,
            'sum_of_independent_1_lot_trade_results_rupees':round(total,2),
            'warning':'Overlapping contracts; NOT portfolio P&L or verified backtest. Costs/taxes incomplete.'},
            'skipped':skipped}

def export_csv(result,path):
    fields=['contract','symbol','index','expiry','open_time','exit_time','entry','exit','exit_reason',
            'gross_one_lot_rupees','net_one_lot_rupees']
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(result['trades'])
