import math,re
from .constants import SKILLS

def modifier(score): return (score-10)//2
def proficiency(level,rank): return 0 if rank==0 else level+2*rank
def boost(score): return score+(2 if score<18 else 1)
def stack(effects):
    result=0
    for typ in ['item','status','circumstance','untyped']:
        values=[e['value'] for e in effects if e.get('type')==typ]
        result+=sum(values) if typ=='untyped' else max([0,*values])+min([0,*values])
    return result

def calculate(character,state,rules,acquired):
    level=state['level']; mods={k:modifier(v) for k,v in state['attrs'].items()}; ranks=state['ranks'].copy()
    effects=[e.model_dump() for e in character.effects if e.active and e.level<=level]
    for e in effects:
        if e['type']=='rank': ranks[e['target']]=max(0,min(4,e['value']))
    def bonus(target,extras=()): return stack([e for e in effects if e['target'] in [target,'all'] and e['type']!='rank']+list(extras))
    def prof(target): return proficiency(level,ranks.get(target,0))
    cl=rules.get(character.class_id) or {}; anc=rules.get(character.ancestry_id) or {}; cp=cl.get('profile',{}); ap=anc.get('profile',{})
    active=[rules.get(a['id']) for a in acquired]; english={a.get('english') for a in active if a}
    hp=ap.get('hp',0)+level*(cp.get('hp',0)+mods['con'])+bonus('hp')+(level if 'Toughness' in english else 0) if 'hp' in ap and 'hp' in cp else None
    gear=[]; warnings=[]
    for p in character.inventory:
        r=rules.get(p.rule_id) or {}; v={**r.get('values',{}),**p.values}; typ=p.kind if p.custom or not r.get('item_type') else r['item_type']
        gear.append({'id':p.id,'name':p.name or r.get('name','Предмет'),'type':typ,'values':v,'equipped':p.equipped,'runes':[rules.get(x) for x in p.runes]})
        if any(not rules.get(x) or rules.get(x).get('item_type')!='rune' for x in p.runes): warnings.append('Проверьте руны предмета: '+(p.name or r.get('name','Предмет')))
    if sum(g['equipped'] and g['type']=='armor' for g in gear)>1: warnings.append('Экипировано несколько доспехов. В расчет взят первый; снимите остальные.')
    armor=next((g for g in gear if g['equipped'] and g['type']=='armor'),{'values':{'category':'unarmored','ac':0,'dex_cap':99},'runes':[]})
    av=armor['values']; category=av.get('category','unarmored')
    rune=lambda g,t,default=0: max([default,*[r.get('values',{}).get('rune_value',0) for r in g['runes'] if r and r.get('values',{}).get('rune_type')==t]])
    armor_bonus=int(av.get('ac',0))+rune(armor,'armor_potency')
    shield=max([0,*[int(g['values'].get('ac',0)) for g in gear if g['type']=='shield' and g['equipped'] and g['values'].get('raised')]])
    ac=10+prof(category)+min(mods['dex'],int(av.get('dex_cap',99)))+bonus('ac',[{'type':'item','value':armor_bonus},{'type':'circumstance','value':shield}])
    meets=state['attrs']['str']>=int(av.get('strength',0)); speedpen=int(av.get('speed_penalty',0)); checkpen=int(av.get('check_penalty',0))
    if meets: speedpen=min(0,speedpen+5); checkpen=0
    skills={}
    skill_defs={**SKILLS,**{k:('Знания: '+k[5:],'int') for k in ranks if k.startswith('lore:')}}
    for k,(name,attr) in skill_defs.items():
        penalty=checkpen if attr in ['dex','str'] else 0
        if 'гибкий' in av.get('traits','').lower() and k in ['acrobatics','athletics']: penalty=0
        if 'шумный' in av.get('traits','').lower() and k=='stealth': penalty=int(av.get('check_penalty',0))
        skills[k]={'name':name,'attr':attr,'rank':ranks.get(k,0),'bonus':mods[attr]+prof(k)+bonus(k)+penalty,'sources':state['rank_sources'].get(k,[])}
    saves={k:mods[a]+prof(k)+bonus(k,[{'type':'item','value':rune(armor,'resilient')}]) for k,a in [('fort','con'),('reflex','dex'),('will','wis')]}
    weapons=[]
    for g in gear:
        if not g['equipped'] or g['type']!='weapon': continue
        v=g['values']; traits=v.get('traits','').lower(); ranged=v.get('ranged',False); cat=v.get('category','simple')
        attackattr=mods['dex'] if ranged else max(mods['str'],mods['dex']) if 'точн' in traits else mods['str']
        weapon_rank=ranks.get(cat,0)
        if state.get('weapon_group') and state['weapon_group']==v.get('group'):
            if 'Weapon Legend' in english: weapon_rank=max(weapon_rank,3 if cat=='advanced' else 4)
            elif 'Fighter Weapon Mastery' in english: weapon_rank=max(weapon_rank,2 if cat=='advanced' else 3)
        attack=proficiency(level,weapon_rank)+attackattr+bonus('attack',[{'type':'item','value':rune(g,'weapon_potency')}])
        damage=v.get('damage',''); m=re.search(r'(\d+)[dк](\d+)',damage)
        damage_mod=mods['str'] if not ranged or 'метат' in traits else math.floor(mods['str']/2) if 'тягов' in traits and mods['str']>0 else min(0,mods['str']) if 'тягов' in traits else 0
        if m: damage=damage[:m.start()]+f'{max(int(m[1]),rune(g,"striking",1))}d{m[2]}'+damage[m.end():]
        if 'Weapon Specialization' in english or 'Greater Weapon Specialization' in english:
            spec={2:2,3:3,4:4}.get(weapon_rank,0); damage_mod+=spec*(2 if 'Greater Weapon Specialization' in english else 1)
        damage_mod+=bonus('damage')
        weapons.append({'id':g['id'],'name':g['name'],'attack':attack,'damage':damage+(f' {damage_mod:+}' if damage_mod else ''),'rank':weapon_rank})
    key=state.get('key_attr'); classdc=10+prof('class_dc')+mods.get(key,0)+bonus('class_dc') if key and ranks.get('class_dc') else None
    spellattack=prof('spell')+mods.get(key,0)+bonus('spell_attack') if key and ranks.get('spell') else None
    return {'attrs':state['attrs'],'mods':mods,'ranks':ranks,'hp':hp,'ac':ac,'speed':max(0,ap.get('speed',25)+speedpen+bonus('speed')+(5 if 'Fleet' in english else 0)),'perception':mods['wis']+prof('perception')+bonus('perception'),'saves':saves,'skills':skills,'weapons':weapons,'class_dc':classdc,'spell_attack':spellattack,'spell_dc':(10+spellattack+bonus('spell_dc')-bonus('spell_attack')) if spellattack is not None else None,'active_effects':effects,'gear':gear,'warnings':warnings}
