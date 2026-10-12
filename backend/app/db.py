import json, os, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
from .constants import ROOT

LOCK = threading.RLock()
def path():
    folder = Path(os.environ.get('PF2E_DATA_DIR',ROOT/'data'))
    folder.mkdir(parents=True, exist_ok=True)
    return folder/'builder.sqlite3'

@contextmanager
def connect():
    with LOCK:
        con = sqlite3.connect(path(),timeout=60)
        con.row_factory=sqlite3.Row
        try:
            con.execute('PRAGMA synchronous=FULL')
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

def migrate():
    with connect() as con:
        for p in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
            con.executescript(p.read_text(encoding='utf-8'))

def active_version():
    with connect() as con:
        row=con.execute("SELECT value FROM settings WHERE key='active_version'").fetchone()
        return int(row[0]) if row else None

class Rules:
    def __init__(self,version=None,items=None):
        self.version=version or active_version()
        self.items={}; self.aliases={}; self.by_kind={}
        if items is None:
            with connect() as con:
                items=[json.loads(r[0]) for r in con.execute('SELECT data FROM elements WHERE version=?',(self.version,))]
            # 0.9.0 did not crawl the deviant-abilities page linked by backgrounds.
            # Fill only missing entries from the attributed bundled source snapshot.
            # Existing versioned rules and the user's database remain untouched.
            supplement=Path(__file__).parent/'bundled_rules.json'
            if supplement.exists():
                known={item['id'] for item in items}
                items.extend(item for item in json.loads(supplement.read_text(encoding='utf-8')) if item['id'] not in known)
        for item in items:
            self.items[item['id']]=item
            self.by_kind.setdefault(item['kind'],[]).append(item)
            for alias in [item['id'],*item.get('aliases',[])]: self.aliases[alias]=item['id']
    def get(self,key): return self.items.get(self.aliases.get(key,key)) if isinstance(key,str) else None
    def kind(self,kind): return self.by_kind.get(kind,[])
