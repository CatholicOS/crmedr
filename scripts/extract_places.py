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

from extract_typology import load_texts

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
    "memoria", "festum", "sollemnitas", "dormitio",
    # "Sanctissimi Nominis ..." opens a feast; lowercase it would be a title.
    "sanctissimi", "sanctissimae", "sanctissimæ",
}
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿæœÆŒ]+")
TRIM = " ,;: "
# A comma followed by a relative pronoun, a reign ("sub N. imperatore") or a
# time phrase starts a clause that is not part of the place; the phrase is
# cut there (it must stay verbatim, so the clause is never removed from the
# middle).
CLAUSE = re.compile(
    r",\s*(?:(?:quod|quam|quo|qui|quae|quæ|sub)\b|in eadem persecutione\b|(?:[a-z]+ )+post annis\b)")
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
    # "Item commemoratio ..." means "also, the commemoration of", not "at the
    # same place": there is no opening place.
    if base_copy(phrase) == "Item" and w.lower().startswith("commemora"):
        return None
    clause = CLAUSE.search(base_copy(phrase))
    if clause:
        phrase = phrase[:clause.start()].strip(TRIM)
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


# Openings that look like a place but are not.
NOT_A_PLACE = {
    "mr:0101-maria-dei-genetrix": "a time phrase (the octave of Christmas), not a place",
}


def lead_items(order, texts, typology, *, not_a_place):
    """Opening-place items by ID, and the IDs of back-references with no
    earlier place on their day. A bare back-reference takes the `la` of the
    last place named that day and names that entry in `via`; an extended
    one keeps its own phrase and names its antecedent in `via`."""
    items, unresolved, last = {}, [], {}
    for mrid, month, day in order:
        phrase = None if mrid in not_a_place else opening_phrase(texts[mrid])
        if phrase is None:
            continue
        kind, la = split_lead(phrase)
        day_key = (month, day)
        item = {"role": ROLE_OF_TYPOLOGY[typology[mrid]]}
        if kind == "back":
            if day_key not in last:
                unresolved.append(mrid)
                continue
            root_la, root = last[day_key]
            item.update(la=root_la, source="lead", via=root)
        else:
            item.update(la=la, source="lead")
            if kind == "extend" and day_key in last:
                item["via"] = last[day_key][1]
            # A later bare back-reference means "at the place just named",
            # which is this one (for an extend, its own printed phrase).
            last[day_key] = (la, mrid)
        items[mrid] = item
    return items, unresolved


def validate_curated(curated, texts, current_ids, leads):
    errors = []
    for mrid, entries in curated.items():
        if mrid not in current_ids:
            errors.append(f"{mrid}: not a current ID")
            continue
        for it in entries:
            if set(it) != {"role", "la"}:
                errors.append(f"{mrid}: curated item keys must be role and la: {sorted(it)}")
                continue
            if it["role"] not in ROLES:
                errors.append(f"{mrid}: unknown role {it['role']!r}")
            if not isinstance(it["la"], str) or not it["la"].strip():
                errors.append(f"{mrid}: la is empty")
                continue
            if it["la"] not in texts[mrid]:
                errors.append(f"{mrid}: la is not verbatim in the elogium: {it['la']!r}")
            if len(it["la"].split()) > MAX_WORDS:
                errors.append(f"{mrid}: la has more than {MAX_WORDS} words")
            if mrid in leads and it["la"] == leads[mrid]["la"]:
                errors.append(f"{mrid}: la repeats the opening place")
    return errors


# Role cues in the body, used only to list curation candidates.
CUES = {
    "birth": re.compile(r"\b(?:natus|nata|ortus|orta|oriundus|oriunda)\b"),
    "ministry": re.compile(r"\bepiscop(?:us|i) \w+ensis\b|\bsedem\b"),
    "burial": re.compile(r"\b(?:sepultus|sepulta|tumulatus|tumulata)\b"),
    "death": re.compile(r"\b(?:obiit|obdormivit|defunctus|defuncta|occubuit)\b"),
}


def cue_roles(text):
    rest = base_copy(text).lower()[len(opening_phrase(text) or ""):]
    return sorted(role for role, cue in CUES.items() if cue.search(rest))


# Opening places over MAX_WORDS that are still pure place designations.
LONG_LEAD_OK = {
    "mr:0420-anastasius-pankiewicz": "a route between two camps (Dachau to Hartheim near Linz)",
    "mr:0514-theodora-guerin": "a village name plus its state and country",
    "mr:0721-gabriel-pergaud": "a prison ship at anchor off Rochefort",
    "mr:0827-ioannes-baptista-de-souzy": "a prison ship at anchor off Rochefort",
}


def build(order, texts, typology, curated, *, not_a_place):
    leads, unresolved = lead_items(order, texts, typology, not_a_place=not_a_place)
    places = {}
    for mrid, _, _ in order:
        items = [leads[mrid]] if mrid in leads else []
        items += [{"role": it["role"], "la": it["la"], "source": "curated"} for it in curated.get(mrid, [])]
        if items:
            places[mrid] = items
    return {
        "places": places,
        "unresolved": unresolved,
        "no_place": [mrid for mrid, _, _ in order if mrid not in places],
        "long": [(mrid, leads[mrid]["la"]) for mrid, _, _ in order
                 if mrid in leads and len(leads[mrid]["la"].split()) > MAX_WORDS],
        "candidates": {mrid: cue_roles(texts[mrid]) for mrid, _, _ in order if cue_roles(texts[mrid])},
        "comma": [(mrid, leads[mrid]["la"]) for mrid, _, _ in order
                  if mrid in leads and "," in leads[mrid]["la"]],
        "curated_ids": set(curated),
    }


def validate(result, texts, current_ids, deprecated_ids, typology, curated, *, long_ok):
    places = result["places"]
    assert set(places) <= set(current_ids), f"non-current IDs: {sorted(set(places) - set(current_ids))}"
    assert not set(places) & set(deprecated_ids), "deprecated IDs must not have places"
    leads = {}
    for mrid, items in places.items():
        for it in items:
            assert it["role"] in ROLES, f"{mrid}: unknown role {it['role']!r}"
            # A bare back-reference quotes the `via` entry; every other la its own text.
            assert it["la"] in texts[mrid] or ("via" in it and it["la"] in texts[it["via"]]), (
                f"{mrid}: la is not verbatim: {it['la']!r}")
            if it["source"] == "lead":
                leads[mrid] = it
                expected = ROLE_OF_TYPOLOGY[typology[mrid]]
                assert it["role"] == expected, f"{mrid}: lead role {it['role']} != {expected} from typology"
    too_long = [mrid for mrid, _ in result["long"] if mrid not in long_ok]
    assert not too_long, f"opening places over {MAX_WORDS} words, not in LONG_LEAD_OK: {too_long}"
    errors = validate_curated(curated, texts, set(current_ids), leads)
    assert not errors, "invalid curated places:\n" + "\n".join(errors)


def render_json(places):
    out = {
        "$comment": "Places stated by each current eulogy: the place designation as printed "
                    "in the Latin editio altera 2004 (la) and its role. Generated by "
                    "scripts/extract_places.py; see docs/canonicalization-report.md (Places). "
                    "Draft pending committee review.",
        "roles": ROLES,
        "places": dict(sorted(places.items())),
    }
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"


def render_report(result):
    places = result["places"]
    items = [it for its in places.values() for it in its]
    role_counts = {r: sum(1 for it in items if it["role"] == r) for r in ROLES}
    source_counts = {s: sum(1 for it in items if it["source"] == s) for s in ("lead", "curated")}
    lines = [
        "# Places report",
        "",
        "Generated by `scripts/extract_places.py`. It holds IDs, cue words and "
        "place designations only.",
        "",
        "## Counts",
        "",
        f"{len(places)} entries with at least one place; "
        f"{source_counts['lead']} opening places, {source_counts['curated']} curated places.",
        "",
        "| Role | Places |",
        "| --- | --- |",
        *[f"| {r} | {role_counts[r]} |" for r in ROLES],
        "",
        "## Unresolved back-references",
        "",
        "*Ibidem* or bare *Item* with no earlier place on the same day.",
        "",
        *([f"- `{m}`" for m in result["unresolved"]] or ["None."]),
        "",
        "## Opening places over 12 words",
        "",
        *([f"- `{m}`: {la}" for m, la in result["long"]] or ["None."]),
        "",
        "## Opening places with a comma",
        "",
        "Check that the part after each comma is still a place designation.",
        "",
        *([f"- `{m}`: {la}" for m, la in result["comma"]] or ["None."]),
        "",
        "## Curation candidates",
        "",
        "Entries whose text holds a role cue outside the opening place. Add the "
        "places they state to `data/places_curated.json`.",
        "",
        "| ID | Cued roles | Curated |",
        "| --- | --- | --- |",
        *[f"| `{m}` | {', '.join(rs)} | {'yes' if m in result['curated_ids'] else ''} |"
          for m, rs in result["candidates"].items()],
        "",
        "## Entries with no place",
        "",
        ", ".join(f"`{m}`" for m in result["no_place"]) or "None.",
    ]
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    texts_repo = Path(sys.argv[1])
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    with open(repo_root / "data" / "martyrology_ids.json", encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    current = sorted((e for e in entries if not e.get("deprecated")),
                     key=lambda e: (e["month"], e["day"], e["entry"] is None, e["entry"] or 0))
    order = [(e["id"], e["month"], e["day"]) for e in current]
    deprecated = {e["id"] for e in entries if e.get("deprecated")}
    with open(repo_root / "data" / "typology.json", encoding="utf-8") as f:
        typology = json.load(f)["typology"]
    curated_path = repo_root / "data" / "places_curated.json"
    curated = json.load(open(curated_path, encoding="utf-8")) if curated_path.exists() else {}
    texts = load_texts(texts_repo)
    result = build(order, texts, typology, curated, not_a_place=NOT_A_PLACE)
    validate(result, texts, {m for m, _, _ in order}, deprecated, typology, curated, long_ok=LONG_LEAD_OK)
    (repo_root / "data" / "places.json").write_text(render_json(result["places"]), encoding="utf-8")
    (repo_root / "docs" / "places-report.md").write_text(render_report(result), encoding="utf-8")
    print(f"{len(result['places'])} entries with places; {len(result['unresolved'])} unresolved "
          f"back-references; {len(result['candidates'])} curation candidates")


if __name__ == "__main__":
    main()
