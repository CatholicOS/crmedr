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

from persons_text import name_key, person_key
from wikidata import Wikidata, WikidataError

EDITION = "martyrologium_romanum_2004"
SCHEMA = "crmedr-changeset/v1"
STATUSES = ["auto", "reviewed", "unresolved"]
QID = re.compile(r"^Q[1-9]\d*$")
CONFIDENCES = {"high", "medium", "low"}
MAX_CANDIDATES = 10
# Wikidata's canonization statuses (P411) of a saint or a blessed: saint, Catholic saint,
# canonized saint, blessed, and the titles Wikidata gives ancient and Eastern saints
# instead (Telemachus is a "Reverend Martyr"): hieromartyr, Reverend Martyr, thaumaturge,
# pre-congregation saint, great martyr, passion bearer. Not Venerable or Servant of God.
SAINT_STATUSES = {"Q43115", "Q3464126", "Q123110154", "Q2369287",
                  "Q2993173", "Q4377390", "Q1349880", "Q18344276", "Q3332786", "Q2032316"}
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
FORCE_REVIEW = {
    # The only "Valentinus" candidate passing is the Valentine of 14 February; the 7 January
    # eulogy is another (a commemoratio, so no death date could tell them apart).
    "mr:0107-valentinus|Valentinus": "the item is the Valentine of 14 February, not this eulogy's",
    # One-word names of undated eulogies that matched a famous namesake (CatholicOS/crmedr#79 review);
    # Simon Peter's alias "Simeon" matched both Simeons.
    "mr:0203-simeon-et-anna-prophetissa|Simeon": "the eulogy's Simeon is the prophet of the Presentation, not Saint Peter",
    "mr:0427-simeon|Simeon": "the eulogy's Simeon is the bishop of Jerusalem, not Saint Peter",
    "mr:0206-paulus-miki-et-socii|Thomas": "a Japanese martyr, not Thomas the Apostle",
    "mr:0206-paulus-miki-et-socii|Bonaventura": "a Japanese martyr, not Saint Bonaventure",
    "mr:0212-martyres-abitinenses|Maria": "an Abitinian martyr, not the Blessed Virgin",
    "mr:1003-faustus-et-socii|Petrus": "a companion of Faustus, not Saint Peter",
    "mr:1003-faustus-et-socii|Caius": "a companion of Faustus, not Pope Caius",
}
SEARCH_LANGUAGES = ("la", "it", "en")
# After this many persons in a row whose lookups failed (Wikidata lagged or down), a
# run stops asking: the rest are "not processed", for the next run, instead of each
# waiting out its own retries.
MAX_CONSECUTIVE_FAILURES = 5


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
    names = c.get("names", []) + [c.get("label", "")]
    if any(name_matches(nm, names) for nm in [person["name"], *person.get("also", [])]):
        ev.append("name")  # under any of the person's names
    if person["typology"] == "dies_natalis" and _death_agrees(c.get("died") or "", person["day"]):
        ev.append("death")
    return ev


def _death_agrees(died, day):
    """A death date on the eulogy's day (MM-DD), or, when Wikidata knows only the month, in its
    month (the user's ruling, 2026-10-09). A year alone can be checked against nothing, since a
    eulogy has no year, and does not count; nor does no date."""
    if len(died) == 10:
        return died[5:] == day
    if len(died) == 7:
        return died[5:] == day[:2]
    return False


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
    # Each of the person's names: Kinga is also sought as Cunegundis.
    terms = dict.fromkeys(t for nm in [person["name"], *person.get("also", [])] for t in search_terms(nm))
    for term in terms:
        for c in client.person_candidates(term, SEARCH_LANGUAGES):
            seen.setdefault(c["wikidata"], c)
    return list(seen.values())


def person_index(persons_doc, entries, typology, subjects):
    by_id = {e["id"]: e for e in entries}
    out = {}
    for mrid, persons in persons_doc["editions"][EDITION].items():
        e = by_id[mrid]
        for p in persons:
            out[f"{mrid}|{person_key(p)}"] = {
                "eulogy": mrid, "name": p["name"], **({"n": p["n"]} if "n" in p else {}),
                **({"also": p["also"]} if "also" in p else {}), "where": p["where"],
                "day": f"{e['month']:02d}-{e['day']:02d}", "typology": typology.get(mrid),
                "subject": subjects.get(mrid, ""),
                # Each other name once: a repeated name is one companion to search with.
                "companions": list(dict.fromkeys(q["name"] for q in persons if q["name"] != p["name"])),
            }
    return out


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/build_person_items.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": EDITION, "registry": "data/persons.json"}, "operations": operations}


def make_op(key, person, result, old):
    op = {"op": "resolve_person", "id": key, **{k: person[k] for k in
          ("eulogy", "day", "typology", "subject", "name", "n", "also", "where", "companions") if k in person},
          "failed": result["failed"], "candidates": result["candidates"]}
    for k in ("suggested", "reasoning", "confidence"):
        if old and k in old:
            op[k] = old[k]
    op["decision"], op["edited"] = None, None
    return op


def _decided(items, person):
    return person_key(person) in items.get(person["eulogy"], {})


def _one_word(name):
    return len(name.split()) == 1


def _shared_items(items, index, pending):
    """The items matched in more than one eulogy, by any decided or pending match, whatever the
    name. A one-word name matched to such an item is usually a famous namesake (Augustine of Hippo
    for Augustine of Canterbury): the user's ruling after the CatholicOS/crmedr#79 review is that
    none of those one-word matches is automatic."""
    eulogies = {}
    for mrid, persons in items.items():
        for e in persons.values():
            if e.get("wikidata"):
                eulogies.setdefault(e["wikidata"], set()).add(mrid)
    for key, result in pending.items():
        eulogies.setdefault(result["auto"]["wikidata"], set()).add(index[key]["eulogy"])
    return {qid for qid, ms in eulogies.items() if len(ms) > 1}


SHARED = "the same item ({qid}) is matched in another eulogy, and this name is one word: a namesake?"
SAME_EULOGY = "the same item ({qid}) is matched for another person of this eulogy"


def _holders(items, extra=()):
    """Who holds each item within a eulogy, {(eulogy, QID): {person keys}}: the decisions in
    `items`, plus `extra` (eulogy, person key, QID) triples not written yet."""
    out = {}
    for mrid, persons in items.items():
        for key, e in persons.items():
            if e.get("wikidata"):
                out.setdefault((mrid, e["wikidata"]), set()).add(key)
    for mrid, key, qid in extra:
        out.setdefault((mrid, qid), set()).add(key)
    return out


def propose(items, review, index, client, force_review=FORCE_REVIEW):
    # A queued op whose person is no longer in persons.json (a corrected list) is dropped: it was undecided.
    ops = {op["id"]: op for op in review["operations"] if op["id"] in index}
    not_processed = []
    failures = 0
    pending = {}  # automatic results, written once it is known which items are shared

    def keep(key, person):
        """A queued op not looked up this time takes the person's details (other names, companions)
        and keeps its candidates and reasons."""
        if key in ops:
            old = ops[key]
            ops[key] = make_op(key, person, {"failed": old["failed"], "candidates": old["candidates"]}, old)

    for key in sorted(index):
        person = index[key]
        if _decided(items, person):
            ops.pop(key, None)
            continue
        if failures >= MAX_CONSECUTIVE_FAILURES:
            not_processed.append((key, "skipped: Wikidata unavailable"))
            keep(key, person)
            continue
        try:
            result = evaluate(person, gather(person, client))
        except WikidataError as e:
            not_processed.append((key, str(e)))
            failures += 1
            keep(key, person)
            continue
        failures = 0
        if key in force_review:
            result["auto"] = None
            result["failed"].append("forced review: " + force_review[key])
        if result["auto"]:
            pending[key] = result
        else:
            ops[key] = make_op(key, person, result, ops.get(key))
    shared = _shared_items(items, index, pending)
    # propose withdraws its own automatic one-word matches of a shared item; a curator's
    # decision (reviewed, unresolved) it never touches.
    for key, person in index.items():
        e = items.get(person["eulogy"], {}).get(person_key(person))
        if not (e and e["status"] == "auto" and _one_word(person["name"]) and e["wikidata"] in shared):
            continue
        try:
            result = evaluate(person, gather(person, client))
        except WikidataError as err:
            not_processed.append((key, str(err)))
            continue
        result["failed"].append(SHARED.format(qid=e["wikidata"]))
        del items[person["eulogy"]][person_key(person)]
        if not items[person["eulogy"]]:
            del items[person["eulogy"]]
        ops[key] = make_op(key, person, result, ops.get(key))
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), r["auto"]["wikidata"])
                            for k, r in pending.items()])
    for key, result in pending.items():
        person, qid = index[key], result["auto"]["wikidata"]
        if len(held[(person["eulogy"], qid)]) > 1:
            result["failed"].append(SAME_EULOGY.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        elif _one_word(person["name"]) and qid in shared:
            result["failed"].append(SHARED.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        else:
            items.setdefault(person["eulogy"], {})[person_key(person)] = {"wikidata": qid, "status": "auto"}
            ops.pop(key, None)
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
    # An edit names its item; only an accept falls back to the suggestion or the top candidate.
    qid = edited.get("wikidata") if decision == "edit" else (
        suggested.get("wikidata") or (candidates[0]["wikidata"] if candidates else None))
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
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), e["wikidata"])
                            for k, e in decided.items() if e["wikidata"]])
    for (mrid, qid), keys in sorted(held.items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} would be the item of more than one person ({', '.join(sorted(keys))})")
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    for key, entry in decided.items():
        items.setdefault(index[key]["eulogy"], {})[person_key(index[key])] = entry
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
        names.setdefault(p["eulogy"], set()).add(person_key(p))
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
    for (mrid, qid), keys in sorted(_holders(items).items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} is the item of more than one person ({', '.join(sorted(keys))})")
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
    # The user's ruling (2026-10-09): automatic matches of eulogies that do not mark a death
    # stay automatic, listed here for a curator to scan; a wrong one goes into FORCE_REVIEW.
    undated = sorted(f"{key}: {items[p['eulogy']][person_key(p)]['wikidata']}" for key, p in index.items()
                     if p["typology"] != "dies_natalis"
                     and items.get(p["eulogy"], {}).get(person_key(p), {}).get("status") == "auto")
    lines += [f"## Automatic without a date check, to scan ({len(undated)})", "",
              "Eulogies that do not mark the day of death: name, status and a single candidate decided.", ""]
    lines += [f"- {x}" for x in undated] + [""]
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
