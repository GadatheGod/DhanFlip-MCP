"""Official DhanHQ v2 read-only endpoints; shared, conservative HTTP limiters.

NO broker order, modify, cancel, IP-whitelist or token-renewal calls exist here.
Docs: https://dhanhq.co/docs/v2/ ; /option-chain/ ; /historical-data/
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from io import StringIO
import threading,time,requests,pandas as pd

BASE='https://api.dhan.co/v2'
MASTER='https://images.dhan.co/api-data/api-scrip-master-detailed.csv'
class DhanError(RuntimeError): pass

class RateLimiter:
    """Single-process sliding start spacing for ALL threads / endpoints.

    Dhan docs: Data 5/sec, Quote 1/sec, Option Chain 1 unique request / 3 sec.
    We enforce max 4 data/sec and global chain 1/3.25 sec for extra headroom.
    """
    def __init__(self,clock=time.monotonic,sleep=time.sleep):
        self.clock,self.sleep=clock,sleep
        self.lock=threading.Lock()
        self.next={'data':0.,'quote':0.,'chain':0.}
        self.global_next=0.
        self.cooldown_until=0.
        self.counts={'data':0,'quote':0,'chain':0}
        self.day=date.today()
    def acquire(self,category):
        if category not in self.next:raise ValueError('Invalid Dhan request category')
        with self.lock:
            if date.today()!=self.day:
                self.counts={k:0 for k in self.counts};self.day=date.today()
            if sum(self.counts.values())>=95000:
                raise DhanError('Dhan daily API safety budget reached (95,000 requests)')
            now=self.clock();start=max(now,self.next[category],self.global_next,self.cooldown_until)
            self.next[category]=start+{'data':.27,'quote':1.15,'chain':3.25}[category]
            self.global_next=start+.27
            self.counts[category]+=1
        if start>now:self.sleep(start-now)
    def backoff(self,seconds):
        with self.lock:self.cooldown_until=max(self.cooldown_until,self.clock()+min(120,max(2,seconds)))
    def statistics(self):
        with self.lock:return dict(self.counts)

class DhanReadOnly:
    def __init__(self,client_id:str,token:str,timeout=18,limiter=None):
        if not client_id or not token:raise DhanError('Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN locally in .env')
        self.client_id,self.token=client_id,token
        self.timeout=timeout;self.limiter=limiter or RateLimiter()
        self._local=threading.local();self._expiry_cache={}
    def session(self):
        if not hasattr(self._local,'session'):
            s=requests.Session();s.headers.update({'access-token':self.token,'client-id':self.client_id,
                'Accept':'application/json','Content-Type':'application/json'})
            self._local.session=s
        return self._local.session
    def _request(self,verb,path,data=None,category='data'):
        allowed={'POST':{'/charts/intraday','/marketfeed/quote','/marketfeed/ltp','/optionchain','/optionchain/expirylist'},
                 'GET':{'/profile'}}
        if path not in allowed.get(verb,{}):raise DhanError('Read-only endpoint allowlist rejected: '+path)
        for attempt in range(3):
            self.limiter.acquire(category)
            try:
                res=self.session().request(verb,BASE+path,json=data if verb=='POST' else None,timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt<2:
                    self.limiter.backoff(2*(attempt+1));continue
                raise DhanError('Dhan network error: '+type(exc).__name__) from exc
            if res.status_code in (429,500,502,503,504):
                delay=res.headers.get('Retry-After','')
                try:wait=min(60,max(3,float(delay)))
                except ValueError:wait=3*(2**attempt)
                self.limiter.backoff(wait)
                if attempt<2:continue
            try:body=res.json()
            except ValueError:raise DhanError(f'Dhan returned non-JSON HTTP {res.status_code}')
            if not res.ok or (isinstance(body,dict) and str(body.get('status','')).lower() in ('failure','error')):
                code=body.get('errorCode','') if isinstance(body,dict) else ''
                msg=body.get('errorMessage','') if isinstance(body,dict) else ''
                # Avoid leaking request headers or access token into logs/tool results.
                raise DhanError(f'Dhan HTTP {res.status_code} {str(code)[:50]} {str(msg).replace(self.token,"[redacted]")[:160]}')
            return body
        raise DhanError('Dhan API retry attempts exhausted')
    def post(self,path,data,category='data'):return self._request('POST',path,data,category)
    def profile(self):
        x=self._request('GET','/profile',category='data')
        return {k:x.get(k) for k in ('dhanClientId','tokenValidity','activeSegment','dataPlan','dataValidity')}
    def history(self,security_id,segment,from_dt,to_dt):
        if to_dt<=from_dt:return {'timestamp':[],'open':[],'high':[],'low':[],'close':[],'volume':[]}
        return self.post('/charts/intraday',{'securityId':str(security_id),'exchangeSegment':segment,'instrument':'OPTIDX',
                    'interval':'1','oi':False,'fromDate':from_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'toDate':to_dt.strftime('%Y-%m-%d %H:%M:%S')})
    def expiries(self,underlying_id):
        key=(int(underlying_id),date.today())
        if key not in self._expiry_cache:
            v=self.post('/optionchain/expirylist',{'UnderlyingScrip':int(underlying_id),'UnderlyingSeg':'IDX_I'},'chain')
            self._expiry_cache={key:v['data']}
        return self._expiry_cache[key]
    def chain(self,underlying_id,expiry):
        return self.post('/optionchain',{'UnderlyingScrip':int(underlying_id),'UnderlyingSeg':'IDX_I','Expiry':expiry},'chain')['data']
    def quote(self,segments):
        return self.post('/marketfeed/quote',segments,'quote').get('data',{})

# Unchanged original instrument parsing, with cache on disk.
def instruments_file(cache:Path,refresh_hours=20)->pd.DataFrame:
    cache.parent.mkdir(parents=True,exist_ok=True)
    if not cache.exists() or time.time()-cache.stat().st_mtime>refresh_hours*3600:
        try:
            r=requests.get(MASTER,timeout=45)
            r.raise_for_status()
            new=pd.read_csv(StringIO(r.text),dtype=str,low_memory=False)
            if 'UNDERLYING_SYMBOL' not in new.columns:
                raise DhanError('Dhan instrument master schema changed')
            tmp=cache.with_suffix('.tmp');tmp.write_text(r.text,encoding='utf-8');tmp.replace(cache)
            return new
        except (requests.RequestException,ValueError) as exc:
            if not cache.exists():raise DhanError('Cannot load instrument master: '+type(exc).__name__) from exc
    return pd.read_csv(cache,dtype=str,low_memory=False)


def choose_contracts(master:pd.DataFrame,index:str,underlying_ltp:float,expiry:str,count=2):
    name=index.upper();m=master
    for col in ('UNDERLYING_SYMBOL','OPTION_TYPE','STRIKE_PRICE','SM_EXPIRY_DATE','SECURITY_ID','UNDERLYING_SECURITY_ID','LOT_SIZE','TICK_SIZE'):
        if col not in m:raise DhanError(f'Instrument column {col} missing; update adapter')
    mask=m['UNDERLYING_SYMBOL'].fillna('').str.upper().str.strip().eq(name)
    mask &= m['OPTION_TYPE'].fillna('').str.upper().isin(['CE','PE'])
    expiry_col=pd.to_datetime(m['SM_EXPIRY_DATE'],errors='coerce').dt.strftime('%Y-%m-%d')
    mask &= expiry_col.eq(expiry)
    sub=m.loc[mask].copy();sub['strike']=pd.to_numeric(sub['STRIKE_PRICE'],errors='coerce')
    sub=sub.dropna(subset=['strike']);strikes=sorted(sub['strike'].unique())
    if not strikes:raise DhanError(f'No active option contracts for {name} {expiry}')
    atm=min(range(len(strikes)), key=lambda i:abs(strikes[i]-underlying_ltp))
    selected=set(strikes[max(0,atm-count):min(len(strikes),atm+count+1)])
    out=[]
    for _,r in sub[sub.strike.isin(selected)].iterrows():
        seg='NSE_FNO' if name=='NIFTY' else 'BSE_FNO'
        if str(r['SECURITY_ID']).lower()=='nan':continue
        out.append({'key':f'{seg}:{r.SECURITY_ID}','index':name,'segment':seg,'security_id':str(r.SECURITY_ID),
                    'symbol':str(r.get('DISPLAY_NAME') or r.get('SYMBOL_NAME') or ''),
                    'strike':float(r.strike),'type':str(r.OPTION_TYPE),'expiry':expiry,
                    'lot_size':int(float(r.LOT_SIZE)),'tick_size':float(r.TICK_SIZE)})
    return sorted(out,key=lambda r:(r['strike'],r['type']))


def underlying_id(master:pd.DataFrame,index:str)->int:
    m=master[master['UNDERLYING_SYMBOL'].fillna('').str.upper().str.strip()==index.upper()]
    m=m[m['OPTION_TYPE'].fillna('').str.upper().isin(['CE','PE'])]
    ids=pd.to_numeric(m['UNDERLYING_SECURITY_ID'],errors='coerce').dropna()
    if ids.empty:raise DhanError(f'Cannot derive underlying ID for {index} from instrument master')
    return int(ids.mode().iloc[0])
