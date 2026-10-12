import math,re
from collections import Counter
from .constants import ATTR_STEMS,BASE
from .calculations import modifier,proficiency

def tradition(text):
    return [k for k,v in [('arcane','аркан'),('divine','сакраль'),('occult','оккульт'),('primal','природ')] if re.search(v+r'\w*\s+(?:заклинан|колдовств|обыча)',text.lower())]

def heighten(rule,rank):
    original=rule.get('heightening',[]); base=rule['text']
    base=re.split(r'Усиление\s*\(',base)[0]
    starts=re.findall(r'(?:наносит|нанося|получает)\s+(\d+)[dк](\d+)\s+(?:\w+\s+)?урона',base,re.I)
    steps=[]
    for h in original:
        m=re.search(r'Усиление\s*\(\+(\d+)\).*?Урон увеличивается на (\d+)[dк](\d+)',h,re.I)
        if m: steps.append(tuple(map(int,m.groups())))
    if len(starts)==1 and len(steps)==1 and int(starts[0][1])==steps[0][2]:
        n,d=map(int,starts[0]); step,extra,_=steps[0]
        n+=max(0,(rank-rule['level'])//step)*extra
        return {'value':f'{n}d{d} урона','evidence':original,'automatic':True}
    return {'value':'Примените полное правило усиления ниже' if original else 'Отдельное правило усиления не найдено','evidence':original,'automatic':False}

def archetype_sources(character,state,rules,active):
    byowner={}
    for r in active:
        if r and r['kind']=='archetype_feat': byowner.setdefault(r['owner'],[]).append(r)
    sources=[]; level=state['level']
    for owner,feats in byowner.items():
        joined=' '.join(f.get('own_text','') for f in feats); refs={ref for f in feats for ref in f.get('links',[])}
        has_spell=bool(re.search('заклинан|колдовств',joined,re.I))
        if not has_spell: continue
        title=(rules.get(owner) or {}).get('name','Архетип'); slots={}; warnings=[]; rank=0
        keys=[]
        for f in feats:
            m=re.search(r'ключев\w* характеристик\w*[^.!?]*',f.get('own_text',''),re.I)
            if m: keys.extend(k for k,stem in ATTR_STEMS.items() if re.search(stem,m[0],re.I))
        key=keys[0] if len(set(keys))==1 else None
        bounded=any('bounded' in r for r in refs)
        stages=[n for n,word in [(1,'basic'),(2,'expert'),(3,'master')] if any(re.search('arch-'+word+r'-(?:bounded-)?spellcasting',r) and rules.get(r) for r in refs)]
        stage=max(stages,default=0)
        if stage:
            rank=stage
            if bounded:
                if stage>=1 and level>=6: slots={1:1,2:1} if level<10 else {2:1,3:1}
                if stage>=2 and level>=12: slots={2:1,3:2} if level<14 else {4:2,5:1} if level<16 else {5:2,6:1}
                if stage>=3 and level>=18: slots={5:2,6:2} if level<20 else {6:2,7:2}
            else:
                slots={1:1}
                for r,minlevel,need in [(2,6,1),(3,8,1),(4,12,2),(5,14,2),(6,16,2),(7,18,3),(8,20,3)]:
                    if level>=minlevel and stage>=need: slots[r]=1
                if any('breadth' in f.get('english','').lower() for f in feats):
                    for r in slots:
                        if r<=max(slots)-2: slots[r]+=1
        cantrips=None
        ded=next((f for f in feats if 'посвящение' in [t.lower() for t in f['traits']]),None)
        if ded:
            m=re.search(r'(?:подготавливаете|получаете|изучаете).{0,35}(дв[ае]|одн[иоу]|\d+)\s+чар',ded.get('own_text',''),re.I)
            if m: cantrips={'две':2,'два':2,'одну':1,'одно':1}.get(m[1].lower(),int(m[1]) if m[1].isdigit() else 1)
            if re.search(r'обучены.{0,45}(?:атак|кс).{0,35}заклинан',ded.get('own_text',''),re.I): rank=max(1,rank)
        if not key: warnings.append('Ключевую характеристику этого источника нужно проверить по описанию')
        if cantrips is None: warnings.append('Число чар этого архетипа требует проверки по описанию')
        attack=proficiency(level,rank)+modifier(state['attrs'][key]) if rank and key else None
        sources.append({'id':owner,'name':title,'slots':{str(k):v for k,v in slots.items()},'cantrips':cantrips,'traditions':tradition(joined),'attack':attack,'dc':attack+10 if attack is not None else None,'mode':'repertoire' if 'репертуар' in joined.lower() else 'prepared','warnings':warnings})
    return sources

def spell_sheet(c,state,rules,acquired,stats):
    level=state['level']; cl=rules.get(c.class_id) or {}; active=[rules.get(a['id']) for a in acquired]; active=[r for r in active if r]
    table=cl.get('spell_table',{}).get(str(level),cl.get('spell_table',{}).get(level,{}))
    sources=[]; issues=[]
    subclass_text=' '.join(r.get('own_text','') for r in active if r['kind']=='subclass')
    main_text=' '.join(r.get('own_text','') for r in active if r['kind']=='feature')
    tr=tradition(subclass_text) or tradition(' '.join(e.get('evidence','') for e in cl.get('profile',{}).get('effects',[])))
    if c.tradition: tr=[c.tradition]
    mode='repertoire' if any('repertoire' in r.get('english','').lower() for r in active) else 'prepared'
    if table: sources.append({'id':'class','name':cl.get('name','Класс'),'cantrips':table.get('cantrips',0),'slots':table.get('slots',{}),'traditions':tr,'attack':stats['spell_attack'],'dc':stats['spell_dc'],'mode':mode,'warnings':[],'source':table.get('source')})
    sources.extend(archetype_sources(c,state,rules,active))
    bases=[e['value'] for r in active for e in r.get('effects',[]) if e['op']=='focus_base']; adds=[e['value'] for r in active for e in r.get('effects',[]) if e['op']=='focus_add']
    auto_focus=[r for r in active if r['kind']=='focus_spell']; pool=min(3,max(bases,default=1 if auto_focus else 0)+sum(adds))
    source_map={s['id']:s for s in sources}; counts=Counter(); signatures=Counter(); picks=[]
    auto_granted=[{'id':r['id'],'name':r['name'],'rank':0 if r.get('cantrip') else r['level']} for r in active if r['kind']=='spell']
    if mode=='repertoire':
        explicit={p.rule_id for p in c.spells if p.source=='class' and p.mode=='repertoire' and p.level<=level}
        for grant in auto_granted:
            if grant['id'] not in explicit: counts[('class',grant['rank'])]+=1
    for pick in c.spells:
        rule=rules.get(pick.rule_id); msgs=[]
        if not rule: issues.append('Заклинание отсутствует: '+pick.rule_id); continue
        if pick.level>level: picks.append({'pick':pick.model_dump(),'name':rule['name'],'status':'inactive','messages':['Получено на более высоком уровне']}); continue
        cantrip=rule.get('cantrip'); focus=rule['kind']=='focus_spell'; rank=math.ceil(level/2) if cantrip or focus else pick.cast_rank
        source=source_map.get(pick.source)
        if not focus and not cantrip and rank<rule['level']: msgs.append('Уровень сотворения ниже базового')
        if source and pick.mode not in ['known','focus','innate']:
            tr=source.get('traditions',[])
            if tr and rule.get('traditions') and not set(tr)&set(rule['traditions']) and rule['id'] not in state['selected']: msgs.append('Заклинание другого магического обычая')
            slotrank=0 if cantrip else rank
            counts[(pick.source,slotrank)]+=1
            capacity=source['cantrips'] if cantrip else source['slots'].get(str(rank),0)
            if capacity is not None and counts[(pick.source,slotrank)]>capacity: msgs.append('Превышено число чар или слотов источника')
            if pick.mode=='repertoire' and pick.signature:
                signatures[(pick.source,rank)]+=1
                if level<3 or cantrip or signatures[(pick.source,rank)]>1: msgs.append('Проверьте право на коронное заклинание этого уровня')
        elif not focus and pick.mode not in ['known','innate']: msgs.append('Источник слотов не определен')
        if focus and rule['id'] not in state['selected']: msgs.append('Источник этого заклинания фокусировки не выбран')
        picks.append({'pick':pick.model_dump(),'name':rule['name'],'rank':rank,'status':'invalid' if msgs else 'valid','messages':msgs,'heightening':heighten(rule,rank)})
        issues.extend(rule['name']+': '+m for m in msgs)
    return {'sources':sources,'focus_pool':pool,'auto_focus':[{'id':r['id'],'name':r['name'],'rank':math.ceil(level/2)} for r in auto_focus],'auto_granted':auto_granted,'picks':picks,'issues':issues,'cantrip_rank':math.ceil(level/2)}
