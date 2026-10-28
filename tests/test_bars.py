from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import pytest
from dhanflip.bars import aggregate_3m,parse_dhan_candles,IST,check_latest_freshness

def make():
    idx=pd.date_range('2026-10-28 09:15',periods=7,freq='min',tz=IST)
    return pd.DataFrame({'open':[100,101,102,103,104,105,106],
                         'high':[102,103,104,105,106,107,108],
                         'low':[99,100,101,102,103,104,105],
                         'close':[101,102,103,104,105,106,107],
                         'volume':[2]*7},index=idx)

def test_aggregation_no_lookahead():
    m=make();out=aggregate_3m(m,datetime(2026,10,28,9,21,tzinfo=IST))
    assert len(out)==2
    assert out.iloc[0]['open']==100
    assert out.iloc[0]['close']==103
    assert out.iloc[0]['high']==104
    assert out.iloc[0]['low']==99
    assert out.iloc[0]['volume']==6

def test_missing_minute_rejects_entire_3m():
    m=make().drop(make().index[1])
    out=aggregate_3m(m,datetime(2026,10,28,9,21,tzinfo=IST))
    assert len(out)==1 and out.index[0].minute==18

def test_history_parse():
    times=[1793159100,1793159160]
    d={k:[1,2] for k in ('open','high','low','close','volume')}
    d['high']=[2,3];d['low']=[0,1];d['timestamp']=times
    out=parse_dhan_candles(d)
    assert len(out)==2 and str(out.index.tz)=='Asia/Kolkata'

def test_historical_array_mismatch():
    with pytest.raises(ValueError):parse_dhan_candles({'timestamp':[1,2],'open':[1]})

def test_freshness():
    m=aggregate_3m(make(),datetime(2026,10,28,9,21,tzinfo=IST))
    assert check_latest_freshness(m,datetime(2026,10,28,9,21,1,tzinfo=IST),10)[0]
    assert not check_latest_freshness(m,datetime(2026,10,28,9,23,tzinfo=IST),10)[0]
