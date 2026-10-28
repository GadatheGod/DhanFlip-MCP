from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env', override=False)


def settings() -> dict:
    override = os.getenv('DHANFLIP_CONFIG')
    src = Path(override) if override else ROOT / 'config/settings.yaml'
    with src.open(encoding='utf-8') as f:
        d = yaml.safe_load(f)
    if d['timeframe_minutes'] != 3:
        raise ValueError('Only 3-minute candles are supported in this build')
    return d


def secrets() -> tuple[str, str]:
    return os.getenv('DHAN_CLIENT_ID', '').strip(), os.getenv('DHAN_ACCESS_TOKEN', '').strip()
