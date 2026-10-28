"""Concurrent, cache-first, read-only scanner. No broker order execution APIs."""
from __future__ import annotations
import copy,threading,time,math
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,date,time as dt_time
from pathlib import Path
from .config import ROOT,settings,secrets
from .dhan import DhanReadOnly,instruments_file,choose_contracts,underlying_id,DhanError
from .bars import IST,parse_dhan_candles,aggregate_3m,check_latest_freshness
from .store import Store
from .strategy import evaluate,target,stop
from .demo import demo_contracts,sample_minute
from .feed import Feed


def latest_complete_end(now,delay=10):
    """Return end-exclusive clock time for latest fully closed 3m bar in IST.
    Accounts for weekends (not full NSE holiday calendar); no fake candles.
    """
    now=now.astimezone(IST)-timedelta(seconds=delay)
    day=now.date()
    if now.weekday()>=5 or now.time()<dt_time(9,18):
        day-=timedelta(days=1 if now.time()<dt_time(9,18) and now.weekday()<5 else 0)
        while day.weekday()>=5:day-=timedelta(days=1)
        return datetime.combine(day,dt_time(15,30),IST)
    if now.time()>=dt_time(15,30):return datetime.combine(day,dt_time(15,30),IST)
    mins=int((now-datetime.combine(day,dt_time(9,15),IST)).total_seconds()//60)
    return datetime.combine(day,dt_time(9,15),IST)+timedelta(minutes=(mins//3)*3)


class Scanner:
    def __init__(self,config:dict|None=None,db_path:Path|None=None):
        self.c=config or settings();self.mode=self.c['mode']
        self.db=Store(db_path or ROOT/'data/market_data.sqlite')
        self.state={'mode':self.mode,'running':False,'last_scan':None,'last_error':None,'contracts':0,'fresh':0,
                    'warning':'READ ONLY. Manual execution in Dhan; no Dhan order functions implemented',
                    'scanning':False,'revision':0,'processed':0,'requests':{},'cache_hits':0,'api_fetches':0}
        self.contracts=[];self.results={};self.lock=threading.RLock();self.scan_lock=threading.Lock()
        self._history_cache={};self._evaluation_cache={};self._saved_signal_ids=set()
        self.last_discovery=None;self.feed=None;self.last_chain={};self._master=None;self._master_date=None
        self.stop=threading.Event()
        if self.mode=='live':
            client,token=secrets();self.broker=DhanReadOnly(client,token)
            self.feed=Feed(client,token)
        elif self.mode=='demo':self.broker=None
        else:raise ValueError('mode must be demo or live')

    def discover(self,now):
        if self.mode=='demo':
            self.contracts=demo_contracts();return self.contracts
        if self._master is None or self._master_date!=now.date():
            self._master=instruments_file(ROOT/'data/instrument_master_detailed.csv')
            self._master_date=now.date()
        master=self._master;contracts=[];chain_data={}
        for index in self.c['symbols']:
            uid=underlying_id(master,index)
            active=sorted(e for e in self.broker.expiries(uid) if date.fromisoformat(e)>=now.date())
            if not active:raise DhanError('No active '+index+' expiries')
            expiry=active[0]
            ch=self.broker.chain(uid,expiry)
            if 'last_price' not in ch:raise DhanError('Option chain missing underlying last_price: '+index)
            cs=choose_contracts(master,index,float(ch['last_price']),expiry,self.c['strikes_each_side'])
            if not cs:raise DhanError('No matching contracts: '+index)
            bykey={(round(float(k),2),typ):(val or {}) for k,row in ch.get('oc',{}).items() for typ,val in row.items()}
            for co in cs:
                data=bykey.get((round(co['strike'],2),co['type'].lower()),{})
                chain_data[co['key']]={'bid':data.get('top_bid_price'),'ask':data.get('top_ask_price'),
                    'ltp':data.get('last_price'),'oi':data.get('oi'),'updated':now.isoformat()}
            contracts.extend(cs)
        old={co['key'] for co in self.contracts};new={co['key'] for co in contracts}
        self.contracts=contracts;self.last_chain=chain_data;self.last_discovery=now
        # Preserve candle/indicator cache for unchanged contracts across chain refresh.
        if new!=old:
            for k in old-new:self._history_cache.pop(k,None);self._evaluation_cache.pop(k,None)
            if self.feed:
                self.feed.close()
                client,token=secrets();self.feed=Feed(client,token)
                self.feed.configure(contracts);self.feed.start()
        elif self.feed and not self.feed.thread:
            self.feed.configure(contracts);self.feed.start()
        return contracts

    def _history(self,co,now):
        key=co['key'];end=latest_complete_end(now,self.c.get('candle_finalization_delay_seconds',10))
        old=self._history_cache.get(key)
        if old is not None and old[0]==end:
            return old[1],True
        last=self.db.last_candle(key)
        if self.mode=='demo':
            if last is None:
                df=sample_minute(co,now=now,days=min(5,self.c['history_days']))
                if not df.empty:self.db.upsert_candles(key,df)
        else:
            watermark=self.db.get_fetch_mark(key)
            # Request only NEW missing minutes; archive in SQLite for subsequent scans/restarts.
            if watermark is None and last is None:start=end-timedelta(days=self.c['history_days'])
            elif watermark is None:start=last+timedelta(minutes=1)
            else:start=watermark
            if last is not None:start=max(start,last+timedelta(minutes=1))
            if start<end:
                if (end-start).days>89:start=end-timedelta(days=89)
                raw=self.broker.history(co['security_id'],co['segment'],start,end)
                # A successful empty response is still a fetch; do not spin on closed markets.
                if raw.get('timestamp') or isinstance(raw.get('data'),dict) and raw['data'].get('timestamp'):
                    df=parse_dhan_candles(raw)
                    if not df.empty:self.db.upsert_candles(key,df)
                self.db.set_fetch_mark(key,end)
        bars=aggregate_3m(self.db.candles(key,limit=int(self.c.get('cache_max_minutes',4500))),
                          now-timedelta(seconds=self.c.get('candle_finalization_delay_seconds',10)))
        self._history_cache[key]=(end,bars)
        return bars,False

    def _work(self,co,now):
        bars,hit=self._history(co,now)
        if len(bars)<max(self.c['strategy']['atr_period'],self.c['strategy']['vcb_length']):
            raise ValueError('Not enough valid 3-minute candles to warm up')
        cached=self._evaluation_cache.get(co['key'])
        if cached is not None and cached[0] is bars:res=cached[1]
        else:
            res=evaluate(bars,self.c['strategy'],co['index'],co['tick_size'])
            self._evaluation_cache[co['key']]=(bars,res)
        good,why=check_latest_freshness(bars,now,self.c['max_data_age_seconds'])
        current=[]
        for sig in res['signals']:
            sig={**sig,**{k:co[k] for k in ('key','security_id','segment','strike','type','expiry','lot_size','tick_size','symbol')}}
            sig['id']=f"{co['key']}:{sig['id']}";sig['contract']=co['key']
            age=(now-datetime.fromisoformat(sig['signal_time'])).total_seconds()
            active=good and 0<=age<=self.c['max_quote_age_seconds'] and sig['bar_start']==bars.index[-1].isoformat()
            sig['signal_status']='CANDIDATE' if active else 'HISTORICAL'
            if active:current.append(sig)
            elif sig['id'] not in self._saved_signal_ids:
                self.db.save_signal(co['key'],sig,sig['signal_status']);self._saved_signal_ids.add(sig['id'])
        if current:
            current=self._qualify(current,co,now)
            for sig in current:self.db.save_signal(co['key'],sig,sig['recommendation'])
        out={'contract':co,'bars':len(bars),'fresh':good,'freshness':why,
             'latest':res['last'],'signals':current,'last_rejections':res['rejections'][-5:],
             'theoretical_trades':len(res['trades']),'from_cache':hit}
        return out

    def scan_once(self,now=None):
        # GUI can never queue overlapping network scans.
        with self.scan_lock:
            with self.lock:self.state.update(scanning=True,processed=0)
            try:return self._scan_once_unlocked(now)
            finally:
                with self.lock:self.state['scanning']=False

    def _scan_once_unlocked(self,now=None):
        now=now or datetime.now(IST)
        if now.tzinfo is None:raise ValueError('now must have timezone')
        if not self.contracts or (self.mode=='live' and (not self.last_discovery or (now-self.last_discovery).total_seconds()>=self.c['chain_refresh_seconds'])):
            self.discover(now)
        self.state['running']=True
        outcomes={};failures=[];fresh=0;hits=0
        threads=min(max(1,int(self.c.get('parallel_contracts',4))),6,len(self.contracts))
        with ThreadPoolExecutor(max_workers=threads,thread_name_prefix='Contract') as pool:
            future={pool.submit(self._work,co,now):co for co in self.contracts}
            for f in as_completed(future):
                co=future[f]
                try:
                    out=f.result();fresh+=int(bool(out.get('fresh')));hits+=int(bool(out.get('from_cache')))
                except Exception as e:
                    failures.append(f"{co['symbol']}({co['security_id']}): {type(e).__name__}: {str(e)[:140]}")
                    out={'contract':co,'fresh':False,'error':str(e)[:150],'signals':[]}
                outcomes[co['key']]=out
                with self.lock:
                    self.results[co['key']]=out
                    self.state['processed']=len(outcomes)
                    self.state['revision']+=1
        with self.lock:
            self.results=outcomes
            self.state.update(last_scan=now.isoformat(),contracts=len(self.contracts),fresh=fresh,
                cache_hits=hits,api_fetches=(self.broker.limiter.statistics().get('data',0) if self.broker else 0),
                requests=(self.broker.limiter.statistics() if self.broker else {}),
                last_error=' | '.join(failures[:5]) if failures else None,
                last_errors_count=len(failures),mode=self.mode,
                feed_connected=bool(self.feed and self.feed.last_packet and
                    (now-datetime.fromisoformat(self.feed.last_packet)).total_seconds()<self.c['max_quote_age_seconds']),
                last_feed_packet=self.feed.last_packet if self.feed else None,
                feed_error=self.feed.error if self.feed else None,
                scanning=False)
            status=copy.deepcopy(self.state)
        self.db.set_state('scanner',status)
        self.db.set_state('snapshot',outcomes)
        return status

    def _qualify(self,signals,co,now):
        # This is a separate recommendation gate; does not modify original Pine entry.
        quote=self.feed.snapshot(co['segment'],co['security_id']) if self.feed else {}
        if quote and quote.get('received_at'):
            try:
                if (now-datetime.fromisoformat(quote['received_at'])).total_seconds()>self.c['max_quote_age_seconds']:
                    quote={}
            except (TypeError,ValueError):quote={}
        chain=self.last_chain.get(co['key'],{})
        # A quote/option-chain is independent of REST candle data.
        if self.mode=='live' and not quote:
            try:
                q=self.broker.quote({co['segment']:[int(co['security_id'])]})
                item=q.get(co['segment'],{}).get(co['security_id'],{})
                depth=item.get('depth',{})
                b=(depth.get('buy') or [{}])[0];a=(depth.get('sell') or [{}])[0]
                quote={'ltp':item.get('last_price'),'bid':b.get('price'),'ask':a.get('price'),
                       'received_at':now.isoformat()}
            except Exception as e:
                quote={'error':str(e)[:160]}
        if self.mode=='demo':quote={'ltp':signals[-1]['reference_entry'],'bid':signals[-1]['reference_entry']-.1,
                                     'ask':signals[-1]['reference_entry']+.1,'received_at':now.isoformat()}
        for sig in signals:
            reasons=[]
            if self.mode!='demo' and not quote.get('ltp'):reasons.append('No fresh executable market quote')
            premium=float(quote.get('ask') or quote.get('ltp') or sig['reference_entry'])
            if premium<self.c['min_premium'] or premium>self.c['max_premium']:reasons.append('Premium outside configured bounds')
            bid=float(quote.get('bid') or 0)
            ask=float(quote.get('ask') or 0)
            spread=100*(ask-bid)/((ask+bid)/2) if ask>0 and bid>0 else None
            if spread is None and self.mode=='live':reasons.append('Bid/ask unavailable')
            if spread is not None and spread>self.c['max_spread_pct']:reasons.append(f'Spread too wide ({spread:.1f}%)')
            if self.db.count_open()>=self.c['max_open_manual_positions']:reasons.append('Manual position limit reached')
            maxrisk=float(self.c['max_risk_per_trade_rupees'])
            # Use actual entry estimate for risk, but SL/target from signal are provisional.
            per_lot=abs(premium-sig['sl'])*co['lot_size']
            lots=min(int(self.c['max_lots']),int(maxrisk/per_lot)) if per_lot>0 else 0
            if lots<1:reasons.append('Minimum one lot exceeds risk budget')
            # A signal confirmed on the 14:57–15:00 candle must NOT become a live candidate
            # at/after the configured 15:00 cutoff. Keep the original Pine signal intact;
            # this is a separate safety gate for *recommendations*.
            if now.time()>=dt_time.fromisoformat(self.c['strategy']['entry_cutoff']):
                reasons.append('Entry cutoff reached; no new live entry')
            if now.time()>=dt_time.fromisoformat(self.c['strategy']['force_close']):
                reasons.append('Force-close threshold reached')
            if self.mode=='demo':reasons.append('Demo data is never executable')
            sig.update({'current_quote':quote,'spread_pct':spread,'estimated_buy_price':premium,
                        'estimated_lots':lots,'risk_at_estimate_rupees':per_lot*lots,
                        'recommendation':'WATCHLIST_ONLY' if reasons else 'MANUAL_REVIEW',
                        'risk_flags':reasons,'quote_snapshot_time':quote.get('received_at')})
        return signals

    def status(self):
        with self.lock:return copy.deepcopy(self.state)
    def latest(self):
        with self.lock:return [s for out in self.results.values() for s in out.get('signals',[])]
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.results)
    def loop(self):
        self.stop.clear()
        while not self.stop.is_set():
            t=time.monotonic()
            try:self.scan_once()
            except Exception as e:
                self.state['last_error']=f'{type(e).__name__}: {str(e)[:200]}'
                self.db.set_state('scanner',self.state)
            self.stop.wait(max(1,self.c['poll_seconds']-(time.monotonic()-t)))
    def start_background(self):
        if getattr(self,'thread',None) and self.thread.is_alive():return
        self.thread=threading.Thread(target=self.loop,daemon=True,name='DhanScanner');self.thread.start()
    def shutdown(self):
        self.stop.set()
        with self.lock:
            self.state['running']=False
            self.state['scanning']=False
            status=copy.deepcopy(self.state)
        self.db.set_state('scanner',status)
        if self.feed:self.feed.close()
    def pause(self):
        self.shutdown()
    def resume(self):
        self.stop.clear();self.start_background()

    def position_advisories(self,now=None):
        """Manual exit reminders only. Does NOT control Dhan positions or submit exits."""
        now=now or datetime.now(IST)
        active=[]
        bykey=self.snapshot()
        for trade in self.db.trades():
            if trade['exit_time'] is not None:continue
            item=bykey.get(trade['contract'],{})
            co=item.get('contract',{})
            quote=self.feed.snapshot(co.get('segment',''),co.get('security_id','')) if self.feed else {}
            price=None;asof=None
            if quote and quote.get('ltp') and quote.get('received_at'):
                try:
                    seconds=(now-datetime.fromisoformat(quote['received_at'])).total_seconds()
                    if 0<=seconds<=self.c['max_quote_age_seconds']:
                        price=float(quote['ltp']);asof=quote['received_at']
                except (TypeError,ValueError):pass
            if price is None and item.get('fresh') and item.get('latest',{}).get('close'):
                price=float(item['latest']['close']);asof=item['latest'].get('bar_start')
            flags=[]
            if now.time()>=dt_time(15,20) and now.time()<=dt_time(15,30):flags.append('EOD: manually close if still open')
            if price is None:flags.append('No fresh quote: CHECK DHAN APP; never assume SL protection')
            else:
                if price<=trade['sl']:flags.append('SL LEVEL TOUCHED: CHECK/EXIT MANUALLY')
                if price>=trade['target']:flags.append('TARGET LEVEL TOUCHED: CHECK/EXIT MANUALLY')
            active.append({'trade_id':trade['id'],'contract':trade['contract'],'reported_entry':trade['entry'],
                           'current_indicative_price':price,'asof':asof,'sl':trade['sl'],
                           'target':trade['target'],'advisories':flags,
                           'warning':'ADVISORY ONLY — NO BROKER EXIT ORDER; manual action required'})
        return active

    def record_manual_fill(self,signal_id,entry,lots):
        # This updates only a LOCAL JOURNAL. Never connects to Dhan order API.
        found=self.db.get_signal(signal_id)
        if not found:raise ValueError('Unknown signal ID')
        contract,sig=found
        if int(lots)!=lots or lots<=0:raise ValueError('Lots must be a positive integer')
        if self.db.count_open()>=self.c['max_open_manual_positions']:raise ValueError('Maximum open manual trades reached')
        if not 0<float(entry)<1_000_000:raise ValueError('Invalid fill price')
        co={'lot_size':sig['lot_size'],'tick_size':sig['tick_size']}
        cc=self.c['strategy'];lng=sig['direction']=='LONG'
        # Reconstruct structural fields from signal-time indicator snapshot; avoid mistakenly
        # applying *current* indicators to an older manual trade.
        atr=sig.get('signal_atr');vwap=sig.get('signal_vwap');ema=sig.get('signal_ema50')
        if cc['sl_mode']=='structural' and not (atr is not None and vwap is not None and ema is not None):
            raise ValueError('Missing signal-time structural snapshot; cannot safely recalculate SL')
        t=target(float(entry),float(atr or 0),cc,sig['index'],lng)
        s=stop(float(entry),float(vwap or 0),float(ema or 0),float(atr or 0),cc,float(co['tick_size']),lng)
        total=abs(float(entry)-s)*int(co['lot_size'])*lots
        if total>self.c['max_risk_per_trade_rupees']:raise ValueError(f'Risk ₹{total:.2f} exceeds max trade risk')
        when=datetime.now(IST).isoformat()
        id=self.db.add_manual(signal_id,contract,float(entry),int(lots),int(co['lot_size']),float(t),float(s),when)
        return {'trade_id':id,'journal_only':True,'target':t,'sl':s,'estimated_max_loss_excl_slippage':total}
    def record_manual_exit(self,trade_id,exit_price):
        self.db.exit_manual(int(trade_id),float(exit_price),datetime.now(IST).isoformat())
        return {'trade_id':trade_id,'recorded':True,'broker_order_submitted':False}
