"""Run/stop existing OpenAI tunnel-client via local profile with non-logged secrets.

Tunnel health is NOT equivalent to ChatGPT connection or tool authorization.
No Dhan token is ever sent to the tunnel subprocess by this controller.
"""
from __future__ import annotations
import os, json, subprocess, threading, sys, urllib.request, urllib.error, time
from pathlib import Path
from dotenv import dotenv_values
import yaml
from .config import ROOT

CONFIG_FILE = ROOT / 'config' / 'tunnel.local.json'
KEY_FILE = ROOT / '.env.tunnel'
DEFAULTS = {'executable': '', 'config': '', 'admin_url': 'http://127.0.0.1:8082', 'enabled': False}


def _safe_log_dir():
    p=ROOT / 'logs';p.mkdir(parents=True,exist_ok=True);return p


def load_tunnel_settings():
    c=DEFAULTS.copy()
    if CONFIG_FILE.exists():
        raw=json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        if not isinstance(raw,dict):raise ValueError('Invalid tunnel config')
        c.update({k:raw[k] for k in DEFAULTS if k in raw})
    return c


def save_tunnel_settings(executable,config,admin_url='http://127.0.0.1:8082'):
    ex=str(Path(executable).expanduser()) if executable else ''
    cf=str(Path(config).expanduser()) if config else ''
    if not admin_url.startswith(('http://127.0.0.1:','http://localhost:')):
        raise ValueError('Tunnel admin URL must point to localhost')
    data={'executable':ex,'config':cf,'admin_url':admin_url,'enabled':True}
    CONFIG_FILE.parent.mkdir(parents=True,exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    try:os.chmod(CONFIG_FILE,0o600)
    except OSError:pass
    return data


def save_tunnel_key(key):
    if not key or '\n' in key or '\r' in key or '"' in key:raise ValueError('Invalid tunnel API key')
    # File is local + .gitignored, credentials are never embedded in commands or YAML.
    KEY_FILE.write_text('CONTROL_PLANE_API_KEY='+key+'\n',encoding='utf-8')
    try:os.chmod(KEY_FILE,0o600)
    except OSError:pass


def local_http_status(url,timeout=1):
    if not url.startswith(('http://127.0.0.1:','http://localhost:')):
        raise ValueError('Health checks restricted to localhost')
    try:
        with urllib.request.urlopen(url,timeout=timeout) as res:
            return {'reachable':True,'http_status':res.status}
    except urllib.error.HTTPError as e:
        # MCP may validly return non-200 for GET; socket still reachable.
        return {'reachable':True,'http_status':e.code}
    except (urllib.error.URLError,TimeoutError,OSError):
        return {'reachable':False,'http_status':None}


class TunnelController:
    def __init__(self):
        self.proc=None;self._log=None;self._lock=threading.RLock();self.last_error=''
    def start(self):
        with self._lock:
            if self.proc and self.proc.poll() is None:return {'running':True,'message':'Tunnel already started'}
            opts=load_tunnel_settings()
            binary=Path(opts['executable']).expanduser()
            profile=Path(opts['config']).expanduser()
            if not binary.is_file():raise FileNotFoundError('Choose an existing tunnel-client executable')
            if not profile.is_file():raise FileNotFoundError('Choose your existing tunnel-client YAML profile')
            loaded=yaml.safe_load(profile.read_text(encoding='utf-8')) or {}
            urls=(loaded.get('mcp') or {}).get('server_urls') or []
            if not any(isinstance(c,dict) and c.get('channel')=='main' and
                       c.get('url')=='http://127.0.0.1:8766/mcp' for c in urls):
                raise ValueError('Selected tunnel profile does not route main to DhanFlip http://127.0.0.1:8766/mcp; create a dedicated DhanFlip profile')
            # Never launch a remote URL or pass key on the CLI (would leak in process listing).
            env={k:v for k,v in os.environ.items() if k not in ('DHAN_CLIENT_ID','DHAN_ACCESS_TOKEN')}
            env.update({k:v for k,v in dotenv_values(KEY_FILE).items() if k=='CONTROL_PLANE_API_KEY' and v})
            if not env.get('CONTROL_PLANE_API_KEY'):
                raise ValueError('Set the OpenAI CONTROL_PLANE_API_KEY under Configure Tunnel')
            log=_safe_log_dir()/'tunnel.log'
            self._log=log.open('ab',buffering=0)
            cmd=[str(binary),'run','--config',str(profile)]
            try:
                self.proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                                           stdout=self._log,stderr=subprocess.STDOUT)
            except Exception:
                self._log.close();self._log=None
                raise
            self.last_error=''
            return {'running':True,'pid':self.proc.pid,'message':'Tunnel process started; check /readyz and ChatGPT registration'}
    def stop(self):
        with self._lock:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                try:self.proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.proc.kill();self.proc.wait(timeout=4)
            self.proc=None
            if self._log:self._log.close();self._log=None
    def status(self):
        opts=load_tunnel_settings()
        with self._lock:running=bool(self.proc and self.proc.poll() is None)
        health=local_http_status(opts['admin_url'].rstrip('/')+'/healthz')
        ready=local_http_status(opts['admin_url'].rstrip('/')+'/readyz')
        return {'process_started_by_this_app':running,'health':health,'ready':ready,
                'admin_url':opts['admin_url'],'chatgpt_registered':'not_verified_here',
                'note':'A ready tunnel is not proof that the ChatGPT connector is installed or authorized.'}
