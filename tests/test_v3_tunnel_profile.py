import pytest
from pathlib import Path
from dhanflip.tunnel import TunnelController,save_tunnel_settings
from dhanflip import tunnel

def test_refuses_unrelated_mcp_profile(tmp_path,monkeypatch):
    exe=tmp_path/'tunnel-client';exe.write_text('not executed')
    profile=tmp_path/'artcraft.yaml'
    profile.write_text('mcp:\n  server_urls:\n    - channel: main\n      url: http://127.0.0.1:7878/mcp\n')
    monkeypatch.setattr(tunnel,'CONFIG_FILE',tmp_path/'tunnel.local.json')
    monkeypatch.setattr(tunnel,'KEY_FILE',tmp_path/'.env.tunnel')
    save_tunnel_settings(str(exe),str(profile))
    with pytest.raises(ValueError,match='does not route main'):
        TunnelController().start()
