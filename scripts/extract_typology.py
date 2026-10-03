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

# extract_typology.py and extract_places.py read the current IDs from the
# registry, and extract_places.py reads data/typology.json, so after an ID
# change everything is regenerated in this order.
RECOVERY = (
    "To recover: move data/typology.json aside, move data/places.json aside, "
    "run scripts/extract_registry.py, then scripts/extract_typology.py, "
    "then scripts/extract_places.py, then scripts/extract_registry.py again."
)

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
# Cross or All Saints. Dedications (incl. the Archangels, kept "in die
# dedicationis"), the translation of the Magi, All Souls and the ancestors of
# Christ are deliberately absent: the dedication-day rule or their lead marker
# decides.
FEAST_IDS = {
    "mr:0101-maria-dei-genetrix",
    "mr:0103-nomen-iesu",
    "mr:0106-epiphania-domini",
    "mr:0125-conversio-pauli-apostoli",
    "mr:0202-praesentatio-domini",
    "mr:0211-maria-de-lourdes",
    "mr:0222-cathedra-petri-apostoli",
    "mr:0325-annuntiatio-domini",
    "mr:0501-ioseph",  # Joseph the Worker: a title feast, not an event
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
    "mr:1002-angeli-custodes",
    "mr:1007-maria-de-rosario",
    "mr:1101-omnes-sancti",
    "mr:1121-praesentatio-beatae-mariae-virginis",
    "mr:1208-conceptio-immaculata-beatae-mariae-virginis",
    "mr:1212-maria-de-guadalupe",
    "mr:1225-nativitas-domini",
}

# Hand decisions that override the rules, one per line with the reason.
TYPOLOGY_OVERRIDES = {
    # Printed only in the CEI edition, so there is no Latin 2004 text to read the
    # typology from; values as tagged from the former Latin texts.
    "mr:0712-proclus-et-hilarion": "dies_natalis",
    "mr:0825-eusebius-et-socii": "depositio",
    "mr:0709-maria-a-iesu-crucifixo": "dies_natalis",
    # Unnumbered lead memorials that open with the name, not "Memoria", so the
    # cross-reference from the dies natalis finds no candidate.
    "mr:0807-xystus-ii-et-socii": "celebratio",  # passio at 0806 ("memoria cras")
    "mr:1019-ioannes-de-brebeuf-et-socii": "celebratio",  # group memorial; deaths on other days
    "mr:1116-gertrudis-magna": "celebratio",  # natalis at 1117 ("memoria pridie")
    # The text states, after the lead, that the burial is kept on this day.
    "mr:0121-agnes": "depositio",
    "mr:1014-callistus-i": "depositio",
    "mr:1123-clemens-i": "depositio",
    "mr:0512-pancratius": "depositio",
    # Died in April; the text says he is honoured on the day he took up his see.
    "mr:1207-ambrosius": "ordinatio",
    # A solemnity of his nativity: the date marks the birth, not the death.
    "mr:0624-ioannes-baptista": "celebratio",
}


# An honorific right after one of these nouns is part of a place name
# ("in monasterio sancti N.", "in vico sancti N."), not the subject's.
PLACE_NOUNS = {
    "monasterio", "monasterium", "cenobio", "cenobium", "ecclesia", "ecclesiam",
    "basilica", "basilicam", "laura", "oppido", "vico", "pago", "loco", "fano",
    "fanum", "burgo", "burgi", "insula", "castro", "castello", "cella", "eremo",
    "urbe", "civitate", "porta", "via", "monte", "montem", "colle", "collem",
}
# A marker right after these names the event of a neighbouring day
# ("postridie dedicationis"), not of this one.
NEIGHBOUR_DAYS = {"postridie", "pridie"}


def lead(words):
    # A relative pronoun before the subject's honorific belongs to the place
    # phrase ("via quae ... dicitur", "in monasterio sancti N., quod
    # condiderat"), not to the body.
    out, seen_honorific = [], False
    for i, w in enumerate(words[:LEAD_MAX_WORDS]):
        if w in RELATIVES and seen_honorific:
            break
        if w in HONORIFICS and not (i and words[i - 1] in PLACE_NOUNS):
            seen_honorific = True
        out.append(w)
    return out


def lead_marker(folded):
    words = lead(folded.split())
    for i, w in enumerate(words):
        prev = words[i - 1] if i else None
        if w in MARKERS and prev not in HONORIFICS and prev not in NEIGHBOUR_DAYS:
            return w
    return None


def has_feast_head(folded):
    return any(w in FEAST_HEADS for w in lead(folded.split()))


# Words naming an event other than death; used to surface default-tagged
# entries that mention one outside the lead.
EVENT_WORDS = {w for w, v in MARKERS.items() if v not in ("dies_natalis",)}


def event_words_outside_lead(folded):
    words = folded.split()
    rest = words[len(lead(words)):]
    return sorted({_BASE[w] for w in rest if w in EVENT_WORDS})


def markers_in(folded):
    return sorted({_BASE[w] for w in folded.split() if w in _BASE})


# The text says this date is the anniversary of a church's dedication
# ("in die dedicationis", "die anniversaria dedicationis"), even when the
# elogium is a saint's feast. "Postridie dedicationis" (the day after) is not.
DEDICATION_DAY = re.compile(r"\bdie (?:anniversaria )?dedicationis\b")


def classify(mrid, folded, *, offday, feast_ids, overrides):
    if mrid in overrides:
        return overrides[mrid], "override"
    if DEDICATION_DAY.search(" ".join(folded.split())):
        return "dedicatio", "dedication-day"
    if mrid in offday:
        value, source = offday[mrid]
        return value, f"off-day:{source}"
    if mrid in feast_ids:
        return "celebratio", "feast"
    word = lead_marker(folded)
    if word:
        return MARKERS[word], f"marker:{word}"
    return "dies_natalis", "default"


# Off-day memorials: an elogium on the dies natalis points to the day its
# memorial is celebrated ("cuius memoria cras agitur", "... die vigesima
# quarta ianuarii ..."). That target elogium marks a liturgical celebration,
# unless the cross-reference names the event of that day.
XREF = re.compile(r"\b(?:cuius|eius|quorum|earum)\s+(?:memoria|festum|sollemnitas)\b")
XREF_WINDOW = 12
RELATIVE_DAYS = {
    "cras": 1, "crastina": 1, "postridie": 1,
    "perendie": 2, "biduo": 2,
    "pridie": -1, "hodie": 0,
}
MONTHS = {
    "ianuarii": 1, "februarii": 2, "martii": 3, "aprilis": 4, "maii": 5, "iunii": 6,
    "iulii": 7, "augusti": 8, "septembris": 9, "octobris": 10, "novembris": 11, "decembris": 12,
}
_ORDINAL_STEMS = [
    ("prim", 1), ("secund", 2), ("terti", 3), ("quart", 4), ("quint", 5),
    ("sext", 6), ("septim", 7), ("octav", 8), ("non", 9), ("decim", 10),
    ("undecim", 11), ("duodecim", 12), ("duodevicesim", 18), ("duodevigesim", 18),
    ("undevicesim", 19), ("undevigesim", 19), ("vicesim", 20), ("vigesim", 20),
    ("tricesim", 30), ("trigesim", 30),
]
# Compound ordinals are summed: "vigesima quarta" = 24, "tertia decima" = 13.
ORDINALS = {stem + end: n for stem, n in _ORDINAL_STEMS for end in ("a", "ae", "o", "us", "um", "i")}
EVENT_OF_DAY = {"depositionis": "depositio", "ordinationis": "ordinatio", "translationis": "translatio"}
LEAP_YEAR = 2000  # date arithmetic that admits Feb 29


def resolve_xref(folded, month, day):
    m = XREF.search(folded)
    if not m:
        return None
    words = folded[m.end():].split()[:XREF_WINDOW]
    event = next((EVENT_OF_DAY[w] for w in words if w in EVENT_OF_DAY), None)
    for i, w in enumerate(words):
        if w in RELATIVE_DAYS:
            target = date(LEAP_YEAR, month, day) + timedelta(days=RELATIVE_DAYS[w])
            return (target.month, target.day), event
        if w in MONTHS:
            j, n = i - 1, 0
            if j >= 0 and words[j] == "mensis":
                j -= 1
            while j >= 0 and words[j] in ORDINALS:
                n += ORDINALS[words[j]]
                j -= 1
            try:
                date(LEAP_YEAR, MONTHS[w], n)
            except ValueError:
                return None
            return (MONTHS[w], n), event
    return None


def _slug(mrid):
    return mrid.split("-", 1)[1]


def find_offday_targets(entries):
    by_date = defaultdict(list)
    for mrid, (month, day, _) in entries.items():
        by_date[(month, day)].append(mrid)
    targets, unresolved = {}, []
    for mrid, (month, day, folded) in sorted(entries.items()):
        if not XREF.search(folded):
            continue
        hit = resolve_xref(folded, month, day)
        if hit is None:
            unresolved.append((mrid, "no resolvable date"))
            continue
        when, event = hit
        candidates = [c for c in by_date.get(when, []) if c != mrid]
        same = [c for c in candidates if _slug(c) == _slug(mrid)]
        headed = [c for c in candidates if has_feast_head(entries[c][2])]
        pick = same if len(same) == 1 else headed if len(headed) == 1 else []
        if not pick:
            unresolved.append((mrid, f"{when[0]:02d}/{when[1]:02d}: {len(same)} same-slug, "
                                     f"{len(headed)} memoria/festum/sollemnitas candidates"))
            continue
        targets[pick[0]] = (event or "celebratio", mrid)
    return targets, unresolved


def build(current, texts, *, feast_ids, overrides):
    folded = {mrid: fold(texts[mrid]) for mrid in current}
    offday, unresolved = find_offday_targets(
        {mrid: (m, d, folded[mrid]) for mrid, (m, d) in current.items()})
    typology, rules = {}, {}
    for mrid in sorted(current):
        typology[mrid], rules[mrid] = classify(
            mrid, folded[mrid], offday=offday, feast_ids=feast_ids, overrides=overrides)
    multi = {mrid: markers_in(f) for mrid, f in sorted(folded.items()) if len(markers_in(f)) > 1}
    hidden = {mrid: event_words_outside_lead(folded[mrid]) for mrid in sorted(current)
              if rules[mrid] == "default" and event_words_outside_lead(folded[mrid])}
    return {"typology": typology, "rules": rules, "offday": offday,
            "unresolved": unresolved, "multi": multi, "hidden": hidden}


def validate(typology, current_ids, deprecated_ids, *, feast_ids, overrides):
    assert set(typology) == set(current_ids), "typology must cover exactly the current IDs"
    bad = {k: v for k, v in typology.items() if v not in VALUES}
    assert not bad, f"unknown typology values: {bad}"
    assert set(overrides) <= set(current_ids), f"overrides for unknown IDs: {set(overrides) - set(current_ids)}"
    assert all(v in VALUES for v in overrides.values()), "override with unknown value"
    assert set(feast_ids) <= set(current_ids), f"FEAST_IDS not current: {set(feast_ids) - set(current_ids)}"
    assert not set(typology) & set(deprecated_ids), "deprecated IDs must not be tagged"


def render_json(typology):
    out = {
        "$comment": "Typology of each current eulogy: what the date of the elogium marks. "
                    "Generated by scripts/extract_typology.py from the Latin editio altera "
                    "2004; values and rules in docs/canonicalization-report.md (Typology). "
                    "Draft pending committee review.",
        "values": VALUES,
        "typology": dict(sorted(typology.items())),
    }
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"


def render_report(result):
    typology, rules = result["typology"], result["rules"]
    counts = {v: sum(1 for x in typology.values() if x == v) for v in VALUES}
    lines = [
        "# Typology report",
        "",
        "Generated by `scripts/extract_typology.py`. It holds IDs and marker words only. "
        "Every tag other than `dies_natalis`, and every entry with several marker words, "
        "is listed for review against the Latin editio altera 2004.",
        "",
        "## Counts",
        "",
        "| Typology | Entries |",
        "| --- | --- |",
        *[f"| {v} | {counts[v]} |" for v in VALUES],
        "",
        "## Tags other than dies_natalis",
        "",
        "| ID | Typology | Rule |",
        "| --- | --- | --- |",
        *[f"| `{k}` | {v} | {rules[k]} |" for k, v in typology.items() if v != "dies_natalis"],
        "",
        "## Off-day cross-references",
        "",
        "| Source (dies natalis) | Target | Typology |",
        "| --- | --- | --- |",
        *[f"| `{src}` | `{tgt}` | {val} |" for tgt, (val, src) in sorted(result["offday"].items())],
        "",
        "## Unresolved cross-references",
        "",
        *([f"- `{k}`: {why}" for k, why in result["unresolved"]] or ["None."]),
        "",
        "## Default entries with an event word outside the lead",
        "",
        "| ID | Event words |",
        "| --- | --- |",
        *([f"| `{k}` | {', '.join(ws)} |" for k, ws in result["hidden"].items()] or ["None."]),
        "",
        "## Entries with several marker words",
        "",
        "| ID | Typology | Rule | Marker words |",
        "| --- | --- | --- | --- |",
        *[f"| `{k}` | {typology[k]} | {rules[k]} | {', '.join(ms)} |" for k, ms in result["multi"].items()],
    ]
    return "\n".join(lines) + "\n"


def load_texts(texts_repo, edition="martyrologium_romanum_2004"):
    folder = texts_repo / "data" / "editions" / edition
    texts = {}
    for month in range(1, 13):
        with open(folder / f"{month:02d}.json", encoding="utf-8") as f:
            texts.update(json.load(f))
    return texts


def latin_texts(entries, texts):
    """The Latin 2004 texts, plus, for a current eulogy the Latin print files
    under another day's ID, its `same_eulogy` twin's text."""
    out = dict(texts)
    for e in entries:
        if e.get("deprecated") or e["id"] in out:
            continue
        for twin in e.get("same_eulogy", []):
            if twin in texts:
                out[e["id"]] = texts[twin]
                break
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    texts_repo = Path(sys.argv[1])
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    with open(repo_root / "data" / "martyrology_ids.json", encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    current = {e["id"]: (e["month"], e["day"]) for e in entries if not e.get("deprecated")}
    deprecated = {e["id"] for e in entries if e.get("deprecated")}
    texts = latin_texts(entries, load_texts(texts_repo))
    missing = sorted(set(current) - set(texts) - set(TYPOLOGY_OVERRIDES))
    assert not missing, f"no Latin 2004 text for: {missing}"
    for mrid in set(current) - set(texts):
        texts[mrid] = ""  # typology comes from TYPOLOGY_OVERRIDES
    result = build(current, texts, feast_ids=FEAST_IDS, overrides=TYPOLOGY_OVERRIDES)
    validate(result["typology"], set(current), deprecated,
             feast_ids=FEAST_IDS, overrides=TYPOLOGY_OVERRIDES)
    (repo_root / "data" / "typology.json").write_text(render_json(result["typology"]), encoding="utf-8")
    (repo_root / "docs" / "typology-report.md").write_text(render_report(result), encoding="utf-8")
    counts = {v: sum(1 for x in result["typology"].values() if x == v) for v in VALUES}
    print(f"Tagged {len(result['typology'])} current entries: {counts}; "
          f"{len(result['unresolved'])} unresolved cross-references")


if __name__ == "__main__":
    main()
