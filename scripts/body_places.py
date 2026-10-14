#!/usr/bin/env python3
"""Body places: check the proposal pass into the add_place change-set, and apply its review.

A body place is a place a eulogy names outside its opening place, with its role
(see ROLES in extract_places.py). Proposals come from a model reading the texts;
nothing is decided until a person reviews it in martyrology-frontend.

Usage:
  python3 scripts/body_places.py brief <MMa|MMb> <out.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py check [--final] <proposals.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py apply <exported.json> /path/to/martyrology-texts [repo_root]

brief writes what a proposing subagent reads for a half-month (a: days 1-15,
b: 16-31): the Latin and Italian 2004 texts, the opening place, the persons
and the curated items of each eulogy. It quotes the 2004 edition, so it is
written outside the repository (brief refuses a path inside it).
check --final keeps the proposals that still fail under "unqueued" in
data/places_review.json, for docs/places-report.md.

check validates each proposal with the rules of data/places_curated.json
(validate_curated) and queues the valid ones as add_place ops in
data/places_review.json; it prints the failures. apply writes accepted and
edited items into data/places_curated.json and remembers rejected ones; an
invalid decision applies nothing. Rerun scripts/extract_places.py afterwards.
"""
import copy
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

from extract_places import CURATED_KEYS, EDITION_IT, load_persons, occurrences, validate_curated
from extract_typology import latin_texts, load_texts

SCHEMA = "crmedr-changeset/v1"
CONFIDENCE = ("high", "medium", "low")
REVIEW = "data/places_review.json"
CURATED = "data/places_curated.json"


def new_changeset():
    return {"schema": SCHEMA, "generated_by": "scripts/body_places.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": "martyrologium_romanum_2004", "registry": "data/places_curated.json"},
            "operations": [], "rejected": []}


def item_of(p, text="", text_it=""):
    """The curated item of a proposal or decision. A first person of a name is the
    default, so n of 1 is left out; occurrence (occurrence_it) of 1 is left out only
    when its form is printed once in the Latin (Italian) text, since a form printed
    more than once needs it."""
    printed = {"occurrence": (text, p.get("la")), "occurrence_it": (text_it, p.get("it"))}

    def default(k, v):
        if v != 1 or k not in ("n", *printed):
            return False
        return k == "n" or len(occurrences(printed[k][0], printed[k][1] or "")) <= 1

    return {k: p[k] for k in CURATED_KEYS if k in p and p[k] is not None and not default(k, p[k])}


MAX_REASONING = 300
QUOTE_WORDS = 4  # a run of this many words of the eulogy is a quotation


def _words(s):
    return re.findall(r"\w+", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def _grams(words):
    return {tuple(words[i:i + QUOTE_WORDS]) for i in range(len(words) - QUOTE_WORDS + 1)}


def reasoning_errors(mrid, p, texts, texts_it):
    """The reasoning may quote the place designation, never the eulogy: no run of
    QUOTE_WORDS words of the Latin or Italian text beyond the place's own words."""
    reasoning = p.get("reasoning", "")
    if not isinstance(reasoning, str):
        return [f"{mrid}: reasoning must be a string"]
    if len(reasoning) > MAX_REASONING:
        return [f"{mrid}: reasoning is longer than {MAX_REASONING} characters"]
    place = _grams(_words(p.get("la", ""))) | _grams(_words(p.get("it", "") or ""))
    text = _grams(_words(texts.get(mrid, ""))) | _grams(_words(texts_it.get(mrid, "")))
    if (_grams(_words(reasoning)) & text) - place:
        return [f"{mrid}: reasoning quotes the text (keep to the place designation)"]
    return []


def op_id(p):
    """One id per item: a first printing and a first person of a name are the default."""
    p = item_of(p) | {"eulogy": p["eulogy"]}
    p = {k: v for k, v in p.items() if not (k in ("occurrence", "n") and v == 1)}
    parts = [p["eulogy"], p["role"], p["la"]]
    if p.get("occurrence"):
        parts.append(str(p["occurrence"]))
    if p.get("person"):
        parts.append(p["person"])
        if p.get("n"):
            parts.append(str(p["n"]))
    return "#".join(parts)


def _text_persons(persons, mrid):
    return [{"name": p["name"]} | ({"n": p["n"]} if p.get("n", 1) != 1 else {})
            for p in persons.get(mrid, []) if p.get("where") == "text"]


def _failure(p, errors):
    return {"eulogy": p.get("eulogy"), "role": p.get("role"), "la": p.get("la"), "errors": errors}


def _key(f):
    return (str(f["eulogy"]), str(f["role"]), str(f["la"]))


def _item_errors(mrid, item, curated, texts, texts_it, leads, persons):
    """validate_curated on the eulogy's existing items plus this one; only errors this item adds."""
    others = curated.get(mrid, [])
    base = set(validate_curated({mrid: others}, texts, set(texts), leads, texts_it, persons)) if others else set()
    return [e for e in validate_curated({mrid: others + [item]}, texts, set(texts), leads, texts_it, persons)
            if e not in base]


def check(proposals, curated, review, texts, texts_it, leads, persons, final=False):
    queued = {o["id"] for o in review["operations"]}
    rejected = set(review.get("rejected", []))
    done = {op_id(dict(it, eulogy=m)) for m, items in curated.items() for it in items}
    failures, added, passed = [], 0, set()
    for p in proposals:
        mrid = p.get("eulogy")
        if mrid not in texts:
            failures.append(_failure(p, [f"{mrid}: not a current ID with a Latin text"]))
            continue
        if p.get("confidence") not in CONFIDENCE:
            failures.append(_failure(p, [f"{mrid}: confidence must be one of {', '.join(CONFIDENCE)}"]))
            continue
        item = item_of(p, texts[mrid], texts_it.get(mrid, ""))
        if not {"role", "la"} <= set(item):
            failures.append(_failure(p, [f"{mrid}: a proposal needs role and la"]))
            continue
        oid = op_id(dict(item, eulogy=mrid))
        if oid in queued or oid in rejected or oid in done:
            passed.add(_key(_failure(p, [])))
            continue
        errors = reasoning_errors(mrid, p, texts, texts_it) or _item_errors(
            mrid, item, curated, texts, texts_it, leads, persons)
        if errors:
            failures.append(_failure(p, errors))
            continue
        op = {"op": "add_place", "id": oid, "eulogy": mrid, **item,
              "confidence": p["confidence"], "reasoning": p.get("reasoning", "")}
        who = _text_persons(persons, mrid)
        if len(who) > 1:
            op["persons"] = who
        review["operations"].append(op | {"decision": None, "edited": None})
        queued.add(oid)
        passed.add(_key(_failure(p, [])))
        added += 1
    review["operations"].sort(key=lambda o: o["id"])
    if final:
        new = {_key(f): f for f in failures}
        kept = [f for f in review.get("unqueued", []) if _key(f) not in new and _key(f) not in passed]
        review["unqueued"] = sorted(kept + list(new.values()), key=_key)
    return added, failures


def half_month(mm, half):
    return (f"{mm}01", f"{mm}15") if half == "a" else (f"{mm}16", f"{mm}31")


def brief(first, last, texts, texts_it, leads, persons, curated):
    out = []
    for mrid in sorted(m for m in texts if first <= m[3:7] <= last):
        lead = leads.get(mrid)
        out.append({"id": mrid, "la_text": texts[mrid], "it_text": texts_it.get(mrid, ""),
                    "opening": {k: lead[k] for k in ("la", "it", "role") if k in lead} if lead else None,
                    "persons": _text_persons(persons, mrid), "curated": curated.get(mrid, [])})
    return out


def apply(exported, curated, review, texts, texts_it, leads, persons):
    if exported.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    new_curated, new_review = copy.deepcopy(curated), copy.deepcopy(review)
    new_review.setdefault("rejected", [])
    errors, decided = [], set()
    for op in exported.get("operations", []):
        if op.get("op") != "add_place" or op.get("decision") is None:
            continue
        mrid = op["eulogy"]
        if op["decision"] == "reject":
            new_review["rejected"].append(op["id"])
        elif op["decision"] in ("accept", "edit"):
            text, text_it = texts.get(mrid, ""), texts_it.get(mrid, "")
            item = item_of(op, text, text_it)
            if op["decision"] == "edit":
                item = item_of(item | (op.get("edited") or {}), text, text_it)
            item_errors = _item_errors(mrid, item, new_curated, texts, texts_it, leads, persons)
            if item_errors:
                errors += [f"{op['id']}: {e}" for e in item_errors]
                continue
            new_curated.setdefault(mrid, []).append(item)
        else:
            errors.append(f"{op['id']}: unknown decision {op['decision']!r}")
            continue
        decided.add(op["id"])
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    new_review["operations"] = [o for o in new_review["operations"] if o["id"] not in decided]
    new_review["rejected"] = sorted(set(new_review["rejected"]))
    curated.clear()
    curated.update(dict(sorted(new_curated.items())))
    review.clear()
    review.update(new_review)
    return len(decided)


def _load(repo_root, texts_repo):
    entries = json.loads((repo_root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    places = json.loads((repo_root / "data" / "places.json").read_text(encoding="utf-8"))["places"]
    leads = {m: it for m, items in places.items() for it in items if it["source"] == "lead"}
    current = {e["id"] for e in entries if not e.get("deprecated")}
    texts = {m: t for m, t in load_texts(texts_repo).items() if m in current}
    texts_it = latin_texts(entries, load_texts(texts_repo, EDITION_IT))
    curated_path, review_path = repo_root / CURATED, repo_root / REVIEW
    curated = json.loads(curated_path.read_text(encoding="utf-8")) if curated_path.exists() else {}
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else new_changeset()
    return curated, review, texts, texts_it, leads, load_persons(repo_root)


def _write(repo_root, curated, review):
    (repo_root / CURATED).write_text(json.dumps(curated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review["generated_at"] = datetime.date.today().isoformat()
    (repo_root / REVIEW).write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    final = "--final" in argv
    argv = [a for a in argv if a != "--final"]
    cmds = {"brief": 4, "check": 3, "apply": 3}
    if not argv or argv[0] not in cmds or len(argv) < cmds[argv[0]]:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "brief":
        which, out, texts_repo = argv[1], Path(argv[2]), Path(argv[3])
        repo_root = Path(argv[4]) if len(argv) > 4 else Path(__file__).resolve().parent.parent
        if out.resolve().is_relative_to(repo_root.resolve()):
            sys.exit(f"{out}: a brief quotes the 2004 edition; write it outside the repository")
        if not re.fullmatch(r"(0[1-9]|1[0-2])[ab]", which):
            sys.exit(f"{which}: expected MMa or MMb (e.g. 01a)")
        curated, _, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
        records = brief(*half_month(which[:2], which[2]), texts, texts_it, leads, persons, curated)
        out.write_text(json.dumps({"batch": which, "eulogies": records}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"{len(records)} eulogies in {out}")
        return 0
    path, texts_repo = Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
    curated, review, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if cmd == "check":
        added, failures = check(doc["proposals"], curated, review, texts, texts_it, leads, persons, final=final)
        _write(repo_root, curated, review)
        for f in failures:
            print(f"{f['eulogy']} [{f['role']} {f['la']!r}]: " + "; ".join(f["errors"]))
        print(f"{added} queued; {len(failures)} failed; {len(review['operations'])} awaiting review")
        return 1 if failures else 0
    try:
        n = apply(doc, curated, review, texts, texts_it, leads, persons)
    except ValueError as e:
        sys.exit(str(e))
    _write(repo_root, curated, review)
    print(f"{n} decisions applied; {len(review['operations'])} awaiting review; "
          "now run scripts/extract_places.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
