#!/usr/bin/env python3
"""The date of each current eulogy: data/dates.json and docs/dates-report.md.

A date is the main year a eulogy is associated with (`year`), or a range (`from`, `to`) when one
year is too precise, with what it marks (`basis`) and where it comes from (`source`). It is
optional and only a signal (docs/superpowers/specs/2026-10-22-eulogy-dates-design.md). Sources, the
first that applies: data/dates_curated.json; the death dates of the eulogy's persons
(data/persons.json, data/person_items.json, data/person_details.json); the year of the oldest
edition that prints the eulogy (data/edition_bounds.json), as an upper bound.

Usage:
  python3 scripts/extract_dates.py [--check] [repo_root]
  python3 scripts/extract_dates.py bounds /path/to/martyrology-api [repo_root]

The first form reads only this repository; --check writes nothing and fails when the committed
files differ from what it would write. `bounds` reads the 1630 and 1914 editions of
martyrology-api and writes data/edition_bounds.json (IDs and years, no text).
"""
import collections
import json
import math
import sys
import tempfile
from pathlib import Path

from persons_text import person_key

# What a eulogy's date marks, by its typology (data/typology.json); the others have no default.
BASIS_OF_TYPOLOGY = {"dies_natalis": "death", "depositio": "deposition", "translatio": "translation",
                     "dedicatio": "dedication"}
# The editions older than 2004 whose IDs bound a eulogy's date, oldest first, with the year of the
# text printed. Not martyrologium_romanum_1749: its copy is a 1913 Mechelen printing that carries
# later additions (John Bosco, canonized 1934), so it bounds nothing. The English edition (Baltimore,
# 1916) translates the Roman copy of 1914.
EDITION_YEARS = (("martyrologium_romanum_1630", 1630), ("martyrologium_romanum_1914_en_unofficial", 1914))
BOUNDS = "data/edition_bounds.json"
CURATED = "data/dates_curated.json"
DATES = "data/dates.json"
REPORT = "docs/dates-report.md"
EDITION_2004 = "martyrologium_romanum_2004"
# A range of death dates wider than this many years likely holds a wrong person.
WIDE = 300
DATE_KEYS = ("year", "from", "to", "circa", "basis", "source", "note")


def life_range(died):
    """(first, last, circa) of a person_details life date; there is no year 0."""
    year, precision = died["year"], died.get("precision", "year")
    if precision == "decade":
        first, last = year, year + 9
    elif precision == "century":
        n = math.ceil(abs(year) / 100)
        first, last = (100 * (n - 1) + 1, 100 * n) if year > 0 else (-100 * n, -100 * (n - 1) - 1)
    else:
        first = last = year
    return first, last, bool(died.get("circa"))


def death_date(persons, items, details):
    """The date of a eulogy from the death dates of its persons with a decided item, or None."""
    ranges = []
    for p in persons:
        qid = (items.get(person_key(p)) or {}).get("wikidata")
        died = (details.get(qid) or {}).get("died") if qid else None
        if died:
            ranges.append(life_range(died))
    if not ranges:
        return None
    first, last = min(r[0] for r in ranges), max(r[1] for r in ranges)
    date = {"year": first} if first == last else {"from": first, "to": last}
    if any(r[2] for r in ranges):
        date["circa"] = True
    return date


def ordered(date):
    return {k: date[k] for k in DATE_KEYS if k in date}


def with_basis(date, typology):
    """date with the basis its typology implies, unless it has one."""
    basis = date.get("basis") or BASIS_OF_TYPOLOGY.get(typology)
    return ordered({**date, "basis": basis} if basis else date)


def edition_keys(api_root):
    """The eulogy IDs each older edition prints (martyrology-api data/editions/<edition>/MM.json).
    Raises ValueError unless every edition has its twelve month files (a wrong path, say)."""
    keys = {}
    for edition, _ in EDITION_YEARS:
        folder = api_root / "data" / "editions" / edition
        missing = [f"{m:02d}.json" for m in range(1, 13) if not (folder / f"{m:02d}.json").is_file()]
        if missing:
            raise ValueError(f"{folder}: not the 12 month files of {edition} (missing {', '.join(missing)})")
        ids = set()
        for f in sorted(folder.glob("[01][0-9].json")):
            for day in json.loads(f.read_text(encoding="utf-8")).values():
                if isinstance(day, dict):
                    ids |= set(day.get("elogia") or {})
        keys[edition] = ids
    return keys


def edition_bounds(entries, keys):
    """For each current entry, the year of the oldest edition that prints it or any ID its
    same_eulogy links reach, through deprecated IDs too (a cross-day ID included: the link says it
    is the same eulogy)."""
    links = {}
    for e in entries:
        for other in e.get("same_eulogy", []):
            links.setdefault(e["id"], set()).add(other)
            links.setdefault(other, set()).add(e["id"])
    out = {}
    for e in entries:
        if e.get("deprecated"):
            continue
        ids, todo = {e["id"]}, [e["id"]]
        while todo:
            for other in links.get(todo.pop(), ()):
                if other not in ids:
                    ids.add(other)
                    todo.append(other)
        year = next((y for edition, y in EDITION_YEARS if ids & keys.get(edition, set())), None)
        if year:
            out[e["id"]] = year
    return out


def death_dates(current_ids, persons, items, details):
    """The death-date date of each current eulogy that has one (before precedence)."""
    out = {}
    for mid in sorted(current_ids):
        date = death_date(persons.get(mid, []), items.get(mid, {}), details)
        if date:
            out[mid] = date
    return out


def latest(date):
    return date.get("year", date.get("to"))


def curated_errors(curated):
    """The curated dates that are not a date: unknown keys, year with a range, no year at all,
    a year that is not a nonzero integer, a range that runs backwards."""
    errors = []
    for mid, date in sorted(curated.items()):
        if date is None:
            continue
        unknown = sorted(set(date) - (set(DATE_KEYS) - {"source"}))
        if unknown:
            errors.append(f"{mid}: unknown keys {unknown}")
        elif "year" in date and ("from" in date or "to" in date):
            errors.append(f"{mid}: year together with from/to")
        elif not {"year", "from", "to"} & set(date):
            errors.append(f"{mid}: no year, from or to")
        elif any(type(date[k]) is not int or date[k] == 0 for k in ("year", "from", "to") if k in date):
            errors.append(f"{mid}: years are nonzero integers (no year 0)")
        elif "from" in date and "to" in date and date["from"] > date["to"]:
            errors.append(f"{mid}: from is later than to")
    return errors


def build_dates(current_ids, typology, persons, items, details, bounds, curated):
    """The date of each current eulogy: curated (null removes), else its persons' death dates,
    else the edition bound as `to`. A death later than the bound comes from a wrong person link
    (reported by checks()): the bound is written instead."""
    unknown = sorted(set(curated) - set(current_ids))
    if unknown:
        raise ValueError(f"{CURATED} names IDs that are not current: {', '.join(unknown)}")
    errors = curated_errors(curated)
    if errors:
        raise ValueError(f"{CURATED}:\n" + "\n".join(errors))
    wikidata = death_dates(current_ids, persons, items, details)
    out = {}
    for mid in sorted(current_ids):
        if mid in curated:
            date = curated[mid] and {**curated[mid], "source": "curated"}
        elif mid in wikidata and not (mid in bounds and latest(wikidata[mid]) > bounds[mid]):
            date = {**wikidata[mid], "source": "wikidata"}
        elif mid in bounds:
            date = {"to": bounds[mid], "source": "edition"}
        else:
            date = None
        if date:
            out[mid] = with_basis(date, typology.get(mid))
    return out


def checks(wikidata, bounds):
    """after_bound: a death later than the edition that already prints the eulogy (a likely wrong
    person link); wide: death dates more than WIDE years apart (a likely wrong person among several)."""
    after, wide = [], []
    for mid, date in sorted(wikidata.items()):
        last = latest(date)
        if mid in bounds and last > bounds[mid]:
            after.append((mid, last, bounds[mid]))
        if "from" in date and date["to"] - date["from"] > WIDE:
            wide.append((mid, date["from"], date["to"]))
    return {"after_bound": after, "wide": wide}


def shown(date):
    if "year" in date:
        return ("c. " if date.get("circa") else "") + str(date["year"])
    return f"{date.get('from', '…')}–{date.get('to', '…')}"


def report(dates, found, typology, current_ids):
    sources = collections.Counter(d["source"] for d in dates.values())
    bases = collections.Counter(d.get("basis", "(none)") for d in dates.values())
    undated = [mid for mid in sorted(current_ids) if typology.get(mid) in ("celebratio", "commemoratio")
               and dates.get(mid, {}).get("source") in (None, "edition")]
    lines = ["# Eulogy dates", "",
             "Generated by `scripts/extract_dates.py` "
             "(docs/superpowers/specs/2026-10-22-eulogy-dates-design.md). Do not edit.", "",
             f"{len(dates)} of {len(current_ids)} current eulogies have a date.", "",
             "| Source | Eulogies |", "|---|---|",
             *[f"| {k} | {v} |" for k, v in sorted(sources.items())], "",
             "| Basis | Eulogies |", "|---|---|",
             *[f"| {k} | {v} |" for k, v in sorted(bases.items())], "",
             "## Death after the edition bound", "",
             "A subject died after an edition that already prints the eulogy: the person link is "
             "likely wrong, and the eulogy's date is the edition bound instead.", "",
             "| Eulogy | Death | Edition |", "|---|---|---|",
             *[f"| {m} | {y} | {b} |" for m, y, b in found["after_bound"]], "",
             f"## Death dates more than {WIDE} years apart", "",
             "| Eulogy | From | To |", "|---|---|---|",
             *[f"| {m} | {a} | {b} |" for m, a, b in found["wide"]], "",
             "## Feasts and commemorations to date", "",
             f"`celebratio` and `commemoratio` eulogies with no date, or only an edition bound "
             f"({len(undated)}): candidates for `{CURATED}`. A eulogy with no bound is only absent "
             f"from the 1630 and 1914 editions, which says nothing about its date.", "",
             *[f"- {m}" + (f" (before {dates[m]['to']})" if m in dates else "") for m in undated], ""]
    return "\n".join(lines)


def write_json(path, comment, key, value):
    path.write_text(json.dumps({"$comment": comment, key: dict(sorted(value.items()))},
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def bounds_main(api_root, repo_root):
    entries = json.loads((repo_root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    try:
        keys = edition_keys(api_root)
    except ValueError as e:
        print(f"{e}\nnothing written", file=sys.stderr)
        return 1
    bounds = edition_bounds(entries, keys)
    write_json(repo_root / BOUNDS,
               "The year of the oldest edition before 2004 (1630, 1914) that prints each current "
               "eulogy or one of its same_eulogy IDs: an upper bound of its date. Generated by "
               "scripts/extract_dates.py bounds from martyrology-api's editions.", "bounds", bounds)
    counts = {y: sum(1 for v in bounds.values() if v == y) for _, y in EDITION_YEARS}
    print(f"wrote {BOUNDS}: {len(bounds)} bounds {counts}")
    return 0


def _read(repo_root, path):
    return json.loads((repo_root / path).read_text(encoding="utf-8"))


def render(repo_root, out_root):
    """Write data/dates.json and docs/dates-report.md under out_root from repo_root's inputs."""
    entries = _read(repo_root, "data/martyrology_ids.json")["entries"]
    current_ids = {e["id"] for e in entries if not e.get("deprecated")}
    typology = _read(repo_root, "data/typology.json")["typology"]
    persons = _read(repo_root, "data/persons.json")["editions"][EDITION_2004]
    items = _read(repo_root, "data/person_items.json")["persons"]
    details = _read(repo_root, "data/person_details.json")
    bounds = _read(repo_root, BOUNDS)["bounds"]
    curated = _read(repo_root, CURATED)["dates"]
    dates = build_dates(current_ids, typology, persons, items, details, bounds, curated)
    found = checks(death_dates(current_ids, persons, items, details), bounds)
    (out_root / "data").mkdir(parents=True, exist_ok=True)
    (out_root / "docs").mkdir(parents=True, exist_ok=True)
    write_json(out_root / DATES,
               "The optional date of each current eulogy: year, or a range from/to (either may be "
               "open); circa; basis (death, deposition, translation, dedication, event); source "
               "(curated, wikidata: its persons' death dates, edition: the oldest edition before 2004 "
               "that prints it, as an upper bound; estimate). Years are negative before Christ. "
               "Generated by scripts/extract_dates.py; corrections go in data/dates_curated.json.",
               "dates", dates)
    (out_root / REPORT).write_text(report(dates, found, typology, current_ids), encoding="utf-8")
    return dates, found


def main(argv):
    if argv[:1] == ["bounds"]:
        if len(argv) < 2:
            print(__doc__, file=sys.stderr)
            return 2
        repo_root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
        return bounds_main(Path(argv[1]), repo_root)
    check = "--check" in argv
    rest = [a for a in argv if a != "--check"]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    try:
        if not check:
            dates, found = render(repo_root, repo_root)
            sources = collections.Counter(d["source"] for d in dates.values())
            print(f"wrote {DATES} ({len(dates)} dates: {dict(sorted(sources.items()))}) and {REPORT} "
                  f"({len(found['after_bound'])} after the edition bound, {len(found['wide'])} wide)")
            return 0
        with tempfile.TemporaryDirectory() as d:
            render(repo_root, Path(d))
            stale = [p for p in (DATES, REPORT)
                     if not (repo_root / p).exists() or (Path(d) / p).read_bytes() != (repo_root / p).read_bytes()]
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    if stale:
        print("out of date: " + ", ".join(stale) + "\nrun: python3 scripts/extract_dates.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
