"""DhanFlip V3 unified desktop: scanner, read-only MCP, tunnel, charts and settings."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog,filedialog
from datetime import datetime
from pathlib import Path
import queue,subprocess,sys,socket,os,threading,json
from .config import ROOT,settings
from .scanner import Scanner
from .bars import IST,aggregate_3m
from .indicators import enrich
from .tunnel import TunnelController,load_tunnel_settings,save_tunnel_settings,save_tunnel_key,local_http_status

class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('DhanFlip V3 — NIFTY / SENSEX • 3-minute • Manual execution')
        self.geometry('1220x760');self.minsize(950,560)
        self.svc=Scanner()
        self._mcp_proc=None;self._chart_queue=queue.Queue();self._last_chart_key=None;self.canvas=None
        self._log_file=None
        self.tunnel=TunnelController();self.tunnel_status=tk.StringVar(value='Tunnel stopped');self._last_signal_ids=set()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.mode=tk.StringVar(value='Initializing…');self.selected=tk.StringVar(value='')
        header=ttk.Frame(self,padding=8);header.pack(fill='x')
        ttk.Label(header,text='DHANFLIP V3  •  3-MIN OPTIONS',font=('Segoe UI',15,'bold')).pack(side='left')
        ttk.Label(header,textvariable=self.mode).pack(side='right',padx=9)
        controls=ttk.Frame(self,padding=(8,0,8,3));controls.pack(fill='x')
        self.start_btn=ttk.Button(controls,text='▶ Start Scanner',command=self.start_scanner)
        self.start_btn.pack(side='left',padx=3)
        self.stop_btn=ttk.Button(controls,text='■ Stop Scanner',command=self.stop_scanner)
        self.stop_btn.pack(side='left',padx=3)
        ttk.Button(controls,text='↻ Refresh',command=self.refresh_scan).pack(side='left',padx=3)
        ttk.Button(controls,text='Dhan Credentials',command=self.set_credentials).pack(side='left',padx=3)
        ttk.Button(controls,text='Test Dhan API',command=self.test_dhan).pack(side='left',padx=3)
        self.want_live=tk.StringVar(value=self.svc.mode)
        ttk.Label(controls,text='Data:').pack(side='left',padx=(12,2))
        ttk.Combobox(controls,textvariable=self.want_live,values=['demo','live'],width=6,state='readonly').pack(side='left')
        ttk.Button(controls,text='Apply',command=self.apply_mode).pack(side='left',padx=3)
        mcp_controls=ttk.Frame(self,padding=(8,0,8,7));mcp_controls.pack(fill='x')
        ttk.Label(mcp_controls,text='ChatGPT (optional):').pack(side='left',padx=3)
        self.mcp_btn=ttk.Button(mcp_controls,text='▶ Start MCP',command=self.start_mcp)
        self.mcp_btn.pack(side='left',padx=3)
        ttk.Button(mcp_controls,text='■ Stop MCP',command=self.stop_mcp).pack(side='left',padx=3)
        ttk.Button(mcp_controls,text='Connect ChatGPT',command=self.connect_chatgpt).pack(side='left',padx=3)
        ttk.Button(mcp_controls,text='■ Stop Tunnel',command=self.stop_tunnel).pack(side='left',padx=3)
        ttk.Button(mcp_controls,text='Configure Tunnel',command=self.configure_tunnel).pack(side='left',padx=3)
        self.mcp_status=tk.StringVar(value='MCP stopped')
        ttk.Label(self,textvariable=self.mcp_status,anchor='w').pack(fill='x',padx=12)
        ttk.Label(self,textvariable=self.tunnel_status,anchor='w').pack(fill='x',padx=12)
        if self.svc.c.get('auto_start_scanner',True):self.after(200,self.start_scanner)
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True,padx=10,pady=6)
        self.t_signals=ttk.Frame(self.tabs,padding=8);self.t_chart=ttk.Frame(self.tabs,padding=8);self.t_journal=ttk.Frame(self.tabs,padding=8);self.t_settings=ttk.Frame(self.tabs,padding=8);self.t_diagnostics=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(self.t_signals,text='Signals and contracts');self.tabs.add(self.t_chart,text='3-minute option chart');self.tabs.add(self.t_journal,text='Manual trade journal')
        self.tabs.add(self.t_settings,text='Strategy & Risk Settings');self.tabs.add(self.t_diagnostics,text='Diagnostics')
        cols=['Index','Type','Strike','Expiry','Last Premium','EMA50','VWAP','ST Dir','Fresh','Signals','Error']
        self.table=self._tree(self.t_signals,cols,7)
        self.table.bind('<<TreeviewSelect>>',self.on_select)
        action=ttk.Frame(self.t_signals);action.pack(fill='x',pady=5)
        ttk.Button(action,text='Inspect selected',command=self.show_detail).pack(side='left',padx=4)
        ttk.Button(action,text='Show latest signals',command=self.show_signals).pack(side='left',padx=4)
        ttk.Button(action,text='Record MANUAL fill (journal only)',command=self.record_fill).pack(side='right',padx=4)
        ttk.Label(self.t_signals,text='Current trade proposals (requires manual approval/execution in Dhan)',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(5,2))
        self.proposals=self._tree(self.t_signals,['Contract','Setup','Signal time','Entry','SL','Target','Status / risk'],4)
        self.details=tk.Text(self.t_signals,height=6,wrap='word',font=('Consolas',10));self.details.pack(fill='both',expand=True)
        self.chart_toolbar=ttk.Frame(self.t_chart);self.chart_toolbar.pack(fill='x')
        ttk.Button(self.chart_toolbar,text='Plot selected contract',command=self.draw_chart).pack(side='left')
        self.chart_area=ttk.Frame(self.t_chart);self.chart_area.pack(fill='both',expand=True)
        self.trades=self._tree(self.t_journal,['ID','Contract','Entry','Lots','Target','SL','Exit','P&L before costs'])
        action2=ttk.Frame(self.t_journal);action2.pack(fill='x',pady=8)
        ttk.Button(action2,text='Record manual exit',command=self.record_exit).pack(side='left')
        ttk.Button(action2,text='Refresh journal',command=self.update_trades).pack(side='left',padx=8)
        self.footer=tk.StringVar(value='Orders must be placed manually in Dhan. Demo cannot trade.')
        ttk.Label(self,textvariable=self.footer,anchor='w',foreground='#a33').pack(fill='x',padx=12,pady=5)
        self._init_settings_tab();self._init_diagnostics_tab()
        self._last_revision=-1;self._chart_loading=False;self._polls=0;self.after(400,self.poll)


    def start_scanner(self):
        self.svc.resume()
        self.mode.set('Scanner running — loading cached data…')
    def stop_scanner(self):
        self.svc.pause()
        self.mode.set('Scanner stopped')
    def apply_mode(self):
        requested=self.want_live.get()
        if requested==self.svc.mode:return
        if self.svc.status().get('scanning'):
            messagebox.showinfo('Scan active','Stop and finish the current scan before switching data modes.');return
        self.svc.shutdown()
        old_thread=getattr(self.svc,'thread',None)
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=3)
            if old_thread.is_alive():
                messagebox.showwarning('Scanner finishing','The in-flight API scan is still finishing. Wait for it to stop before changing modes.')
                return
        # Persist only the mode setting; all indicator settings preserved.
        import yaml
        path=ROOT/'config/settings.yaml'
        cfg=settings();cfg['mode']=requested
        path.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
        try:new=Scanner(config=cfg)
        except Exception as exc:
            cfg['mode']=self.svc.mode;path.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
            messagebox.showerror('Cannot enable live mode',str(exc));return
        self.svc=new;self._last_revision=-1;self.selected.set('')
        self.start_scanner()
    def set_credentials(self):
        from dotenv import dotenv_values,load_dotenv
        current=dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
        window=tk.Toplevel(self);window.title('Dhan API credentials — local only');window.resizable(False,False)
        ttk.Label(window,text='Dhan Client ID').grid(row=0,column=0,padx=12,pady=9,sticky='w')
        e1=ttk.Entry(window,width=46);e1.grid(row=0,column=1,padx=12,pady=9)
        e1.insert(0,current.get('DHAN_CLIENT_ID',''))
        ttk.Label(window,text='Access token (24-hour validity)').grid(row=1,column=0,padx=12,pady=9,sticky='w')
        e2=ttk.Entry(window,width=46,show='●');e2.grid(row=1,column=1,padx=12,pady=9)
        e2.insert(0,current.get('DHAN_ACCESS_TOKEN',''))
        def save():
            client=e1.get().strip();token=e2.get().strip()
            if not client or not token or '\n' in client or '\n' in token or '\r' in token:
                messagebox.showerror('Invalid values','Enter a valid client ID and access token.',parent=window);return
            (ROOT/'.env').write_text('DHAN_CLIENT_ID='+client+'\nDHAN_ACCESS_TOKEN='+token+'\n',encoding='utf-8')
            try:os.chmod(ROOT/'.env',0o600)
            except OSError:pass
            load_dotenv(ROOT/'.env',override=True)
            window.destroy()
            messagebox.showinfo('Saved locally','Saved to .env. Restart the application if live scanner was already running to reload credentials.')
        ttk.Button(window,text='Save locally',command=save).grid(row=2,column=1,sticky='e',pady=8,padx=12)
    def test_dhan(self):
        self.mcp_status.set('Testing Dhan token and data plan…')
        def work():
            try:
                from .config import secrets
                from .dhan import DhanReadOnly
                obj=(self.svc.broker if self.svc.mode=='live' else DhanReadOnly(*secrets())).profile()
                self._chart_queue.put(('connection',obj))
            except Exception as exc:self._chart_queue.put(('connection_error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    @staticmethod
    def _port_busy(port=8766):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.25):return True
        except OSError:return False
    def start_mcp(self):
        if self._mcp_proc and self._mcp_proc.poll() is None:
            self.mcp_status.set('MCP already running on localhost:8766/mcp');return
        if self._port_busy():
            self.mcp_status.set('Port 8766 already occupied — check existing MCP service');return
        logs=ROOT/'logs';logs.mkdir(exist_ok=True)
        self._log_file=(logs/'mcp.log').open('ab')
        # Dhan credentials are not needed in the cache-only MCP subprocess.
        env={k:v for k,v in os.environ.items() if k not in ('DHAN_CLIENT_ID','DHAN_ACCESS_TOKEN','CONTROL_PLANE_API_KEY','OPENAI_API_KEY','OPENAI_ADMIN_KEY')}
        self._mcp_proc=subprocess.Popen([sys.executable,'-m','dhanflip','mcp-http','--port','8766'],
            cwd=ROOT,env=env,stdout=self._log_file,stderr=subprocess.STDOUT)
        self.mcp_status.set('Starting cache-only MCP on 127.0.0.1:8766/mcp…')
    def stop_mcp(self):
        # A tunnel must not be left forwarding to a stopped MCP backend.
        self.tunnel.stop();self.tunnel_status.set('Tunnel stopped')
        if self._mcp_proc and self._mcp_proc.poll() is None:
            self._mcp_proc.terminate()
            try:self._mcp_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self._mcp_proc.kill()
        self._mcp_proc=None
        if self._log_file:self._log_file.close();self._log_file=None
        self.mcp_status.set('MCP stopped')

    def configure_tunnel(self):
        cfg=load_tunnel_settings()
        w=tk.Toplevel(self);w.title('OpenAI tunnel-client — local configuration');w.geometry('850x255')
        exe=tk.StringVar(value=cfg['executable']);prof=tk.StringVar(value=cfg['config']);adm=tk.StringVar(value=cfg['admin_url']);secret=tk.StringVar()
        for i,(caption,var,browse) in enumerate([('Tunnel executable',exe,True),('Existing tunnel YAML profile',prof,True),('Local admin URL',adm,False),('Control-plane API key (optional replace)',secret,False)]):
            ttk.Label(w,text=caption).grid(row=i,column=0,padx=8,pady=10,sticky='w')
            ttk.Entry(w,textvariable=var,width=73,show='●' if i==3 else '').grid(row=i,column=1,padx=5,pady=7,sticky='we')
            if browse:
                ttk.Button(w,text='Browse',command=lambda v=var:v.set(filedialog.askopenfilename(parent=w) or v.get())).grid(row=i,column=2,padx=8)
        def save():
            try:
                save_tunnel_settings(exe.get().strip(),prof.get().strip(),adm.get().strip())
                if secret.get():save_tunnel_key(secret.get())
                w.destroy();self.tunnel_status.set('Tunnel settings saved locally; press Connect ChatGPT')
            except Exception as exc:messagebox.showerror('Invalid configuration',str(exc),parent=w)
        ttk.Button(w,text='Save local settings',command=save).grid(row=5,column=1,pady=10,sticky='e')
        ttk.Label(w,text='A running tunnel is NOT proof of ChatGPT registration; authorize the connector once in ChatGPT.').grid(row=6,column=0,columnspan=3,sticky='w',padx=9)

    def connect_chatgpt(self):
        """Start read-only MCP and tunnel, verifying local MCP before tunnel launch."""
        self.start_mcp()
        self.tunnel_status.set('Starting local MCP then OpenAI tunnel…')
        threading.Thread(target=self._connect_worker,daemon=True).start()

    def _connect_worker(self):
        import time
        for _ in range(40):
            if self._port_busy(8766):break
            time.sleep(.2)
        else:
            self._chart_queue.put(('tunnel_error','Local MCP server on port 8766 did not start; see logs/mcp.log'))
            return
        if not (self._mcp_proc and self._mcp_proc.poll() is None):
            self._chart_queue.put(('tunnel_error','Refusing tunnel startup: MCP server is not owned by this application'))
            return
        try:
            info=self.tunnel.start()
            self._chart_queue.put(('tunnel_ok',info['message']))
        except Exception as exc:self._chart_queue.put(('tunnel_error',str(exc)))

    def stop_tunnel(self):
        self.tunnel.stop();self.tunnel_status.set('Tunnel stopped (local MCP may still run)')

    def _notify_signals(self):
        if self.svc.mode!='live':return
        ids={s['id'] for s in self.svc.latest() if s.get('recommendation')=='MANUAL_REVIEW'}
        new=ids-self._last_signal_ids
        if new:
            try:self.bell()
            except tk.TclError:pass
            self.footer.set(f'{len(new)} new advisory signal(s). Review manually in Dhan; no order was placed.')
        self._last_signal_ids=ids

    def _init_settings_tab(self):
        import yaml
        pane=ttk.Frame(self.t_settings);pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='Settings for the original Pine-equivalent strategy. Changes take effect after restart.',
                  font=('Segoe UI',11,'bold')).pack(anchor='w',pady=6)
        outer=ttk.Frame(pane);outer.pack(fill='both',expand=True)
        cvs=tk.Canvas(outer,borderwidth=0,highlightthickness=0);scroll=ttk.Scrollbar(outer,orient='vertical',command=cvs.yview)
        inner=ttk.Frame(cvs);inner.bind('<Configure>',lambda _e:cvs.configure(scrollregion=cvs.bbox('all')))
        cvs.create_window((0,0),window=inner,anchor='nw');cvs.configure(yscrollcommand=scroll.set)
        cvs.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self._setting_vars={};cfg=self.svc.c
        exposed=['strikes_each_side','poll_seconds','chain_refresh_seconds','max_risk_per_trade_rupees',
                  'max_lots','max_spread_pct','max_premium','min_premium','auto_start_scanner']
        sc=['atr_period','factor','ema50_length','ema200_length','use_ema200_filter','ema200_na_passes',
            'use_vwap_at_flip','use_vwap_at_break','use_ema200_dist_filter','ema200_dist_mult',
            'ema200_check_rising','use_st_proximity_filter','st_proximity_atr_mult','st_proximity_na_passes',
            'enable_long','enable_short','extend_candles','target_mode','target_pts_custom','target_pct',
            'target_atr_mult','sl_mode','sl_pts_custom','sl_pct','sl_atr_mult','max_sl_pts',
            'vcb_length','use_vol_filter','use_green_vol_filter','green_vol_multiplier',
            'use_red_vol_filter','red_vol_multiplier','skip_first_n','entry_cutoff','force_close']
        def draw_section(keys,d,where):
            for key in keys:
                original=d[key]
                var=tk.BooleanVar(value=original) if isinstance(original,bool) else tk.StringVar(value=str(original))
                self._setting_vars[(where,key)]=(var,type(original))
                row=ttk.Frame(inner,padding=2);row.pack(fill='x')
                ttk.Label(row,text=(where+'.' if where else '')+key,width=39).pack(side='left')
                if isinstance(original,bool):ttk.Checkbutton(row,variable=var).pack(side='left')
                elif key=='target_mode':ttk.Combobox(row,textvariable=var,state='readonly',values=['auto','custom','percentage','atr'],width=25).pack(side='left')
                elif key=='sl_mode':ttk.Combobox(row,textvariable=var,state='readonly',values=['structural','fixed','percentage','atr'],width=25).pack(side='left')
                else:ttk.Entry(row,textvariable=var,width=29).pack(side='left')
        ttk.Label(inner,text='Scanner and risk',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=5)
        draw_section(exposed,cfg,'')
        ttk.Separator(inner).pack(fill='x',pady=9)
        ttk.Label(inner,text='Original Pine strategy',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=5)
        draw_section(sc,cfg['strategy'],'strategy')
        actions=ttk.Frame(pane);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Save strategy settings',command=self.save_strategy_settings).pack(side='left')
        ttk.Label(actions,text='Restart application after saving; the running scanner is not modified.',foreground='#a33').pack(side='left',padx=12)

    def save_strategy_settings(self):
        import yaml,copy,math
        cfg=copy.deepcopy(self.svc.c)
        try:
            for (where,key),(var,kind) in self._setting_vars.items():
                raw=var.get()
                value=(bool(raw) if kind is bool else kind(raw))
                if isinstance(value,float) and not math.isfinite(value):raise ValueError(key+' must be finite')
                (cfg['strategy'] if where else cfg)[key]=value
            if cfg['strikes_each_side']<0 or cfg['strikes_each_side']>20:raise ValueError('strikes_each_side must be 0–20')
            if cfg['poll_seconds']<5:raise ValueError('poll_seconds must be >= 5')
            if cfg['max_lots']<1 or cfg['max_risk_per_trade_rupees']<=0:raise ValueError('Invalid risk limits')
            if cfg['strategy']['extend_candles'] not in range(5,31):raise ValueError('extend_candles must be 5–30')
            if cfg['strategy']['atr_period']<1 or cfg['strategy']['factor']<=0:raise ValueError('Invalid SuperTrend parameters')
            if cfg['strategy']['ema50_length']<1 or cfg['strategy']['ema200_length']<1:raise ValueError('EMA lengths must be > 0')
            if cfg['strategy']['vcb_length']<1:raise ValueError('VCB length must be > 0')
            if cfg['strategy']['entry_cutoff']>cfg['strategy']['force_close']:raise ValueError('Entry cutoff must precede EOD close')
            (ROOT/'config/settings.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf-8')
            messagebox.showinfo('Saved','Settings written. Restart DhanFlip to apply them safely.')
        except Exception as exc:messagebox.showerror('Invalid settings',str(exc))

    def _init_diagnostics_tab(self):
        act=ttk.Frame(self.t_diagnostics);act.pack(fill='x')
        ttk.Button(act,text='Refresh diagnostics',command=self.show_diagnostics).pack(side='left',padx=5)
        ttk.Button(act,text='Open logs folder',command=self.open_logs).pack(side='left',padx=5)
        self.diag=tk.Text(self.t_diagnostics,height=30,wrap='word',font=('Consolas',10));self.diag.pack(fill='both',expand=True,pady=5)
        self.after(1200,self.show_diagnostics)

    def open_logs(self):
        import subprocess,os
        dest=ROOT/'logs';dest.mkdir(parents=True,exist_ok=True)
        try:
            if sys.platform.startswith('win'):os.startfile(dest)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(dest)])
            else:subprocess.Popen(['xdg-open',str(dest)])
        except Exception as exc:messagebox.showwarning('Logs folder',str(dest)+'\n'+str(exc))

    def show_diagnostics(self):
        cfg=load_tunnel_settings()
        out={'scanner':self.svc.status(),'mcp_process_started':bool(self._mcp_proc and self._mcp_proc.poll() is None),
             'mcp_local':local_http_status('http://127.0.0.1:8766/mcp'),
             'tunnel':self.tunnel.status(),
             'data_db':str(self.svc.db.path),'credentials_file_present':(ROOT/'.env').exists(),
             'tunnel_configured':bool(cfg.get('config') and cfg.get('executable')),
             'important':'The MCP tool does not submit orders. Tunnel ready is not proof of ChatGPT connector registration.'}
        self.diag.delete('1.0','end');self.diag.insert('end',json.dumps(out,indent=2,default=str))
        for name in ['mcp.log','tunnel.log']:
            file=ROOT/'logs'/name
            if file.exists():
                recent=file.read_bytes()[-2000:].decode('utf-8','replace')
                import re
                recent=re.sub(r'(?i)(?:access-token|CONTROL_PLANE_API_KEY|DHAN_ACCESS_TOKEN)[=:][^\s]+',r'\1=[REDACTED]',recent)
                self.diag.insert('end','\n--- '+name+' (last 2000 bytes) ---\n'+recent)

    def _tree(self,parent,columns,height=11):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tv=ttk.Treeview(frame,columns=columns,show='headings',height=height)
        for c in columns:tv.heading(c,text=c);tv.column(c,width=105,anchor='center',stretch=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=tv.yview);tv.configure(yscrollcommand=scroll.set)
        tv.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        return tv
    def refresh_scan(self):
        # Skip overlap. Never queue an unbounded backlog of scans.
        if self.svc.status().get('scanning'):return
        threading.Thread(target=self._scan_thread,daemon=True).start()
    def _scan_thread(self):
        try:self.svc.scan_once()
        except Exception as exc:self._chart_queue.put(('scan_error',str(exc)))
    def poll(self):
        while True:
            try:event,data=self._chart_queue.get_nowait()
            except queue.Empty:break
            if event=='chart':self._show_chart(*data)
            elif event=='chart_error':self._chart_error(data)
            elif event=='connection':self.mcp_status.set('Dhan profile: '+json.dumps(data))
            elif event=='connection_error':self.mcp_status.set('Dhan connection ERROR: '+data[:160])
            elif event=='scan_error':self.mcp_status.set('Scanner error: '+data[:160])
            elif event=='tunnel_ok':self.tunnel_status.set('Tunnel: '+data)
            elif event=='tunnel_error':self.tunnel_status.set('Tunnel error: '+data[:150])
        s=self.svc.status();self.mode.set(f"{s['mode'].upper()} | {s.get('processed',0)} scanned | {s['fresh']}/{s['contracts']} fresh | cache hits {s.get('cache_hits',0)} | {'SCANNING' if s.get('scanning') else 'READY' if s.get('running') else 'STOPPED'}")
        if s.get('revision',0)!=self._last_revision:
            self._last_revision=s.get('revision',0);self.render();self.update_trades();self._notify_signals()
        if self._mcp_proc and self._mcp_proc.poll() is None:self.mcp_status.set('MCP running: http://127.0.0.1:8766/mcp (cache-only)')
        elif self._mcp_proc and self._mcp_proc.poll() is not None:self.mcp_status.set('MCP exited — see logs/mcp.log')
        self._polls+=1
        if self._polls%6==0:
            try:
                ts=self.tunnel.status()
                state='READY' if ts['ready']['http_status']==200 else 'running (not ready)' if ts['process_started_by_this_app'] else 'stopped'
                self.tunnel_status.set('Tunnel: '+state+' | ChatGPT app registration must be confirmed in ChatGPT')
            except Exception as exc:self.tunnel_status.set('Tunnel status unavailable: '+str(exc)[:90])
        advs=self.svc.position_advisories()
        reminders=[f"trade {a['trade_id']}: {','.join(a['advisories'])}" for a in advs if a['advisories']]
        self.footer.set(('DEMO DATA — no actual market prices. ' if s['mode']=='demo' else 'LIVE READ-ONLY market data. ') +
                        ('Data errors: '+str(s['last_error'])[:120] if s['last_error'] else 'No API orders, no automatic exits; trade manually in Dhan.')+((' | '+reminders[0]) if reminders else ''))
        self.after(900,self.poll)
    def render(self):
        prior=self.selected.get(); rows=self.svc.snapshot();self.table.delete(*self.table.get_children())
        for key,ob in rows.items():
            co=ob['contract'];last=ob.get('latest',{})
            sigs=ob.get('signals',[])
            item=(co['index'],co['type'],co['strike'],co['expiry'],_fmt(last.get('close')),_fmt(last.get('ema50')),_fmt(last.get('vwap')),
                  'Green' if last.get('direction')==-1 else 'Red' if last.get('direction')==1 else '—',
                  'YES' if ob.get('fresh') else 'NO',','.join(x['setup'] for x in sigs) or '—',ob.get('error',''))
            self.table.insert('', 'end',iid=key,values=item)
        if prior in rows:self.table.selection_set(prior)
        self.proposals.delete(*self.proposals.get_children())
        for sig in self.svc.latest():
            quote=sig.get('estimated_buy_price') or sig.get('reference_entry')
            status=sig.get('recommendation','HISTORICAL')
            flags='; '.join(sig.get('risk_flags',[])[:2])
            self.proposals.insert('', 'end',values=(sig.get('symbol'),sig.get('setup'),sig.get('signal_time'),
                _fmt(quote),_fmt(sig.get('sl')),_fmt(sig.get('target')),status+(' — '+flags if flags else '')))
    def on_select(self,event=None):
        sels=self.table.selection()
        if sels:self.selected.set(sels[0])
    def show_detail(self):
        key=self.selected.get();res=self.svc.snapshot().get(key)
        import json
        self.details.delete('1.0','end')
        self.details.insert('end',json.dumps(res or {'error':'Select a contract'},indent=2,default=str))
    def show_signals(self):
        import json
        self.details.delete('1.0','end')
        self.details.insert('end',json.dumps(self.svc.latest() or self.svc.db.signals(10),indent=2,default=str))
    def record_fill(self):
        signals=self.svc.db.signals(50)
        if not signals:messagebox.showinfo('No signals','No recorded strategy signals');return
        w=tk.Toplevel(self);w.title('Record a manual Dhan fill — LOCAL JOURNAL ONLY');w.geometry('850x225')
        entries={}
        for s in signals:
            txt=f"{s.get('index')} {s.get('strike')} {s.get('type')} {s.get('setup')} @ {s.get('signal_time')} | {s['id']}"
            entries[txt]=s['id']
        selection=tk.StringVar(value=next(iter(entries)))
        ttk.Label(w,text='Select recorded signal (no order will be submitted)').pack(anchor='w',padx=12,pady=(12,3))
        ttk.Combobox(w,textvariable=selection,values=list(entries),width=115,state='readonly').pack(fill='x',padx=12)
        row=ttk.Frame(w);row.pack(fill='x',padx=12,pady=12)
        ttk.Label(row,text='Actual executed premium ₹').pack(side='left')
        premium=tk.StringVar();ttk.Entry(row,textvariable=premium,width=14).pack(side='left',padx=6)
        ttk.Label(row,text='Lots').pack(side='left',padx=(15,0))
        qty=tk.StringVar(value='1');ttk.Entry(row,textvariable=qty,width=8).pack(side='left',padx=6)
        def accept():
            try:
                result=self.svc.record_manual_fill(entries[selection.get()],float(premium.get()),int(qty.get()))
                self.update_trades();w.destroy()
                messagebox.showinfo('Recorded locally','Journal trade #'+str(result['trade_id'])+
                    f"\nTarget {result['target']:.2f} / SL {result['sl']:.2f}\nNO BROKER ORDER WAS SENT")
            except Exception as exc:messagebox.showerror('Validation error',str(exc),parent=w)
        ttk.Button(w,text='Record manual fill (local only)',command=accept).pack(anchor='e',padx=12,pady=8)

    def record_exit(self):
        trade_id=simpledialog.askinteger('Manual exit','Journal trade ID:',minvalue=1,parent=self)
        if trade_id is None:return
        px=simpledialog.askfloat('Manual exit','Actual exit premium ₹:',minvalue=.01,parent=self)
        if px is None:return
        try:self.svc.record_manual_exit(trade_id,px);self.update_trades()
        except Exception as e:messagebox.showerror('Exit error',str(e))
    def update_trades(self):
        self.trades.delete(*self.trades.get_children())
        for t in self.svc.db.trades():
            pnl='' if t['exit_price'] is None else round((t['exit_price']-t['entry'])*t['lot_size']*t['lots'],2)
            self.trades.insert('', 'end', values=(t['id'],t['contract'],t['entry'],t['lots'],_fmt(t['target']),_fmt(t['sl']),_fmt(t['exit_price']),pnl))
    def draw_chart(self):
        key=self.selected.get()
        if not key:
            messagebox.showinfo('Select contract','Select a contract in Signals first')
            return
        if self._chart_loading:return
        # Reuse the already rendered chart until the underlying minute cache changes.
        mark=self.svc.db.last_candle(key)
        if key==self._last_chart_key and mark==getattr(self,'_last_chart_minute',None) and self.canvas:
            self.tabs.select(self.t_chart);return
        self._chart_loading=True
        self.tabs.select(self.t_chart)
        for item in self.chart_area.winfo_children():item.destroy()
        ttk.Label(self.chart_area,text='Loading 3-minute chart…',padding=18).pack(anchor='center')
        import threading
        threading.Thread(target=self._prepare_chart,args=(key,),daemon=True).start()

    def _prepare_chart(self,key):
        # SQLite reads, indicators, and plotting preparation never block Tk UI.
        try:
            import numpy as np
            from matplotlib.figure import Figure
            from matplotlib.collections import LineCollection,PolyCollection
            candles=self.svc.db.candles(key)
            bars=aggregate_3m(candles,datetime.now(IST))
            if len(bars)<20:raise ValueError('Insufficient 3-minute data')
            d=enrich(bars,self.svc.c['strategy']).tail(110)
            xs=np.arange(len(d),dtype=float)
            up=(d.close.to_numpy()>=d.open.to_numpy())
            colors=np.where(up,'#13976d','#bd423a').tolist()
            op=d.open.to_numpy(dtype=float);cl=d.close.to_numpy(dtype=float)
            lo=d.low.to_numpy(dtype=float);hi=d.high.to_numpy(dtype=float)
            vol=d.volume.to_numpy(dtype=float)
            fig=Figure(figsize=(11,6),dpi=105)
            ax=fig.add_subplot(211);v=fig.add_subplot(212,sharex=ax)
            ax.add_collection(LineCollection([[ (x,l),(x,h) ] for x,l,h in zip(xs,lo,hi)],colors=colors,linewidths=.85))
            body=[[(x-.3,min(o,c)),(x+.3,min(o,c)),(x+.3,max(o,c,min(o,c)+.02)),(x-.3,max(o,c,min(o,c)+.02))] for x,o,c in zip(xs,op,cl)]
            ax.add_collection(PolyCollection(body,facecolors=colors,edgecolors=colors,linewidths=.4))
            heights=[[(x-.35,0),(x+.35,0),(x+.35,y),(x-.35,y)] for x,y in zip(xs,vol)]
            v.add_collection(PolyCollection(heights,facecolors=colors,edgecolors=colors))
            ax.set_xlim(-1,len(d));pad=max(1.,(max(hi)-min(lo))*.06)
            ax.set_ylim(min(lo)-pad,max(hi)+pad)
            v.set_ylim(0,max(vol)*1.12 if len(vol) else 1)
            for line,color,label in [('ema50','#2563eb','EMA50'),('ema200','#7c3aed','EMA200'),('vwap','#d97706','VWAP'),('st','#64748b','SuperTrend')]:
                ax.plot(xs,d[line].to_numpy(dtype=float),color=color,linewidth=1.05,label=label)
            ax.legend(fontsize=8,loc='upper left');ax.set_title(key+' — 3m option premium')
            labels=list(range(0,len(d),max(1,len(d)//8)))
            v.set_xticks(labels);v.set_xticklabels([d.index[i].strftime('%d %H:%M') for i in labels],rotation=25,fontsize=8)
            fig.tight_layout()
            self._chart_queue.put(('chart',(fig,key)))
        except Exception as e:
            msg=str(e)
            self._chart_queue.put(('chart_error',msg))

    def _show_chart(self,fig,key):
        for item in self.chart_area.winfo_children():item.destroy()
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.canvas=FigureCanvasTkAgg(fig,master=self.chart_area)
        self.canvas.draw_idle()
        self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self._chart_loading=False
        self._last_chart_key=key
        self._last_chart_minute=self.svc.db.last_candle(key)

    def _chart_error(self,msg):
        self._chart_loading=False
        for item in self.chart_area.winfo_children():item.destroy()
        ttk.Label(self.chart_area,text='Chart unavailable: '+msg).pack(pady=15)
    def close(self):
        self.svc.shutdown();self.tunnel.stop();self.stop_mcp();self.destroy()

def _fmt(x):
    try:return '—' if x is None else f'{float(x):.2f}'
    except (TypeError,ValueError):return '—'

def run_gui():Dashboard().mainloop()
