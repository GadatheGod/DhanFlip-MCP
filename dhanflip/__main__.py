import argparse,json
from .scanner import Scanner

def main():
    p=argparse.ArgumentParser(description='DhanFlip v2 — 3-minute read-only options monitoring')
    p.add_argument('command',nargs='?',default='gui',choices=['gui','mcp','mcp-http','scan-once','monitor','status','backtest','demo-report'])
    p.add_argument('--port',type=int,default=8766)
    args=p.parse_args()
    if args.command=='gui':
        from .singleinstance import SingleScannerInstance
        from .gui import run_gui
        with SingleScannerInstance():return run_gui()
    if args.command in ('mcp','mcp-http'):
        from .mcp_server import run_server
        return run_server('http' if args.command=='mcp-http' else 'stdio',port=args.port)
    from .singleinstance import SingleScannerInstance
    with SingleScannerInstance():
        return _scanner_command(args)

def _scanner_command(args):
    svc=Scanner()
    try:
        if args.command in ('scan-once','demo-report'):
            status=svc.scan_once();print(json.dumps({'status':status,'active':svc.latest(),
                          'recent_history':svc.db.signals(5) if args.command=='demo-report' else []},indent=2))
        elif args.command=='backtest':
            from .replay import backtest_all,export_csv
            svc.scan_once();report=backtest_all(svc);export_csv(report,'backtest_report.csv')
            print(json.dumps({'summary':report['summary'],'report':'backtest_report.csv','skipped':report['skipped']},indent=2))
        elif args.command=='status':print(json.dumps(svc.db.get_state('scanner') or svc.status(),indent=2))
        elif args.command=='monitor':
            print('Read-only scanner. Stop Ctrl+C.',flush=True);svc.loop()
    except KeyboardInterrupt:pass
    finally:svc.shutdown()
if __name__=='__main__':main()
