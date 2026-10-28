"""Best-effort cross-platform exclusive lock for market-data-owning processes.

Cache-only MCP services do not take this lock and never make Dhan network calls.
"""
from __future__ import annotations
import os
from .config import ROOT

class SingleScannerInstance:
    def __init__(self):self.handle=None
    def __enter__(self):
        path=ROOT/'data/scanner.lock';path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=path.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.handle.seek(0)
                self.handle.write(b'0');self.handle.flush();self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError,BlockingIOError):
            self.handle.close();self.handle=None
            raise SystemExit('Another DhanFlip GUI/scanner already owns the data connection. Close it first.')
        return self
    def __exit__(self,*args):
        if self.handle:
            if os.name=='nt':
                import msvcrt
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            self.handle.close();self.handle=None
