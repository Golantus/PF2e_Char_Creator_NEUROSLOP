"""Resumable source-only crawl. A failed staging version never replaces active rules."""
import asyncio, gzip, hashlib, json, threading, time
from urllib.parse import urljoin, urldefrag, urlsplit
import httpx
from bs4 import BeautifulSoup
from . import db
from .constants import BASE
from .parser import parse_page

PREFIXES=('classes/','ancestries_and_backgrounds/','spells/','equipment/','crafting_and_treasure/','appendix/','game_mastering/variant-rules')
FILES={'index.html','introduction.html','skills.html','feats.html','licenses.html','playing_the_game.html','books/Dark-Archive/Deviant-Abilities.html'}
PROGRESS={'running':False,'phase':'idle','loaded':0,'total':0,'parsed':0,'errors':0,'version':None}
PAUSE=threading.Event(); MUTEX=threading.Lock()

def allowed(url):
    p=urlsplit(url)
    return url.startswith(BASE) and not p.query and p.path.endswith('.html') and (url[len(BASE):] in FILES or url[len(BASE):].startswith(PREFIXES))

def links(url,raw):
    soup=BeautifulSoup(raw,'lxml'); main=soup.select_one('[role="main"]') or soup
    return {u for a in main.find_all('a',href=True) if allowed(u:=urldefrag(urljoin(url,a['href']))[0])}

def log(version,url,severity,message):
    with db.connect() as c: c.execute('INSERT INTO import_log(version,url,severity,message) VALUES(?,?,?,?)',(version,url,severity,str(message)))

async def run(version=None):
    db.migrate(); PAUSE.clear(); PROGRESS.update(running=True,phase='loading',loaded=0,total=0,parsed=0,errors=0)
    with db.connect() as c:
        if version:
            row=c.execute('SELECT status FROM rule_versions WHERE id=?',(version,)).fetchone()
            if not row or row[0]=='ready': raise ValueError('Нельзя изменять готовую версию')
            c.execute("UPDATE rule_versions SET status='loading' WHERE id=?",(version,))
        else: version=c.execute("INSERT INTO rule_versions(status) VALUES('loading')").lastrowid
        cached={r['url']:dict(r) for r in c.execute('SELECT * FROM pages WHERE version=?',(version,))}
    PROGRESS['version']=version
    queue=asyncio.Queue(); seen=set()
    def enqueue(url):
        if url not in seen: seen.add(url); queue.put_nowait(url); PROGRESS['total']=len(seen)
    enqueue(BASE+'index.html'); enqueue(BASE+'licenses.html')
    async with httpx.AsyncClient(headers={'User-Agent':'PF2eRuBuilder/1.0 (+local offline rules importer)'},timeout=60,follow_redirects=False) as client:
        async def worker():
            while True:
                url=await queue.get()
                try:
                    if PAUSE.is_set(): continue
                    old=cached.get(url)
                    if old and old['status']=='ok': raw=gzip.decompress(old['raw_gzip'])
                    else:
                        error=None
                        for attempt in range(4):
                            try:
                                r=await client.get(url); r.raise_for_status(); raw=r.content
                                if b'<html' not in raw[:5000].lower(): raise ValueError('Ответ не является HTML')
                                error=None; break
                            except Exception as e:
                                error=e; await asyncio.sleep(min(2**attempt,8))
                        if error: raise error
                        with db.connect() as c: c.execute('INSERT OR REPLACE INTO pages(version,url,status,sha256,raw_gzip,error) VALUES(?,?,?,?,?,NULL)',(version,url,'ok',hashlib.sha256(raw).hexdigest(),gzip.compress(raw)))
                        await asyncio.sleep(.15)
                    for u in links(url,raw): enqueue(u)
                    PROGRESS['loaded']+=1
                except Exception as e:
                    PROGRESS['errors']+=1; log(version,url,'error',e)
                    with db.connect() as c: c.execute('INSERT OR REPLACE INTO pages(version,url,status,error) VALUES(?,?,?,?)',(version,url,'error',str(e)))
                finally: queue.task_done()
        workers=[asyncio.create_task(worker()) for _ in range(5)]
        await queue.join()
        for w in workers: w.cancel()
        await asyncio.gather(*workers,return_exceptions=True)
    if PAUSE.is_set():
        with db.connect() as c: c.execute("UPDATE rule_versions SET status='paused' WHERE id=?",(version,))
        PROGRESS.update(running=False,phase='paused'); return version
    parse_version(version)
    return version

def parse_version(version):
    PROGRESS.update(version=version,phase='parsing',running=True,parsed=0)
    with db.connect() as c:
        state=c.execute('SELECT status FROM rule_versions WHERE id=?',(version,)).fetchone()
        if not state or state[0]=='ready': raise ValueError('Готовая версия неизменяема; создайте новую')
        pages=list(c.execute("SELECT url,raw_gzip,sha256 FROM pages WHERE version=? AND status='ok'",(version,)))
        c.execute('DELETE FROM elements WHERE version=?',(version,)); c.execute('DELETE FROM aliases WHERE version=?',(version,))
    errors=0
    for page in pages:
        if PAUSE.is_set(): break
        try:
            raw=gzip.decompress(page['raw_gzip'])
            if hashlib.sha256(raw).hexdigest()!=page['sha256']: raise ValueError('Нарушена контрольная сумма страницы')
            items=parse_page(page['url'],raw)
            with db.connect() as c:
                for it in items:
                    c.execute('INSERT OR REPLACE INTO elements VALUES(?,?,?,?,?,?,?)',(version,it['id'],it['kind'],it['name'],it['level'],it['owner'],json.dumps(it,ensure_ascii=False)))
                    for a in it['aliases']: c.execute('INSERT OR REPLACE INTO aliases VALUES(?,?,?)',(version,a,it['id']))
            PROGRESS['parsed']+=1
        except Exception as e: errors+=1; log(version,page['url'],'error',e)
    with db.connect() as c:
        counts={r[0]:r[1] for r in c.execute('SELECT kind,count(*) FROM elements WHERE version=? GROUP BY kind',(version,))}
        failed=c.execute("SELECT count(*) FROM pages WHERE version=? AND status='error'",(version,)).fetchone()[0]
        classes=[json.loads(r[0]) for r in c.execute("SELECT data FROM elements WHERE version=? AND kind='class'",(version,))]
        complete=bool(classes) and all(len(x.get('progression',{}))==20 for x in classes)
        integrity=c.execute('PRAGMA quick_check').fetchone()[0]
        status='paused' if PAUSE.is_set() else 'ready' if not errors and not failed and complete and counts.get('spell',0)>0 and integrity=='ok' else 'incomplete'
        summary={'counts':counts,'pages':len(pages),'errors':errors+failed,'complete_class_tables':complete,'integrity':integrity}
        c.execute('UPDATE rule_versions SET status=?,summary=?,finished_at=CURRENT_TIMESTAMP WHERE id=?',(status,json.dumps(summary),version))
        if status=='ready': c.execute("INSERT OR REPLACE INTO settings VALUES('active_version',?)",(str(version),))
    PROGRESS.update(running=False,phase=status,errors=errors+failed,summary=summary)

def start(version=None):
    if not MUTEX.acquire(blocking=False): raise ValueError('Импорт уже идет')
    PROGRESS.update(running=True,phase='loading')
    def target():
        try: asyncio.run(run(version))
        except Exception as e:
            PROGRESS.update(running=False,phase='error',error=str(e))
            if PROGRESS['version']: log(PROGRESS['version'],'','error',e)
        finally: MUTEX.release()
    threading.Thread(target=target,daemon=True).start()

if __name__=='__main__':
    import sys
    v=int(sys.argv[1]) if len(sys.argv)>1 else None
    asyncio.run(run(v)); print(json.dumps(PROGRESS,ensure_ascii=False))
