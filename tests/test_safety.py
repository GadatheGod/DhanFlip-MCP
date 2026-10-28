from pathlib import Path
import copy
from datetime import datetime
import pytest
from dhanflip.config import settings
from dhanflip.scanner import Scanner
from dhanflip.dhan import choose_contracts,DhanError,DhanReadOnly
from dhanflip.store import Store
from dhanflip.feed import decode_packet
import pandas as pd
import struct

def test_readonly_endpoint_allowlist():
    obj=DhanReadOnly('fake','not-a-token')
    with pytest.raises(DhanError):obj.post('/orders',{'test':'bad'})

def test_master_selection():
    records=[]
    for strike in (100,150,200,250,300):
        for opt in ('CE','PE'):
            records.append({'UNDERLYING_SYMBOL':'NIFTY','OPTION_TYPE':opt,'STRIKE_PRICE':str(strike),
                'SM_EXPIRY_DATE':'2026-11-05','SECURITY_ID':str(strike)+('1' if opt=='CE' else '2'),
                'UNDERLYING_SECURITY_ID':'13','LOT_SIZE':'65','TICK_SIZE':'0.05','DISPLAY_NAME':'TEST'})
    sel=choose_contracts(pd.DataFrame(records),'NIFTY',202,'2026-11-05',2)
    assert len(sel)==10 and {a['type'] for a in sel}=={'CE','PE'}

def test_db_no_duplicate_signals(tmp_path):
    db=Store(tmp_path/'x.db');sig={'id':'unique','signal_time':'2026-10-28T09:18:00+05:30'}
    db.save_signal('NSE_FNO:1',sig);db.save_signal('NSE_FNO:1',sig)
    assert len(db.signals())==1

def test_feed_decode_quote():
    binary=struct.pack('<BHBI',2,16,2,123)+struct.pack('<fi',100.5,1790000000)
    p=decode_packet(binary)
    assert p['segment']=='NSE_FNO' and p['ltp']==100.5

def test_demo_scanner_end_to_end(tmp_path):
    c=copy.deepcopy(settings());c['mode']='demo';c['history_days']=3
    scanner=Scanner(c,tmp_path/'market.sqlite')
    try:
        state=scanner.scan_once(datetime(2026,10,28,15,31,tzinfo=__import__('dhanflip.bars',fromlist=['IST']).IST))
        assert state['contracts']==20
        assert len(scanner.snapshot())==20
        assert scanner.db.count_open()==0
    finally:scanner.shutdown()
