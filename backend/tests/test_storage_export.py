import pytest
from fastapi.testclient import TestClient
from app import db,main
from app.progression import build
from app.exporter import export_character

def test_full_export(rules,druid):
    result=build(druid,rules);text=export_character(druid,result,rules)
    for x in result['acquired']:
        r=rules.get(x['id'])
        if r['kind'] in ['class_feat','ancestry_feat','general_feat','skill_feat','focus_spell']:
            assert r['text'] in text
    assert rules.get(druid.class_id)['text'] not in text
    assert '\n\nИсточник: https://' in text
    assert '\n\nИсточник: https://' not in export_character(druid,result,rules,links=False)

def test_storage_conflict_restore_and_api(tmp_path,monkeypatch,rules,druid):
    monkeypatch.setenv('PF2E_DATA_DIR',str(tmp_path));db.migrate()
    monkeypatch.setattr(main,'rules',lambda version=None:rules)
    with TestClient(main.app) as client:
        a=client.post('/api/characters',json=druid.model_dump()).json();assert a['revision']==1
        a['name']='Проверка';b=client.put('/api/characters/'+a['id'],json=a).json();assert b['revision']==2
        assert client.put('/api/characters/'+a['id'],json=a).status_code==409
        assert client.get('/api/characters/'+a['id']).json()['name']=='Проверка'
        restored=client.post('/api/characters/'+a['id']+'/restore/1').json();assert restored['name']==druid.name
        imported=client.post('/api/characters',json=restored).json();assert imported['id']!=a['id']
        assert client.post('/api/calculate',json=restored).json()['stats']['hp']==74
        exported=client.post('/api/export',json={'character':restored}).json()['text'];assert 'Исцеление животного' in exported
        assert client.post('/api/calculate',json=restored,headers={'Origin':'https://evil.invalid'}).status_code==403

def test_failed_rules_update_preserves_active_version(tmp_path,monkeypatch):
    from app.importer import parse_version,PAUSE
    monkeypatch.setenv('PF2E_DATA_DIR',str(tmp_path));db.migrate();PAUSE.clear()
    with db.connect() as con:
        con.execute("INSERT INTO rule_versions(id,status) VALUES(1,'ready')")
        con.execute("INSERT INTO settings VALUES('active_version','1')")
        con.execute("INSERT INTO rule_versions(id,status) VALUES(2,'loading')")
        con.execute("INSERT INTO pages(version,url,status,error) VALUES(2,'missing','error','network error')")
    parse_version(2)
    assert db.active_version()==1
    with db.connect() as con: assert con.execute('SELECT status FROM rule_versions WHERE id=2').fetchone()[0]=='incomplete'
