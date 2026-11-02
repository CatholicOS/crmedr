#!/usr/bin/env python3
"""Pipeline for the persons a eulogy only mentions (role "mentioned"; data/persons_mentioned.json).

  brief   writes, for the eulogies of one month, the material an extraction agent reads: each eulogy's
          Latin and Italian texts and footnotes, its persons (name, n, role) and its current marks as
          [kind, where, start, end, form] (offsets in UTF-16 code units, per edition).
  check   validates the proposals an extraction agent returns, before anything is applied.

A proposal file is {"<mrid>": [{"name": Latin nominative, "n"?: int, "where": "text" | {"footnote": n},
"la": [printed phrases], "it": [printed phrases, [] if the Italian does not name them],
"who": one line, "kind": "saint" | "other"}]}. Every named human person is marked except Christ, the
Persons of the Trinity and the Virgin Mary; a phrase covers the name with its epithets and attached office
and must not overlap a commemorated person's mark. A place mark inside a phrase is allowed (apply removes it).

Usage:
  python3 mentioned_persons.py brief MM /path/to/martyrology-texts /outside/the/repo/brief-MM.json [repo_root]
  python3 mentioned_persons.py check proposals.json /path/to/martyrology-texts [repo_root]
    (exit 1, one problem per line, when a proposal fails a check)

The brief quotes the 2004 texts: it is written only outside any git work tree.
Standard library only.
"""

import json
import re
import sys
from pathlib import Path

from body_places import _in_a_repository
from extract_mentions import load_edition, source_text, where_key, with_mentioned_marks
from mentions_text import from_utf16, utf16
from persons_text import name_key, person_key

EDITIONS = {"la": "martyrologium_romanum_2004", "it": "martyrologium_romanum_2004_it_IT"}
# Latin nominatives never marked as mentioned persons: Christ, the Persons of the Trinity, the Virgin Mary.
EXCLUDED = ("Christus", "Iesus", "Dominus", "Deus", "Spiritus Sanctus", "Trinitas")
VIRGIN_NAMES = ("Maria Virgo", "Beata Maria Virgo")  # Maria alone is excluded only when `who` says the Virgin
VIRGIN_WHO = re.compile(r"\b(?:the virgin|virgin mary|blessed virgin|mother of (?:god|jesus|christ)|theotokos"
                        r"|our lady|virgo)\b", re.I)
KINDS = ("saint", "other")


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def is_excluded(proposal):
    """Christ, a Person of the Trinity or the Virgin Mary: not marked."""
    key = name_key(proposal.get("name") or "")
    if key in {name_key(n) for n in EXCLUDED + VIRGIN_NAMES}:
        return True
    return key == "maria" and bool(VIRGIN_WHO.search(proposal.get("who") or ""))


def current_ids(registry, month):
    """The current (not deprecated) eulogy IDs of a month, in registry order."""
    return [e["id"] for e in registry["entries"] if e.get("month") == month and not e.get("deprecated")]


def span_form(src, start, end):
    """The printed words of a mark (UTF-16 offsets in `src`)."""
    return src[from_utf16(src, start):from_utf16(src, end)]


def brief_marks(marks, texts, notes, mrid):
    out = []
    for m in marks:
        src = source_text((texts, notes), mrid, m["where"]) or ""
        out.append([m["kind"], m["where"], m["start"], m["end"], span_form(src, m["start"], m["end"])])
    return out


def build_brief(month, registry, sources, persons, mentions):
    """`sources`: lang -> (texts, notes); `persons`/`mentions`: lang -> {eulogy: [...]}. The eulogies of the
    month that the Latin edition prints."""
    out = {}
    for mrid in current_ids(registry, month):
        la_texts, la_notes = sources["la"]
        if mrid not in la_texts:
            continue
        it_texts, it_notes = sources["it"]
        out[mrid] = {
            "id": mrid,
            "la": la_texts[mrid], "la_footnotes": la_notes.get(mrid, []),
            "it": it_texts.get(mrid), "it_footnotes": it_notes.get(mrid, []),
            "persons": [{"name": p["name"], "n": p.get("n", 1), "role": p.get("role", "commemorated")}
                        for p in persons["la"].get(mrid, [])],
            "marks": {lang: brief_marks(mentions[lang].get(mrid, []), *sources[lang], mrid) for lang in sources},
        }
    return list(out.values())


def check_proposals(proposals, sources, persons, mentions):
    """Problems in the proposals, one message each (empty when they pass)."""
    problems = []
    for mrid, items in proposals.items():
        if mrid not in sources["la"][0]:
            problems.append(f"{mrid}: not a eulogy of the Latin edition")
            continue
        known = {person_key({**p, "name": name_key(p["name"])}) for p in persons.get(mrid, [])}
        for p in items:
            key = person_key(p)
            label = f"{mrid} {key}"
            if not isinstance(p.get("name"), str) or not p["name"]:
                problems.append(f"{mrid}: a proposal without a name")
                continue
            if p.get("kind") not in KINDS:
                problems.append(f"{label}: kind must be one of {KINDS}")
            if not isinstance(p.get("who"), str) or not p["who"].strip():
                problems.append(f"{label}: who is missing")
            if is_excluded(p):
                problems.append(f"{label}: excluded (Christ, the Trinity or the Virgin Mary are not marked)")
            if person_key({**p, "name": name_key(p["name"])}) in known:
                problems.append(f"{label}: already a person of the eulogy")
            for lang in ("la", "it"):
                if not isinstance(p.get(lang), list) or (lang == "la" and not p[lang]):
                    problems.append(f"{label}: {lang} must list the printed phrases"
                                    + (" ([] if the Italian does not name them)" if lang == "it" else ""))
                    continue
                problems += phrase_problems(mrid, p, lang, sources[lang], mentions[lang].get(mrid, []), label)
    return problems


def phrase_problems(mrid, p, lang, edition_sources, marks, label):
    """Phrases not printed in the person's `where`, or overlapping a commemorated person's mark."""
    if not p[lang]:
        return []
    key = where_key(p["where"]) if p.get("where") == "text" or isinstance(p.get("where"), dict) else None
    if key is None or source_text(edition_sources, mrid, p["where"]) is None:
        return [f"{label}: there is no {p.get('where')!r} in the {lang} edition"]
    errors = []
    found = with_mentioned_marks([], [p], {key: source_text(edition_sources, mrid, p["where"])}, lang,
                                 lambda k: None, {}, errors)
    problems = [f"{mrid}: {e}" for e in errors]
    src = source_text(edition_sources, mrid, p["where"])
    for m in found:
        s, e = utf16(src, m["start"]), utf16(src, m["end"])
        for c in marks:
            if (c["kind"] == "person" and c.get("role") != "mentioned" and where_key(c["where"]) == key
                    and s < c["end"] and c["start"] < e):
                problems.append(f"{label}: {m['form']!r} ({lang}) overlaps the mark of {c.get('name', 'a person')}")
    return problems


def load_sources(texts_repo):
    return {lang: load_edition(Path(texts_repo), ed) for lang, ed in EDITIONS.items()}


def load_data(repo_root):
    d = Path(repo_root) / "data"
    persons = read_json(d / "persons.json")["editions"]
    mentions = read_json(d / "mentions.json")["editions"]
    return ({lang: persons.get(ed, {}) for lang, ed in EDITIONS.items()},
            {lang: mentions.get(ed, {}) for lang, ed in EDITIONS.items()})


def main(argv):
    if len(argv) < 3 or argv[0] not in ("brief", "check"):
        sys.exit(__doc__)
    default_root = Path(__file__).resolve().parent.parent
    if argv[0] == "brief":
        if len(argv) < 4 or not argv[1].isdigit() or not 1 <= int(argv[1]) <= 12:
            sys.exit(__doc__)
        repo_root = Path(argv[4]) if len(argv) > 4 else default_root
        out = Path(argv[3])
        if _in_a_repository(out, repo_root):
            sys.exit("the brief quotes the 2004 texts: write it outside any git work tree")
        persons, mentions = load_data(repo_root)
        registry = read_json(repo_root / "data" / "martyrology_ids.json")
        brief = build_brief(int(argv[1]), registry, load_sources(argv[2]), persons, mentions)
        out.write_text(json.dumps(brief, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(brief)} eulogies to {out}")
        return
    repo_root = Path(argv[3]) if len(argv) > 3 else default_root
    persons, mentions = load_data(repo_root)
    problems = check_proposals(read_json(argv[1]), load_sources(argv[2]), persons["la"], mentions)
    for line in problems:
        print(line)
    if problems:
        sys.exit(1)
    print("proposals ok")


if __name__ == "__main__":
    main(sys.argv[1:])
