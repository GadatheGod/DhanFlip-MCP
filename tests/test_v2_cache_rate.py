"""Offline V2 regression tests: no real Dhan calls."""
import copy
from datetime import datetime,timedelta
from pathlib import Path
import pandas as pd
import pytest
from dhanflip.dhan import RateLimiter,DhanReadOnly,DhanError
from dhanflip.scanner import Scanner,latest_complete_end
from dhanflip.config import settings
from dhanflip.bars import IST
from dhanflip.mcp_server import CacheReader
from dhanflip.store import Store


def test_rate_limiter_categories_and_spacing():
    x=[0.]
    def clock():return x[0]
    def sleep(s):x[0]+=s
    limiter=RateLimiter(clock,sleep)
    limiter.acquire('data');assert x[0]==0
    limiter.acquire('data');assert x[0]>=.27
    limiter.acquire('quote');assert x[0]>=.54
    limiter.acquire('quote');assert x[0]>=1.69
    limiter.acquire('chain');limiter.acquire('chain')
    assert limiter.statistics()=={'data':2,'quote':2,'chain':2}
    assert x[0]>=4.94


def test_only_read_endpoints_allowed():
    client=DhanReadOnly('test','redacted-test')
    for verb,path in [('POST','/orders'),('POST','/super/orders'),('GET','/orders'),('POST','/ip/setIP')]:
        with pytest.raises(DhanError,match='allowlist'):
            client._request(verb,path,{})


def test_3min_cutoff_in_ist():
    n=datetime(2026,10,29,9,20,5,tzinfo=IST)
    assert latest_complete_end(n,delay=10).strftime('%H:%M')=='09:18'
    assert latest_complete_end(n+timedelta(seconds=9),delay=10).strftime('%H:%M')=='09:18'
    n=datetime(2026,10,29,9,21,20,tzinfo=IST)
    assert latest_complete_end(n).strftime('%H:%M')=='09:21'


def test_local_fetch_watermark_survives_restart(tmp_path):
    first=Store(tmp_path/'cache.sqlite')
    t=datetime(2026,10,29,9,18,tzinfo=IST)
    first.set_fetch_mark('NSE_FNO:TEST',t)
    assert Store(tmp_path/'cache.sqlite').get_fetch_mark('NSE_FNO:TEST')==t


def test_scanner_reuses_candles_within_same_bar(tmp_path):
    cfg=copy.deepcopy(settings());cfg['mode']='demo'
    svc=Scanner(cfg,tmp_path/'data.sqlite')
    t=datetime(2026,10,29,10,10,30,tzinfo=IST)
    svc.scan_once(t);assert len(svc.snapshot())==20
    r=svc.scan_once(t+timedelta(seconds=20))
    assert r['cache_hits']==20
    assert r['requests']=={}
    assert len(CacheReader(svc.db).snapshot())==20
    svc.shutdown()


def test_mcp_cache_reader_no_broker_dependency(tmp_path):
    st=Store(tmp_path/'state.sqlite');st.set_state('scanner',{'mode':'live','running':False})
    st.set_state('snapshot',{'X':{'contract':{'key':'X'},'signals':[]}})
    reader=CacheReader(st)
    assert reader.status()['mode']=='live'
    assert reader.contracts()==[{'key':'X'}]
    assert reader.latest()==[]


def test_only_one_scanner_instance_in_process():
    from dhanflip.singleinstance import SingleScannerInstance
    with SingleScannerInstance():
        with pytest.raises(SystemExit,match='Another DhanFlip'):
            with SingleScannerInstance():pass
