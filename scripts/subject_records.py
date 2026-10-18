#!/usr/bin/env python3
"""Subject identity records: the brief a research agent reads, and the check of what it writes.

An identity record says who a eulogy's subject is, as the 2004 Latin text prints it:
kind, surname, roles, places (with their grammar), cognomen, relations. Records come
from a model reading the texts; the later steps derive ID renames and Wikidata
candidates from them. Nothing is decided here.

Usage:
  python3 scripts/subject_records.py brief <MMa|MMb> <out.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/subject_records.py check <records.json> /path/to/martyrology-texts [repo_root]

brief writes, for a half-month (a: days 1-15, b: 16-31), the Latin, Italian and English
2004 texts, the Latin subject, the persons and their decided Wikidata items of each
current eulogy. It quotes the 2004 edition, so it is written outside any git work tree
(brief refuses a path inside one). check prints the errors of each record and exits 1
if there are any; it writes nothing.
"""
import json
import re
import sys
from pathlib import Path

from body_places import _in_a_repository, half_month
from extract_places import EDITION_EN, EDITION_IT, load_persons
from extract_typology import latin_texts, load_texts
from gazetteer_text import fold

CLERIC_ROLES = ("episcopus", "archiepiscopus", "presbyter", "diaconus", "subdiaconus", "abbas", "abbatissa", "prior")

# nominative role -> its printed forms, folded (nominative, genitive, dative, accusative, ablative)
ROLE_FORMS = {
    "episcopus": {"episcopus", "episcopi", "episcopo", "episcopum"},
    "archiepiscopus": {"archiepiscopus", "archiepiscopi", "archiepiscopo", "archiepiscopum"},
    "presbyter": {"presbyter", "presbyteri", "presbytero", "presbyterum"},
    "diaconus": {"diaconus", "diaconi", "diacono", "diaconum"},
    "subdiaconus": {"subdiaconus", "subdiaconi", "subdiacono", "subdiaconum"},
    "abbas": {"abbas", "abbatis", "abbati", "abbatem", "abbate"},
    "abbatissa": {"abbatissa", "abbatissae", "abbatissam", "abbatissa"},
    "prior": {"prior", "prioris", "priori", "priorem", "priore"},
    "monachus": {"monachus", "monachi", "monacho", "monachum"},
    "eremita": {"eremita", "eremitae", "eremitam"},
    "papa": {"papa", "papae", "papam"},
    "martyr": {"martyr", "martyris", "martyri", "martyrem", "martyre"},
    "virgo": {"virgo", "virginis", "virgini", "virginem", "virgine"},
    "confessor": {"confessor", "confessoris", "confessori", "confessorem", "confessore"},
    "rex": {"rex", "regis", "regi", "regem", "rege"},
    "regina": {"regina", "reginae", "reginam"},
    "propheta": {"propheta", "prophetae", "prophetam"},
    "patriarcha": {"patriarcha", "patriarchae", "patriarcham"},
    "iudex": {"iudex", "iudicis", "iudici", "iudicem", "iudice"},
    "levita": {"levita", "levitae", "levitam"},
}
assert all(r in ROLE_FORMS for r in CLERIC_ROLES)

GRAMMAR = ("adjective-person", "adjective-noun", "locative", "genitive", "ablative")
PLACE_KINDS = ("see", "monastery", "death", "burial", "cult", "origin")
KINDS = ("person", "celebration", "group")
COGNOMEN_SOURCES = ("text", "twin", "wikidata")

INFLECTION = re.compile(r"(ensis|ensi|ensem|ense|ensium|anus|ani|ano|anum|ana|anae|inus|ini|ina|inae)$")


def _stem(s):
    return INFLECTION.sub("", fold(s))


def _occurrences(text, printed):
    """Non-overlapping, case-sensitive, accents as printed."""
    return text.count(printed) if printed else 0


def _locate(label, item, la_text):
    """Errors of a printed form and its occurrence index."""
    printed, occ = item.get("printed"), item.get("occurrence")
    if not isinstance(printed, str) or not printed or printed not in la_text:
        return [f"{label}: printed form not in the text"]
    n = _occurrences(la_text, printed)
    if not isinstance(occ, int) or isinstance(occ, bool) or not 0 <= occ < n:
        return [f"{label}: occurrence {occ} of {n}"]
    return []


def check_record(record, la_text):
    """Error strings of an identity record against its Latin text; empty when valid."""
    errors = []
    if not isinstance(record.get("id"), str) or not record["id"]:
        errors.append("id missing")
    if not isinstance(record.get("name"), str) or not record["name"]:
        errors.append("name missing")
    if record.get("kind") not in KINDS:
        errors.append(f"kind: {record.get('kind')}")
    if not isinstance(record.get("feminine"), bool):
        errors.append("feminine: not a boolean")
    if record.get("surname") is not None and not isinstance(record["surname"], str):
        errors.append("surname: not a string or null")
    for i, r in enumerate(record.get("roles") or []):
        label = f"roles[{i}]"
        if r.get("role") not in ROLE_FORMS:
            errors.append(f"{label}: role {r.get('role')}")
        errors += (found := _locate(label, r, la_text))
        if not found and r.get("role") in ROLE_FORMS and fold(r["printed"]) not in ROLE_FORMS[r["role"]]:
            errors.append(f"{label}: {r['printed']} is not a form of {r['role']}")
    for i, p in enumerate(record.get("places") or []):
        label = f"places[{i}]"
        if p.get("kind") not in PLACE_KINDS:
            errors.append(f"{label}: kind {p.get('kind')}")
        if p.get("grammar") not in GRAMMAR:
            errors.append(f"{label}: grammar {p.get('grammar')}")
        errors += (found := _locate(label, p, la_text))
        for k in ("nominative", "en", "it"):
            if not isinstance(p.get(k), str) or not p[k]:
                errors.append(f"{label}: {k} missing")
        if p.get("genitive") is not None and not isinstance(p["genitive"], str):
            errors.append(f"{label}: genitive not a string or null")
        if str(p.get("grammar", "")).startswith("adjective-"):
            adj = p.get("adjective")
            if not adj:
                errors.append(f"{label}: adjective missing")
            elif not found and _stem(adj) != _stem(p["printed"]):
                errors.append(f"{label}: adjective {adj} does not match {p['printed']}")
    cog = record.get("cognomen")
    if cog is not None and (not isinstance(cog, dict) or not cog.get("value")
                            or cog.get("source") not in COGNOMEN_SOURCES):
        errors.append("cognomen: needs a value and a source (text, twin or wikidata)")
    for i, rel in enumerate(record.get("relations") or []):
        if not isinstance(rel, dict) or not rel.get("name") or not rel.get("relation"):
            errors.append(f"relations[{i}]: needs a name and a relation")
    year = record.get("death_year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
        errors.append("death_year: not an integer or null")
    for k in ("role_en", "role_it"):
        if record.get(k) is not None and not isinstance(record[k], str):
            errors.append(f"{k}: not a string or null")
    return errors


def brief(first, last, texts, texts_it, texts_en, persons, subjects_la, entries, items):
    """What a research agent reads for each current eulogy whose MMDD is in [first, last]."""
    out = []
    for e in sorted((e for e in entries if not e.get("deprecated") and first <= e["id"][3:7] <= last),
                    key=lambda e: e["id"]):
        mrid = e["id"]
        out.append({"id": mrid, "la_text": texts.get(mrid, ""), "it_text": texts_it.get(mrid, ""),
                    "en_text": texts_en.get(mrid, ""), "subject_la": subjects_la.get(mrid),
                    "persons": persons.get(mrid, []), "same_eulogy": e.get("same_eulogy", []),
                    "person_items": items.get(mrid, {})})
    return out


def _load(repo_root, texts_repo):
    read = lambda *p: json.loads(repo_root.joinpath(*p).read_text(encoding="utf-8"))  # noqa: E731
    entries = read("data", "martyrology_ids.json")["entries"]
    texts = latin_texts(entries, load_texts(texts_repo))
    texts_it = latin_texts(entries, load_texts(texts_repo, EDITION_IT))
    texts_en = latin_texts(entries, load_texts(texts_repo, EDITION_EN))
    return (entries, texts, texts_it, texts_en, load_persons(repo_root), read("i18n", "la.json"),
            read("data", "person_items.json")["persons"])


def main(argv):
    cmds = {"brief": 4, "check": 3}
    if not argv or argv[0] not in cmds or len(argv) < cmds[argv[0]]:
        sys.exit(__doc__)
    cmd = argv[0]
    here = Path(__file__).resolve().parent.parent
    if cmd == "brief":
        which, out, texts_repo = argv[1], Path(argv[2]), Path(argv[3])
        repo_root = Path(argv[4]) if len(argv) > 4 else here
        if _in_a_repository(out, repo_root):
            sys.exit(f"{out}: a brief quotes the 2004 edition; write it outside the repository")
        if not re.fullmatch(r"(0[1-9]|1[0-2])[ab]", which):
            sys.exit(f"{which}: expected MMa or MMb (e.g. 01a)")
        entries, texts, texts_it, texts_en, persons, subjects, items = _load(repo_root, texts_repo)
        records = brief(*half_month(which[:2], which[2]), texts, texts_it, texts_en, persons, subjects,
                        entries, items)
        out.write_text(json.dumps({"batch": which, "eulogies": records}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"{len(records)} eulogies in {out}")
        return 0
    path, texts_repo = Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else here
    texts = _load(repo_root, texts_repo)[1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    records = doc["records"] if isinstance(doc, dict) else doc
    bad = 0
    for r in records:
        errors = check_record(r, texts.get(r.get("id"), "")) if r.get("id") in texts else ["id: no such eulogy"]
        if errors:
            bad += 1
            print(f"{r.get('id')} [{r.get('name')}]: " + "; ".join(errors))
    print(f"{len(records) - bad} of {len(records)} records valid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
