#!/usr/bin/env python3
"""The English and Italian forms of the Latin first names, as the 2004 editions print them.

A eulogy's English and Italian subjects (i18n/en.json, i18n/it.json, from the 2004 English and
Italian editions) name its first person in the vernacular: "Saint John Speed" for Ioannes Speed.
When the words after the first name are the same on both sides, the first names are the same
name in two languages (Ioannes: John, Giovanni). harvest counts those pairs over every eulogy and
keeps, for each Latin first name, its forms with their counts, the commonest first. A form seen once that
is another Latin first name, or another Latin name's form (Angelus called Benedict in religion),
is left out, unless it begins like the Latin: a religious name, not a translation. A form spelled like the Latin itself adds
nothing and is left out too. The table holds single first names, no text.

build_person_items.py searches Wikidata under every form, and reads a form seen twice or more as
the same name (a form seen once may still be a religious name).

Usage:
  python3 scripts/name_forms.py [repo_root]

Writes data/name_forms.json. Standard library only.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from persons_text import name_key

EDITION = "martyrologium_romanum_2004"
LANGUAGES = ("en", "it")
# A subject's title, then its first person: up to a comma, "and"/"e", or the end.
SUBJECT = re.compile(r"^(?:Saints?|Blessed|Sant[’']|Santi|Sante|Santo|Santa|San|Beati|Beate|Beato|Beata)\s*"
                     r"(.+?)(?:,|\s+(?:and|e|ed)\s+|$)")


def first_name_pair(latin, subject):
    """(the Latin first name's key, its vernacular form) when the subject's first person is the
    Latin name, word for word after the first name; else None. One-word names give none."""
    m = SUBJECT.match(subject or "")
    if not m:
        return None
    la, vern = latin.split(), m.group(1).split()
    if len(la) < 2 or len(la) != len(vern) or any(name_key(a) != name_key(b) for a, b in zip(la[1:], vern[1:])):
        return None
    return name_key(la[0]), vern[0]


def _norm(s):
    """A name read loosely: folded, ae and oe as e, j as i, h silent (Martha, Marta)."""
    return name_key(s).replace("ae", "e").replace("oe", "e").replace("j", "i").replace("h", "")


def _begins_like(form, latin):
    """The form begins with the Latin name's first three letters (Benedict, Benedictus)."""
    return _norm(form)[:3] == _norm(latin)[:3]


LATIN_ENDINGS = re.compile(r"(?:ius|us|is|es|a|um)$")


def _alike(latin, form):
    """The form is the Latin name, or its stem with an ending of two letters at most (Gertrudis:
    Gertrude; Aurelius: Aurelio)."""
    la, f = _norm(latin), _norm(form)
    stem = LATIN_ENDINGS.sub("", la)
    return f == la or (len(stem) >= 3 and f.startswith(stem) and len(f) - len(stem) <= 2)


def harvest(persons, subjects):
    """{Latin first name key: {language: [[form, times seen], commonest first]}} from the first text person of
    each eulogy (`persons`: {eulogy: [person]}) and its subject in each language (`subjects`:
    {language: {eulogy: subject}})."""
    counts = {lang: defaultdict(Counter) for lang in LANGUAGES}
    # Every person's first name, in a footnote list too: a form like one of them is that name.
    latin_names = {name_key(p["name"].split()[0]) for ps in persons.values() for p in ps if p["name"].split()}
    for mrid, ps in persons.items():
        text = [p for p in ps if p.get("where") == "text"]
        if not text:
            continue
        for lang in LANGUAGES:
            pair = first_name_pair(text[0]["name"], subjects.get(lang, {}).get(mrid))
            if pair:
                counts[lang][pair[0]][pair[1]] += 1
    forms = {}
    for lang in LANGUAGES:
        claimed = defaultdict(set)  # a form's key: the Latin names it was seen for
        for latin, c in counts[lang].items():
            for form in c:
                claimed[name_key(form)].add(latin)

        def another_name(form, latin):
            return bool(claimed[name_key(form)] - {latin}) or any(
                other != latin and _alike(other, form) for other in latin_names)

        for latin, c in sorted(counts[lang].items()):
            kept = [[form, n] for form, n in c.most_common()
                    if name_key(form) != latin and (n >= 2 or _begins_like(form, latin) or not another_name(form, latin))]
            if kept:
                forms.setdefault(latin, {})[lang] = kept
    return forms


def main(argv):
    repo_root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    persons = json.loads((repo_root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
    subjects = {lang: json.loads((repo_root / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
                for lang in LANGUAGES}
    forms = harvest(persons, subjects)
    doc = {"$comment": "The English and Italian forms of the Latin first names, commonest first, from the "
                       "eulogies' subjects in the 2004 English and Italian editions. Generated by "
                       "scripts/name_forms.py; do not edit.",
           "forms": forms}
    (repo_root / "data" / "name_forms.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                                         encoding="utf-8")
    print(f"wrote data/name_forms.json: {len(forms)} Latin first names")


if __name__ == "__main__":
    main(sys.argv[1:])
