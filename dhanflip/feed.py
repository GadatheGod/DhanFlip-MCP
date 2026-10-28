"""Optional read-only Dhan Full Feed WebSocket; REST 1m candles remain truth for signals."""
from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlencode
import struct,json,threading,time
from websockets.sync.client import connect

ENUM={2:'NSE_FNO',8:'BSE_FNO'}

def decode_packet(b:bytes):
    if not isinstance(b,bytes) or len(b)<8:return None
    code,length,segment,sid=struct.unpack_from('<BHB I',b,0)
    item={'code':code,'segment':ENUM.get(segment,str(segment)),'security_id':str(sid)}
    if code not in (2,4,8) or len(b)<16:return item
    item['ltp']=round(struct.unpack_from('<f',b,8)[0],4)
    if code in (4,8) and len(b)>=34:
        item['timestamp']=int(struct.unpack_from('<i',b,14)[0])
        item['volume']=int(struct.unpack_from('<i',b,22)[0])
    elif code==2:item['timestamp']=int(struct.unpack_from('<i',b,12)[0])
    if code==8 and len(b)>=162:
        item['oi']=int(struct.unpack_from('<i',b,34)[0])
        item['bid']=round(struct.unpack_from('<f',b,62+12)[0],4)  # depth first bid: offset 62+12 = 74
        item['ask']=round(struct.unpack_from('<f',b,62+16)[0],4)
    return item

class Feed:
    def __init__(self,client_id,token):
        self.client_id=client_id;self.token=token;self.quotes={};self.contracts=[]
        self.stop=threading.Event();self.thread=None;self.last_packet=None;self.error=None;self.lock=threading.RLock()
    def configure(self,contracts):
        with self.lock:self.contracts=[(c['segment'],str(c['security_id'])) for c in contracts]
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop.clear();self.thread=threading.Thread(target=self._loop,daemon=True,name='DhanFullFeed');self.thread.start()
    def close(self):self.stop.set()
    def snapshot(self,segment,sid):
        with self.lock:return self.quotes.get((segment,str(sid)),{}).copy()
    def _loop(self):
        url='wss://api-feed.dhan.co?'+urlencode({'version':2,'token':self.token,'clientId':self.client_id,'authType':2})
        while not self.stop.is_set():
            try:
                with connect(url,open_timeout=15,ping_interval=20,ping_timeout=15,max_size=2**20) as ws:
                    self.error=None
                    with self.lock: c=list(self.contracts)
                    for x in range(0,len(c),100):
                        chunk=c[x:x+100]
                        ws.send(json.dumps({'RequestCode':21,'InstrumentCount':len(chunk),'InstrumentList':[
                            {'ExchangeSegment':seg,'SecurityId':sid} for seg,sid in chunk]}))
                    for msg in ws:
                        if self.stop.is_set():break
                        p=decode_packet(msg)
                        if not p or 'ltp' not in p:continue
                        # Do not use WS quote packet to generate indicator candles: gaps are possible.
                        p['received_at']=datetime.now(timezone.utc).isoformat()
                        with self.lock:
                            self.quotes[(p['segment'],p['security_id'])]=p;self.last_packet=p['received_at']
            except Exception as ex:
                self.error=(f'{type(ex).__name__}: {ex}'.replace(self.token,'[REDACTED]'))[:200]
                if self.stop.wait(5):break
