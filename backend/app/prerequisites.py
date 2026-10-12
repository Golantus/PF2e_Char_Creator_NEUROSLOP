import re
from .constants import ATTR_STEMS,ATTRS,SKILL_STEMS,SKILLS,RANKS

def check(item,state,slot,rules):
    reasons=[]; review=[]
    if not item: return {'status':'invalid','reasons':['Элемент отсутствует в этой версии базы']}
    kind=slot['kind']; level=state['level']; cap=slot.get('max_level',level)
    if item.get('level',1)>cap: reasons.append(f'Требуется уровень {item["level"]}; в этом выборе допустим {cap}')
    allowed={'class_feat':['class_feat','archetype_feat'],'free_archetype':['archetype_feat'],'ancestry_feat':['ancestry_feat'],'general_feat':['general_feat','skill_feat'],'skill_feat':['skill_feat'],'subclass':['subclass'],'linked':list(rules.by_kind)}.get(kind,[kind])
    if item['kind'] not in allowed: reasons.append('Не подходит для этого слота')
    if kind=='subclass' and item.get('parent')!=slot.get('group'): reasons.append('Другая группа специализации')
    if item['kind']=='class_feat' and item['owner']!=slot.get('owner',state['class_id']): reasons.append('Способность другого класса')
    if item['kind']=='ancestry_feat' and item['owner'] not in [state['ancestry_id'],state.get('heritage_owner')]: reasons.append('Другая родословная или наследие')
    if item['id'] in state['selected'] and not item.get('repeatable') and kind!='linked': reasons.append('Уже получена; повторный выбор не разрешен')
    raw=item.get('prerequisites',''); rest=raw.lower().replace('ё','е')
    if re.search(r'\bили\b',rest): review.append('Альтернативные условия: '+raw)
    else:
        for key,stem in ATTR_STEMS.items():
            for m in re.finditer(stem+r'\w*\s+(\d+)',rest):
                if state['attrs'][key]<int(m[1]): reasons.append(f'{ATTRS[key]} {m[1]} (сейчас {state["attrs"][key]})')
                rest=rest.replace(m[0],'')
        for m in list(re.finditer(r'(обучен\w*|эксперт\w*|мастер(?:ом|а)?|легенд\w*)\s+(?:в\s+)?([а-я]+)',rest)):
            rank=next((n for n,w in [(1,'обуч'),(2,'эксперт'),(3,'мастер'),(4,'легенд')] if m[1].startswith(w)),0)
            key=next((k for k,v in SKILL_STEMS.items() if re.search(v,m[2])),None)
            if key:
                actual=max([0,*[v for k,v in state['ranks'].items() if k.startswith('lore:')]]) if key=='lore' else state['ranks'].get(key,0)
                if actual<rank: reasons.append(f'{RANKS[rank]}: {SKILLS[key][0]}')
                rest=rest.replace(m[0],'')
        for ref in item.get('field_links',{}).get('Предварительные условия',[]):
            dep=rules.get(ref)
            if dep and dep['kind'] in ['class_feat','ancestry_feat','general_feat','skill_feat','archetype_feat','feature','subclass','heritage']:
                if dep['id'] not in state['selected']: reasons.append('Требуется: '+dep['name'])
                for name in [dep['title'],dep['name'],dep.get('english','')]:
                    if name: rest=rest.replace(name.lower().replace('ё','е'),'')
        if re.search('[а-яa-z]{3}',re.sub(r'\([^)]*\)|способность|класса|уровень|[\d\W_]+',' ',rest)):
            review.append('Нужна проверка условия: '+raw)
    if any(t.lower() in ['необычный','редкий','уникальный'] for t in item.get('traits',[])) or item.get('fields',{}).get('Доступ'):
        review.append('Проверьте доступ к редкому правилу')
    if item['kind']=='archetype_feat' and any('посвящение'==t.lower() for t in item.get('traits',[])):
        for sid in state['selected']:
            old=rules.get(sid)
            if not old or old['owner']==item['owner'] or old['kind']!='archetype_feat' or 'посвящение' not in [t.lower() for t in old['traits']]: continue
            if re.search(r'(?:две|2) (?:другие|других)',old['text'],re.I):
                count=sum(1 for s in state['selected'] if (r:=rules.get(s)) and r['owner']==old['owner'] and r['id']!=old['id'] and r['kind']=='archetype_feat')
                if count<2: reasons.append('Перед новым посвящением нужны две другие способности: '+old['name'])
    return {'status':'invalid' if reasons else 'review' if review else 'available','reasons':reasons+review}
