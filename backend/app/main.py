import json,threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from . import db,importer
from .models import Character
from .constants import ROOT,ATTRS,SKILLS,RANKS,KINDS,TRADITIONS
from .progression import build
from .prerequisites import check
from .exporter import export_character

_cache={}; _cache_lock=threading.RLock()
def rules(version=None):
    version=version or db.active_version()
    with _cache_lock:
        if version not in _cache:
            if len(_cache)>2: _cache.clear()
            _cache[version]=db.Rules(version)
        return _cache[version]
def brief(r): return {k:r.get(k) for k in ['id','kind','name','english','level','owner','traits','prerequisites','parent','profile','item_type','values']}
@asynccontextmanager
async def lifespan(app):
    db.migrate(); yield
app=FastAPI(title='PF2e: конструктор персонажей',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])
@app.middleware('http')
async def local_only(request:Request,call_next):
    if request.url.hostname not in ['127.0.0.1','localhost','testserver','::1']: return JSONResponse({'detail':'Доступ разрешен только с этого компьютера'},400)
    origin=request.headers.get('origin')
    if request.method in ['POST','PUT','DELETE','PATCH'] and origin:
        p=urlsplit(origin)
        if p.scheme!='http' or p.hostname not in ['127.0.0.1','localhost','::1']: return JSONResponse({'detail':'Недопустимый источник запроса'},403)
    return await call_next(request)

@app.get('/api/meta')
def meta(version:int|None=None):
    rr=rules(version)
    return {'app_id':'pf2e-ru-builder','version':rr.version,'active_version':db.active_version(),'attrs':ATTRS,'skills':SKILLS,'ranks':RANKS,'kinds':KINDS,'traditions':TRADITIONS,**{k:[brief(r) for r in sorted(rr.kind(v),key=lambda x:x['name'])] for k,v in [('classes','class'),('ancestries','ancestry'),('heritages','heritage'),('backgrounds','background')]}}
@app.get('/api/rule')
def rule(id:str,version:int|None=None):
    r=rules(version).get(id)
    if not r: raise HTTPException(404,'Правило не найдено в этой версии базы')
    return r
@app.post('/api/calculate')
def calc(c:Character): return build(c,rules(c.rules_version))

class CatalogQuery(BaseModel):
    character: Character|None=None
    kinds: list[str]=Field(default_factory=list)
    slot: str=''
    level: int=Field(default=20,ge=1,le=20)
    q: str=''
    owner: str=''
    trait: str=''
    tradition: str=''
    rank: int|None=None
    available_only: bool=False
    offset: int=Field(default=0,ge=0)
    limit: int=Field(default=80,ge=1,le=200)

@app.post('/api/catalog')
def catalog(q:CatalogQuery):
    rr=rules(q.character.rules_version if q.character else None); state=None; slot=None
    if q.character and q.slot:
        char=q.character.model_copy(deep=True); char.choices=[c for c in char.choices if c.slot!=q.slot]; char.level=q.level
        result=build(char,rr); state=result['state']; slot=next((s for t in result['timeline'] for s in t['slots'] if s['id']==q.slot),None)
        if not slot: slot={'kind':'linked','level':q.level,'id':q.slot}
    pool=[r for kind in q.kinds for r in rr.kind(kind)] if q.kinds else rr.items.values()
    out=[]; query=q.q.casefold().replace('ё','е')
    for r in pool:
        if query and query not in (r['name']+' '+r.get('english','')).casefold().replace('ё','е'): continue
        if q.owner and r['owner']!=q.owner: continue
        if q.trait and not any(q.trait.lower() in t.lower() for t in r.get('traits',[])): continue
        if q.tradition and q.tradition not in r.get('traditions',[]): continue
        if q.rank is not None and (0 if r.get('cantrip') else r.get('level'))!=q.rank: continue
        eligibility=check(r,state,slot,rr) if state and slot else {'status':'available','reasons':[]}
        if q.available_only and eligibility['status']=='invalid': continue
        out.append({**brief(r),'eligibility':eligibility,'cantrip':r.get('cantrip')})
    out.sort(key=lambda x:(x['level'],x['name']))
    return {'total':len(out),'items':out[q.offset:q.offset+q.limit]}

@app.get('/api/characters')
def characters():
    with db.connect() as con: return [dict(r) for r in con.execute('SELECT id,name,revision,updated_at FROM characters ORDER BY updated_at DESC')]
@app.post('/api/characters')
def create(c:Character):
    c.id=str(uuid4()); c.revision=1; c.rules_version=c.rules_version or db.active_version(); data=c.model_dump_json()
    with db.connect() as con:
        con.execute('INSERT INTO characters(id,name,data,revision) VALUES(?,?,?,?)',(c.id,c.name,data,1)); con.execute('INSERT INTO character_history(character_id,revision,data) VALUES(?,?,?)',(c.id,1,data))
    return c
@app.get('/api/characters/{id}')
def get_character(id:str):
    with db.connect() as con: row=con.execute('SELECT data FROM characters WHERE id=?',(id,)).fetchone()
    if not row: raise HTTPException(404,'Персонаж не найден')
    return json.loads(row[0])
@app.put('/api/characters/{id}')
def save(id:str,c:Character):
    if c.id!=id: raise HTTPException(400,'Идентификаторы не совпадают')
    with db.connect() as con:
        row=con.execute('SELECT revision FROM characters WHERE id=?',(id,)).fetchone()
        if not row: raise HTTPException(404,'Персонаж не найден')
        if row[0]!=c.revision: raise HTTPException(409,'Персонаж изменен в другом окне. Сохраните JSON и откройте актуальную версию.')
        c.revision+=1; data=c.model_dump_json()
        con.execute('UPDATE characters SET name=?,data=?,revision=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(c.name,data,c.revision,id))
        con.execute('INSERT INTO character_history(character_id,revision,data) VALUES(?,?,?)',(id,c.revision,data))
    return c
@app.delete('/api/characters/{id}')
def delete(id:str):
    with db.connect() as con: con.execute('DELETE FROM characters WHERE id=?',(id,))
    return {'ok':True}
@app.get('/api/characters/{id}/history')
def history(id:str):
    with db.connect() as con: return [dict(r) for r in con.execute('SELECT revision,saved_at FROM character_history WHERE character_id=? ORDER BY revision DESC LIMIT 100',(id,))]
@app.post('/api/characters/{id}/restore/{revision}')
def restore(id:str,revision:int):
    current=get_character(id)
    with db.connect() as con: row=con.execute('SELECT data FROM character_history WHERE character_id=? AND revision=?',(id,revision)).fetchone()
    if not row: raise HTTPException(404,'Версия не найдена')
    c=Character.model_validate_json(row[0]); c.revision=current['revision']; return save(id,c)

class ExportQuery(BaseModel):
    character: Character
    mode: str='full'
    links: bool=True
    markdown: bool=False
@app.post('/api/export')
def export(q:ExportQuery):
    if q.mode not in ['full','brief','abilities','spells','levels']: raise HTTPException(400,'Неверный вид экспорта')
    rr=rules(q.character.rules_version); result=build(q.character,rr)
    return {'text':export_character(q.character,result,rr,q.mode,q.links,q.markdown)}

@app.get('/api/diagnostics')
def diagnostics():
    with db.connect() as con:
        versions=[{**dict(r),'summary':json.loads(r['summary'])} for r in con.execute('SELECT * FROM rule_versions ORDER BY id DESC')]
        logs=[dict(r) for r in con.execute('SELECT * FROM import_log ORDER BY id DESC LIMIT 100')]
    return {'active_version':db.active_version(),'versions':versions,'progress':importer.PROGRESS,'logs':logs}
@app.post('/api/import/start')
def import_start(version:int|None=None):
    try: importer.start(version)
    except ValueError as e: raise HTTPException(409,str(e))
    return importer.PROGRESS
@app.post('/api/import/pause')
def import_pause(): importer.PAUSE.set(); return {'ok':True}
@app.post('/api/import/activate/{version}')
def activate(version:int):
    with db.connect() as con:
        row=con.execute('SELECT status FROM rule_versions WHERE id=?',(version,)).fetchone()
        if not row or row[0]!='ready': raise HTTPException(400,'Версия не прошла проверку импорта')
        con.execute("INSERT OR REPLACE INTO settings VALUES('active_version',?)",(str(version),))
    return {'active_version':version}

DIST=ROOT/'frontend'/'dist'
@app.get('/{path:path}')
def frontend(path:str):
    if path.startswith('api/'): raise HTTPException(404,'Метод API не найден')
    target=(DIST/path).resolve()
    if not target.is_relative_to(DIST.resolve()): raise HTTPException(404)
    if target.is_file(): return FileResponse(target)
    if (DIST/'index.html').exists(): return FileResponse(DIST/'index.html')
    raise HTTPException(503,'Frontend еще не собран')
