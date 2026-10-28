import json, pytest
from dhanflip import tunnel

def test_defaults_no_credentials(monkeypatch,tmp_path):
    monkeypatch.setattr(tunnel,'CONFIG_FILE',tmp_path/'tunnel.local.json')
    d=tunnel.load_tunnel_settings()
    assert 'api_key' not in d and d['executable']==''

def test_config_requires_local_health(monkeypatch,tmp_path):
    monkeypatch.setattr(tunnel,'CONFIG_FILE',tmp_path/'tunnel.local.json')
    with pytest.raises(ValueError):tunnel.save_tunnel_settings('abc','x','http://test.com:8081')
    d=tunnel.save_tunnel_settings('/bin/true','/tmp/local.yaml')
    assert 'CONTROL_PLANE_API_KEY' not in (tmp_path/'tunnel.local.json').read_text()
    assert d['enabled']

def test_secret_local_only(monkeypatch,tmp_path):
    monkeypatch.setattr(tunnel,'KEY_FILE',tmp_path/'.env.tunnel')
    tunnel.save_tunnel_key('testing123')
    assert 'CONTROL_PLANE_API_KEY=testing123' in (tmp_path/'.env.tunnel').read_text()
    with pytest.raises(ValueError):tunnel.save_tunnel_key('bad\nINJECT')

def test_health_rejects_other_hosts():
    with pytest.raises(ValueError):tunnel.local_http_status('https://example.com')

def test_tunnel_no_process_default(monkeypatch,tmp_path):
    monkeypatch.setattr(tunnel,'CONFIG_FILE',tmp_path/'local.json')
    ctrl=tunnel.TunnelController()
    with pytest.raises(FileNotFoundError):ctrl.start()
