#!/usr/bin/env python3
"""Copy the gazetteer onto the registry's places and derive each current entry's country.

Each place item of a current entry whose place the gazetteer resolves gets the
place's `wikidata`, `label`, `country` and the `text_says` claims of its own
Italian phrase. An entry's `country` is the country of its opening place when
the gazetteer resolves it, otherwise the value in data/countries_curated.json;
COUNTRY_CONVENTIONS (the Holy Land is PS) applies last. Deprecated entries are
untouched. No private source and no network are needed.

Usage:
  python3 scripts/registry_places.py [--check] [repo_root]

--check writes nothing and fails when the committed registry differs from what
the script would write (rerun it after build_gazetteer.py apply or after editing
data/gazetteer.json or data/countries_curated.json).
"""
import json
import sys
import tempfile
from pathlib import Path

import extract_registry as reg
from gazetteer_text import ISO_CODES, convention

PLACE_FIELDS = ("wikidata", "label", "country", "text_says")
CURATED = "data/countries_curated.json"


def _resolved(gazetteer, la):
    g = gazetteer.get(la)
    return g if g and g.get("wikidata") else None


def _lead(entry):
    return next((p for p in entry.get("places", []) if p["source"] == "lead"), None)


def has_resolved_lead(entry, gazetteer):
    lead = _lead(entry)
    return lead is not None and _resolved(gazetteer, lead["la"]) is not None


def _curated_country(value):
    return value["country"] if isinstance(value, dict) else value


def validate(entries, gazetteer, curated):
    errors = []
    current = {e["id"]: e for e in entries if not e.get("deprecated")}
    known = {e["id"] for e in entries}
    for mr_id in sorted(set(curated) - set(current)):
        errors.append(f"{mr_id}: in {CURATED} but {'deprecated' if mr_id in known else 'unknown'}")
    for mr_id, e in sorted(current.items()):
        if has_resolved_lead(e, gazetteer) and mr_id in curated:
            errors.append(f"{mr_id}: its opening place is resolved in the gazetteer; remove it from {CURATED}")
        elif not has_resolved_lead(e, gazetteer) and mr_id not in curated:
            errors.append(f"{mr_id}: no resolved opening place; add its country to {CURATED}")
    for mr_id, value in sorted(curated.items()):
        if isinstance(value, dict):
            if set(value) - {"country", "note"}:
                errors.append(f"{mr_id}: unexpected keys {sorted(set(value) - {'country', 'note'})}")
        elif value is not None and not isinstance(value, str):
            errors.append(f"{mr_id}: a value is a code, null or {{country, note}}")
            continue
        code = _curated_country(value)
        if code is not None and code not in ISO_CODES:
            errors.append(f"{mr_id}: {code!r} is not an ISO 3166-1 alpha-2 code")
    return errors


def _place(item, g):
    out = {k: v for k, v in item.items() if k not in PLACE_FIELDS}
    if g:
        out |= {"wikidata": g["wikidata"], "label": g["label"], "country": convention(g["country"])}
        claims = [c for c in g.get("text_says", []) if "it" in item and c["it"] == item["it"]]
        if claims:
            out["text_says"] = claims
    return out


def apply(entries, gazetteer, curated):
    errors = validate(entries, gazetteer, curated)
    if errors:
        raise ValueError("\n".join(errors))
    out = []
    for e in entries:
        if e.get("deprecated"):
            out.append(e)
            continue
        e = dict(e)
        if "places" in e:
            e["places"] = [_place(p, _resolved(gazetteer, p["la"])) for p in e["places"]]
        lead = _lead(e)
        code = (_resolved(gazetteer, lead["la"])["country"] if has_resolved_lead(e, gazetteer)
                else _curated_country(curated[e["id"]]))
        e["country"] = convention(code) if code else None
        out.append(e)
    return out


def load(repo_root):
    data = repo_root / "data"
    registry = json.loads((data / "martyrology_ids.json").read_text(encoding="utf-8"))
    gazetteer = json.loads((data / "gazetteer.json").read_text(encoding="utf-8"))["places"]
    curated = json.loads((repo_root / CURATED).read_text(encoding="utf-8"))["countries"]
    return registry["entries"], gazetteer, curated


def render(entries, repo_root):
    """Write the registry files for entries under repo_root (data/ and registry/)."""
    current = [e for e in entries if not e.get("deprecated")]
    deprecated = [e for e in entries if e.get("deprecated")]
    reg.write_json(current, deprecated, repo_root)
    reg.write_markdown(current, repo_root)


def _files(root):
    paths = [root / "data" / "martyrology_ids.json", *sorted((root / "registry").glob("*.md"))]
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in paths}


def main(argv):
    check = "--check" in argv
    rest = [a for a in argv if a != "--check"]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    entries, gazetteer, curated = load(repo_root)
    try:
        out = apply(entries, gazetteer, curated)
    except ValueError as e:
        print(f"invalid {CURATED}:\n{e}", file=sys.stderr)
        return 1
    if not check:
        render(out, repo_root)
        print(f"wrote data/martyrology_ids.json and registry/*.md "
              f"({sum(has_resolved_lead(e, gazetteer) for e in out if not e.get('deprecated'))} countries "
              f"from opening places, {len(curated)} curated)")
        return 0
    with tempfile.TemporaryDirectory() as d:
        render(out, Path(d))
        want, have = _files(Path(d)), _files(repo_root)
    stale = sorted(k for k in want if want[k] != have.get(k))
    changed = [n["id"] for n, o in zip(out, entries) if n != o]
    if stale:
        print("out of date: " + ", ".join(stale) + "\nentries: " + ", ".join(changed[:20])
              + "\nrun: python3 scripts/registry_places.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
