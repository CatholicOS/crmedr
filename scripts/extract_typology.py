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
    return {"typology": typology, "rules": rules, "offday": offday,
            "unresolved": unresolved, "multi": multi}


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
        "## Entries with several marker words",
        "",
        "| ID | Typology | Rule | Marker words |",
        "| --- | --- | --- | --- |",
        *[f"| `{k}` | {typology[k]} | {rules[k]} | {', '.join(ms)} |" for k, ms in result["multi"].items()],
    ]
    return "\n".join(lines) + "\n"


def load_texts(texts_repo):
    folder = texts_repo / "data" / "editions" / "martyrologium_romanum_2004"
    texts = {}
    for month in range(1, 13):
        with open(folder / f"{month:02d}.json", encoding="utf-8") as f:
            texts.update(json.load(f))
    return texts


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    texts_repo = Path(sys.argv[1])
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    with open(repo_root / "data" / "martyrology_ids.json", encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    current = {e["id"]: (e["month"], e["day"]) for e in entries if not e.get("deprecated")}
    deprecated = {e["id"] for e in entries if e.get("deprecated")}
    texts = load_texts(texts_repo)
    missing = sorted(set(current) - set(texts))
    assert not missing, f"no Latin 2004 text for: {missing}"
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
