import copy,re
from .constants import ATTRS,SKILLS,KINDS
from .calculations import boost,modifier,calculate
from .prerequisites import check
from .choice_rules import extra_choices

def build(character,rules):
    c=character; cl=rules.get(c.class_id); anc=rules.get(c.ancestry_id); bg=rules.get(c.background_id); heritage=rules.get(c.heritage_id)
    state={'level':1,'attrs':{a:10 for a in ATTRS},'ranks':{},'rank_sources':{},'selected':set(),'class_id':c.class_id,'ancestry_id':c.ancestry_id,'heritage_owner':heritage['owner'] if heritage else None,'key_attr':None}
    acquired=[]; timeline=[]; issues=[]; snapshots={}; outcomes={}; choices={x.slot:x for x in c.choices}; handled=set(); replacements=[]; extra_slots=[]; applied_effects=set(); instances=set()
    def problem(message,level=1,slot=None,kind='warning'): issues.append({'message':message,'level':level,'slot':slot,'type':kind})
    for label,rule in [('класс',cl),('родословную',anc),('предысторию',bg)]:
        if not rule: problem('Выберите '+label,kind='missing')
    def rank(key,value,source,level,replace=True):
        old=state['ranks'].get(key,0)
        if replace and old>=1 and value==1 and (key in SKILLS or key.startswith('lore:')):
            sid=f'L{level}:replacement:{source}:{key}'
            if not any(s['id']==sid for s in replacements): replacements.append({'id':sid,'level':level,'kind':'trained','count':1,'label':'Замена повторного обучения: '+(SKILLS[key][0] if key in SKILLS else 'Знания '+key[5:])})
        state['ranks'][key]=max(old,value)
        state['rank_sources'].setdefault(key,[]).append({'source':source,'level':level,'rank':value})
    def acquire(item,level,via='',depth=0):
        if not item or depth>12: return
        if item['id'] in state['selected'] and (not item.get('repeatable') or not via.startswith('L') or (item['id'],via) in instances): return
        instances.add((item['id'],via))
        state['selected'].add(item['id']); acquired.append({'id':item['id'],'level':level,'via':via,'kind':item['kind'],'name':item['name']})
        localtargets=set()
        for ef in item.get('effects',[]):
            if ef['op']=='rank':
                key=ef['target']
                if ef.get('level',1)>level: continue
                if key in localtargets or (item['kind']=='archetype_feat' and key=='spell'): continue
                localtargets.add(key); rank(key,ef['value'],item['id'],level); applied_effects.add((item['id'],key,ef.get('level',1),ef['value']))
        for grant in item.get('grants',[]):
            if grant.get('level',1)>level: continue
            other=rules.get(grant['id'])
            if other and other['kind'] in ['class_feat','ancestry_feat','general_feat','skill_feat','focus_spell','spell','feature']:
                acquire(other,level,item['id'],depth+1)
        for i,spec in enumerate(extra_choices(item,level,c.class_id)):
            if spec['kind']=='weapon_group': spec['options']=sorted({r['values']['group'] for r in rules.kind('item') if r.get('values',{}).get('group')})
            extra_slots.append({'id':f'L{level}:extra:{item["id"]}:{i}:{via}','level':level,'parent':item['id'],**spec})
    if cl:
        state['selected'].add(cl['id']); acquired.append({'id':cl['id'],'name':cl['name'],'level':1,'kind':'class','via':'initial'})
        for ef in cl.get('profile',{}).get('effects',[]): rank(ef['target'],ef['value'],cl['id'],1,False)
    if anc:
        for a in anc.get('profile',{}).get('boosts',[]): state['attrs'][a]=boost(state['attrs'][a])
        for a in anc.get('profile',{}).get('flaws',[]): state['attrs'][a]-=2
    for rule in [anc,heritage,bg]: acquire(rule,1)
    class_names={r['name']:r for r in rules.kind('feature') if cl and r['owner']==cl['id']}
    groups={}
    for s in rules.kind('subclass'):
        if cl and s['owner']==cl['id']: groups.setdefault(s['parent'],[]).append(s)
    previous_int=0
    for level in range(1,c.level+1):
        state['level']=level; slots=[]; automatic=[]
        def add(kind,label=None,**kw):
            sid=kw.pop('id',f'L{level}:{kind}:{sum(1 for s in slots if s["kind"]==kind)}')
            slots.append({'id':sid,'level':level,'kind':kind,'label':label or KINDS.get(kind,kind),**kw})
        if level==1:
            add('boost','Повышения родословной',id='L1:ancestry_boost',count=anc.get('profile',{}).get('free_boosts',0) if anc else 0,options=[a for a in ATTRS if a not in (anc or {}).get('profile',{}).get('boosts',[])])
            add('boost','Повышения предыстории',id='L1:background_boost',count=2,options=list(ATTRS),required_one=(bg or {}).get('boost_options',[]))
            add('boost','Ключевая характеристика',id='L1:class_boost',count=1,options=(cl or {}).get('profile',{}).get('key_attrs',[]))
            add('boost','Четыре свободных повышения',id='L1:free_boost',count=4,options=list(ATTRS))
            if anc: add('ancestry_feat')
        if cl:
            entries=cl.get('progression',{}).get(str(level),cl.get('progression',{}).get(level,[]))
            for entry in entries:
                if entry['kind']!='feature':
                    if entry['kind']=='ancestry_feat' and level==1: continue
                    add(entry['kind'],entry['label'],**({'count':4,'options':list(ATTRS)} if entry['kind']=='boost' else {}))
                else:
                    rule=rules.get(entry.get('ref')) or class_names.get(entry['label'].split(' (')[0].split(' /')[0])
                    if rule:
                        before=len(acquired); acquire(rule,level,'class_table'); automatic.extend(acquired[before:])
                    elif entry.get('ref'): problem('Не найдено автоматическое правило: '+entry['label'],level)
        for group,variants in groups.items():
            lv=min(s.get('choice_level',1) for s in variants)
            if lv==level:
                gr=rules.get(group)
                add('subclass',gr['name'] if gr else 'Специализация',id=f'L{level}:subclass:{group}',group=group,options=[s['id'] for s in variants])
        if c.free_archetype and level>=2 and level%2==0: add('free_archetype',id=f'L{level}:free_archetype')
        def outcome(slot,status,reasons=(),choice=None):
            slot.update(status=status,reasons=list(reasons),choice=choice.model_dump() if choice else None)
            outcomes[slot['id']]=slot; handled.add(slot['id'])
            if status!='valid': problem((slot['label']+': '+('; '.join(reasons) or 'выбор не завершен')),level,slot['id'],'missing' if status=='missing' else status)
        def simple(slot):
            ch=choices.get(slot['id']); vals=ch.value if ch and isinstance(ch.value,list) else []
            if slot['kind']=='weapon_group':
                if ch and ch.value in slot['options']: state['weapon_group']=ch.value;outcome(slot,'valid',[],ch)
                else: outcome(slot,'missing',[],ch)
            elif slot['kind']=='boost':
                valid=[a for a in vals if a in slot.get('options',list(ATTRS))]; good=len(vals)==len(set(vals)) and len(valid)==len(vals) and len(vals)<=slot.get('count',0)
                if not good: outcome(slot,'invalid',['Повышения должны быть разными и допустимыми'],ch); return
                req=slot.get('required_one',[])
                if req and len(vals)==slot['count'] and not set(vals)&set(req): outcome(slot,'invalid',['Одно повышение должно соответствовать предыстории'],ch); return
                for a in valid: state['attrs'][a]=boost(state['attrs'][a])
                if slot['id']=='L1:class_boost' and valid: state['key_attr']=valid[0]
                outcome(slot,'valid' if len(vals)==slot['count'] else 'missing',[],ch)
            else:
                count=slot.get('count',1); errors=[]
                if len(vals)!=len(set(vals)) or len(vals)>count: errors.append('Нужны разные навыки в пределах числа выборов')
                for k in vals:
                    old=state['ranks'].get(k,0)
                    valid_lore=isinstance(k,str) and k.startswith('lore:') and 5<len(k)<100
                    if (k not in SKILLS and not valid_lore) or ('options' in slot and k not in slot['options']): errors.append('Недопустимый навык'); continue
                    name=SKILLS[k][0] if k in SKILLS else 'Знания: '+k[5:]
                    if slot['kind']=='trained' and old>0: errors.append(name+': уже обучен')
                    if slot['kind']=='skill_increase' and (old>=4 or old>=2 and level<7 or old>=3 and level<15): errors.append(name+': мастер с 7-го, легенда с 15-го уровня')
                if errors: outcome(slot,'invalid',errors,ch); return
                for k in vals: rank(k,state['ranks'].get(k,0)+1 if slot['kind']=='skill_increase' else 1,slot['id'],level,False)
                outcome(slot,'valid' if len(vals)==count else 'missing',[],ch)
        for slot in slots:
            if slot['kind']=='boost': simple(slot)
        for slot in slots:
            if slot['kind']=='subclass':
                ch=choices.get(slot['id']); rule=rules.get(ch.value) if ch else None
                if not ch: outcome(slot,'missing'); continue
                result=check(rule,state,slot,rules)
                if result['status']=='invalid': outcome(slot,'invalid',result['reasons'],ch)
                else: acquire(rule,level,slot['id']); outcome(slot,'valid',[],ch)
        for a in acquired[:]:
            parent_rule=rules.get(a['id'])
            for ef in parent_rule.get('effects',[]):
                if ef['op']=='rank' and ef.get('level',1)<=level:
                    ek=(parent_rule['id'],ef['target'],ef.get('level',1),ef['value'])
                    if ek not in applied_effects and not (parent_rule['kind']=='archetype_feat' and ef['target']=='spell'):
                        rank(ef['target'],ef['value'],parent_rule['id'],level,False);applied_effects.add(ek)
            for grant in parent_rule.get('level_grants',[])+parent_rule.get('grants',[]):
                if grant.get('level',1)<=level:
                    target=rules.get(grant['id'])
                    if target and target['kind'] in ['class_feat','ancestry_feat','general_feat','skill_feat','spell','focus_spell','feature']: acquire(target,level,parent_rule['id'])
        if level==1 and cl:
            add('trained','Навыки класса',id='L1:trained',count=max(0,cl.get('profile',{}).get('skill_count',0)+modifier(state['attrs']['int'])))
            for i,spec in enumerate(cl.get('profile',{}).get('skill_choices',[])): add('trained',spec['text'],id=f'L1:class_skill:{i}',count=1,options=spec['options'])
        if level>1 and modifier(state['attrs']['int'])>previous_int:
            add('trained','Навыки от повышения Интеллекта',id=f'L{level}:int_skills',count=modifier(state['attrs']['int'])-previous_int)
        previous_int=modifier(state['attrs']['int'])
        slots.extend(s for s in replacements if s['level']==level and s['id'] not in {x['id'] for x in slots})
        for slot in slots:
            if slot['kind'] in ['trained','skill_increase']: simple(slot)
        pending=[s for s in slots if s['kind'] not in ['trained','skill_increase','boost','subclass']]
        for _ in range(12):
            for ex in extra_slots:
                if ex['level']==level and ex['id'] not in {s['id'] for s in slots}:
                    slots.append(ex)
                    if ex['kind'] in ['trained','weapon_group']: simple(ex)
                    else: pending.append(ex)
            changed=False
            for slot in pending[:]:
                ch=choices.get(slot['id'])
                if not ch: outcome(slot,'missing'); pending.remove(slot); continue
                rule=rules.get(ch.value); result=check(rule,state,slot,rules)
                if result['status']=='available' or result['status']=='review' and ch.confirmed:
                    acquire(rule,level,slot['id']); outcome(slot,'valid',result['reasons'],ch); pending.remove(slot); changed=True
            if not changed: break
        for slot in pending:
            ch=choices.get(slot['id']); result=check(rules.get(ch.value),state,slot,rules)
            outcome(slot,result['status'],result['reasons'],ch)
        for ch in c.choices:
            if ch.kind=='linked' and ch.level==level and ch.parent in state['selected']:
                slot={'id':ch.slot,'level':level,'kind':'linked','label':'Связанный выбор','parent':ch.parent}; slots.append(slot)
                if not ch.confirmed: outcome(slot,'review',['Подтвердите соответствие исходному правилу'],ch)
                elif isinstance(ch.value,str) and rules.get(ch.value): acquire(rules.get(ch.value),level,ch.slot); outcome(slot,'valid',[],ch)
                elif ch.note: outcome(slot,'valid',[],ch)
                else: outcome(slot,'missing',[],ch)
        for ex in extra_slots:
            if ex.get('expert_at')==level:
                ch=choices.get(ex['id'])
                if ch and outcomes.get(ex['id'],{}).get('status')=='valid':
                    for k in ch.value: rank(k,2,ex['parent'],level,False)
        for replacement in replacements:
            if replacement['level']==level and replacement['id'] not in handled: slots.append(replacement); simple(replacement)
        snapshot=copy.deepcopy(state); snapshot['selected']=list(snapshot['selected']); snapshots[level]=snapshot
        timeline.append({'level':level,'automatic':automatic,'slots':slots,'complete':all(s.get('status')=='valid' for s in slots),'new_spells':[p.model_dump() for p in c.spells if p.level==level]})
    for ch in c.choices:
        if ch.slot not in handled: outcomes[ch.slot]={'id':ch.slot,'status':'inactive','choice':ch.model_dump(),'reasons':['Выбор сохранен, но не действует при текущем уровне и параметрах']}
    for a in acquired:
        rule=rules.get(a['id'])
        if rule.get('has_choices') and rule['kind'] in ['class_feat','ancestry_feat','general_feat','skill_feat','archetype_feat','subclass','heritage'] and not any(x.parent==rule['id'] for x in c.choices) and not extra_choices(rule,a['level'],c.class_id):
            problem('Проверьте дополнительные решения: '+rule['name'],a['level'])
    stats=calculate(c,state,rules,acquired)
    issues.extend({'message':m,'level':c.level,'type':'warning'} for m in stats.pop('warnings',[]))
    from .spells import spell_sheet
    spell=spell_sheet(c,state,rules,acquired,stats)
    issues.extend({'message':m,'level':c.level,'type':'warning'} for m in spell['issues'])
    return {'rules_version':rules.version,'timeline':timeline,'acquired':acquired,'issues':issues,'outcomes':outcomes,'snapshots':snapshots,'stats':stats,'spells':spell,'subclass_names':{g:[{'id':s['id'],'name':s['name']} for s in ss] for g,ss in groups.items()},'state':{**state,'selected':list(state['selected'])}}
