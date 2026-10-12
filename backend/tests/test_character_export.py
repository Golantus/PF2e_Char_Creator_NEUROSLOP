import copy
import hashlib

import pytest

from app import db
from app.constants import BASE
from app.exporter import export_character
from app.export_text import CharacterDescriptions
from app.models import Character, Choice, ManualEffect, SpellPick
from app.progression import build

BARBARIAN = BASE + 'classes/barbarian.html'
DRAGON = BARBARIAN + '#class-feature-barbarian-instinct-dragon'
BONE = BASE + 'books/Dark-Archive/Deviant-Abilities.html#deviant-feat-troll-bone-spikes'


@pytest.fixture
def barbarian(rules):
    c = Character(level=3, class_id=BARBARIAN,
                  ancestry_id=BASE+'ancestries_and_backgrounds/ancestries/gnoll.html',
                  heritage_id=BASE+'ancestries_and_backgrounds/versatile_heritages/duskwalker.html#heritage-duskwalker',
                  background_id=BASE+'ancestries_and_backgrounds/backgrounds.html#bg-total-power')
    values = [
        ('L1:ancestry_boost', 1, 'boost', ['dex']),
        ('L1:background_boost', 1, 'boost', ['wis', 'str']),
        ('L1:class_boost', 1, 'boost', ['str']),
        ('L1:free_boost', 1, 'boost', ['str', 'con', 'wis', 'cha']),
        ('L1:subclass:'+BARBARIAN+'#class-feature-barbarian-instincts', 1, 'subclass', DRAGON),
        ('L1:trained', 1, 'trained', ['stealth', 'religion', 'nature', 'lore:гноллов']),
        ('L1:ancestry_feat:0', 1, 'ancestry_feat', BASE+'ancestries_and_backgrounds/ancestries/gnoll.html#ancestry-feat-gnoll-lore'),
        ('L1:class_feat:0', 1, 'class_feat', BARBARIAN+'#class-feat-barbarian-acute-vision'),
        ('L2:class_feat:0', 2, 'class_feat', BARBARIAN+'#class-feat-barbarian-adrenaline-rush'),
        ('L2:skill_feat:0', 2, 'skill_feat', BASE+'feats.html#feat-titan-wrestler'),
        ('L3:general_feat:0', 3, 'general_feat', BASE+'feats.html#feat-quick-squeeze'),
        ('L3:skill_increase:0', 3, 'skill_increase', ['athletics']),
    ]
    c.choices = [Choice(slot=s, level=l, kind=k, value=v, confirmed=True) for s,l,k,v in values]
    # Resolve duplicate skill training exactly as in the supplied TXT example.
    result = build(c, rules)
    for slot in result['outcomes'].values():
        if ':replacement:' in slot['id']:
            value = 'acrobatics' if 'lore:' in slot['id'] else 'performance'
            c.choices.append(Choice(slot=slot['id'], level=1, kind='trained', value=[value]))
    return c


@pytest.mark.parametrize('mode', ['full', 'abilities'])
@pytest.mark.parametrize('markdown', [False, True])
def test_supplied_barbarian_export(rules, barbarian, mode, markdown):
    result = build(barbarian, rules)
    text = export_character(barbarian, result, rules, mode=mode, markdown=markdown)
    for ref in ['#class-feature-barbarian-rage', '#class-feat-barbarian-acute-vision',
                '#class-feat-barbarian-adrenaline-rush', '#class-feature-barbarian-deny-advantage']:
        assert rules.get(BARBARIAN+ref)['text'] in text
    for ref in ['#feat-titan-wrestler', '#feat-quick-squeeze', '#feat-intimidating-glare']:
        assert rules.get(BASE+'feats.html'+ref)['text'] in text
    assert 'Ваше тело и дух никогда не могут стать нежитью.' in text
    assert 'У вас есть безоружная атака челюстями, которая наносит 1d6 колющего урона.' in text
    assert 'Позволить лично оскорбить вас' in text
    assert 'с 2 до 4' in text
    assert '1d6 колющего урона и обладающие признаками' in text  # Bone Spikes
    assert 'Каждый раз, когда вы пытаетесь использовать девиацию' in text
    assert 'Отдача: Напряженный метаболизм' in text
    assert 'Костяные шипы • получено на 1-м уровне' in text
    for absent in ['Умение специализации (Specialization Ability) / 7-й',
                   'Яростное сопротивление (Raging Resistance) / 9-й',
                   'Мощный джаггернаут', 'Черный (Black)', 'Серебряный (Silver)',
                   'Физическое описание', 'Пример имен', 'Чаепитие со смертью',
                   'Начальные умения • получено', 'Родословная и предыстория • получено',
                   'Развитие персонажа', 'Пробуждение : Ваши кости']:
        assert absent not in text
    assert 'Не завершено: укажите вид дракона' in text


@pytest.mark.parametrize('level, specialization, resistance', [(3,False,False),(7,True,False),(9,True,True)])
def test_instinct_unlock_boundaries(rules, barbarian, level, specialization, resistance):
    barbarian.level = level
    result = build(barbarian, rules)
    text = CharacterDescriptions(barbarian,result,rules).text(rules.get(DRAGON))
    assert ('Умение специализации (Specialization Ability) / 7-й' in text) == specialization
    assert ('Яростное сопротивление (Raging Resistance) / 9-й' in text) == resistance
    assert 'Драконья ярость' in text and 'Анафема' in text


def test_only_current_valid_choices_are_exported(rules, barbarian):
    barbarian.choices.extend([
        Choice(slot='L1:dragon-note', level=1, kind='linked', value='', parent=DRAGON,
               confirmed=True, note='Красный дракон, уважение.'),
        Choice(slot='L10:old-note', level=10, kind='linked', value='', parent=DRAGON,
               confirmed=True, note='СКРЫТОЕ БУДУЩЕЕ РЕШЕНИЕ'),
        Choice(slot='L1:unconfirmed', level=1, kind='linked', value='', parent=DRAGON,
               note='НЕПОДТВЕРЖДЕННОЕ РЕШЕНИЕ'),
        Choice(slot='L4:class_feat:0', level=4, kind='class_feat',
               value=BARBARIAN+'#class-feat-barbarian-fast-movement'),
    ])
    barbarian.effects = [ManualEffect(target='ac',value=1,active=True,label='Действующий эффект'),
                        ManualEffect(target='ac',value=1,active=False,label='ОТКЛЮЧЕННЫЙ ЭФФЕКТ'),
                        ManualEffect(target='ac',value=1,active=True,level=10,label='БУДУЩИЙ ЭФФЕКТ')]
    result = build(barbarian,rules)
    text = export_character(barbarian,result,rules)
    assert 'Принятое решение: Красный дракон, уважение.' in text
    assert 'Красный (Red) | цветной | Конус огня' in text
    assert 'Черный (Black)' not in text
    assert 'Действующий эффект' in text
    for absent in ['СКРЫТОЕ БУДУЩЕЕ РЕШЕНИЕ','НЕПОДТВЕРЖДЕННОЕ РЕШЕНИЕ',
                   'ОТКЛЮЧЕННЫЙ ЭФФЕКТ','БУДУЩИЙ ЭФФЕКТ', 'Не завершено: укажите вид дракона']:
        assert absent not in text
    assert 'Сохраненные неактивные решения' in export_character(barbarian,result,rules,mode='levels')


def test_animal_instinct_keeps_full_selected_attack_row(rules,barbarian):
    animal=BARBARIAN+'#class-feature-barbarian-instinct-animal'
    for choice in barbarian.choices:
        if choice.value==DRAGON: choice.value=animal
    barbarian.choices.append(Choice(slot='L1:animal',level=1,kind='linked',value='',
                                    parent=animal,confirmed=True,note='Медведь'))
    text=export_character(barbarian,build(barbarian,rules),rules)
    assert 'Медведь (Bear) | Челюсти Лапа | 1d10 К 1d6 Р' in text
    assert 'Обезьяна (Ape)' not in text and 'Лягушка (Frog)' not in text
    assert 'укажите выбранное животное' not in text


def test_lowering_level_removes_granted_features_and_future_spells(rules, barbarian):
    barbarian.level = 1
    barbarian.spells.append(SpellPick(rule_id=BASE+'spells/F/fireball.html#spell-f-fireball',level=5,cast_rank=3))
    result=build(barbarian,rules)
    text=export_character(barbarian,result,rules)
    assert 'Лишить преимущества' not in text
    assert 'Выброс адреналина' not in text
    assert 'Огненный шар' not in text
    assert 'Костяные шипы' in text  # A background can grant a higher-listed feat early.


def test_doctrine_scope_and_other_order_variants(rules,druid):
    result=build(druid,rules)
    text=export_character(druid,result,rules)
    assert 'Животных • получено' in text
    assert 'Исцеление животного' in text
    assert 'Бури ( Storm )' not in text
    assert 'Дикой природы ( Wild )' not in text
    c=Character(level=3,class_id=BASE+'classes/cleric.html')
    result=build(c,rules)
    rule=rules.get(BASE+'classes/cleric.html#class-feature-cleric-doctrine-warpriest')
    text=CharacterDescriptions(c,result,rules).text(rule)
    assert 'Первое учение' in text and 'Второе учение' in text
    assert 'Третье учение' not in text and 'Последнее учение' not in text


def test_bloodline_does_not_list_unearned_spells(rules):
    owner=BASE+'classes/sorcerer.html'
    c=Character(level=1,class_id=owner,choices=[Choice(slot='L1:subclass:'+owner+'#class-feature-sorcerer-bloodlines',
                level=1,kind='subclass',value=owner+'#class-feature-sorcerer-bloodline-draconic')])
    result=build(c,rules)
    rule=rules.get(owner+'#class-feature-sorcerer-bloodline-draconic')
    # Scope the actual selected bloodline independently of class slot spelling.
    result['acquired'].append({'id':BASE+'spells/focus/Sorcerer.html#spell-focus-dragon-claws','level':1})
    text=CharacterDescriptions(c,result,rules).text(rule)
    assert 'Драконьи когти' in text
    assert 'Драконье дыхание' not in text and 'Драконьи крылья' not in text
    assert 'Форма дракона' not in text


def test_export_endpoint_uses_scoped_text(rules,barbarian,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main,'rules',lambda version=None:rules)
    # No lifespan is needed: this is a read-only export from the supplied object.
    client=TestClient(main.app)
    response=client.post('/api/export',json={'character':barbarian.model_dump(),'links':False})
    assert response.status_code==200
    text=response.json()['text']
    assert 'Костяные шипы • получено на 1-м уровне' in text
    assert 'Умение специализации (Specialization Ability) / 7-й' not in text
    assert '\n\nИсточник: https://' not in text


def test_scoping_never_mutates_catalogue(rules,barbarian):
    original=copy.deepcopy(rules.items)
    result=build(barbarian,rules)
    export_character(barbarian,result,rules)
    assert rules.items==original
    assert 'Яростное сопротивление (Raging Resistance) / 9-й' in rules.get(DRAGON)['text']


def test_supplement_supports_existing_database_without_replacing_data(tmp_path,monkeypatch):
    monkeypatch.setenv('PF2E_DATA_DIR',str(tmp_path))
    db.migrate()
    with db.connect() as con:
        con.execute("INSERT INTO rule_versions(id,status) VALUES(1,'ready')")
        con.execute("INSERT INTO settings VALUES('active_version','1')")
    before=hashlib.sha256(db.path().read_bytes()).hexdigest()
    assert db.Rules().get(BONE)['name']=='Костяные шипы'
    assert hashlib.sha256(db.path().read_bytes()).hexdigest()==before
