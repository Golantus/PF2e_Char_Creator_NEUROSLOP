"""Character-facing descriptions, scoped without changing the source catalogue.

Keep complete rules for acquired abilities. Only structural containers, unchosen
entries and separately labelled future unlocks are removed. Inline conditions,
action costs, limitations and scaling remain part of an ability's full rule.
"""
import re
from collections import defaultdict

from bs4 import BeautifulSoup, Tag

from .parser import clean, norm, txt

HEADINGS = re.compile(r'^h[1-6]$')
META_FEATURES = {'Родословная и предыстория', 'Начальные умения',
                 'Повышения атрибутов', 'Повышения характеристик'}
SEPARATE_KINDS = {'subclass', 'class_feat', 'ancestry_feat', 'general_feat',
                  'skill_feat', 'archetype_feat', 'spell', 'focus_spell'}
INSTINCT_TABLES = ('#class-feature-barbarian-instinct-dragon',
                   '#class-feature-barbarian-instinct-animal')


class CharacterDescriptions:
    def __init__(self, character, result, rules):
        self.character = character
        self.level = character.level
        self.rules = rules
        self.acquired = {a['id'] for a in result['acquired'] if a['level'] <= self.level}
        self.outcomes = result['outcomes']
        self.headings = defaultdict(dict)
        for r in rules.items.values():
            self.headings[r['owner']][norm(r['title'])] = r

    def decisions(self, rule):
        return [c for c in self.character.choices
                if c.parent == rule['id'] and c.level <= self.level
                and self.outcomes.get(c.slot, {}).get('status') == 'valid'
                and c.note.strip()]

    def selected_rows(self, rule, table):
        notes = norm(' '.join(c.note for c in self.decisions(rule))).lower()
        rows = []
        for row in table.find_all('tr'):
            first = row.find('td', recursive=False)
            if first is None:
                continue
            names = [norm(part).lower() for part in re.split(r'[()]', txt(first)) if norm(part)]
            if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)', notes) for name in names):
                rows.append(row)
        return rows

    def unresolved_instinct(self, rule):
        if not rule['id'].endswith(INSTINCT_TABLES):
            return False
        tables = BeautifulSoup(rule.get('html', ''), 'html.parser').find_all('table')
        return not tables or any(len(self.selected_rows(rule, table)) != 1 for table in tables)

    def text(self, rule):
        kind = rule['kind']
        if kind == 'class' or (kind == 'feature' and rule['name'] in META_FEATURES):
            return ''
        # Most feats and spells are leaf entries: preserve their exact full text.
        scoped = kind in {'ancestry', 'heritage', 'feature', 'subclass', 'archetype'}
        deviant = '#deviant-feat-' in rule['id']
        if not scoped and not deviant:
            return rule['text']
        soup = BeautifulSoup(rule.get('html', ''), 'html.parser')
        root = soup.find('section')
        if root is None:
            return rule['text']
        if kind == 'ancestry':
            # The ancestry stat block includes senses, attacks and special rules.
            # The surrounding article is history, names and roleplaying advice.
            statblock = root.find('aside')
            if statblock is not None:
                return clean(statblock, rule['source'])[1]
        if kind == 'heritage':
            entry = next((s for s in root.find_all('section')
                          if 'наследие' in txt(s.find(HEADINGS, recursive=False)).lower()
                          and 'способности' not in txt(s.find(HEADINGS, recursive=False)).lower()), None)
            if entry is not None:
                root = entry

        for section in list(root.find_all('section')):
            if section.parent is None:
                continue
            heading = txt(section.find(HEADINGS, recursive=False))
            unlock = re.search(r'/\s*(\d+)\s*-?\s*(?:й|ый)\b', heading)
            nested = self.headings[rule['owner']].get(norm(heading))
            if unlock and int(unlock[1]) > self.level:
                section.decompose()
            elif nested and nested['id'] != rule['id'] and nested['kind'] in SEPARATE_KINDS:
                # Chosen entries have their own complete description; all other
                # variants are a catalogue, not acquired character abilities.
                section.decompose()

        # Cleric doctrines and similar progressions use labelled paragraphs,
        # rather than separate Sphinx sections, for individual unlocks.
        for container in [root, *root.find_all('section')]:
            future = False
            for node in list(container.children):
                if not isinstance(node, Tag):
                    continue
                label = node.find('strong', recursive=False) if node.name == 'p' else None
                match = re.search(r'\((\d+)-й ур\.\)', txt(label)) if label else None
                if match:
                    future = int(match[1]) > self.level
                elif node.name in {'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                    future = False
                if future:
                    node.decompose()

        # Bloodline lists show all spell ranks and optional advanced focus spells.
        # Only entries actually granted or selected belong on the character sheet.
        for paragraph in list(root.find_all('p')):
            if paragraph.parent is None:
                continue
            label = txt(paragraph.find('strong', recursive=False)).rstrip(':')
            if label not in {'Дарованные заклинания', 'Заклинания наследия'}:
                continue
            listing = paragraph.find_next_sibling()
            if listing is None or listing.name != 'div':
                continue
            for line in list(listing.find_all('div', recursive=False)):
                linked = [self.rules.get(a.get('href')) for a in line.find_all('a')]
                if not any(r and r['id'] in self.acquired for r in linked):
                    line.decompose()
            if not txt(listing):
                listing.decompose()
                paragraph.decompose()

        # These are permanent choices, not tables used while taking the action.
        # Their selected values are exported from linked decisions below.
        if rule['id'].endswith(INSTINCT_TABLES):
            for table in list(root.find_all('table')):
                selected = self.selected_rows(rule, table)
                if len(selected) != 1:
                    table.decompose()
                else:
                    for row in list(table.find_all('tr')):
                        if row.find('td') is not None and row is not selected[0]:
                            row.decompose()
            for paragraph in list(root.find_all('p', recursive=False)):
                if re.search(r'выберите.*таблиц', txt(paragraph), re.I):
                    paragraph.decompose()

        if deviant:
            # Awakenings are separate choices, not an automatic part of a feat.
            # Until one is recorded, never silently grant either alternative.
            awakenings = [p for p in root.find_all('p')
                          if txt(p.find('strong', recursive=False)).rstrip(':') == 'Пробуждение']
            for paragraph in awakenings:
                paragraph.decompose()

        return clean(root, rule['source'])[1]
