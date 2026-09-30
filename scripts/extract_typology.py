#!/usr/bin/env python3
"""Derive the typology of each current eulogy from the Latin editio altera 2004.

`typology` answers one question: what does the date of the elogium mark?
Values and rules are documented in docs/canonicalization-report.md
("Typology"). The copyrighted texts are read, never written: the outputs hold
IDs and marker words only.

  data/typology.json        {id: value} for every current ID
  docs/typology-report.md   review report (tags other than dies_natalis,
                            cross-references, multi-marker entries)

Usage:
  python3 extract_typology.py /path/to/martyrology-texts [repo_root]

Standard library only.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from extract_subjects import fold

VALUES = [
    "dies_natalis", "depositio", "translatio", "inventio",
    "dedicatio", "ordinatio", "celebratio", "commemoratio",
]

# Word lists are in fold() form (æ/œ → e, j → i).
HONORIFICS = {
    "sancti", "sancte", "sanctorum", "sanctarum",
    "beati", "beate", "beatorum", "beatarum", "domini",
}
# A relative pronoun ends the lead and starts the body of the elogium.
RELATIVES = {"qui", "que", "quod", "quorum", "quarum", "cuius", "quibus", "quos", "quas", "quem", "quam"}
LEAD_MAX_WORDS = 25
MARKERS = {
    "depositio": "depositio", "depositionis": "depositio",
    "translatio": "translatio", "translationis": "translatio",
    "inventio": "inventio", "inventionis": "inventio",
    "dedicatio": "dedicatio", "dedicationis": "dedicatio",
    "ordinatio": "ordinatio", "ordinationis": "ordinatio",
    "commemoratio": "commemoratio",
    "natalis": "dies_natalis", "passio": "dies_natalis", "transitus": "dies_natalis",
}
FEAST_HEADS = {"memoria", "festum", "sollemnitas"}
# Base forms reported by markers_in().
_BASE = {w: w.removesuffix("nis") if w.endswith("ionis") else w for w in MARKERS}
_BASE.update({w: w for w in FEAST_HEADS})

# Celebrations whose object is a mystery of the Lord, a Marian feast or
# title, the angels, the Chair of Peter, the Conversion of Paul, the Holy
# Cross or All Saints. Dedications, the translation of the Magi, All Souls and
# the ancestors of Christ are deliberately absent: their lead marker decides.
FEAST_IDS = {
    "mr:0101-maria-dei-genetrix",
    "mr:0103-nomen-iesu",
    "mr:0106-epiphania-domini",
    "mr:0125-conversio-sancti-pauli",
    "mr:0202-praesentatio-domini",
    "mr:0211-maria-de-lourdes",
    "mr:0222-cathedra-sancti-petri",
    "mr:0325-annuntiatio-domini",
    "mr:0513-maria-de-fatima",
    "mr:0531-visitatio-beatae-mariae-virginis",
    "mr:0716-maria-de-monte-carmelo",
    "mr:0806-transfiguratio-domini",
    "mr:0815-assumptio-beatae-mariae-virginis",
    "mr:0822-maria-regina",
    "mr:0908-nativitas-beatae-mariae-virginis",
    "mr:0912-nomen-mariae",
    "mr:0914-exaltatio-sanctae-crucis",
    "mr:0915-maria-perdolens",
    "mr:0929-michael-et-socii",
    "mr:1002-angeli-custodes",
    "mr:1007-maria-de-rosario",
    "mr:1101-omnes-sancti",
    "mr:1121-praesentatio-beatae-mariae-virginis",
    "mr:1208-conceptio-immaculata-beatae-mariae-virginis",
    "mr:1212-maria-de-guadalupe",
    "mr:1225-nativitas-domini",
}

# Hand decisions that override the rules, one per line with the reason.
TYPOLOGY_OVERRIDES = {}


def lead(words):
    out = []
    for w in words[:LEAD_MAX_WORDS]:
        if w in RELATIVES:
            break
        out.append(w)
    return out


def lead_marker(folded):
    words = lead(folded.split())
    for i, w in enumerate(words):
        if w in MARKERS and not (i and words[i - 1] in HONORIFICS):
            return w
    return None


def has_feast_head(folded):
    return any(w in FEAST_HEADS for w in lead(folded.split()))


def markers_in(folded):
    return sorted({_BASE[w] for w in folded.split() if w in _BASE})


def classify(mrid, folded, *, offday, feast_ids, overrides):
    if mrid in overrides:
        return overrides[mrid], "override"
    if mrid in offday:
        value, source = offday[mrid]
        return value, f"off-day:{source}"
    if mrid in feast_ids:
        return "celebratio", "feast"
    word = lead_marker(folded)
    if word:
        return MARKERS[word], f"marker:{word}"
    return "dies_natalis", "default"
