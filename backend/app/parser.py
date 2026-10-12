"""Sphinx sections are authoritative; structured effects retain their evidence."""
import copy, json, re
from pathlib import Path
from urllib.parse import urljoin, urldefrag
import bleach
from bs4 import BeautifulSoup, Tag
from .constants import BASE, ATTR_STEMS, SKILL_STEMS, TARGETS, SUBGROUPS

def norm(s): return re.sub(r'\s+',' ',str(s)).strip().replace('ё','е')
def txt(node): return norm(node.get_text(' ',strip=True)) if node else ''
def names_in(s,stems): return [k for k,v in stems.items() if re.search(v,s.lower().replace('ё','е'))]
def anchors(sec): return [x['id'] for x in sec.find_all('span',id=True,recursive=False)]+([sec['id']] if sec.get('id') else [])
def anchor(sec):
    aa=anchors(sec)
    return next((a for a in aa if not re.fullmatch(r'id\d+|table-.+',a)),aa[0] if aa else '')
def own(sec):
    n=copy.deepcopy(sec)
    for child in n.find_all('section',recursive=False): child.decompose()
    return n
def clean(sec,url):
    n=copy.deepcopy(sec)
    for tag in n.select('script,style,form,iframe,object,embed,nav,.headerlink,.sidebar-title,.toctree-wrapper'): tag.decompose()
    for im in n.find_all('img'): im.replace_with(' ['+im.get('alt','изображение')+'] ')
    for a in n.find_all('a',href=True):
        a['href']=urljoin(url,a['href']); a['target']='_blank'; a['rel']='noopener noreferrer'
    html=bleach.clean(str(n),tags=['section','div','p','span','a','strong','em','b','i','u','s','blockquote','h1','h2','h3','h4','h5','h6','ul','ol','li','dl','dt','dd','table','caption','thead','tbody','tr','th','td','br','hr','sup','sub','code','pre','aside'],attributes={'a':['href','target','rel'],'td':['colspan','rowspan'],'th':['colspan','rowspan']},protocols=['https','http'],strip=True)
    for table in n.find_all('table'):
        lines=[' | '.join(txt(c) for c in row.find_all(['th','td'],recursive=False)) for row in table.find_all('tr')]
        table.replace_with('\n'+'\n'.join(lines)+'\n')
    for p in n.find_all(['p','div','section','h1','h2','h3','h4','h5','h6','li','dt','dd','br']):
        p.insert_before('\n'); p.insert_after('\n')
    text='\n'.join(norm(l) for l in n.get_text(' ').splitlines() if norm(l))
    return html,text

def rank_effects(text,initial=False):
    result=[]
    sentences=[]
    for sentence in re.split(r'[.!?\n]+',text):
        if re.search(r'\bесли\b|этой групп|выбранн',sentence,re.I): continue
        sentences.extend(re.split(r',\s*(?:и\s+)?(?=(?:вы|ваш)\s)',sentence,flags=re.I))
    for sentence in sentences:
        s=sentence.lower().replace('ё','е')
        if re.search(r'\bесли\b|\bили\b|на выбор|можете|выбер|котор|этой групп|выбранн|любимым оружием',s): continue
        if len(set(re.findall(r'обучен|эксперт|мастер(?:а|ом|у|$|\s)|легенд',s)))>1: continue
        rank=next((r for r,pat in [(4,r'легенд'),(3,r'мастер(?:а|ом|у|$|\s)'),(2,r'эксперт'),(1,r'обучен')] if re.search(pat,s)),None)
        if rank is None: continue
        if not initial and not re.search(r'вы обучены|становите[сь]+|увеличива[ею]тся|повышается|вы эксперт|вы мастер|вы получаете (?:уровень )?мастерств|вы имеете уровень мастерства',s): continue
        ts=names_in(s,TARGETS)
        if 'lore' in ts:
            lm=re.search(r'Знания(?:м|х|ми)?\s+([^,;.!?]+)',sentence,re.I)
            ts.remove('lore')
            if lm:
                lore_name=re.split(r'\(|\s+и\s+',lm[1])[0].strip()
                if lore_name: ts.append('lore:'+lore_name)
        if 'заклинан' in s and 'природ' in s: ts=[t for t in ts if t!='nature']
        if 'всем доспех' in s: ts+=['light','medium','heavy']
        if 'доспех' in s:
            for word,key in [('легк','light'),('средн','medium'),('тяжел','heavy')]:
                if word in s: ts.append(key)
        if 'оруж' in s:
            for word,key in [('прост','simple'),('воинск','martial'),('продвинут','advanced')]:
                if word in s: ts.append(key)
        if 'заклинани' in s and ('атакам' in s or 'кс' in s): ts+=['spell']
        for t in set(ts): result.append({'op':'rank','target':t,'value':rank,'evidence':sentence.strip()})
    return result

def profile(sec,kind):
    p={}; side=sec.find('aside'); st=txt(side); head=txt(own(sec))
    p['effects']=rank_effects('\n'.join(txt(x) for x in side.find_all('p')) if side else '',True)
    hp=re.search(r'(?:Очки Здоровья|Очки здоровья)\s*(\d+)',head)
    if hp: p['hp']=int(hp[1])
    if kind=='class':
        key=re.search(r'Ключевая характеристика(.+?)(?:На 1|Очки Здоровья)',head,re.I)
        p['key_attrs']=names_in(key[1],ATTR_STEMS) if key else []
        m=re.search(r'(\d+)\s*\+\s*модификатор Интеллекта',st)
        p['skill_count']=int(m[1]) if m else 0
        p['skill_choices']=[]
        for paragraph in side.find_all('p') if side else []:
            t=txt(paragraph)
            if 'Обучен' in t and ('на выбор' in t or ' или ' in t): p['skill_choices'].append({'text':t,'options':names_in(t,SKILL_STEMS)})
    if kind=='ancestry':
        speed=re.search(r'Скорость\s*(\d+)',st)
        p['speed']=int(speed[1]) if speed else 25
        for name,label in [('boosts','Повышения характеристик'),('flaws','Недостатки характеристик')]:
            marker=side.find(string=re.compile(label,re.I)) if side else None
            bits=[]
            if marker:
                for sibling in marker.parent.next_siblings:
                    if isinstance(sibling,Tag) and 'rubric' in sibling.get('class',[]): break
                    if isinstance(sibling,Tag): bits.append(txt(sibling))
            p[name]=names_in(' '.join(bits),ATTR_STEMS)
        p['free_boosts']=2 if re.search(r'(?:Два|2) свободных',st,re.I) else 1
    return p

def slot_kind(label):
    s=label.lower()
    if 'повышени' in s and 'характеристик' in s: return 'boost'
    if 'увеличени' in s and 'навык' in s: return 'skill_increase'
    if 'способност' in s:
        if 'родослов' in s: return 'ancestry_feat'
        if 'навык' in s: return 'skill_feat'
        if 'общ' in s: return 'general_feat'
        if '(' not in s and '/' not in s: return 'class_feat'
    return 'feature'

def progression(sec,url):
    out={}; spells={}
    for table in sec.find_all('table'):
        caption=txt(table.find('caption')).lower()
        rows=table.select('tbody > tr')
        if 'развитие' in caption and len(rows)==20:
            for row in rows:
                cells=row.find_all('td',recursive=False)
                if len(cells)!=2: continue
                lv=re.match(r'\d+',txt(cells[0]))
                if not lv: continue
                links={txt(a):urljoin(url,a['href']) for a in cells[1].find_all('a',href=True)}
                entries=[]
                for label in re.split(r',\s*(?![^()]*\))',txt(cells[1])):
                    label=label.strip()
                    entries.append({'label':label,'kind':slot_kind(label),'ref':links.get(label)})
                out[int(lv[0])]=entries
        if ('заклинани' in caption and ('в день' in caption or len(rows)==20)) and len(rows)==20:
            for row in rows:
                cells=[txt(c) for c in row.find_all('td',recursive=False)]
                if len(cells)>2 and cells[0].isdigit():
                    vals=[int(m[0]) if (m:=re.match(r'\d+',v)) else 0 for v in cells[1:]]
                    spells[int(cells[0])]={'cantrips':vals[0],'slots':{str(i):n for i,n in enumerate(vals[1:],1)},'source':url+'#'+table.get('id','')}
    return out,spells

def parse_page(url,raw):
    soup=BeautifulSoup(raw,'lxml'); body=soup.select_one('[itemprop="articleBody"]') or soup.select_one('[role="main"]') or soup
    root=body.find('section'); items=[]
    if not root: return []
    isclass='char-class' in root.get('class',[])
    isanc='ancestries_and_backgrounds/ancestries/' in url and url.rsplit('/',1)[-1]!='index.html'
    isarch='/classes/archetypes/' in url and not url.endswith('/index.html')
    for sec in body.find_all('section'):
        h=sec.find(re.compile(r'^h[1-6]$'),recursive=False)
        if not h: continue
        title=txt(h).replace('¶','').strip(); aid=anchor(sec)
        if not title or not aid: continue
        aliases=[url+'#'+a for a in anchors(sec)]; kind='rule'; ownsec=own(sec)
        ids=' '.join(anchors(sec)); parent=sec.find_parent('section'); pid=anchor(parent) if parent else ''
        levelmatch=re.search(r'/\s*(?:(?:Закл\.|Фокус\.|Чары|Предмет|Ритуал|Руна|Силок)\s*)?(\d+)',title,re.I)
        lv=int(levelmatch[1]) if levelmatch else 1
        if sec is root and isclass: kind='class'
        elif sec is root and isanc: kind='ancestry'
        elif sec is root and isarch: kind='archetype'
        elif sec is root and '/versatile_heritages/' in url and not url.endswith('/index.html'): kind='heritage'
        elif re.search(r'class-feat(?!ure)',ids): kind='archetype_feat' if isarch else 'class_feat'
        elif ('ancestry-feat' in ids or 'heritage-feat' in ids) and 'class-feature' not in ids: kind='ancestry_feat'
        elif re.search(r'(?:^|\s)feat-',ids): kind='archetype_feat' if isarch else 'general_feat'
        elif re.search(r'/(?:\s*)Предыстория',title,re.I) or re.search(r'(^|\s)bg-',ids): kind='background'
        elif 'heritage-' in ids or ('Наследие' in title and '(' in title): kind='heritage'
        elif re.search(r'/(?:\s*)(?:Закл\.|Фокус\.|Чары|Ритуал)\s*\d+',title): kind='focus_spell' if '/focus/' in url or 'Фокус.' in title else 'spell'
        elif re.search(r'/\s*(?:Предмет|Руна|Силок)\s*\d+',title): kind='item'
        elif isclass:
            kind='subclass' if any(pid.endswith(g) or re.search(re.escape(g)+r'-\d+$',pid) for g in SUBGROUPS) else 'feature'
            if kind=='subclass' and any(w in title.lower() for w in ['прочтение','формат','как читать','заклинания наследия крови','заклинания эйдолона']): kind='rule'
        if kind.endswith('_feat') and not levelmatch: kind='feature' if isclass else 'rule'
        fields={}; field_links={}
        for p in ownsec.find_all('p'):
            st=p.find('strong',recursive=False)
            if st and len(txt(st))<80 and (':' in txt(st) or txt(p)[len(txt(st)):].lstrip().startswith(':') or txt(st) in ['Предварительные условия','Требования']):
                key=txt(st).strip(': '); fields[key]=txt(p)[len(txt(st)):].strip(': ')
                field_links[key]=[urljoin(url,a['href']) for a in p.find_all('a',href=True)]
        traits=[]
        ul=sec.find('ul',recursive=False)
        if ul:
            candidates=[txt(li) for li in ul.find_all('li',recursive=False)]
            if candidates and all(len(t)<45 for t in candidates): traits=candidates
        if kind=='general_feat' and 'навык' in [t.lower() for t in traits]: kind='skill_feat'
        if kind=='rule' and ('способность' in title.lower() or 'feat' in ids) and levelmatch:
            kind='archetype_feat' if isarch else 'ancestry_feat' if isanc else 'general_feat'
        if '/books/Dark-Archive/Deviant-Abilities.html' in url and (
                'deviant-feat-' in ids or 'backlash' in ids
                or 'classifications-deviation-saves-and-attack-rolls' in ids):
            # These are special grants, not ordinary general-feat choices.
            kind='feature'
        full=ownsec if kind in ['class','ancestry'] else sec
        if kind=='heritage' and sec is root:
            full=copy.deepcopy(sec)
            for child in full.find_all('section',recursive=False):
                heading=child.find(re.compile(r'^h[1-6]$'),recursive=False)
                if 'способности' in txt(heading).lower(): child.decompose()
        html,text=clean(full,url); _,owntext=clean(ownsec,url)
        english=txt(h.select_one('a.external'))
        if not english:
            enmatch=re.search(r'\((.*)\)',title)
            if enmatch: english=enmatch[1].strip()
        ident=url if kind in ['class','ancestry','archetype'] else url+'#'+aid
        item={'id':ident,'aliases':aliases,'kind':kind,'name':title.split(' (')[0].split(' /')[0],'english':english,'title':title,'level':lv,'owner':url,'parent':url+'#'+pid if pid else None,'html':html,'text':text,'own_text':owntext,'source':url+'#'+aid,'traits':traits,'fields':fields,'field_links':field_links,'links':[urljoin(url,a['href']) for a in sec.find_all('a',href=True) if not 'headerlink' in a.get('class',[])],'effects':rank_effects(owntext),'grants':[],'uncertainties':[]}
        item['actions']=[im.get('alt') for im in sec.find_all('img') if im.get('alt')]
        item['prerequisites']=fields.get('Предварительные условия','')
        if 'deviant-feat-' in aid:
            family=re.search(r'deviant-feat-(dragon|troll|wraith)-',aid)
            if family:
                for target in ['deviant-abilities-classifications-backlash',
                               'deviant-abilities-classifications-deviation-saves-and-attack-rolls',
                               'deviant-abilities-'+family[1]+'-backlash']:
                    item['grants'].append({'id':url+'#'+target,'evidence':'Общие правила и отдача классификации девиантного умения.'})
        item['repeatable']=bool(re.search(r'несколько раз|много раз|более одного раза',fields.get('Особенность','')+' '+fields.get('Особое','')+' '+owntext[-1000:],re.I))
        item['has_choices']=bool(re.search(r'выберите|выбираете|на ваш выбор|на выбор',owntext,re.I))
        doctrine=kind=='subclass' and url.endswith('/cleric.html')
        if doctrine:
            item['effects']=[]; current_level=1
            for paragraph in ownsec.find_all('p'):
                content=txt(paragraph); match=re.search(r'учение\s*\((\d+)-й ур\.\)',content,re.I)
                if match: current_level=int(match[1]); content=content[match.end():]
                for ef in rank_effects(content): item['effects'].append({**ef,'level':current_level})
            if english=='Warpriest':
                for key in ['light','medium']: item['effects'].append({'op':'rank','target':key,'value':2,'level':13,'evidence':'На 13-м уровне, если вы получаете Божественную защиту, становитесь экспертом с легкими и средними доспехами.'})
            for key in ['simple','unarmed']:
                item['effects'].append({'op':'rank','target':key,'value':2,'level':7 if english=='Warpriest' else 11,'evidence':owntext})
        if english=='Versatile Legend' and url.endswith('/fighter.html'):
            item['effects']=[{'op':'rank','target':k,'value':v,'evidence':owntext} for k,v in [('simple',4),('martial',4),('unarmed',4),('advanced',3),('class_dc',3)]]
        if kind in ['class','ancestry']:
            item['profile']=profile(sec,kind)
            if kind=='class': item['progression'],item['spell_table']=progression(sec,url)
        if kind=='subclass':
            ph=parent.find(re.compile(r'^h[1-6]$'),recursive=False)
            m=re.search(r'/\s*(\d+)',txt(ph)); item['choice_level']=int(m[1]) if m else 1
            for label in ['Навыки наследия','Обученный навык','Навык']:
                skillfield=fields.get(label,'')
                if skillfield and ' или ' not in skillfield:
                    item['effects'].extend({'op':'rank','target':key,'value':1,'evidence':label+': '+skillfield} for key in names_in(skillfield,SKILL_STEMS))
            for line in ownsec.select('.line'):
                if re.match(r'Начальное\s*:',txt(line)):
                    for a in line.find_all('a',href=True): item['grants'].append({'id':urljoin(url,a['href']),'evidence':txt(line)})
            item['level_grants']=[]
            grant_heading=next((p for p in ownsec.find_all('p') if txt(p).startswith('Дарованные заклинания')),None)
            block=grant_heading.find_next_sibling('div') if grant_heading else None
            for line in block.select('.line') if block else []:
                m=re.match(r'(\d+)-й',txt(line)); required=max(1,2*int(m[1])-1) if m else 1
                for a in line.find_all('a',href=True): item['level_grants'].append({'id':urljoin(url,a['href']),'level':required,'evidence':txt(line)})
        if kind=='background':
            before=re.split(r'Вы обучены|Вы получаете',owntext)[0]
            item['boost_options']=names_in(before,ATTR_STEMS)
        if kind in ['spell','focus_spell']:
            item['cantrip']='чары' in [t.lower() for t in traits] or '/ Чары ' in title
            item['traditions']=[k for k,v in [('arcane','аркан'),('divine','сакраль'),('occult','оккульт'),('primal','природ')] if v in fields.get('Обычай','').lower()]
            item['heightening']=[txt(p) for p in sec.find_all('p') if re.match('Усилен',txt(p))]
        for p in ownsec.find_all('p'):
            for link in p.find_all('a',href=True):
                target=urljoin(url,link['href']); lt=txt(link)
                sentence=next((s for s in re.split(r'[.!?\n]',txt(p).replace(lt,'__TARGET__')) if '__TARGET__' in s),'')
                if re.search(r'(?:вы |вам |также |еще )?(?:получаете|изучаете|дается)',sentence,re.I) and not re.search(r'если|можете|выбер|на выбор',sentence,re.I):
                    grant={'id':target,'evidence':sentence.replace('__TARGET__',lt).strip()}
                    if doctrine:
                        m=re.search(r'учение\s*\((\d+)-й ур\.\)',txt(p),re.I)
                        grant['level']=int(m[1]) if m else 1
                    item['grants'].append(grant)
        if re.search(r'начинаете с 1 очком|запас.{0,20}из 1 Очка',owntext,re.I): item['effects'].append({'op':'focus_base','value':1,'evidence':owntext})
        if re.search(r'увеличиваете (?:свой )?запас очков фокусировки на 1',owntext,re.I): item['effects'].append({'op':'focus_add','value':1,'evidence':owntext})
        if kind in ['feature','subclass','heritage','class_feat','ancestry_feat','general_feat','skill_feat','archetype_feat'] and re.search(r'бонус|штраф|сопротивлен|компаньон|фамильяр|увеличива|дополнительн',owntext,re.I):
            item['uncertainties'].append('Числовые и условные эффекты, не показанные в расчетах или дополнительных выборах, применяются вручную по полному описанию.')
        items.append(item)
    if '/equipment/' in url: items.extend(equipment_rows(body,url))
    variants=[]
    for it in items:
        runetype={'Armor Potency':'armor_potency','Weapon Potency':'weapon_potency','Striking':'striking','Resilient':'resilient'}.get(it['english'])
        if it['kind']!='item' or not runetype or '/runes.html#' not in it['id']: continue
        blocks=re.split(r'\nВид\s*:',it['text'])[1:]
        for i,block in enumerate(blocks):
            lv=re.search(r'Уровень\s*:\s*(\d+)',block)
            if not lv: continue
            if runetype in ['weapon_potency','armor_potency']: val=re.search(r'\+(\d+)',block)
            elif runetype=='striking': val=re.search(r'(\d+) кости',block)
            else: val=re.search(r'предмета \+(\d+)',block)
            value=int(val[1]) if val else 2 if runetype=='striking' and i==0 else 1 if i==0 else None
            if value is None: continue
            variant=copy.deepcopy(it);variant.update(id=it['id']+f':variant:{i}',aliases=[],name=block.split('\n')[0].split(' (')[0].strip(),level=int(lv[1]),item_type='rune',values={'rune_type':runetype,'rune_value':value},effects=[])
            variants.append(variant)
        it['kind']='rule'
    items.extend(variants)
    overrides=json.loads((Path(__file__).parent/'parser_overrides.json').read_text(encoding='utf-8'))
    for it in items:
        if it['id'] in overrides: it.update(overrides[it['id']])
    return items

def equipment_rows(body,url):
    out=[]
    for ti,table in enumerate(body.find_all('table')):
        heads=[txt(h) for h in table.select('thead tr:last-child th')]; hs=' '.join(heads).lower(); caption=txt(table.find('caption'))
        typ='armor' if 'бонус кб' in hs or 'кб' in hs and 'ловк' in hs else 'weapon' if 'урон' in hs and ('рук' in hs or 'групп' in hs) else 'shield' if 'твердость' in hs and 'кб' in hs else None
        if not typ: continue
        category='unarmored' if typ=='armor' else 'simple'
        cats={'легк':'light','средн':'medium','тяжел':'heavy'} if typ=='armor' else {'прост':'simple','воинск':'martial','продвинут':'advanced','безоруж':'unarmed'}
        for stem,cat in cats.items():
            if stem in (caption+' '+(heads[0] if heads else '')).lower(): category=cat
        for ri,row in enumerate(table.select('tbody > tr')):
            cells=row.find_all(['th','td'],recursive=False)
            if len(cells)!=len(heads) or not cells: continue
            name=txt(cells[0]); values={'category':category,'ranged': 'дальнего боя' in caption.lower() or 'дистанция' in hs}
            for h,c in zip(heads,cells):
                s=h.lower(); v=txt(c); num=re.search(r'-?\d+',v)
                field=next((k for k,terms in {'ac':['бонус кб'],'dex_cap':['ловк'],'strength':['сила'],'check_penalty':['штраф провер'],'speed_penalty':['штраф скор'],'damage':['урон'],'traits':['признак'],'hands':['рук'],'group':['групп']}.items() if any(t in s for t in terms)),None)
                if field: values[field]=v if field in ['damage','traits','hands','group'] else int(num[0]) if num else 99 if field=='dex_cap' else 0
            html='<h3>'+bleach.clean(name,tags=[],strip=True)+'</h3><dl>'+''.join('<dt>'+bleach.clean(h,tags=[],strip=True)+'</dt><dd>'+str(c)+'</dd>' for h,c in zip(heads,cells))+'</dl>'
            safe,plain=clean(BeautifulSoup(html,'lxml'),url)
            out.append({'id':url+f'#table-{ti}-row-{ri}','aliases':[],'kind':'item','item_type':typ,'name':name,'english':'','title':name,'level':0,'owner':url,'html':safe,'text':plain,'own_text':plain,'source':url+'#'+table.get('id',''),'traits':values.get('traits','').split(', '),'fields':dict(zip(heads,map(txt,cells))),'field_links':{},'links':[],'effects':[],'grants':[],'values':values,'uncertainties':[]})
    return out
