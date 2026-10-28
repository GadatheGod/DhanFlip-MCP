"""SQLite local journal, 1m candle cache, raw signals. Does not sync orders to broker."""
from __future__ import annotations
import json,sqlite3,threading
from pathlib import Path
import pandas as pd
from .bars import IST

class Store:
    def __init__(self,path:Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.path=path;self.lock=threading.RLock()
        with self._conn() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS candles(contract TEXT, ts TEXT, o REAL,h REAL,l REAL,c REAL,v REAL, PRIMARY KEY(contract,ts));
            CREATE TABLE IF NOT EXISTS signals(id TEXT PRIMARY KEY, contract TEXT NOT NULL, signal_time TEXT NOT NULL, status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS manual_trades(id INTEGER PRIMARY KEY AUTOINCREMENT,signal_id TEXT NOT NULL,contract TEXT NOT NULL,entry REAL NOT NULL,lots INTEGER NOT NULL,lot_size INTEGER NOT NULL,target REAL NOT NULL,sl REAL NOT NULL,entry_time TEXT NOT NULL,exit_price REAL,exit_time TEXT,notes TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS fetch_mark(contract TEXT PRIMARY KEY, through_ts TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS signals_date ON signals(signal_time);
            ''')
    def _conn(self):
        c=sqlite3.connect(self.path,timeout=20)
        c.execute('PRAGMA busy_timeout=20000')
        return c

    def last_candle(self,contract):
        with self.lock,self._conn() as db:
            r=db.execute('SELECT MAX(ts) FROM candles WHERE contract=?',(contract,)).fetchone()
        return pd.Timestamp(r[0]).tz_convert(IST).to_pydatetime() if r and r[0] else None

    def get_fetch_mark(self,contract):
        with self.lock,self._conn() as db:
            r=db.execute('SELECT through_ts FROM fetch_mark WHERE contract=?',(contract,)).fetchone()
        return pd.Timestamp(r[0]).tz_convert(IST).to_pydatetime() if r else None

    def set_fetch_mark(self,contract,through):
        with self.lock,self._conn() as db:
            db.execute('INSERT INTO fetch_mark(contract,through_ts) VALUES (?,?) '
                       'ON CONFLICT(contract) DO UPDATE SET through_ts=excluded.through_ts',
                       (contract,through.isoformat()))

    def candle_count(self,contract):
        with self.lock,self._conn() as db:
            return db.execute('SELECT COUNT(*) FROM candles WHERE contract=?',(contract,)).fetchone()[0]

    def upsert_candles(self,contract,df):
        rows=[(contract,ts.isoformat(),float(r.open),float(r.high),float(r.low),float(r.close),float(r.volume)) for ts,r in df.iterrows()]
        with self.lock,self._conn() as db:
            db.executemany('INSERT INTO candles VALUES (?,?,?,?,?,?,?) ON CONFLICT(contract,ts) DO UPDATE SET o=excluded.o,h=excluded.h,l=excluded.l,c=excluded.c,v=excluded.v',rows)
    def candles(self,contract,limit=7000):
        with self.lock,self._conn() as db:
            rows=db.execute('SELECT ts,o,h,l,c,v FROM (SELECT * FROM candles WHERE contract=? ORDER BY ts DESC LIMIT ?) ORDER BY ts ASC',(contract,limit)).fetchall()
        if not rows:return pd.DataFrame(columns=['open','high','low','close','volume'],index=pd.DatetimeIndex([],tz=IST))
        idx=pd.to_datetime([r[0] for r in rows],utc=True).tz_convert(IST)
        return pd.DataFrame([r[1:] for r in rows],index=idx,columns=['open','high','low','close','volume'])
    def save_signal(self,contract,ev,status='REFERENCE_ONLY'):
        with self.lock,self._conn() as db:
            db.execute("INSERT INTO signals(id,contract,signal_time,status,payload) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,status=CASE WHEN signals.status='MANUAL_FILL_REPORTED' THEN signals.status ELSE excluded.status END",
                       (ev['id'],contract,ev['signal_time'],status,json.dumps(ev,allow_nan=False)))
    def signals(self,limit=50):
        with self.lock,self._conn() as db:
            rows=db.execute('SELECT id,contract,signal_time,status,payload FROM signals ORDER BY signal_time DESC LIMIT ?',(limit,)).fetchall()
        return [{'id':id,'contract':contract,'signal_time':tm,'status':status,**json.loads(payload)} for id,contract,tm,status,payload in rows]
    def get_signal(self,ident):
        with self.lock,self._conn() as db:
            row=db.execute('SELECT contract,payload FROM signals WHERE id=?',(ident,)).fetchone()
        return (row[0],json.loads(row[1])) if row else None
    def count_open(self):
        with self.lock,self._conn() as db:
            return db.execute('SELECT COUNT(*) FROM manual_trades WHERE exit_time IS NULL').fetchone()[0]
    def add_manual(self,signal_id,contract,entry,lots,lot_size,target,sl,now):
        with self.lock,self._conn() as db:
            cur=db.execute('INSERT INTO manual_trades(signal_id,contract,entry,lots,lot_size,target,sl,entry_time) VALUES(?,?,?,?,?,?,?,?)',
                           (signal_id,contract,entry,lots,lot_size,target,sl,now))
            db.execute('UPDATE signals SET status=? WHERE id=?',('MANUAL_FILL_REPORTED',signal_id))
            return cur.lastrowid
    def exit_manual(self,trade_id,px,at):
        with self.lock,self._conn() as db:
            cur=db.execute('UPDATE manual_trades SET exit_price=?,exit_time=? WHERE id=? AND exit_time IS NULL',(px,at,trade_id))
            if cur.rowcount!=1:raise ValueError('No open trade with that ID')
    def trades(self):
        with self.lock,self._conn() as db:
            rows=db.execute('SELECT id,signal_id,contract,entry,lots,lot_size,target,sl,entry_time,exit_price,exit_time FROM manual_trades ORDER BY id DESC').fetchall()
        cols=['id','signal_id','contract','entry','lots','lot_size','target','sl','entry_time','exit_price','exit_time']
        return [dict(zip(cols,r)) for r in rows]
    def get_state(self,key):
        with self.lock,self._conn() as db:row=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def set_state(self,key,val):
        with self.lock,self._conn() as db:
            db.execute('INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(val)))
