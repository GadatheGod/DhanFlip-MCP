"""Deterministic offline candles/contract universe. Not market data or backtesting evidence."""
from __future__ import annotations
from datetime import datetime,timedelta
import numpy as np
import pandas as pd
from .bars import IST

def demo_contracts():
    contracts=[]
    for index,seg,base,step,expiry,lot in [('NIFTY','NSE_FNO',25000,50,'2099-12-31',65),('SENSEX','BSE_FNO',82000,100,'2099-12-31',20)]:
        for i in (-2,-1,0,1,2):
            for typ in ('CE','PE'):
                sid=str(100000+len(contracts))
                contracts.append({'key':seg+':'+sid,'index':index,'segment':seg,'security_id':sid,'symbol':f'DEMO-{index}-{base+i*step}-{typ}',
                                  'strike':base+i*step,'type':typ,'expiry':expiry,'lot_size':lot,'tick_size':.05})
    return contracts

def sample_minute(contract, now=None, days=9):
    now=now or datetime.now(IST)
    dates=pd.bdate_range(now.date()-timedelta(days=days),now.date(),freq='B')
    idx=[]
    for d in dates:
        s=pd.Timestamp(datetime.combine(d.date(),datetime.min.time(),IST))+pd.Timedelta(hours=9,minutes=15)
        idx.extend(pd.date_range(s,periods=375,freq='min'))
    idx=pd.DatetimeIndex(idx)
    idx=idx[idx+pd.Timedelta(minutes=1)<=pd.Timestamp(now)]
    if len(idx)==0:return pd.DataFrame(columns=['open','high','low','close','volume'],index=idx)
    seed=int(contract['security_id'])
    rng=np.random.default_rng(seed)
    x=np.arange(len(idx))
    step=rng.normal(0,1.6,len(idx))+0.07*np.sin(x/30)
    close=np.maximum(8,120+np.cumsum(step))
    op=np.r_[close[0],close[:-1]]
    high=np.maximum(op,close)+rng.random(len(idx))*1.5
    low=np.minimum(op,close)-rng.random(len(idx))*1.5
    vol=rng.integers(150,2500,len(idx))
    return pd.DataFrame({'open':op,'high':high,'low':low,'close':close,'volume':vol},index=idx)
