from datetime import datetime
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from dhanflip.config import settings
from dhanflip.indicators import rma,ema,atr,supertrend,enrich
from dhanflip.strategy import evaluate,target,stop
from dhanflip.bars import IST

def conf():return deepcopy(settings()['strategy'])
def candles():
    idx=pd.date_range('2026-10-28 09:15',periods=100,freq='3min',tz=IST)
    x=np.arange(100)
    y=100+4*np.sin(x/8)+np.where(x>42,(x-42)*.25,0)
    return pd.DataFrame({'open':y-.2,'high':y+1,'low':y-1,'close':y,'volume':[1000]*100},index=idx)

def test_ema_first_seed():
    s=pd.Series([10.,20.,30.]);assert ema(s,3).tolist()==[10.,15.,22.5]

def test_rma_seed():
    a=rma(pd.Series([1.,2.,3.,4.,5.]),3)
    assert np.isnan(a.iloc[1]) and a.iloc[2]==2
    assert a.iloc[3]==pytest.approx(8/3)

def test_supertrend_direction():
    d=supertrend(candles(),4,10)
    assert d[1].iloc[0]!=d[1].iloc[0]
    assert d[1].dropna().isin([-1,1]).all()

def test_targets_premium():
    c=conf()
    assert target(120,5,c,'NIFTY')==140
    assert target(120,5,c,'SENSEX')==170
    assert target(120,5,c,'NIFTY',False)==100

def test_sl_structural_cap():
    c=conf()
    assert stop(120,60,70,2,c)==80 # 40 points max
    assert stop(120,200,190,2,c)<120 # min gap enforces proper side

def test_long_only_and_no_future_signals():
    d=candles();res=evaluate(d,conf(),'NIFTY')
    assert isinstance(res['signals'],list)
    assert all(s['direction']=='LONG' for s in res['signals'])
    assert all(pd.Timestamp(s['signal_time'])==pd.Timestamp(s['bar_start'])+pd.Timedelta(minutes=3) for s in res['signals'])

def test_short_disabled_no_pe_short():
    c=conf();c['enable_long']=False
    result=evaluate(candles(),c,'NIFTY')
    assert not result['signals']

def test_vwap_reset():
    d=candles(); idx2=pd.date_range('2026-10-29 09:15',periods=10,freq='3min',tz=IST)
    x=pd.concat([d,pd.DataFrame({'open':[200]*10,'high':[202]*10,'low':[198]*10,'close':[201]*10,'volume':[50]*10},index=idx2)])
    en=enrich(x,conf());assert en.loc[idx2[0],'vwap']==pytest.approx((202+198+201)/3)
