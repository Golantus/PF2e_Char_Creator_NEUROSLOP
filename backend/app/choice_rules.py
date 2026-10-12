"""Explicit handlers. Unknown choices remain visible and require a recorded decision."""
import re

def extra_choices(item,level,class_id):
    en=item.get('english','').lower(); text=item.get('own_text',item['text']); out=[]
    if en in ['general training','versatile heritage']:
        out.append({'kind':'general_feat','max_level':1 if en=='general training' else level,'label':'Дополнительная общая способность'})
    elif en=='natural ambition': out.append({'kind':'class_feat','max_level':1,'owner':class_id,'label':'Дополнительная классовая способность'})
    elif en=='natural skill': out.append({'kind':'trained','count':2,'label':'Два обученных навыка'})
    elif en in ['skilled human','skilled heritage']: out.append({'kind':'trained','count':1,'label':'Навык умелого наследия','expert_at':5})
    elif en in ['fighter weapon mastery','weapon legend']:
        out.append({'kind':'weapon_group','label':'Группа оружия для повышения мастерства'})
    elif en=='combat flexibility': out.append({'kind':'class_feat','max_level':8,'owner':class_id,'label':'Боевая адаптация: ежедневная способность'})
    elif en=='improved flexibility': out.append({'kind':'class_feat','max_level':14,'owner':class_id,'label':'Улучшенная адаптация: вторая способность'})
    if item['kind']=='archetype_feat':
        if re.search(r'способност\w*.{0,60}1-го или 2-го уровня',text,re.I):
            out.append({'kind':'class_feat','max_level':2,'owner':item['owner'].replace('/archetypes/','/'),'label':'Способность другого класса'})
        elif re.search(r'половин\w* вашего уровня|равен половине',text,re.I) and 'способност' in text:
            out.append({'kind':'class_feat','max_level':max(1,level//2),'owner':item['owner'].replace('/archetypes/','/'),'label':'Способность другого класса'})
    return out
