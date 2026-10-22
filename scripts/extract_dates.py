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
files differ from what it would write. `bounds` reads the 1630, 1749 and 1914 editions of
martyrology-api and writes data/edition_bounds.json (IDs and years, no text).
"""
import math

from persons_text import person_key

# What a eulogy's date marks, by its typology (data/typology.json); the others have no default.
BASIS_OF_TYPOLOGY = {"dies_natalis": "death", "depositio": "deposition", "translatio": "translation",
                     "dedicatio": "dedication"}
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
