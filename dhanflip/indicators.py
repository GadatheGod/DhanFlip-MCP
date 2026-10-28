"""Pine-shaped arithmetic, explicit Wilder RMA seed and SuperTrend final bands."""
from __future__ import annotations
import numpy as np
import pandas as pd


def ema(x:pd.Series,n:int)->pd.Series:
    # Pine ta.ema starts at the first non-NA input, alpha=2/(n+1).
    return x.astype(float).ewm(alpha=2/(n+1),adjust=False,ignore_na=True).mean()


def rma(x:pd.Series,n:int)->pd.Series:
    # Pine ta.rma seeded with SMA of first n non-NA values.
    vals=x.to_numpy(dtype=float); out=np.full(len(vals),np.nan)
    initial=[]; prev=np.nan
    for i,v in enumerate(vals):
        if not np.isfinite(v): continue
        if len(initial)<n:
            initial.append(v)
            if len(initial)==n: prev=float(np.mean(initial));out[i]=prev
        else:
            prev=(prev*(n-1)+v)/n;out[i]=prev
    return pd.Series(out,index=x.index)


def atr(df:pd.DataFrame,n:int)->pd.Series:
    prev=df.close.shift(1)
    tr=pd.concat([(df.high-df.low), (df.high-prev).abs(),(df.low-prev).abs()],axis=1).max(axis=1)
    return rma(tr,n)


def supertrend(df:pd.DataFrame,factor:float=4,n:int=10):
    a=atr(df,n); hl2=(df.high+df.low)/2
    bu=hl2+factor*a;bl=hl2-factor*a
    upper=np.full(len(df),np.nan);lower=np.full(len(df),np.nan)
    line=np.full(len(df),np.nan);direction=np.full(len(df),np.nan)
    for i in range(len(df)):
        if not np.isfinite(a.iloc[i]):continue
        up=float(bu.iloc[i]);lo=float(bl.iloc[i])
        if i>0 and np.isfinite(upper[i-1]):
            up=up if (up<upper[i-1] or df.close.iloc[i-1]>upper[i-1]) else upper[i-1]
            lo=lo if (lo>lower[i-1] or df.close.iloc[i-1]<lower[i-1]) else lower[i-1]
        upper[i]=up;lower[i]=lo
        if i==0 or not np.isfinite(a.iloc[i-1]) or not np.isfinite(line[i-1]): direction[i]=1
        elif np.isclose(line[i-1],upper[i-1],atol=1e-10):direction[i]=-1 if df.close.iloc[i]>up else 1
        else: direction[i]=1 if df.close.iloc[i]<lo else -1
        line[i]=lo if direction[i]<0 else up
    return pd.Series(line,index=df.index),pd.Series(direction,index=df.index),a


def enrich(df:pd.DataFrame,conf:dict)->pd.DataFrame:
    d=df.copy()
    d['ema50']=ema(d.close,conf['ema50_length'])
    d['ema200']=ema(d.close,conf['ema200_length'])
    d['st'],d['direction'],d['atr']=supertrend(d,conf['factor'],conf['atr_period'])
    d['avg_volume']=d.volume.rolling(conf['vcb_length'],min_periods=conf['vcb_length']).mean()
    typ=(d.high+d.low+d.close)/3
    dates=d.index.tz_convert('Asia/Kolkata').date
    v=(typ*d.volume).groupby(dates).cumsum()
    vol=d.volume.groupby(dates).cumsum()
    d['vwap']=(v/vol.replace(0,np.nan)).to_numpy()
    d['green_vcb']=(d.volume>1.5*d.avg_volume)&(d.close>d.open)
    d['red_vcb']=(d.volume>1.5*d.avg_volume)&(d.close<d.open)
    return d
