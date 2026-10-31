#!/usr/bin/env python3
"""The optional Wikidata item of each eulogy that does not commemorate a single person: a group
of saints, a feast, a dedicated church, a translation of relics (data/eulogy_items.json, curated).

A person is commemorated unless data/persons.json (the Latin 2004 edition) gives it the role
`mentioned`. A eulogy commemorating exactly one person is single-person, unless its typology is
celebratio, dedicatio or translatio: it gets no item, since its person item already says what it
commemorates (curator, 2026-10-31), and an item there needs a curator `note`. A eulogy commemorating
none, or one under those typologies, is decided by hand ("hand"); one commemorating several may
get a group item ("several"). A Marian title whose mention links the title item is recorded as
{"wikidata": null, "kind": null, "status": "reviewed", "note": "the mention links the title"}.
extract_registry.py copies each item onto its registry entry as `item`.
Design: docs/superpowers/specs/2026-10-31-eulogy-items-design.md.

Usage:
  build_eulogy_items.py check [repo_root]     validate data/eulogy_items.json (offline)
"""
import json
import re
import sys
from pathlib import Path

EDITION = "martyrologium_romanum_2004"
ITEMS = Path("data/eulogy_items.json")
HAND_TYPOLOGIES = ("celebratio", "dedicatio", "translatio")
KINDS = ("group", "feast", "dedication", "translation")
STATUSES = ("auto", "reviewed", "unresolved")
QID = re.compile(r"^Q[1-9]\d*$")
COMMENT = ("The optional Wikidata item of each current eulogy that does not commemorate a single person "
           "(a group, a feast, a dedicated church, a translation), by eulogy ID: wikidata, kind (group, "
           "feast, dedication, translation), status (auto, reviewed, unresolved) and an optional note. "
           "Curated; scripts/build_eulogy_items.py validates it and extract_registry.py copies it onto "
           "the registry as `item`.")


def commemorated(persons):
    """The persons a eulogy commemorates: all but those with the role `mentioned`."""
    return [p for p in persons if p.get("role") != "mentioned"]


def eulogy_class(persons, typology):
    """"single", "hand" or "several" (see the module docstring)."""
    n = len(commemorated(persons))
    if n >= 2:
        return "several"
    if n == 0 or typology in HAND_TYPOLOGIES:
        return "hand"
    return "single"


def check(items, current_ids, classes):
    """Error strings for data/eulogy_items.json's `items`, each naming its eulogy ID."""
    errors = []
    for mrid, x in sorted(items.items()):
        if mrid not in current_ids:
            errors.append(f"{mrid}: not a current eulogy ID (renamed or deprecated?)")
            continue
        status, qid, kind = x.get("status"), x.get("wikidata"), x.get("kind")
        if status not in STATUSES:
            errors.append(f"{mrid}: status {status!r} is not one of {', '.join(STATUSES)}")
        if qid is not None and not (isinstance(qid, str) and QID.match(qid)):
            errors.append(f"{mrid}: wikidata {qid!r} is not a QID")
        if qid is None:
            if status == "auto":
                errors.append(f"{mrid}: an auto suggestion needs a QID")
            if not x.get("note"):
                errors.append(f"{mrid}: an entry without an item needs a note")
        elif kind not in KINDS:
            errors.append(f"{mrid}: kind {kind!r} is not one of {', '.join(KINDS)}")
        if qid is not None and classes.get(mrid) == "single" and not x.get("note"):
            errors.append(f"{mrid}: a single-person eulogy gets no item without a curator note")
    return errors


def load(repo_root):
    """The `items` of data/eulogy_items.json; {} when the file is missing."""
    path = Path(repo_root) / ITEMS
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else {}


def classes(repo_root):
    """{current eulogy ID: its class}, from data/persons.json and data/typology.json."""
    repo_root = Path(repo_root)
    persons = json.loads((repo_root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
    typology = json.loads((repo_root / "data" / "typology.json").read_text(encoding="utf-8"))["typology"]
    registry = json.loads((repo_root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))
    return {e["id"]: eulogy_class(persons.get(e["id"], []), typology.get(e["id"]))
            for e in registry["entries"] if not e.get("deprecated")}


def main(argv):
    if not argv or argv[0] != "check":
        print(__doc__, file=sys.stderr)
        return 2
    repo_root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    cls = classes(repo_root)
    errors = check(load(repo_root), set(cls), cls)
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
