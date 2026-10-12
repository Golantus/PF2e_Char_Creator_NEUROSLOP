"""One local server serves the compiled UI and the API."""
import json,os,socket,sys,threading,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
os.chdir(ROOT)
os.environ.setdefault('PF2E_DATA_DIR',str(ROOT/'data'))
from app import db,importer
import uvicorn

def app_at(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/meta',timeout=2) as r:
            return json.load(r).get('app_id')=='pf2e-ru-builder'
    except Exception: return False

def main():
    port=8765
    if app_at(port): webbrowser.open(f'http://127.0.0.1:{port}'); return
    with socket.socket() as s:
        try: s.bind(('127.0.0.1',port))
        except OSError: s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    db.migrate()
    if not db.active_version(): importer.start()
    def open_browser():
        for _ in range(120):
            if app_at(port): webbrowser.open(f'http://127.0.0.1:{port}');return
            time.sleep(.5)
    threading.Thread(target=open_browser,daemon=True).start()
    print(f'Откройте http://127.0.0.1:{port} . Для остановки нажмите Ctrl+C.')
    uvicorn.run('app.main:app',host='127.0.0.1',port=port,log_level='info')
if __name__=='__main__': main()
