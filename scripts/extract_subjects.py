#!/usr/bin/env python3
"""Generate the i18n subject files (i18n/la.json, it.json, en.json).

The *subject* of a eulogy is the saint, blessed or celebration the eulogy is
directed to, in nominative display form ("Sancta Maria Dei Genetrix",
"Sanctus Basilius"). Subject and slug are tightly coupled and do not change
between editions, so this association lives here in the registry, outside any
edition's texts.

Generation rules (all draft, committee review expected):
- **la** (complete): the honorific comes from the sanctity marker of the 2004
  Latin text (sancti -> Sanctus, sanctae -> Sancta, plural markers and joined
  pairs -> Sancti/Sanctae, beat- forms -> Beatus/Beata/Beati), suppressed for
  feast-type slugs (nativitas-, dedicatio-, octava-...) and pluralized for
  anonymous-group slugs (martyres, milites, virgines...); the name is the
  slug rendered in display form (connectors lowercase, papal ordinals as
  Roman numerals). Deprecated IDs carry the subject extracted from the
  historical edition they are attested in (subject_la in
  data/deprecated_ids.json).
- **it / en** (partial): extracted from the corresponding 2004-edition texts
  by honorific-marker patterns (san/santa/santi/beato..., Saint/Blessed...),
  kept only when the extracted name fuzzily corresponds to the slug or the
  marker opens the text. Feast-type subjects and entries whose extraction
  failed are omitted, to be completed by translators.

Requires the PRIVATE CatholicOS/martyrology-texts repository for the 2004
texts.

Usage:
  python3 extract_subjects.py /path/to/martyrology-texts [repo_root]
"""

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROMAN = {'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii', 'xiii', 'xxiii'}
FEASTS = {'nativitas', 'epiphania', 'annuntiatio', 'praesentatio', 'visitatio', 'assumptio',
          'exaltatio', 'dedicatio', 'conversio', 'cathedra', 'transfiguratio', 'conceptio',
          'nomen', 'omnes', 'omnium', 'angeli', 'avi', 'bonus', 'duo', 'translatio',
          'commemoratio', 'circumcisio', 'octava', 'vigilia', 'purificatio', 'inventio',
          'apparitio', 'festum'}
GROUPS_M = {'martyres', 'milites', 'monachi', 'fratres', 'presbyteri', 'diaconi', 'viri',
            'socii', 'confessores', 'pueri', 'sancti'}
GROUPS_F = {'virgines', 'mulieres', 'viduae', 'moniales'}
MARKER_LA = re.compile(r'\b([Ss]anct|[Bb]eat)[a-zA-ZÀ-ſ]*')
IT_M = re.compile(r"\b(santi|sante|santo|santa|san|sant'|sant’|beati|beate|beato|beata)\s+"
                  r"([A-ZÀ-Ý][\w'’\-]+(?:\s+(?:e|da|di|de'|del|della|dei)\s+"
                  r"[A-ZÀ-Ý][\w'’\-]+|\s+[A-ZÀ-Ý][\w'’\-]+){0,3})", re.I)
EN_M = re.compile(r"\b(Saints|Saint|St\.|Blesseds|Blessed)\s+([A-Z][\w'\-]+"
                  r"(?:\s+(?:of|the|de|and)\s+[A-Z][\w'\-]+|\s+[A-Z][\w'\-]+){0,3})")


def fold(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z ]', ' ', s.lower().replace('æ', 'e').replace('œ', 'e').replace('j', 'i'))


def display_from_slug(mrid):
    out = []
    for p in mrid.split('-', 1)[1].split('-'):
        if p in ROMAN:
            out.append(p.upper())
        elif p in ('et', 'de', 'a', 'socii'):
            out.append(p)
        else:
            out.append(p.capitalize())
    return ' '.join(out)


def la_subject(mrid, text):
    parts = mrid.split('-', 1)[1].split('-')
    toks = set(parts)
    name = display_from_slug(mrid)
    if parts[0] in FEASTS:
        return name
    base = 'Sanct'
    m = MARKER_LA.search(text or '')
    if m and fold(m.group(0)).strip().startswith('beat'):
        base = 'Beat'
    if toks & GROUPS_F and not (toks & GROUPS_M):
        return ('Beatae ' if base == 'Beat' else 'Sanctae ') + name
    if toks & GROUPS_M:
        return ('Beati ' if base == 'Beat' else 'Sancti ') + name
    pair = '-et-' in mrid and not mrid.endswith('et-socii')
    if pair:
        return ('Beati ' if base == 'Beat' else 'Sancti ') + name
    fem = parts[0].endswith('a') and parts[0] not in ROMAN
    if m:
        f = fold(m.group(0)).strip()
        if f in ('sancte', 'sanctae', 'sancta', 'beate', 'beatae', 'beata') or \
           (f.endswith(('orum', 'arum')) and fem):
            return ('Beata ' if base == 'Beat' else 'Sancta ') + name
    return ('Beatus ' if base == 'Beat' else 'Sanctus ') + name


def vern_subject(mrid, text, pat):
    if not text:
        return None
    m = pat.search(text)
    if not m:
        return None
    first_slug = mrid.split('-', 1)[1].split('-')[0]
    nf = fold(m.group(2)).split()
    if not nf:
        return None
    ok = any(w[:4] == first_slug[:4] or SequenceMatcher(None, w, first_slug).ratio() >= 0.5
             for w in nf) or m.start() < 60
    if not ok:
        return None
    hon = m.group(1)
    return f'{hon[0].upper()}{hon[1:]} {m.group(2)}'.strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    texts_repo = Path(sys.argv[1])
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    reg = json.load(open(repo_root / 'data' / 'martyrology_ids.json', encoding='utf-8'))
    current = [e for e in reg['entries'] if not e.get('deprecated')]
    tex = {}
    folders = {'la': 'martyrologium_romanum_2004', 'it': 'martyrologium_romanum_2004_it_IT',
               'en': 'martyrologium_romanum_2004_en_unofficial'}
    for loc, folder in folders.items():
        tex[loc] = {}
        for m in range(1, 13):
            tex[loc].update(json.load(open(texts_repo / 'data' / 'editions' / folder / f'{m:02d}.json',
                                           encoding='utf-8')))
    out = {'la': {}, 'it': {}, 'en': {}}
    for e in current:
        out['la'][e['id']] = la_subject(e['id'], tex['la'].get(e['id'], ''))
        s = vern_subject(e['id'], tex['it'].get(e['id'], ''), IT_M)
        if s:
            out['it'][e['id']] = s
        s = vern_subject(e['id'], tex['en'].get(e['id'], ''), EN_M)
        if s:
            out['en'][e['id']] = s
    for e in reg['entries']:
        if e.get('deprecated') and e.get('subject_la'):
            out['la'][e['id']] = e['subject_la']
    # Every locale file carries the same complete key set; untranslated
    # subjects are empty strings awaiting completion.
    all_ids = sorted(e['id'] for e in reg['entries'])
    i18n = repo_root / 'i18n'
    i18n.mkdir(exist_ok=True)
    for loc in ('la', 'it', 'en'):
        full = {i: out[loc].get(i, '') for i in all_ids}
        with open(i18n / f'{loc}.json', 'w', encoding='utf-8') as f:
            json.dump(full, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(loc, 'keys:', len(full), 'filled:', sum(1 for v in full.values() if v))


if __name__ == '__main__':
    main()
