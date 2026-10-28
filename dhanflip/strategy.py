"""Stateful port of user's Pine v6 entry/exit rules. No broker orders in this module.

Signal bar times are candle START times; generated signal is known at bar END.
Theoretical strategy fills take place at following bar OPEN. Manual user fill is separate.
"""
from __future__ import annotations
from datetime import time
import math
import pandas as pd
import numpy as np
from .indicators import enrich


def ok_num(x):
    return x is not None and math.isfinite(float(x))


def target(entry, a, c, index, long=True):
    mode=c['target_mode']
    pts = (20 if index.upper()=='NIFTY' else 50) if mode=='auto' else float(c['target_pts_custom'])
    dist= (pts if mode in ('auto','custom') else entry*c['target_pct']/100 if mode=='percentage' else a*c['target_atr_mult'])
    return entry+(dist if long else -dist)


def stop(entry,vwap,ema50,a,c,tick=0.05,long=True):
    mode=c['sl_mode']; gap=max(tick*2,entry*.0002)
    if mode=='structural':
        raw=min(vwap,ema50) if long else max(vwap,ema50)
        if not ok_num(raw): return math.nan
        clamped=max(raw,entry-c['max_sl_pts']) if long else min(raw,entry+c['max_sl_pts'])
        return min(clamped,entry-gap) if long else max(clamped,entry+gap)
    raw = (entry-c['sl_pts_custom'] if long else entry+c['sl_pts_custom']) if mode=='fixed' else (entry*(1-c['sl_pct']/100) if long else entry*(1+c['sl_pct']/100)) if mode=='percentage' else (entry-a*c['sl_atr_mult'] if long else entry+a*c['sl_atr_mult'])
    return min(raw,entry-gap) if long else max(raw,entry+gap)


def _time(text): return time.fromisoformat(text)


def evaluate(candles:pd.DataFrame, c:dict, index_name:str, tick_size:float=.05)->dict:
    """Replay full history. Returns completed signal events, theoretical trades and last indicator row.

    Ported Pine variants: stop/target set on theoretical NEXT BAR open. The demo replay uses
    bar-range SL priority when SL and target are both hit, preventing optimistic fills.
    """
    if candles.empty: return {'signals':[],'trades':[],'last':{},'rejections':[]}
    if candles.index.tz is None:raise ValueError('Candles require timezone')
    d=enrich(candles,c)
    signals=[];trades=[];rejections=[]
    wait_long=wait_short=False; waited_long=waited_short=0
    position=None;pending=None;prev_day=None;bars_day=0
    for i,(ts,r) in enumerate(d.iterrows()):
        day=ts.date();new_day=day!=prev_day
        if new_day:bars_day=0
        else:bars_day+=1
        prev_day=day
        tm=ts.timetz().replace(tzinfo=None)
        allowed=bars_day>=c['skip_first_n'] and tm<_time(c['entry_cutoff']) and tm<_time(c['force_close'])
        # Original has close_all at EOD; realtime should issue a wall-clock reminder at 15:20.
        forced=tm>=_time(c['force_close']) or (new_day and position is not None)
        if pending and position is None:
            # Close-of-bar Pine strategy fills at next bar open. No fills beyond cutoff.
            if allowed and not new_day:
                px=float(r.open);lng=pending['direction']=='LONG'
                tg=target(px,float(r.atr),c,index_name,lng)
                sl=stop(px,float(r.vwap),float(r.ema50),float(r.atr),c,tick_size,lng)
                if ok_num(sl) and ok_num(tg) and px>0:
                    position={'entry':px,'target':float(tg),'sl':float(sl),'open_time':ts.isoformat(),'side':pending['direction'],'signal_id':pending['id']}
            pending=None
        if position:
            pos=position;lng=pos['side']=='LONG'
            # When stop and target trade in one bar, stop wins (conservative OHLC assumption).
            hit_sl=(r.low<=pos['sl'] if lng else r.high>=pos['sl'])
            hit_tg=(r.high>=pos['target'] if lng else r.low<=pos['target'])
            exit_type='EOD' if forced else ('SL' if hit_sl else 'TARGET' if hit_tg else None)
            if exit_type:
                exit_px=float(r.close) if exit_type=='EOD' else pos['sl'] if hit_sl else pos['target']
                trades.append({**pos,'exit_time':ts.isoformat(),'exit':exit_px,'reason':exit_type,
                               'pnl_points':(exit_px-pos['entry'])*(1 if lng else -1)})
                position=None
        direction=float(r.direction) if ok_num(r.direction) else np.nan
        green=direction<0;red=direction>0
        prevdir=float(d.direction.iloc[i-1]) if i>0 and ok_num(d.direction.iloc[i-1]) else np.nan
        flip_green=green and not (prevdir<0)
        flip_red=red and not (prevdir>0)
        if red or position or new_day:wait_long=False;waited_long=0
        if green or position or new_day:wait_short=False;waited_short=0
        ema200ok_long=not c['use_ema200_filter'] or (r.close>r.ema200 if ok_num(r.ema200) else c['ema200_na_passes'])
        ema200ok_short=not c['use_ema200_filter'] or (r.close<r.ema200 if ok_num(r.ema200) else c['ema200_na_passes'])
        prevst=float(d.st.iloc[i-1]) if i>0 and ok_num(d.st.iloc[i-1]) else np.nan
        prevres=prevst if prevdir>0 else np.nan
        prevsup=prevst if prevdir<0 else np.nan
        stgap_long=abs(r.ema200-prevres) if ok_num(r.ema200) and ok_num(prevres) else np.nan
        stgap_short=abs(r.ema200-prevsup) if ok_num(r.ema200) and ok_num(prevsup) else np.nan
        stmin=r.atr*c['st_proximity_atr_mult']
        stlong=(not c['use_st_proximity_filter'] or
                (not ok_num(stgap_long) and c['st_proximity_na_passes']) or
                not (ok_num(r.ema200) and r.ema200>r.high) or
                (ok_num(stgap_long) and stgap_long>=stmin))
        stshort=(not c['use_st_proximity_filter'] or
                 (not ok_num(stgap_short) and c['st_proximity_na_passes']) or
                 not (ok_num(r.ema200) and r.ema200<r.low) or
                 (ok_num(stgap_short) and stgap_short>=stmin))
        green_vol=not c['use_green_vol_filter'] or (r.close>r.open and ok_num(r.avg_volume) and r.volume>r.avg_volume*c['green_vol_multiplier'])
        red_vol=not c['use_red_vol_filter'] or (r.close<r.open and ok_num(r.avg_volume) and r.volume>r.avg_volume*c['red_vol_multiplier'])
        vol_long=not c['use_vol_filter'] or r.close>r.open
        vol_short=not c['use_vol_filter'] or r.close<r.open

        def dist_ok(long):
            if not c['use_ema200_dist_filter'] or not ok_num(r.ema200):return True
            tg=target(float(r.close),float(r.atr),c,index_name,long)
            distance=abs(tg-r.close)*c['ema200_dist_mult']
            p=float(r.ema200);entry=float(r.close)
            if long:
                in_path=entry<=p<=tg
                close_opp=p>entry and p-entry<distance
                rising=i>1 and p>d.ema200.iloc[i-1]>d.ema200.iloc[i-2]
                approach=c['ema200_check_rising'] and p<=entry and entry-p<distance and rising
            else:
                in_path=tg<=p<=entry
                close_opp=p<entry and entry-p<distance
                falling=i>1 and p<d.ema200.iloc[i-1]<d.ema200.iloc[i-2]
                approach=c['ema200_check_rising'] and p>=entry and p-entry<distance and falling
            return not (in_path or close_opp or approach)

        def propose(side,kind):
            # Proposed entry at completed bar CLOSE; theoretical fill happens next bar open.
            px=float(r.close);lng=side=='LONG'
            tg=target(px,float(r.atr),c,index_name,lng)
            sl=stop(px,float(r.vwap),float(r.ema50),float(r.atr),c,tick_size,lng)
            if not ok_num(tg) or not ok_num(sl) or px<=0: return
            ident=f'{index_name}:{ts.isoformat()}:{side}:{kind}'
            events={'id':ident,'index':index_name,'bar_start':ts.isoformat(),
                    'signal_time':(ts+pd.Timedelta(minutes=3)).isoformat(),
                    'direction':side,'setup':kind,'reference_entry':px,'target':float(tg),'sl':float(sl),
                    'risk_points':abs(px-sl),'reward_points':abs(tg-px),
                    'signal_atr':float(r.atr),'signal_vwap':float(r.vwap),'signal_ema50':float(r.ema50)}
            signals.append(events)
            return events

        if not position and not pending and allowed:
            if c['enable_long'] and flip_green:
                above=r.close>r.ema50;vw=(not c['use_vwap_at_flip'] or r.close>r.vwap)
                dst=dist_ok(True)
                base=above and vw and ema200ok_long and vol_long
                if base and dst and green_vol and stlong:
                    pending=propose('LONG','PRIMARY');wait_long=False;waited_long=0
                elif base and dst and green_vol and not stlong:
                    wait_long=False;waited_long=0
                    rejections.append({'time':ts.isoformat(),'reason':'st-prox','side':'LONG'})
                elif base and not dst:
                    wait_long=False;waited_long=0
                    rejections.append({'time':ts.isoformat(),'reason':'ema200-dist','side':'LONG'})
                else:
                    wait_long=True;waited_long=0
                    rejections.append({'time':ts.isoformat(),'reason':'primary filters; extended waiting','side':'LONG'})
            if c['enable_short'] and flip_red:
                below=r.close<r.ema50;vw=(not c['use_vwap_at_flip'] or r.close<r.vwap)
                dst=dist_ok(False);base=below and vw and ema200ok_short and vol_short
                if base and dst and red_vol and stshort:
                    pending=propose('SHORT','PRIMARY');wait_short=False;waited_short=0
                elif base and dst and red_vol and not stshort:
                    wait_short=False;waited_short=0;rejections.append({'time':ts.isoformat(),'reason':'st-prox','side':'SHORT'})
                elif base and not dst:
                    wait_short=False;waited_short=0;rejections.append({'time':ts.isoformat(),'reason':'ema200-dist','side':'SHORT'})
                else:
                    wait_short=True;waited_short=0
        if not position and not pending and c['enable_long'] and wait_long and not flip_green:
            good=allowed and r.close>r.ema50 and (not c['use_vwap_at_break'] or r.close>r.vwap) and ema200ok_long and vol_long and green_vol and stlong
            if good and dist_ok(True):
                pending=propose('LONG','EXTENDED');wait_long=False;waited_long=0
            else:
                if allowed: waited_long+=1
                if waited_long>=c['extend_candles']:wait_long=False;waited_long=0
        if not position and not pending and c['enable_short'] and wait_short and not flip_red:
            good=allowed and r.close<r.ema50 and (not c['use_vwap_at_break'] or r.close<r.vwap) and ema200ok_short and vol_short and red_vol and stshort
            if good and dist_ok(False):
                pending=propose('SHORT','EXTENDED');wait_short=False;waited_short=0
            else:
                if allowed:waited_short+=1
                if waited_short>=c['extend_candles']:wait_short=False;waited_short=0
    last=d.iloc[-1]
    def safe(x):return float(x) if ok_num(x) else None
    return {'signals':signals,'trades':trades,'rejections':rejections[-100:],
            'last':{'bar_start':d.index[-1].isoformat(),'close':safe(last.close),'ema50':safe(last.ema50),
                    'ema200':safe(last.ema200),'vwap':safe(last.vwap),'atr':safe(last.atr),
                    'supertrend':safe(last.st),'direction':safe(last.direction),'avg_volume':safe(last.avg_volume),
                    'waiting_long':wait_long,'waited_long':waited_long},
            'theoretical_position':position}
