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

Groups: `propose` reads P361 (part of) and P463 (member of) from the items of each "several"
eulogy's commemorated persons (data/person_items.json); an item two or more of them, and at least
half, point at is asked of Jev (is it the group the eulogy's clause commemorates?) and, at JEV_MIN or
above, written as an `auto` suggestion, for eulogies with no entry yet. `members` lists, for each
eulogy with a group item, the commemorated persons whose item is not a member of it (no P361 or P463
to it, and not in its P527), in data/eulogy_item_members.json. Both need network access (Wikidata
cached in .cache/wikidata/, Jev in .cache/typesafe/); `report` writes docs/eulogy-items-report.md
offline from the files.

Usage:
  build_eulogy_items.py check [repo_root]                                validate (offline)
  build_eulogy_items.py propose /path/to/martyrology-texts [IDS] [repo_root]   suggest groups (network)
  build_eulogy_items.py members [repo_root]                              the membership check (network)
  build_eulogy_items.py report [--check] [repo_root]                     the report (offline)
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

EDITION = "martyrologium_romanum_2004"
ITEMS = Path("data/eulogy_items.json")
HAND_TYPOLOGIES = ("celebratio", "dedicatio", "translatio")
KINDS = ("group", "feast", "dedication", "translation")
STATUSES = ("auto", "reviewed", "unresolved")
QID = re.compile(r"^Q[1-9]\d*$")
MEMBERS = Path("data/eulogy_item_members.json")
REPORT = Path("docs/eulogy-items-report.md")
JEV_MIN = 0.5  # Jev's probability for an auto group suggestion
QUESTION = ("Is the Wikidata item `group` the group of saints that `clause`, from a eulogy of the Roman "
            "Martyrology, commemorates? Weigh the group's label, description and members against the "
            "persons, places and events the clause names. A larger or different group that only shares "
            "some members is not the same group.")
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


def _ids(raw, prop):
    out = []
    for st in (raw or {}).get("claims", {}).get(prop, []):
        v = st.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.append(v["id"])
    return out


def group_links(raw):
    """The QIDs an item's P361 (part of) and P463 (member of) point at."""
    return set(_ids(raw, "P361")) | set(_ids(raw, "P463"))


def suggest_group(person_qids, entities):
    """The item that two or more of the persons, and at least half, point at by P361 or P463; None
    when there is no such item or two tie."""
    counts = Counter(g for q in person_qids for g in group_links(entities.get(q)))
    if not counts:
        return None
    (best, n), *rest = counts.most_common()
    if n < 2 or 2 * n < len(person_qids) or (rest and rest[0][1] == n):
        return None
    return best


def non_members(group_qid, person_qids, entities):
    """The persons whose item is not a member of the group: no P361/P463 to it, not in its P527."""
    listed = set(_ids(entities.get(group_qid), "P527"))
    return [q for q in person_qids if q not in listed and group_qid not in group_links(entities.get(q))]


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


def person_qids(repo_root):
    """{eulogy ID: the QIDs of its commemorated persons}, persons without an item left out."""
    repo_root = Path(repo_root)
    persons = json.loads((repo_root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
    items = json.loads((repo_root / "data" / "person_items.json").read_text(encoding="utf-8"))["persons"]
    out = {}
    for mrid, ps in persons.items():
        decided = items.get(mrid) or {}
        keys = [p["name"] + (f"#{p['n']}" if p.get("n") else "") for p in commemorated(ps)]
        out[mrid] = [decided[k]["wikidata"] for k in keys if (decided.get(k) or {}).get("wikidata")]
    return out


def report(items, cls, members):
    """docs/eulogy-items-report.md: counts, the non-members of each group, the eulogies to decide."""
    by_class = Counter(cls.values())
    by_kind = Counter(x.get("kind") or "none" for x in items.values())
    by_status = Counter(x.get("status") for x in items.values())
    lines = ["# Eulogy items report", "",
             "Generated by `scripts/build_eulogy_items.py report` from `data/eulogy_items.json` and "
             "`data/eulogy_item_members.json`. Design: `docs/superpowers/specs/2026-10-31-eulogy-items-design.md`.",
             "", "| Class | Eulogies |", "| --- | --- |"]
    lines += [f"| {c} | {by_class[c]} |" for c in ("single", "several", "hand")]
    lines += ["", "| Kind | Entries |", "| --- | --- |"] + [f"| {k} | {n} |" for k, n in sorted(by_kind.items())]
    lines += ["", "| Status | Entries |", "| --- | --- |"] + [f"| {k} | {n} |" for k, n in sorted(by_status.items())]
    flagged = {m: x for m, x in sorted(members.items()) if x.get("non_members")}
    lines += ["", f"## Persons not members of their eulogy's group ({len(flagged)} eulogies)", "",
              "Each is a candidate wrong person link, or a statement missing on Wikidata.", ""]
    lines += [f"- `{m}` ({x['group']}): " + ", ".join(x["non_members"]) for m, x in flagged.items()] or ["None."]
    for c, title in (("hand", "Eulogies to decide by hand"), ("several", "Eulogies of several persons with no entry")):
        todo = sorted(m for m, k in cls.items() if k == c and m not in items)
        lines += ["", f"## {title} ({len(todo)})", ""] + ([" ".join(f"`{m}`" for m in todo)] if todo else ["None."])
    return "\n".join(lines) + "\n"


def _write_items(repo_root, items):
    path = Path(repo_root) / ITEMS
    doc = {"$comment": COMMENT, "items": dict(sorted(items.items()))}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_members(repo_root):
    path = Path(repo_root) / MEMBERS
    return json.loads(path.read_text(encoding="utf-8"))["members"] if path.exists() else {}


def _fold(s):
    s = (s or "").replace("æ", "ae").replace("œ", "oe").replace("Æ", "Ae")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def clause(text, name):
    """At most 400 characters of the Latin around the name's first five letters."""
    stem = _fold(name.split()[0])[:5]
    i = _fold(text).find(stem) if stem else -1
    a = max(0, i - 160) if i >= 0 else 0
    return (text or "")[a:a + 400]


def _label(raw):
    for lang in ("en", "it", "la", "mul"):
        if lang in raw.get("labels", {}):
            return raw["labels"][lang]["value"]
    return None


def _texts(texts_root):
    out = {}
    for m in range(1, 13):
        out.update(json.loads((Path(texts_root) / "data" / "editions" / EDITION / f"{m:02d}.json").read_text(encoding="utf-8")))
    return out


def propose(repo_root, texts_root, only=None, wd=None, client=None):
    """Write `auto` group suggestions for "several" eulogies with no entry; returns (written, doubted)."""
    import mentions_jev as mj
    import wikidata
    repo_root = Path(repo_root)
    wd = wd or wikidata.Wikidata(repo_root / ".cache" / "wikidata")
    client = client or mj.TypeSafe(mj.api_key(), repo_root / ".cache" / "typesafe")
    cls, items, pq = classes(repo_root), load(repo_root), person_qids(repo_root)
    persons = json.loads((repo_root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
    texts = _texts(texts_root)
    todo = [m for m, c in cls.items() if c == "several" and m not in items and (only is None or m in only)]
    ents = wd._entities(sorted({q for m in todo for q in pq.get(m, [])}))
    groups = {m: suggest_group(pq.get(m, []), ents) for m in todo}
    gents = wd._entities(sorted({g for g in groups.values() if g}))
    member_ents = wd._entities(sorted({q for g in gents.values() for q in _ids(g, "P527")}))
    written, doubted = [], []
    for m, g in groups.items():
        if not g or g not in gents:
            continue
        name = commemorated(persons[m])[0]["name"]
        state = {"group": {"label": _label(gents[g]),
                           "description": next((gents[g].get("descriptions", {}).get(l, {}).get("value")
                                                for l in ("en", "it", "la") if l in gents[g].get("descriptions", {})), None),
                           "members": [_label(member_ents[q]) for q in _ids(gents[g], "P527") if q in member_ents][:12]},
                 "clause": clause(texts.get(m), name), "day": f"{m[3:5]}-{m[5:7]}"}
        body = {"model": mj.MODEL, "state": state, "questions": {"same": {"type": "noul", "instructions": QUESTION}}}
        p = ((client.ask(body) or {}).get("answers") or {}).get("same", {}).get("noul")
        if p is not None and p >= JEV_MIN:
            items[m] = {"wikidata": g, "kind": "group", "status": "auto"}
            written.append((m, g, p))
        else:
            doubted.append((m, g, p))
    _write_items(repo_root, items)
    return written, doubted


def members(repo_root, wd=None):
    """Write data/eulogy_item_members.json: the non-members of each eulogy's group item."""
    import wikidata
    repo_root = Path(repo_root)
    wd = wd or wikidata.Wikidata(repo_root / ".cache" / "wikidata")
    items, pq = load(repo_root), person_qids(repo_root)
    groups = {m: x["wikidata"] for m, x in items.items() if x.get("kind") == "group" and x.get("wikidata")}
    ents = wd._entities(sorted(set(groups.values()) | {q for m in groups for q in pq.get(m, [])}))
    out = {m: {"group": g, "non_members": non_members(g, pq.get(m, []), ents)} for m, g in sorted(groups.items())}
    doc = {"$comment": "For each eulogy with a group item (data/eulogy_items.json), the QIDs of its commemorated "
                       "persons whose item is not a member of the group. Written by "
                       "scripts/build_eulogy_items.py members (network).", "members": out}
    (repo_root / MEMBERS).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv):
    cmds = {"check", "propose", "members", "report"}
    if not argv or argv[0] not in cmds:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    here = Path(__file__).resolve().parent.parent
    if cmd == "propose":
        if not rest:
            print(__doc__, file=sys.stderr)
            return 2
        texts_root, rest = rest[0], rest[1:]
        only = set(rest.pop(0).split(",")) if rest and rest[0].startswith("mr:") else None
        written, doubted = propose(Path(rest[0]) if rest else here, texts_root, only)
        for m, g, p in written:
            print(f"auto  {m} {g} {p:.2f}")
        for m, g, p in doubted:
            print(f"doubt {m} {g} {p}")
        return 0
    check_only = bool(rest) and rest[0] == "--check"
    rest = rest[1:] if check_only else rest
    repo_root = Path(rest[0]) if rest else here
    if cmd == "members":
        members(repo_root)
        return 0
    cls = classes(repo_root)
    if cmd == "check":
        errors = check(load(repo_root), set(cls), cls)
        for e in errors:
            print(e, file=sys.stderr)
        return 1 if errors else 0
    text = report(load(repo_root), cls, _load_members(repo_root))
    path = repo_root / REPORT
    if check_only:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            print(f"out of date: {REPORT}; run python3 scripts/build_eulogy_items.py report", file=sys.stderr)
            return 1
        return 0
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
