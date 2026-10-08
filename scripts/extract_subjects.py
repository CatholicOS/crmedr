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

A full rerun overwrites curated values (the deprecated IDs' subjects, and hand
corrections such as #20, #25, #31): diff the output and keep the curated ones.

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

# Printed only in the CEI edition, so there is no Latin 2004 text to take the
# honorific from; subjects as generated from the former Latin texts.
LA_SUBJECT_OVERRIDES = {
    "mr:0712-proclus-et-hilarion": "Sancti Proclus et Hilarion",
    "mr:0825-eusebius-et-socii": "Sancti Eusebius et socii",
    "mr:0709-maria-a-iesu-crucifixo": "Beata Maria a Iesu Crucifixo Petkovic",
}

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
# "sant’" is elided onto the name with no space ("sant’Eutizio").
# Only the honorific is case-insensitive: the name must start with a capital
# ("una santa vita" is not a subject).
# A name runs on through the particles of a surname or religious name ("de la
# Salle", "Jarrige de la Morélie du Breuil", "dell’Immacolata", "d’Andalò").
IT_PARTICLE = r"(?:e|ed|da|di|de'|del|della|dei|de\s+la|de\s+las|de\s+los|de|du|des|van\s+der|van|von|y)"
IT_WORD = r"(?:d['’]|dell['’])?[A-ZÀ-ÖØ-ÞĐŁŚŠŽŻČĆ][\w'’\-]+"
# A descriptor between honorific and name ("beati martiri Pietro Delépine") is
# not part of the subject.
IT_DESCRIPTOR = r"(?:(?:martiri|fratelli|vescovi|monaci|vergini|sacerdoti|coniugi|sposi)\s+)*"
IT_M = re.compile(r"\b((?i:sant['’]|santi|sante|santo|santa|san|beati|beate|beato|beata))(?:(?<=['’])|\s+)"
                  rf"{IT_DESCRIPTOR}({IT_WORD}(?:(?:\s+{IT_PARTICLE})+\s+{IT_WORD}|\s+{IT_WORD}){{0,6}})")
# The English text writes the subject's honorific in lowercase ("At Lviv,
# blessed Sigismund ..."), and a saint named in a place, church or order with a
# capital ("at Saint Paul's"): both are matched; the choice is made below.
EN_M = re.compile(r"\b(Saints|Saint|St\.|Blesseds|Blessed|saints|saint|blessed)\s+"
                  r"([A-ZÀ-Ý][\w'’\-]+(?:\s+(?:of|the|de|and)\s+[A-ZÀ-Ý][\w'’\-]+|\s+[A-ZÀ-Ý][\w'’\-]+){0,3})")
LA_MENTION = re.compile(r"\b([Ss]anct|[Bb]eat)[a-zæœ]*\s+(?=[A-Z])")
# A saint named to date the eulogy ("tempore sancti Gregorii papae") or to place
# it ("apud sanctum Petrum") is not its subject, although his honorific is
# lowercase too.
NOT_SUBJECT_LA = {"tempore", "temporibus", "aetate", "ætate", "sub", "apud", "ad", "iuxta", "prope"}
# The same time phrases in the translations ("al tempo di san Gregorio",
# "in the time of Saint Gregory"): such a mention never matches the slug loosely.
TEMPORAL_VERN = re.compile(r"\b(?:tempo|tempi|sotto|regno|time|times|reign|under)\b(?:\s+\w+){0,2}\s*$", re.I)


# Precomposed Latin letters whose diacritic is a stroke/bar rather than a
# combining mark: NFKD does NOT decompose them, so they survive the combining
# strip below and would otherwise be dropped to a blank by the [^a-z ] filter.
# Mapped to their standard ASCII transliteration before folding (ł -> l, etc.).
STROKE_LETTERS = str.maketrans({
    'ł': 'l', 'ø': 'o', 'đ': 'd', 'ð': 'd', 'ħ': 'h', 'ŧ': 't', 'þ': 'th', 'ß': 'ss',
})


def fold(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().translate(STROKE_LETTERS).replace('æ', 'e').replace('œ', 'e').replace('j', 'i')
    return re.sub(r'[^a-z ]', ' ', s)


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


def latin_subject_index(la_text):
    """Index of the subject among the saints the Latin names: the first one with a
    lowercase honorific (saints inside place names are capitalized), or a
    drop-cap heading at the start."""
    from extract_places import base_copy
    text = base_copy(la_text or '')
    mentions = list(LA_MENTION.finditer(text))
    for i, m in enumerate(mentions):
        if i == 0 and m.start() == 0:
            return i
        before = re.findall(r"[A-Za-zæœ]+", text[:m.start()])
        if m.group(1)[0].islower() and not (before and before[-1].lower() in NOT_SUBJECT_LA):
            return i
    return None


def vern_subject(mrid, text, pat, la_text=None):
    """The subject of a vernacular text: the honorific mention whose name matches
    the slug; failing that, the mention in the Latin subject's position (the
    translations name the saints in the same order); failing that, a drop-cap
    heading. A saint named only in a place, church or order is never taken: in
    Italian such honorifics are capitalized mid-text and are skipped."""
    if not text:
        return None
    if pat is IT_M:
        # A religious name's baptismal name in brackets: "Edmigio (Isidoro) Primo".
        text = re.sub(r"\s*\([^)]*\)", '', text)
    mentions = list(pat.finditer(text))
    if not mentions:
        return None
    first_slug = mrid.split('-', 1)[1].split('-')[0]

    def fmt(m):
        hon = m.group(1)
        sep = '' if hon.endswith(("'", '’')) else ' '
        return f'{hon[0].upper()}{hon[1:]}{sep}{m.group(2)}'.strip()

    def exact(m):
        return any(w[:4] == first_slug[:4] for w in fold(m.group(2)).split())

    def fuzzy(m):
        return any(SequenceMatcher(None, w, first_slug).ratio() >= 0.5 for w in fold(m.group(2)).split())

    italian = pat is IT_M
    i = latin_subject_index(la_text) if la_text else None
    # An exact match on the slug's first letters counts anywhere. A loose one is
    # needed too (the Italian spells Cipriano, Leone, Pellegrino for cyprianus,
    # leo, peregrinus), but never on a saint who only dates the eulogy.
    for m in mentions:
        if italian and m.start() > 0 and m.group(1)[0].isupper():
            continue
        if exact(m) or (fuzzy(m) and not TEMPORAL_VERN.search(text[:m.start()])):
            return fmt(m)
    if i is not None and i < len(mentions):
        m = mentions[i]
        if not (italian and m.start() > 0 and m.group(1)[0].isupper()):
            return fmt(m)
    if mentions[0].start() == 0:
        return fmt(mentions[0])
    return None


IT_PLURAL = {'san': 'Santi', 'santo': 'Santi', 'sant’': 'Santi', "sant'": 'Santi', 'santa': 'Sante',
             'beato': 'Beati', 'beata': 'Beate'}
IT_HONORIFIC = re.compile(r"^(Sant['’]|Santi|Sante|Santo|Santa|San|Beati|Beate|Beato|Beata)(?:(?<=['’])|\s+)")
STRESS = {'\u0300', '\u0301'}
# Names the Latin text prints undeclined with the same stress mark (places,
# Italian surnames, indeclinables), so the test in strip_stress keeps them.
IT_STRESS_MARKED = {'Aozaráza', 'Aríma', 'Cetína', 'Deusdédit', 'Himláya', 'Láconi', 'Mánaen', 'Maryáhb',
                    'Nicosía', 'Ricásoli', 'Rúain', 'Ruíz', 'Sérvoli', 'Victorí'}
# A descriptor before a named subject ("santi martiri Vittorino", "beati
# fratelli Giovanni e Renato Lego") is not part of the subject.
IT_LEAD_DESCRIPTOR = re.compile(r"^(?:(?:martiri|martire|fratelli|sorelle|vescovi|monaci|vergini|sacerdoti|coniugi|sposi)\s+)+(?=[A-ZÀ-ÖØ-ÞĐŁŚŠŽŻČĆ])")


def strip_stress(word, keep):
    """The CEI prints a stress mark on names it Italianizes (Argéo, Teógene,
    Sant’Ágabo), which is not their spelling. Removed from a non-final vowel,
    unless the word is a name left untranslated: one the Latin text prints too
    (García, Brébeuf, Nguyễn; the Latin declines the names it translates) or the
    English prints with the same accent. Final accents are Italian spelling
    (Gesù, Natività) and are kept."""
    out = []
    for part in re.split(r"([’'\-])", word):
        if not part or part in "’'-" or part not in IT_STRESS_MARKED and (
                fold(part).strip() in keep['la'] or part in keep['en']):
            out.append(part)
            continue
        d = unicodedata.normalize('NFD', part)
        last = max(i for i, c in enumerate(d) if not unicodedata.combining(c))
        out.append(unicodedata.normalize('NFC', ''.join(
            c for i, c in enumerate(d) if not (c in STRESS and i < last))))
    return ''.join(out)


def it_label(mrid, label, text='', en='', la_text=''):
    """Normalize an Italian subject: stress marks off (strip_stress); for an
    -et-socii eulogy the Latin form "Sancti N. et socii": plural honorific, the
    first-named subject only, no count ("e dodici compagni"), then "e compagni",
    or "e compagne" for women. A descriptor before a name is dropped from any
    label ("santi martiri Vittorino")."""
    if not label:
        return label
    # Without a Latin text (printed only in the CEI edition), the slug's words.
    keep = {'la': set(fold(la_text).split()) if la_text else set(mrid.split('-', 1)[1].split('-')),
            'en': set(re.findall(r"\w+", en or ''))}
    label = ' '.join(strip_stress(w, keep) for w in label.split(' '))
    m = IT_HONORIFIC.match(label)
    if not m:
        return label
    hon, name = m.group(1), label[m.end():]
    if not set(mrid.split('-', 1)[1].split('-')) & (GROUPS_M | GROUPS_F) - {'socii'}:  # "santi martiri Scillitani"
        name = IT_LEAD_DESCRIPTOR.sub('', name)
    if hon == 'Santo' and not re.match(r"S[^aeiou]|Z", name):    # santo martire Giovanni
        hon = 'Sant’' if re.match(r"[AEIOUÀ-Ü]", name) else 'San'
    if not mrid.endswith('-et-socii'):
        return f"{hon}{'' if hon.endswith(('’', "'")) else ' '}{name}"
    hon = IT_PLURAL.get(hon.lower(), hon)
    female = hon in ('Sante', 'Beate') or bool(re.search(r'\bcompagne\b', label)) or \
        bool(re.search(r'\bcompagne\b', text or '') and not re.search(r'\bcompagni\b', text or ''))
    name = re.split(r",|\s+ed?\s+(?!Maria\b)", name)[0]         # N. e compagni / e N2 (not "Gesù e Maria")
    return f"{hon} {name.strip()} e {'compagne' if female else 'compagni'}"


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
    # Imported here: extract_typology imports `fold` from this module.
    from extract_typology import latin_texts
    tex['la'] = latin_texts(reg['entries'], tex['la'])
    out = {'la': {}, 'it': {}, 'en': {}}
    for e in current:
        out['la'][e['id']] = LA_SUBJECT_OVERRIDES.get(e['id']) or la_subject(e['id'], tex['la'].get(e['id'], ''))
        la_text = tex['la'].get(e['id'], '')
        s = vern_subject(e['id'], tex['en'].get(e['id'], ''), EN_M, la_text)
        if s:
            out['en'][e['id']] = s
        s = vern_subject(e['id'], tex['it'].get(e['id'], ''), IT_M, la_text)
        if s:
            out['it'][e['id']] = it_label(e['id'], s, tex['it'].get(e['id'], ''),
                                         out['en'].get(e['id'], ''), la_text)
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
