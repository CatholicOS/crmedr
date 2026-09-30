#!/usr/bin/env python3
"""Extract the places stated by each current eulogy (Latin editio altera 2004).

Each place is quoted exactly as printed (`la`) and given a role. Place
designations are factual and may be quoted; no other elogium text is stored.
The opening place is extracted automatically and its role comes from
data/typology.json; places in the body come from data/places_curated.json.
Documented in docs/canonicalization-report.md ("Places").

  data/places.json        {id: [places]} for current IDs with a place
  docs/places-report.md   review report and curation candidates

Usage:
  python3 extract_places.py /path/to/martyrology-texts [repo_root]

Standard library only.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROLES = ["death", "burial", "translation", "dedication", "cult", "birth", "ministry"]
ROLE_OF_TYPOLOGY = {
    "dies_natalis": "death",
    "depositio": "burial",
    "translatio": "translation",
    "inventio": "translation",
    "dedicatio": "dedication",
    "ordinatio": "ministry",
    "celebratio": "cult",
    "commemoratio": "cult",
}
MAX_WORDS = 12

# The opening place ends at the first stop word that is lowercase, or at a stop
# word that opens the text in any case. The print capitalizes a saint inside a
# place name ("in monasterio Sancti N.") but not the subject's honorific.
STOP_WORDS = {
    "sanctus", "sancta", "sancti", "sanctae", "sanctæ", "sanctorum", "sanctarum",
    "beatus", "beata", "beati", "beatae", "beatæ", "beatorum", "beatarum",
    "depositio", "translatio", "inventio", "dedicatio", "ordinatio",
    "natalis", "passio", "transitus", "commemoratio", "commemorantur",
    "memoria", "festum", "sollemnitas",
}
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿæœÆŒ]+")
TRIM = " ,;: "
# ", eodem die et anno" (on the same day and year) is not part of the place.
TIME_TAIL = re.compile(r",?\s*eodem die(?: et anno)?$")
BACK_REFS = {"Ibidem", "Item"}


def _base(c):
    b = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
    return b if len(b) == 1 else c


def base_copy(text):
    """Strip accents one character to one, keeping ligatures and case, so
    that offsets in the copy are offsets in the printed text."""
    return "".join(_base(c) for c in text)


def opening_phrase(text):
    copy = base_copy(text)
    for i, m in enumerate(WORD.finditer(copy)):
        w = m.group(0)
        if w.lower() in STOP_WORDS and (w[0].islower() or i == 0):
            phrase = text[:m.start()].strip(TRIM)
            break
    else:
        return None
    tail = TIME_TAIL.search(base_copy(phrase))
    if tail:
        phrase = phrase[:tail.start()].strip(TRIM)
    return phrase or None


def split_lead(phrase):
    copy = base_copy(phrase)
    if copy in BACK_REFS:
        return "back", None
    m = re.match(r"Item\b[\s,]*", copy)
    if m:
        return "place", phrase[m.end():]
    if re.match(r"Ibidem\b", copy):
        return "extend", phrase
    return "place", phrase
