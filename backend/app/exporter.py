from .constants import ATTRS,RANKS,SKILLS
from .export_text import CharacterDescriptions

def export_character(c,result,rules,mode='full',links=True,markdown=False):
    blocks=[]
    descriptions=CharacterDescriptions(c,result,rules)
    def head(s): blocks.append(('## ' if markdown else '')+s)
    def describe(rule):
        if rule:
            blocks.append(rule['text'])
            if links: blocks.append('Источник: '+rule['source'])
    head(c.name+' • '+str(c.level)+' уровень')
    identities=[rules.get(getattr(c,k)) for k in ['class_id','ancestry_id','heritage_id','background_id']]
    blocks.append(' • '.join(r['name'] for r in identities if r))
    stats=result['stats']
    if mode in ['full','brief']:
        blocks.append('\n'.join(f'{ATTRS[k]}: {v} ({stats["mods"][k]:+})' for k,v in stats['attrs'].items()))
        blocks.append(f'ОЗ: {stats["hp"] if stats["hp"] is not None else "не определены"} | КБ: {stats["ac"]} | Скорость: {stats["speed"]} футов | Восприятие: {stats["perception"]:+}')
        blocks.append('Спасброски: '+', '.join(f'{n} {stats["saves"][k]:+}' for k,n in [('fort','Стойкость'),('reflex','Рефлекс'),('will','Воля')]))
        if stats['class_dc'] is not None: blocks.append('КС класса: '+str(stats['class_dc']))
        if mode=='full':
            labels={'simple':'Простое оружие','martial':'Воинское оружие','advanced':'Продвинутое оружие','unarmed':'Безоружные атаки','light':'Легкие доспехи','medium':'Средние доспехи','heavy':'Тяжелые доспехи','unarmored':'Защита без доспехов','spell':'Заклинания'}
            trained=[f'{label}: {RANKS[stats["ranks"][key]]}' for key,label in labels.items() if stats['ranks'].get(key,0)]
            if trained: head('Мастерство'); blocks.append('\n'.join(trained))
        head('Навыки'); blocks.append('\n'.join(f'{s["name"]}: {s["bonus"]:+}, {RANKS[s["rank"]]}' for s in stats['skills'].values()))
        if stats['weapons']: head('Атаки'); blocks.extend(f'{w["name"]}: {w["attack"]:+}; урон {w["damage"]}' for w in stats['weapons'])
        if c.inventory:
            head('Снаряжение')
            for p in c.inventory:
                r=rules.get(p.rule_id); blocks.append(f'{p.name or (r or {}).get("name","Предмет")} × {p.count}'+(' [ручной предмет]' if p.custom else ''))
                if mode=='full': describe(r)
                if p.notes: blocks.append(p.notes)
    if mode in ['full','abilities']:
        head('Полные описания способностей и особенностей')
        for a in result['acquired']:
            r=rules.get(a['id'])
            if r and a['level']<=c.level and r['kind'] not in ['spell','focus_spell']:
                description=descriptions.text(r)
                if not description: continue
                head(f'{r["name"]} • получено на {a["level"]}-м уровне')
                blocks.append(description)
                if links: blocks.append('Источник: '+r['source'])
                for decision in descriptions.decisions(r): blocks.append('Принятое решение: '+decision.note.strip())
                if r['id'].endswith('#class-feature-barbarian-instinct-dragon') and descriptions.unresolved_instinct(r):
                    blocks.append('Не завершено: укажите вид дракона точным названием из таблицы и отношение к нему в связанном решении к инстинкту.')
                if r['id'].endswith('#class-feature-barbarian-instinct-animal') and descriptions.unresolved_instinct(r):
                    blocks.append('Не завершено: укажите выбранное животное точным названием из таблицы в связанном решении к инстинкту.')
    if mode in ['full','spells']:
        active_picks=[p for p in result['spells']['picks'] if p['status']=='valid']
        if result['spells']['sources'] or active_picks or result['spells']['auto_focus'] or result['spells']['auto_granted']:
            head('Заклинания')
        elif mode=='spells': blocks.append('Полученных заклинаний нет.')
        for source in result['spells']['sources']: blocks.append(source['name']+': чары '+str(source['cantrips'])+'; слоты '+', '.join(f'{r}: {n}' for r,n in source['slots'].items() if n))
        if result['spells']['focus_pool']: blocks.append('Очки фокусировки: '+str(result['spells']['focus_pool']))
        seen=set()
        for p in active_picks:
            rule=rules.get(p['pick']['rule_id']); head(p['name']+' • уровень сотворения '+str(p.get('rank','неактивно')))
            describe(rule); seen.add(rule['id'])
            if p.get('heightening',{}).get('automatic'): blocks.append(p['heightening']['value'])
            blocks.extend(p['messages'])
        for p in result['spells']['auto_focus']+result['spells']['auto_granted']:
            if p['id'] not in seen: describe(rules.get(p['id']))
    if mode=='levels':
        head('Развитие персонажа')
        for row in result['timeline']:
            head('Уровень '+str(row['level']))
            for a in row['automatic']: blocks.append('Автоматически: '+a['name'])
            for slot in row['slots']:
                ch=slot.get('choice'); val=ch.get('value') if ch else None; rule=rules.get(val)
                blocks.append(slot['label']+': '+(rule['name'] if rule else ', '.join(ATTRS.get(v,SKILLS[v][0] if v in SKILLS else 'Знания: '+v[5:] if v.startswith('lore:') else v) for v in val) if isinstance(val,list) else str(val or 'не выбрано'))+' ['+{'valid':'готово','missing':'не завершено','invalid':'недействительно','review':'нужна проверка'}.get(slot.get('status'),'?')+']')
                if ch and ch.get('note'): blocks.append(ch['note'])
        inactive=[s for s in result['outcomes'].values() if s['status']=='inactive']
        if inactive:
            head('Сохраненные неактивные решения'); blocks.extend(str(s['choice']) for s in inactive)
    if mode in ['full','brief']:
        active_effects=[e for e in c.effects if e.active and e.level<=c.level]
        if active_effects:
            head('Ручные эффекты'); blocks.extend(f'{e.label}: {e.target} {e.value:+} ({e.type}), включен'+(f'; источник: {e.source}' if e.source else '') for e in active_effects)
        if c.notes: head('Заметки'); blocks.append(c.notes)
    if result['issues']:
        head('Незавершенные выборы и проверки'); blocks.extend('• '+i['message'] for i in result['issues'])
    return '\n\n'.join(blocks)+'\n'
