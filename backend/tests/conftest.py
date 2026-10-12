import gzip,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import Rules
from app.constants import BASE
from app.parser import parse_page
from app.models import Character,Choice

FIXTURES=Path(__file__).parent/'fixtures'
@pytest.fixture(scope='session')
def rules():
    items=[]
    for name,url in json.loads((FIXTURES/'manifest.json').read_text()).items():
        path=FIXTURES/(name+'.html.gz')
        if path.exists(): items.extend(parse_page(BASE+url,gzip.decompress(path.read_bytes())))
    return Rules(version=1,items=items)

@pytest.fixture
def druid(rules):
    c=Character(name='Лесная стража',level=6,class_id=BASE+'classes/druid.html',ancestry_id=BASE+'ancestries_and_backgrounds/ancestries/human.html',background_id=next(r['id'] for r in rules.kind('background') if r['name']=='Послушник'),rules_version=1)
    group=BASE+'classes/druid.html#class-feature-druid-druidic-order'
    def add(slot,level,kind,value): c.choices.append(Choice(slot=slot,level=level,kind=kind,value=value))
    for slot,vals in [('ancestry_boost',['wis','con']),('background_boost',['int','wis']),('class_boost',['wis']),('free_boost',['wis','str','dex','con'])]: add('L1:'+slot,1,'boost',vals)
    add('L1:subclass:'+group,1,'subclass',BASE+'classes/druid.html#class-feature-druid-order-animal')
    add('L1:trained',1,'trained',['medicine','survival','stealth'])
    add('L3:skill_increase:0',3,'skill_increase',['medicine'])
    add('L5:skill_increase:0',5,'skill_increase',['survival'])
    add('L5:boost:0',5,'boost',['wis','con','dex','str'])
    return c
