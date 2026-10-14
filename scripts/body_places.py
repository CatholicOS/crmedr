#!/usr/bin/env python3
"""Body places: check the proposal pass into the add_place change-set, and apply its review.

A body place is a place a eulogy names outside its opening place, with its role
(see ROLES in extract_places.py). Proposals come from a model reading the texts;
nothing is decided until a person reviews it in martyrology-frontend.

Usage:
  python3 scripts/body_places.py check <proposals.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py apply <exported.json> /path/to/martyrology-texts [repo_root]

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

from extract_places import CURATED_KEYS, EDITION_IT, load_persons, validate_curated
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


def item_of(p):
    """The curated item of a proposal or decision. A first printing and a first person
    of a name are the default, so occurrence, occurrence_it and n of 1 are left out:
    one item, one op id."""
    return {k: p[k] for k in CURATED_KEYS
            if k in p and p[k] is not None and not (k in ("occurrence", "occurrence_it", "n") and p[k] == 1)}


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
    p = item_of(p) | {"eulogy": p["eulogy"]}
    parts = [p["eulogy"], p["role"], p["la"]]
    if p.get("occurrence"):
        parts.append(str(p["occurrence"]))
    if p.get("person"):
        parts.append(p["person"])
        if p.get("n"):
            parts.append(str(p["n"]))
    return "#".join(parts)


def _item_errors(mrid, item, curated, texts, texts_it, leads, persons):
    """validate_curated on the eulogy's existing items plus this one; only errors this item adds."""
    others = curated.get(mrid, [])
    base = set(validate_curated({mrid: others}, texts, set(texts), leads, texts_it, persons)) if others else set()
    return [e for e in validate_curated({mrid: others + [item]}, texts, set(texts), leads, texts_it, persons)
            if e not in base]


def check(proposals, curated, review, texts, texts_it, leads, persons):
    queued = {o["id"] for o in review["operations"]}
    rejected = set(review.get("rejected", []))
    done = {op_id(dict(it, eulogy=m)) for m, items in curated.items() for it in items}
    failures, added = [], 0
    for p in proposals:
        mrid = p.get("eulogy")
        if mrid not in texts:
            failures.append(f"{mrid}: not a current ID with a Latin text")
            continue
        if p.get("confidence") not in CONFIDENCE:
            failures.append(f"{mrid}: confidence must be one of {', '.join(CONFIDENCE)}")
            continue
        item = item_of(p)
        if not {"role", "la"} <= set(item):
            failures.append(f"{mrid}: a proposal needs role and la")
            continue
        oid = op_id(dict(item, eulogy=mrid))
        if oid in queued or oid in rejected or oid in done:
            continue
        quoted = reasoning_errors(mrid, p, texts, texts_it)
        if quoted:
            failures += quoted
            continue
        errors = _item_errors(mrid, item, curated, texts, texts_it, leads, persons)
        if errors:
            failures += errors
            continue
        review["operations"].append({"op": "add_place", "id": oid, "eulogy": mrid, **item,
                                     "confidence": p["confidence"], "reasoning": p.get("reasoning", ""),
                                     "decision": None, "edited": None})
        queued.add(oid)
        added += 1
    review["operations"].sort(key=lambda o: o["id"])
    return added, failures


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
            item = item_of(op)
            if op["decision"] == "edit":
                item = item_of(item | (op.get("edited") or {}))
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
    if len(argv) < 3 or argv[0] not in ("check", "apply"):
        sys.exit(__doc__)
    cmd, path, texts_repo = argv[0], Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
    curated, review, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if cmd == "check":
        added, failures = check(doc["proposals"], curated, review, texts, texts_it, leads, persons)
        _write(repo_root, curated, review)
        print("\n".join(failures))
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
