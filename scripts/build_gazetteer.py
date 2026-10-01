#!/usr/bin/env python3
"""Resolve each place designation in data/places.json to a Wikidata item.

Each distinct `la` is resolved once to a Wikidata QID, a modern label and the
place's actual modern country. A place is `auto` only when exactly one
candidate passes every rule of the evidence bar; every other place goes to the
review change-set (crmedr-changeset/v1, op `resolve_place`) for
martyrology-frontend, and comes back through `apply` as `reviewed` or
`unresolved`. Places awaiting review have no key in data/gazetteer.json.
See docs/superpowers/specs/2026-10-01-gazetteer-design.md.

  data/gazetteer.json          {la: {wikidata, label, country, status, ...}}
  data/gazetteer_review.json   the review change-set
  docs/gazetteer-report.md     progress, text_says, country preview

Usage:
  python3 build_gazetteer.py propose [repo_root]              (network)
  python3 build_gazetteer.py verify-suggestions [repo_root]   (network)
  python3 build_gazetteer.py apply <exported.json> [repo_root]
  python3 build_gazetteer.py check [repo_root]

Standard library only. Reads no private sources.
"""

import datetime
import json
import re
import sys
from pathlib import Path

from gazetteer_text import ISO_CODES, fold, latin_nominatives, parse_italian
from wikidata import Wikidata, WikidataError

STATUSES = ["auto", "reviewed", "unresolved"]
ENTRY_KEYS = ["wikidata", "label", "country", "status", "text_says", "note"]
QID = re.compile(r"^Q[1-9]\d*$")
SCHEMA = "crmedr-changeset/v1"
MAX_CANDIDATES = 10
CONFIDENCES = {"high", "medium", "low"}
PUBLISHED_KEYS = ["wikidata", "label", "description", "country", "countries", "la", "p9314", "coords", "types"]


def place_index(places, entries):
    country = {e["id"]: e.get("country") for e in entries}
    index = {}
    for mr_id, items in places.items():
        for it in items:
            slot = index.setdefault(it["la"], {"it": set(), "occurrences": set(), "lead_countries": {}})
            if "it" in it:
                slot["it"].add(it["it"])
            slot["occurrences"].add(mr_id)
            if it["source"] == "lead":
                slot["lead_countries"][mr_id] = country.get(mr_id)
    return {la: {"it": sorted(v["it"]), "occurrences": sorted(v["occurrences"]),
                 "lead_countries": dict(sorted(v["lead_countries"].items()))}
            for la, v in index.items()}


def published(candidate, evidence):
    out = {k: candidate[k] for k in PUBLISHED_KEYS}
    out["evidence"] = evidence
    return out


def auto_entry(candidate):
    return {"wikidata": candidate["wikidata"], "label": candidate["label"],
            "country": candidate["country"], "status": "auto"}


def _checks(c, parsed, noms, claims, region_sets):
    it_ok = bool(parsed) and all(any(fold(h) in c["names_it"] for h in p["heads"]) for p in parsed)
    la_ok = c["p9314"] or any(fold(x) in noms for x in c["la"])
    country_problems = []
    if c["country"] is None:
        country_problems.append("the item has no single current country (" + ", ".join(c["countries"]) + ")")
    else:
        for claim in sorted(claims):
            if claim != c["country"]:
                country_problems.append(f"the Italian says {claim}, the item is in {c['country']}")
        for region, isos in region_sets.items():
            if c["country"] not in isos:
                country_problems.append(f"region '{region}' is not in {c['country']}")
    return {"it": it_ok, "la": la_ok, "country": not country_problems, "type": c["place_type"]}, country_problems


def evaluate(la, item, candidates, region_countries):
    parsed = [parse_italian(it) for it in item["it"]]
    claims = [{"country": iso, "it": it} for it, p in zip(item["it"], parsed) for iso in p["claims"]]
    regions = list(dict.fromkeys(r for p in parsed for r in p["regions"]))
    region_sets = {r: region_countries(r) for r in regions} if candidates else {}
    noms = latin_nominatives(la)
    scored = []
    for rank, c in enumerate(candidates):
        ok, problems = _checks(c, parsed, noms, {x["country"] for x in claims}, region_sets)
        evidence = [k for k in ("it", "la", "country", "type") if ok[k]] + (["p9314"] if c["p9314"] else [])
        scored.append((c, ok, problems, evidence, rank))
    scored.sort(key=lambda s: (-sum(s[1].values()), s[4]))
    passing = [s for s in scored if all(s[1].values())]
    failed = []
    if not parsed:
        failed.append("no Italian phrase")
    if not candidates:
        failed.append("no candidates found")
    if len(passing) > 1:
        failed.append(f"{len(passing)} candidates pass every rule")
    elif not passing and scored:
        named = [s for s in scored if s[1]["it"]]
        if parsed and not named:
            failed.append("no item has the Italian name of every variant")
        else:
            best = named[0] if named else scored[0]
            if not best[1]["la"]:
                failed.append("latin: no Latin label, alias or P9314 matches")
            failed += ["country: " + p for p in best[2]]
            if not best[1]["type"]:
                failed.append("type: the item is not a place")
    return {"auto": passing[0][0] if len(passing) == 1 else None,
            "candidates": [published(s[0], s[3]) for s in scored[:MAX_CANDIDATES]],
            "failed": failed, "claims": claims}


def validate(gazetteer, index, review_ops=()):
    errors = []
    for la, e in gazetteer.items():
        where = f"gazetteer {la!r}"
        if la not in index:
            errors.append(f"{where}: not a place in data/places.json (remove or re-key it)")
            continue
        if set(e) - set(ENTRY_KEYS):
            errors.append(f"{where}: unknown keys {sorted(set(e) - set(ENTRY_KEYS))}")
        status = e.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: status {status!r} not in {STATUSES}")
            continue
        if status == "unresolved":
            if e.get("wikidata") is not None:
                errors.append(f"{where}: unresolved needs wikidata null")
            if not e.get("note"):
                errors.append(f"{where}: unresolved needs a note")
            if "label" in e or "country" in e or "text_says" in e:
                errors.append(f"{where}: unresolved has no label, country or text_says")
            continue
        if not isinstance(e.get("wikidata"), str) or not QID.match(e["wikidata"]):
            errors.append(f"{where}: wikidata {e.get('wikidata')!r} is not a QID")
        if not e.get("label"):
            errors.append(f"{where}: missing label")
        if e.get("country") not in ISO_CODES:
            errors.append(f"{where}: country {e.get('country')!r} is not an ISO 3166-1 alpha-2 code")
        for ts in e.get("text_says", []):
            if set(ts) != {"country", "it"} or ts["it"] not in index[la]["it"] \
                    or ts["country"] not in ISO_CODES or ts["country"] == e.get("country"):
                errors.append(f"{where}: bad text_says {ts!r} (it must be one of the place's Italian "
                              f"phrases, country an ISO code other than the entry's)")
    for op in review_ops:
        if op.get("id") in gazetteer:
            errors.append(f"gazetteer {op['id']!r}: decided but also queued in data/gazetteer_review.json")
    return errors


def render_json(gazetteer):
    out = {
        "$comment": "Each place designation of data/places.json (key: the Latin as printed) resolved "
                    "to a Wikidata item, its label and the place's actual modern country (ISO 3166-1 "
                    "alpha-2). status: auto (passed the evidence bar), reviewed (decided by a person), "
                    "unresolved (no suitable item). text_says: the modern country a printed Italian "
                    "phrase names wrongly. Places awaiting review are absent. Generated by "
                    "scripts/build_gazetteer.py; see docs/canonicalization-report.md (Gazetteer). "
                    "Draft pending committee review.",
        "statuses": STATUSES,
        "places": {la: {k: e[k] for k in ENTRY_KEYS if k in e} for la, e in sorted(gazetteer.items())},
    }
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"


def gather_candidates(item, client):
    seen = {}
    for it in item["it"]:
        for head in parse_italian(it)["heads"]:
            for c in client.candidates(head):
                seen.setdefault(c["wikidata"], c)
    return list(seen.values())


def make_op(la, item, result, old):
    op = {"op": "resolve_place", "id": la, "la": la, "it": item["it"],
          "occurrences": item["occurrences"], "claims": result["claims"],
          "failed": result["failed"], "candidates": result["candidates"]}
    for key in ("suggested", "reasoning", "confidence"):
        if old and key in old:
            op[key] = old[key]
    op["decision"] = None
    op["edited"] = None
    return op


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/build_gazetteer.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": "2004", "registry": "data/places.json"},
            "operations": operations}


def _sort_ops(ops):
    return sorted(ops, key=lambda op: (-len(op.get("occurrences", [])), op["id"]))


def propose(gazetteer, review, index, client):
    ops = {op["id"]: op for op in review["operations"]}
    not_processed = []
    for la in sorted(index):
        if la in gazetteer:
            continue
        try:
            result = evaluate(la, index[la], gather_candidates(index[la], client), client.region_countries)
        except WikidataError as e:
            not_processed.append((la, str(e)))
            continue
        if result["auto"]:
            gazetteer[la] = auto_entry(result["auto"])
            ops.pop(la, None)
        else:
            ops[la] = make_op(la, index[la], result, ops.get(la))
    review["operations"] = _sort_ops(ops.values())
    review["generated_at"] = datetime.date.today().isoformat()
    return not_processed


def _cell(s):
    return str(s).replace("|", "\\|")


def render_report(gazetteer, index, review_ops, not_processed=()):
    counts = {s: sum(1 for e in gazetteer.values() if e["status"] == s) for s in STATUSES}
    text_says = [(la, e["country"], ts["country"]) for la, e in sorted(gazetteer.items())
                 for ts in e.get("text_says", [])]
    preview = [(mr_id, la, reg, gazetteer[la]["country"]) for la in sorted(index) if la in gazetteer
               and gazetteer[la].get("country") for mr_id, reg in index[la]["lead_countries"].items()
               if reg and reg != gazetteer[la]["country"]]
    lines = [
        "# Gazetteer report",
        "",
        "Generated by `scripts/build_gazetteer.py`. It holds place designations, IDs and "
        "Wikidata QIDs only.",
        "",
        "## Progress",
        "",
        f"{len(index)} distinct places; {len(gazetteer)} decided; {len(review_ops)} awaiting review"
        + (f"; {len(not_processed)} not processed (network)" if not_processed else "") + ".",
        "",
        "| Status | Places |",
        "| --- | --- |",
        *[f"| {s} | {counts[s]} |" for s in STATUSES],
        "",
        "## Awaiting review",
        "",
        "In `data/gazetteer_review.json`, most frequent first.",
        "",
        "| Place | Occurrences | Why not auto |",
        "| --- | --- | --- |",
        *[f"| {_cell(op['id'])} | {len(op.get('occurrences', []))} | {_cell('; '.join(op.get('failed', [])))} |"
          for op in review_ops],
        "",
        "## The text names another country (text_says)",
        "",
        "| Place | Country | The text says |",
        "| --- | --- | --- |",
        *([f"| {_cell(la)} | {c} | {t} |" for la, c, t in text_says] or ["| | | |"]),
        "",
        "## Preview: registry country differs from the opening place",
        "",
        "For the cross-check of sub-project 3. Registry conventions (e.g. `PS` for the Holy "
        "Land) show up here too.",
        "",
        "| ID | Place | Registry | Gazetteer |",
        "| --- | --- | --- | --- |",
        *([f"| `{m}` | {_cell(la)} | {r} | {g} |" for m, la, r, g in preview] or ["| | | | |"]),
    ]
    if not_processed:
        lines += ["", "## Not processed (network)", "",
                  *[f"- {_cell(la)}: {_cell(err)}" for la, err in not_processed]]
    return "\n".join(lines) + "\n"


def _read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_state(repo_root):
    data = repo_root / "data"
    places = json.loads((data / "places.json").read_text(encoding="utf-8"))["places"]
    entries = json.loads((data / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    gazetteer = _read_json(data / "gazetteer.json", {"places": {}})["places"]
    review = _read_json(data / "gazetteer_review.json", new_changeset([]))
    return gazetteer, review, place_index(places, entries)


def write_state(repo_root, gazetteer, review, index, not_processed=()):
    errors = validate(gazetteer, index, review["operations"])
    if errors:
        sys.exit("invalid gazetteer:\n" + "\n".join(errors))
    data = repo_root / "data"
    (data / "gazetteer.json").write_text(render_json(gazetteer), encoding="utf-8")
    (data / "gazetteer_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (repo_root / "docs" / "gazetteer-report.md").write_text(
        render_report(gazetteer, index, review["operations"], not_processed), encoding="utf-8")


def main(argv):
    if not argv or argv[0] not in {"propose", "verify-suggestions", "apply", "check"}:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    exported = None
    if cmd == "apply":
        if not rest:
            sys.exit(__doc__)
        exported, rest = Path(rest[0]), rest[1:]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    gazetteer, review, index = load_state(repo_root)
    client = Wikidata(repo_root / ".cache" / "wikidata")
    if cmd == "check":
        errors = validate(gazetteer, index, review["operations"])
        print("\n".join(errors) or f"ok: {len(gazetteer)} places decided, {len(review['operations'])} queued")
        return 1 if errors else 0
    if cmd == "propose":
        not_processed = propose(gazetteer, review, index, client)
        write_state(repo_root, gazetteer, review, index, not_processed)
        auto = sum(1 for e in gazetteer.values() if e["status"] == "auto")
        print(f"{len(index)} places; {auto} auto; {len(review['operations'])} awaiting review; "
              f"{len(not_processed)} not processed")
        return 1 if not_processed else 0
    raise NotImplementedError(cmd)  # verify-suggestions and apply: Task 5


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
