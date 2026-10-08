#!/usr/bin/env python3
"""Identify the persons of data/persons.json with Wikidata items.

A person is `auto` only when exactly one candidate passes every rule of the
evidence bar; every other goes to the review change-set (crmedr-changeset/v1,
op `resolve_person`) for martyrology-frontend and comes back through `apply`
as `reviewed` or `unresolved`. Decisions are per eulogy and name.
See docs/superpowers/specs/2026-10-08-persons-design.md.

  data/person_items.json          {persons: {id: {name: {wikidata, status, note?}}}}
  data/person_items_review.json   the review change-set
  docs/person-items-report.md     progress

Usage:
  python3 build_person_items.py propose [repo_root]              (network)
  python3 build_person_items.py verify-suggestions [repo_root]   (network)
  python3 build_person_items.py apply <exported.json> [repo_root]
  python3 build_person_items.py check [repo_root]

Standard library only. Reads no private sources.
"""

import datetime
import json
import re
import sys
from pathlib import Path

from persons_text import name_key
from wikidata import Wikidata, WikidataError

EDITION = "martyrologium_romanum_2004"
SCHEMA = "crmedr-changeset/v1"
STATUSES = ["auto", "reviewed", "unresolved"]
QID = re.compile(r"^Q[1-9]\d*$")
CONFIDENCES = {"high", "medium", "low"}
MAX_CANDIDATES = 10
# Wikidata's canonization statuses (P411) of a saint or a blessed.
SAINT_STATUSES = {"Q43115", "Q3464126", "Q123110154", "Q2369287"}
# Words of a label that are not part of the name ("Saint Basil", "San Basilio").
TITLE_WORDS = {"saint", "st", "san", "santo", "santa", "santi", "sante", "sant", "beato", "beata", "beati",
               "blessed", "the", "of", "sanctus", "sancta", "beatus"}
# Latin first names whose vernacular forms share no prefix with them.
NAME_EQUIVALENTS = {
    "ioannes": {"john", "giovanni", "juan", "jean", "joao", "johannes", "jan"},
    "iacobus": {"james", "giacomo", "jacques", "jaime", "diego", "jacob", "jakob"},
    "gulielmus": {"william", "guglielmo", "guillaume", "guillermo", "wilhelm"},
    "ludovicus": {"louis", "luigi", "luis", "ludwig", "lewis"},
    "henricus": {"henry", "enrico", "henri", "enrique", "heinrich"},
    "carolus": {"charles", "carlo", "carlos", "karl"},
    "aegidius": {"giles", "egidio", "gilles"},
    "iosephus": {"joseph", "giuseppe", "jose", "josef"},
    "petrus": {"peter", "pietro", "pierre", "pedro", "pieter", "piotr"},
}
# The same table in name_key form ("John" -> "iohn", "Giovanni" -> "giouanni"), for comparing.
_EQUIVALENTS = {name_key(k): {name_key(v) for v in vs} for k, vs in NAME_EQUIVALENTS.items()}
# Persons that pass the evidence bar but are known to be wrong: always reviewed.
FORCE_REVIEW = {}
SEARCH_LANGUAGES = ("la", "it", "en")


def _tokens(s):
    return [t for t in name_key(s).split() if len(t) > 1 and t not in TITLE_WORDS]


# A Latin ending, and the endings its vernacular forms may have instead (Paulus: Paul,
# Paolo; Augustinus: Augustine; Basilius: Basil; Caecilia: Cecilia). A name without
# one of these endings matches only itself: Leo is not Leontius, Victor not Victoria.
LATIN_ENDINGS = [("ius", {"", "io", "ius", "e"}), ("us", {"", "o", "e", "us"}), ("ia", {"ia", "ie", "a", "e", "y"}),
                 ("a", {"a", "e", ""}), ("es", {"es", "", "e", "i"}), ("is", {"is", "", "e"}), ("um", {"um", ""})]


def _same(latin, other):
    """The same name: equal, equivalents, or one stem with a Latin and a vernacular ending."""
    if other in _EQUIVALENTS.get(latin, ()):
        return True
    latin, other = latin.replace("ae", "e").replace("oe", "e"), other.replace("ae", "e").replace("oe", "e")
    if latin == other:
        return True
    for ending, vernacular in LATIN_ENDINGS:
        if latin.endswith(ending) and len(latin) - len(ending) >= 2:
            stem = latin[: -len(ending)]
            return any(other == stem + v for v in vernacular)
    return False


def name_matches(name, candidate_names):
    """The Latin name and one of the item's names have the same words, pair by pair
    (see _same): Paulus Miki = Paul Miki."""
    latin = [t for t in _tokens(name) if t not in {"de", "a", "ab", "la", "y"}]
    for other in candidate_names:
        words = [t for t in _tokens(other) if t not in {"de", "di", "da", "la", "y", "van", "von"}]
        if latin and len(words) == len(latin) and all(_same(a, b) for a, b in zip(latin, words)):
            return True
    return False


def evidence(person, c):
    ev = []
    if c.get("human"):
        ev.append("human")
    if SAINT_STATUSES & set(c.get("statuses", [])):
        ev.append("status")
    if name_matches(person["name"], c.get("names", []) + [c.get("label", "")]):
        ev.append("name")
    died = c.get("died") or ""
    if person["typology"] == "dies_natalis" and len(died) == 10 and died[5:] == person["day"]:
        ev.append("death")
    return ev


def _required(person):
    return ["human", "status", "name"] + (["death"] if person["typology"] == "dies_natalis" else [])


def evaluate(person, candidates):
    scored = []
    for c in candidates:
        c = dict(c, evidence=evidence(person, c))
        scored.append(c)
    need = _required(person)
    passing = [c for c in scored if all(r in c["evidence"] for r in need)]
    scored.sort(key=lambda c: (-len(c["evidence"]), c["wikidata"]))
    failed = []
    if not passing:
        best = scored[0] if scored else None
        failed = ([f"{r}: the best candidate ({best['wikidata']}) fails it" for r in need if r not in best["evidence"]]
                  if best else ["no candidate found"])
    elif len(passing) > 1:
        failed = [f"{len(passing)} candidates pass every rule: " + ", ".join(c["wikidata"] for c in passing)]
    return {"auto": passing[0] if len(passing) == 1 else None, "failed": failed,
            "candidates": scored[:MAX_CANDIDATES]}


def search_terms(name):
    """The name, and for a first name with vernacular equivalents, its English and Italian forms."""
    words = name.split()
    terms = [name]
    first = name_key(words[0]) if words else ""
    equivalents = next((vs for k, vs in NAME_EQUIVALENTS.items() if name_key(k) == first), ())
    for vern in sorted(equivalents)[:4]:
        terms.append(" ".join([vern.capitalize()] + words[1:]))
    return terms


def gather(person, client):
    seen = {}
    for term in search_terms(person["name"]):
        for c in client.person_candidates(term, SEARCH_LANGUAGES):
            seen.setdefault(c["wikidata"], c)
    return list(seen.values())


def person_index(persons_doc, entries, typology, subjects):
    by_id = {e["id"]: e for e in entries}
    out = {}
    for mrid, persons in persons_doc["editions"][EDITION].items():
        e = by_id[mrid]
        for p in persons:
            out[f"{mrid}|{p['name']}"] = {
                "eulogy": mrid, "name": p["name"], "where": p["where"],
                "day": f"{e['month']:02d}-{e['day']:02d}", "typology": typology.get(mrid),
                "subject": subjects.get(mrid, ""),
                "companions": [q["name"] for q in persons if q["name"] != p["name"]],
            }
    return out


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/build_person_items.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": EDITION, "registry": "data/persons.json"}, "operations": operations}


def make_op(key, person, result, old):
    op = {"op": "resolve_person", "id": key, **{k: person[k] for k in
          ("eulogy", "day", "typology", "subject", "name", "where", "companions")},
          "failed": result["failed"], "candidates": result["candidates"]}
    for k in ("suggested", "reasoning", "confidence"):
        if old and k in old:
            op[k] = old[k]
    op["decision"], op["edited"] = None, None
    return op


def _decided(items, person):
    return person["name"] in items.get(person["eulogy"], {})


def propose(items, review, index, client, force_review=FORCE_REVIEW):
    ops = {op["id"]: op for op in review["operations"]}
    not_processed = []
    for key in sorted(index):
        person = index[key]
        if _decided(items, person):
            ops.pop(key, None)
            continue
        try:
            result = evaluate(person, gather(person, client))
        except WikidataError as e:
            not_processed.append((key, str(e)))
            continue
        if key in force_review:
            result["auto"] = None
            result["failed"].append("forced review: " + force_review[key])
        if result["auto"]:
            items.setdefault(person["eulogy"], {})[person["name"]] = {"wikidata": result["auto"]["wikidata"],
                                                                     "status": "auto"}
            ops.pop(key, None)
        else:
            ops[key] = make_op(key, person, result, ops.get(key))
    review["operations"] = sorted(ops.values(), key=lambda op: op["id"])
    review["generated_at"] = datetime.date.today().isoformat()
    return not_processed


def _is_saint(c):
    return bool(c) and c.get("human") and bool(SAINT_STATUSES & set(c.get("statuses", [])))


def _resolve(op, client):
    key, decision = op["id"], op.get("decision")
    edited, suggested = op.get("edited") or {}, op.get("suggested") or {}
    if decision == "reject":
        reason = (edited.get("reason") or "").strip()
        if not reason:
            return None, f"{key}: reject needs a reason (edited.reason)"
        return {"wikidata": None, "status": "unresolved", "note": reason}, None
    if decision not in ("accept", "edit"):
        return None, f"{key}: unknown decision {decision!r}"
    candidates = op.get("candidates", [])
    qid = (edited.get("wikidata") if decision == "edit" else None) or suggested.get("wikidata") \
        or (candidates[0]["wikidata"] if candidates else None)
    if not qid or not QID.match(qid):
        return None, f"{key}: no item chosen"
    chosen = next((c for c in candidates if c["wikidata"] == qid), None) or client.person(qid)
    if not _is_saint(chosen):
        return None, f"{key}: {qid} is not a human with a saint or blessed status"
    return {"wikidata": qid, "status": "reviewed"}, None


def apply_decisions(items, review, exported, index, client):
    if exported.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    decided, errors = {}, []
    for op in exported.get("operations", []):
        if op.get("op") != "resolve_person" or op.get("decision") is None:
            continue
        key = op["id"]
        if key not in index:
            errors.append(f"{key}: not a person of data/persons.json")
            continue
        if _decided(items, index[key]):
            errors.append(f"{key}: already decided")
            continue
        entry, error = _resolve(op, client)
        if error:
            errors.append(error)
        else:
            decided[key] = entry
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    for key, entry in decided.items():
        items.setdefault(index[key]["eulogy"], {})[index[key]["name"]] = entry
    review["operations"] = [op for op in review["operations"] if op["id"] not in decided]
    return len(decided)


def verify_suggestions(review, client):
    errors = []
    for op in review["operations"]:
        s = op.get("suggested")
        if not s:
            continue
        if op.get("confidence") not in CONFIDENCES:
            errors.append(f"{op['id']}: confidence {op.get('confidence')!r} not in {sorted(CONFIDENCES)}")
        qid = s.get("wikidata")
        if not isinstance(qid, str) or not QID.match(qid):
            errors.append(f"{op['id']}: suggested wikidata {qid!r} is not a QID")
            continue
        if all(c["wikidata"] != qid for c in op["candidates"]):
            c = client.person(qid)
            if c is None:
                errors.append(f"{op['id']}: no such item {qid}")
                continue
            op["candidates"].append(dict(c, evidence=evidence(op, c)))
        c = next(c for c in op["candidates"] if c["wikidata"] == qid)
        if not _is_saint(c):
            errors.append(f"{op['id']}: suggested {qid} is not a human with a saint or blessed status")
    return errors


def validate(items, index, ops=()):
    errors = []
    names = {}
    for key, p in index.items():
        names.setdefault(p["eulogy"], set()).add(p["name"])
    for mrid, persons in items.items():
        for name, e in persons.items():
            where = f"{mrid}|{name}"
            if name not in names.get(mrid, set()):
                errors.append(f"{where}: not a person of data/persons.json")
            if e.get("status") not in STATUSES:
                errors.append(f"{where}: status {e.get('status')!r}")
            elif e["status"] == "unresolved":
                if e.get("wikidata") is not None or not (e.get("note") or "").strip():
                    errors.append(f"{where}: unresolved needs wikidata null and a note")
            elif not isinstance(e.get("wikidata"), str) or not QID.match(e["wikidata"]):
                errors.append(f"{where}: wikidata {e.get('wikidata')!r} is not a QID")
    for op in ops:
        if op["id"] not in index:
            errors.append(f"{op['id']}: queued but not a person of data/persons.json")
    return errors


def render_json(items):
    doc = {"$comment": "Wikidata items of the persons of data/persons.json, by eulogy and name. auto: exactly one "
                       "candidate passed the evidence bar; reviewed: chosen by a curator; unresolved: no item "
                       "(note says why). Generated by scripts/build_person_items.py; see "
                       "docs/superpowers/specs/2026-10-08-persons-design.md. Draft pending committee review.",
           "statuses": STATUSES, "persons": {k: items[k] for k in sorted(items)}}
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def render_report(items, index, ops, not_processed=()):
    counts = {s: sum(1 for v in items.values() for e in v.values() if e["status"] == s) for s in STATUSES}
    lines = ["# Person items report", "", "Generated by `scripts/build_person_items.py`.", "",
             f"- Persons: {len(index)}",
             *(f"- {s}: {counts[s]}" for s in STATUSES),
             f"- Queued for review: {len(ops)}", f"- Not processed (lookup failed): {len(not_processed)}", ""]
    if not_processed:
        lines += ["## Not processed", ""] + [f"- {k}: {e}" for k, e in not_processed] + [""]
    return "\n".join(lines)


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main(argv):
    if not argv or argv[0] not in {"propose", "verify-suggestions", "apply", "check"}:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    exported = None
    if cmd == "apply":
        if not rest:
            sys.exit(__doc__)
        exported = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
        rest = rest[1:]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    data = repo_root / "data"
    entries = _read(data / "martyrology_ids.json", {})["entries"]
    typology = _read(data / "typology.json", {"typology": {}})["typology"]
    subjects = _read(repo_root / "i18n" / "la.json", {})
    index = person_index(_read(data / "persons.json", {}), entries, typology, subjects)
    items = _read(data / "person_items.json", {"persons": {}})["persons"]
    review = _read(data / "person_items_review.json", new_changeset([]))
    not_processed = []
    client = Wikidata(repo_root / ".cache" / "wikidata")
    if cmd == "propose":
        not_processed = propose(items, review, index, client)
    elif cmd == "verify-suggestions":
        errors = verify_suggestions(review, client)
        if errors:
            sys.exit("\n".join(errors))
    elif cmd == "apply":
        print(f"applied {apply_decisions(items, review, exported, index, client)} decisions")
    errors = validate(items, index, review["operations"])
    if errors:
        sys.exit("invalid person items:\n" + "\n".join(errors))
    if cmd == "check":
        print("ok")
        return
    (data / "person_items.json").write_text(render_json(items), encoding="utf-8")
    (data / "person_items_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
    (repo_root / "docs" / "person-items-report.md").write_text(
        render_report(items, index, review["operations"], not_processed), encoding="utf-8")
    for key, err in not_processed:
        print(f"not processed: {key}: {err}")


if __name__ == "__main__":
    main(sys.argv[1:])
