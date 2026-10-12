from app.models import Choice,Character,ManualEffect,SpellPick,ItemPick
from app.constants import BASE
from app.progression import build
from app.calculations import boost,proficiency,stack
from app.prerequisites import check
from app.spells import heighten

def test_druid_six(rules,druid):
    r=build(druid,rules); s=r['stats']
    assert s['attrs']=={'str':14,'dex':14,'con':16,'int':12,'wis':19,'cha':10}
    assert s['hp']==74
    assert s['saves']=={'fort':13,'reflex':12,'will':14}
    assert s['perception']==14
    assert s['ranks']['athletics']==1 and s['ranks']['medicine']==2
    assert r['spells']['sources'][0]['cantrips']==5
    assert [r['spells']['sources'][0]['slots'][str(i)] for i in [1,2,3]]==[3,3,3]
    assert any('animal-companion' in x['id'] for x in r['acquired'])
    assert r['spells']['focus_pool']==1 and r['spells']['auto_focus']
    slots=[s for row in r['timeline'] for s in row['slots']]
    for kind,levels in [('class_feat',[2,4,6]),('skill_feat',[2,4,6]),('general_feat',[3]),('ancestry_feat',[1,5]),('skill_increase',[3,5])]:
        assert [s['level'] for s in slots if s['kind']==kind]==levels

def test_boost_and_proficiency():
    assert boost(18)==19 and boost(17)==19 and boost(10)==12
    assert [proficiency(6,r) for r in range(5)]==[0,8,10,12,14]

def test_history_level_down_and_master_gate(rules,druid):
    original=druid.model_dump(); druid.level=2;r=build(druid,rules)
    assert r['outcomes']['L5:boost:0']['status']=='inactive'
    assert druid.choices==Character(**original).choices
    druid.level=6;druid.choices[-2]=Choice(slot='L5:skill_increase:0',level=5,kind='skill_increase',value=['medicine'])
    r=build(druid,rules);assert r['outcomes']['L5:skill_increase:0']['status']=='invalid'
    assert r['stats']['ranks']['medicine']==2

def test_historical_prerequisite(rules,druid):
    r=build(druid,rules)
    item={'id':'test','kind':'class_feat','owner':druid.class_id,'level':1,'name':'Тест','prerequisites':'Сила 14','traits':[],'field_links':{}}
    assert check(item,r['snapshots'][2],{'kind':'class_feat'},rules)['status']=='invalid'
    assert check(item,r['snapshots'][6],{'kind':'class_feat'},rules)['status']=='available'

def test_free_archetype_keeps_choices(rules,druid):
    druid.free_archetype=True;r=build(druid,rules)
    assert sum(s['kind']=='free_archetype' for row in r['timeline'] for s in row['slots'])==3
    ded=next(x for x in rules.kind('archetype_feat') if 'dedication' in x['english'].lower())
    druid.choices.append(Choice(slot='L2:free_archetype',level=2,kind='free_archetype',value=ded['id'],confirmed=True))
    druid.free_archetype=False;r=build(druid,rules)
    assert r['outcomes']['L2:free_archetype']['status']=='inactive'
    assert druid.choices[-1].value==ded['id']

def test_link_dependency_and_early_change(rules,druid):
    feat=next(x for x in rules.kind('class_feat') if x['english'].startswith('Mature Animal Companion'))
    druid.choices.append(Choice(slot='L4:class_feat:0',level=4,kind='class_feat',value=feat['id'],confirmed=True))
    assert build(druid,rules)['outcomes']['L4:class_feat:0']['status']=='valid'
    druid.choices=[c for c in druid.choices if c.kind!='subclass']
    assert build(druid,rules)['outcomes']['L4:class_feat:0']['status']=='invalid'

def test_fighter_and_sorcerer(rules):
    fighter=rules.get(BASE+'classes/fighter.html'); assert fighter['profile']['hp']==10
    s=build(Character(class_id=fighter['id'],level=6),rules)['stats']; assert s['ranks']['heavy']==1
    sorcerer=build(Character(class_id=BASE+'classes/sorcerer.html',level=6),rules)
    assert sorcerer['spells']['sources'][0]['mode']=='repertoire'
    assert [sorcerer['spells']['sources'][0]['slots'][str(i)] for i in [1,2,3]]==[4,4,4]

def test_typed_bonuses_and_activation(rules,druid):
    base=build(druid,rules)['stats']['ac']
    druid.effects=[ManualEffect(label='A',target='ac',value=1,type='status',active=True),ManualEffect(label='B',target='ac',value=2,type='status',active=True),ManualEffect(label='C',target='ac',value=2,type='circumstance',active=True),ManualEffect(label='D',target='ac',value=20,type='item',active=False)]
    assert build(druid,rules)['stats']['ac']==base+4
    assert stack([{'type':'status','value':2},{'type':'status','value':-1}])==1

def test_unknown_or_condition_requires_review(rules,druid):
    state=build(druid,rules)['state']; item={'id':'test','kind':'class_feat','owner':druid.class_id,'level':1,'name':'Тест','prerequisites':'эксперт Атлетики или Акробатики','traits':[]}
    assert check(item,state,{'kind':'class_feat'},rules)['status']=='review'

def test_spells_capacity_and_heightening(rules,druid):
    heal=next(r for r in rules.kind('spell') if r['english']=='Heal')
    druid.spells=[SpellPick(rule_id=heal['id'],cast_rank=3,level=5) for _ in range(4)]
    r=build(druid,rules); assert r['spells']['picks'][-1]['status']=='invalid'
    fireball=next(r for r in rules.kind('spell') if r['english']=='Fireball')
    h=heighten(fireball,5);assert h['automatic'] and h['value']=='10d6 урона'

def test_extra_feat_handler(rules,druid):
    natural=next(x for x in rules.kind('ancestry_feat') if x['english']=='Natural Ambition')
    druid.choices.append(Choice(slot='L1:ancestry_feat:0',level=1,kind='ancestry_feat',value=natural['id']))
    r=build(druid,rules)
    assert any(s.get('parent')==natural['id'] and s['kind']=='class_feat' for s in r['timeline'][0]['slots'])

def test_cleric_doctrine_is_level_gated(rules):
    cls=BASE+'classes/cleric.html'
    sub=next(r for r in rules.kind('subclass') if r['english']=='Cloistered Cleric')
    c=Character(class_id=cls,level=1,choices=[Choice(slot='L1:subclass:'+sub['parent'],level=1,kind='subclass',value=sub['id'])])
    r=build(c,rules);assert r['stats']['ranks']['spell']==1 and r['stats']['ranks']['fort']==1
    c.level=6;r=build(c,rules);assert r['stats']['ranks']['fort']==2 and r['stats']['ranks']['spell']==1
    c.level=19;r=build(c,rules);assert r['stats']['ranks']['spell']==4
    war=next(r for r in rules.kind('subclass') if r['english']=='Warpriest');c.choices[0].value=war['id'];c.level=1;r=build(c,rules)
    assert r['stats']['ranks']['light']==1 and r['stats']['ranks']['medium']==1 and r['stats']['ranks']['fort']==2

def test_sorcerer_bloodline_grants(rules):
    sub=next(r for r in rules.kind('subclass') if r['english']=='Aberrant')
    c=Character(class_id=BASE+'classes/sorcerer.html',choices=[Choice(slot='L1:subclass:'+sub['parent'],level=1,kind='subclass',value=sub['id'])])
    r=build(c,rules);assert r['stats']['ranks']['intimidation']==1 and r['stats']['ranks']['occultism']==1
    assert r['spells']['auto_focus'] and r['spells']['sources'][0]['traditions']==['occult']

def test_runes_and_weapon_group(rules):
    c=Character(class_id=BASE+'classes/fighter.html',level=6)
    weapon=next(r for r in rules.kind('item') if r.get('item_type')=='weapon' and r.get('values',{}).get('category')=='martial' and r['values'].get('group') and '1d8' in r['values'].get('damage',''))
    potency=next(r for r in rules.kind('item') if r.get('values',{}).get('rune_type')=='weapon_potency' and r['values']['rune_value']==1)
    striking=next(r for r in rules.kind('item') if r.get('values',{}).get('rune_type')=='striking' and r['values']['rune_value']==2)
    c.inventory=[ItemPick(rule_id=weapon['id'],equipped=True,runes=[potency['id'],striking['id']])]
    r=build(c,rules);base=r['stats']['weapons'][0]['attack'];assert '2d8' in r['stats']['weapons'][0]['damage']
    slot=next(s for row in r['timeline'] for s in row['slots'] if s['kind']=='weapon_group')
    c.choices.append(Choice(slot=slot['id'],level=5,kind='weapon_group',value=weapon['values']['group']))
    assert build(c,rules)['stats']['weapons'][0]['attack']==base+2

def test_repeated_feat_has_separate_linked_slots(rules,druid):
    feat=next(x for x in rules.kind('ancestry_feat') if x['english']=='General Training')
    assert feat['repeatable']
    druid.choices.extend([Choice(slot=f'L{n}:ancestry_feat:0',level=n,kind='ancestry_feat',value=feat['id']) for n in [1,5]])
    r=build(druid,rules);slots=[s for row in r['timeline'] for s in row['slots'] if s.get('parent')==feat['id']]
    assert len(slots)==2 and len({s['id'] for s in slots})==2
