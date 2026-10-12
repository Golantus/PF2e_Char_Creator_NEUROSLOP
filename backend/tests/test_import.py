from app.parser import parse_page
from app.constants import BASE
from app.importer import allowed

def test_source_boundary():
    assert allowed(BASE+'classes/druid.html')
    assert not allowed('https://evil.invalid/ru/latest/classes/druid.html')
    assert not allowed(BASE+'classes/druid.html?x=1')

def test_real_tables_profiles_and_subclasses(rules):
    for name in ['druid','fighter','sorcerer']:
        r=rules.get(BASE+'classes/'+name+'.html');assert len(r['progression'])==20
    assert rules.get(BASE+'ancestries_and_backgrounds/ancestries/human.html')['profile']['free_boosts']==2
    assert len([x for x in rules.kind('subclass') if x['owner']==BASE+'classes/druid.html'])==7
    assert len([x for x in rules.kind('subclass') if x['owner']==BASE+'classes/sorcerer.html'])==15
    assert len(rules.kind('background'))>200
    assert all('/' in r['title'] for r in rules.kind('class_feat'))

def test_full_nested_description_and_sanitization():
    html='''<html><main role="main"><section id="root"><h1>Книга</h1><section id="feat-one"><h2>Первая (First) / 2</h2><p><strong>Предварительные условия:</strong> Сила 14</p><p>Абзац один.</p><section id="inside"><h3>Вариант</h3><p>Второй абзац.</p><table><tr><th>Число</th></tr><tr><td>7</td></tr></table></section><script>alert(1)</script><a href="javascript:alert(1)" onclick="bad()">опасно</a></section><section id="feat-two"><h2>Соседняя / 3</h2><p>ЧУЖОЙ ТЕКСТ</p></section></section></main></html>'''
    r=next(x for x in parse_page(BASE+'feats.html',html) if x['id'].endswith('#feat-one'))
    assert r['level']==2 and r['prerequisites']=='Сила 14'
    assert all(t in r['text'] for t in ['Абзац один.','Второй абзац.','Число','7'])
    assert 'ЧУЖОЙ ТЕКСТ' not in r['text']
    assert 'javascript:' not in r['html'] and 'onclick' not in r['html'] and '<script' not in r['html']

def test_equipment_categories(rules):
    armor=[x for x in rules.kind('item') if x.get('item_type')=='armor']
    assert armor and {'light','medium','heavy'}<=set(x['values']['category'] for x in armor)
