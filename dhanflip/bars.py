"""Time/alignment-safe 1m -> 3m aggregation (no look-ahead, no fake candles)."""
from __future__ import annotations
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
IST = ZoneInfo('Asia/Kolkata')
FIELDS = ['open','high','low','close','volume']


def parse_dhan_candles(payload: dict) -> pd.DataFrame:
    if isinstance(payload, dict) and isinstance(payload.get('data'), dict):
        payload = payload['data']
    if not isinstance(payload, dict):
        raise ValueError('Unexpected Dhan historical JSON')
    ts = payload.get('timestamp', [])
    arrays = [payload.get(k, []) for k in FIELDS]
    if not ts or any(len(a) != len(ts) for a in arrays):
        raise ValueError('Missing/mismatched candle arrays; do not use for signals')
    idx = pd.to_datetime(pd.Series(ts), unit='s', utc=True).dt.tz_convert(IST)
    df = pd.DataFrame({k:pd.to_numeric(a, errors='coerce') for k,a in zip(FIELDS,arrays)},index=pd.DatetimeIndex(idx))
    df = df.sort_index()
    if df.index.has_duplicates: df=df[~df.index.duplicated(keep='last')]
    if df[FIELDS].isna().any().any(): raise ValueError('NaN in historical candles')
    if ((df['high']<df[['open','close','low']].max(axis=1)) | (df['low']>df[['open','close','high']].min(axis=1)) | (df['volume']<0)).any():
        raise ValueError('Invalid historical OHLCV')
    return df


def aggregate_3m(one:pd.DataFrame, now:datetime|None=None) -> pd.DataFrame:
    """Input timestamps must be candle START, timezone-aware; zero-tolerance for missing minute bars."""
    if one.empty: return pd.DataFrame(columns=FIELDS)
    if one.index.tz is None: raise ValueError('tz-aware candle timestamps required')
    now = now or datetime.now(IST)
    now = now.astimezone(IST)
    df=one.sort_index().copy()
    df.index=df.index.tz_convert(IST)
    # restrict standard cash-market session; if markets change, update this rule.
    times=df.index.time
    df=df[(times>=time(9,15)) & (times<time(15,30))]
    if df.empty: return df
    base = df.index.normalize()+pd.Timedelta(hours=9,minutes=15)
    minute = ((df.index-base).total_seconds()//60).astype(int)
    start=base+pd.to_timedelta((minute//3)*3,unit='m')
    df['bucket']=start
    rows=[]
    for start_ts,g in df.groupby('bucket',sort=True):
        expected=pd.date_range(start_ts,periods=3,freq='min')
        if len(g)!=3 or not g.index.equals(expected): continue
        if start_ts+pd.Timedelta(minutes=3)>pd.Timestamp(now): continue
        rows.append((start_ts,float(g['open'].iloc[0]),float(g['high'].max()),float(g['low'].min()),float(g['close'].iloc[-1]),float(g['volume'].sum())))
    if not rows: return pd.DataFrame(columns=FIELDS,index=pd.DatetimeIndex([],tz=IST))
    return pd.DataFrame([r[1:] for r in rows],index=pd.DatetimeIndex([r[0] for r in rows]),columns=FIELDS)


def check_latest_freshness(df:pd.DataFrame, now:datetime, max_age:int) -> tuple[bool,str]:
    if df.empty: return False,'No complete 3-minute candles'
    last=df.index[-1].to_pydatetime()
    diff=(now.astimezone(IST)-(last+timedelta(minutes=3))).total_seconds()
    if diff < -1: return False,'Latest candle is in the future'
    if diff > max_age: return False,f'Stale data: last 3m candle completed {int(diff)}s ago'
    return True,'Fresh'
