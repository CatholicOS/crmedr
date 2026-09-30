#!/usr/bin/env python3
"""Extract the places stated by each current eulogy (Latin editio altera 2004).

Each place is quoted exactly as printed in the Latin editio altera (`la`) and,
where the Italian (CEI) edition has it, in Italian (`it`), and given a role.
Place designations are factual and may be quoted; no other elogium text is
stored.
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

from extract_typology import RECOVERY, load_texts

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
EDITION_LA = "martyrologium_romanum_2004"
EDITION_IT = "martyrologium_romanum_2004_it_IT"
MISPRINT_KEYS = {"id", "edition", "printed", "intended", "verified"}


def _base(c):
    b = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
    return b if len(b) == 1 else c


def base_copy(text):
    """Strip accents one character to one, keeping ligatures and case, so
    that offsets in the copy are offsets in the printed text."""
    return "".join(_base(c) for c in text)


def opening_phrase(text, stop_words=STOP_WORDS):
    copy = base_copy(text)
    for i, m in enumerate(WORD.finditer(copy)):
        w = m.group(0)
        if w.lower() in stop_words and (w[0].islower() or i == 0):
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


# Italian (CEI 2004). Same rule as the Latin: a stop word counts when it is
# lowercase or opens the text. "anniversario (della morte)" renders natalis,
# "martirio" passio, "Parimenti si commemorano" Item commemorantur.
STOP_WORDS_IT = {
    "san", "sant", "santo", "santa", "santi", "sante",
    "beato", "beata", "beati", "beate", "santissimo", "santissima",
    "memoria", "commemorazione", "commemorano", "parimenti",
    "deposizione", "traslazione", "natale", "anniversario", "martirio",
    "passione", "transito", "dedicazione", "festa", "solennita", "dormizione",
}
# A comma segment is kept when it opens with one of these (a locative or a
# modern-country hint such as ", nell'odierna Turchia"), unless it is a
# relative or time clause (CUT_IT).
LOCATIVE_IT = {
    "in", "nel", "nella", "nello", "nell", "nei", "negli", "nelle",
    "presso", "vicino", "sul", "sulla", "sulle", "sui", "al", "alla", "ai",
    "lungo", "tra", "fra", "ora", "oggi", "attualmente", "sempre", "ancora",
}
CUT_IT = re.compile(
    r"^(?:dove|da lui|che|chiamat\w*|sotto)\b|\banni (?:dopo|piu tardi)\b|^(?:nello stesso )?giorno e anno\b")
BACK_REFS_IT = {"nello stesso luogo", "nella stessa citta"}
# Openings that name a time, not a place.
TIME_OPENINGS_IT = {"nello stesso giorno"}
HONORIFICS_IT = {"san", "sant", "santo", "santa", "santi", "sante",
                 "beato", "beata", "beati", "beate", "santissimo", "santissima"}
# The CEI edition prints some church and monastery names lowercase ("presso
# san Pietro", "monastero di sant'Elia"): an honorific directly after one of
# these, with no punctuation between, belongs to the place name.
PREPOSITIONS_IT = {
    "a", "ad", "di", "da", "in", "presso", "verso", "nel", "nella", "nello", "del",
    "della", "dello", "dei", "degli", "delle", "al", "alla", "sul", "sulla",
}
# A phrase ending in one of these was cut inside a place name.
FUNCTION_WORDS_IT = PREPOSITIONS_IT | {"il", "lo", "la", "i", "gli", "le", "e"}
MAX_WORDS_IT = 20


def italian_phrase(text, stop_words=STOP_WORDS_IT):
    """The Italian opening phrase, or None when there is none or it is a
    bare back-reference ("Nello stesso luogo")."""
    if not text:
        return None
    copy = base_copy(text)
    words = list(WORD.finditer(copy))
    for i, m in enumerate(words):
        w = m.group(0)
        if w.lower() in stop_words and (w[0].islower() or i == 0):
            if i and w.lower() in HONORIFICS_IT and words[i - 1].group(0).lower() in PREPOSITIONS_IT \
                    and not copy[words[i - 1].end():m.start()].strip(" ’'"):
                continue
            phrase = text[:m.start()].strip(TRIM)
            break
    else:
        return None
    if base_copy(phrase).lower() in TIME_OPENINGS_IT:
        return None
    segments = phrase.split(",")
    kept = segments[0]
    for seg in segments[1:]:
        s = base_copy(seg).strip().lower()
        first = WORD.match(s)
        if not s or CUT_IT.search(s) or not first or first.group(0) not in LOCATIVE_IT:
            break
        kept += "," + seg
    kept = kept.strip(TRIM)
    adverb = re.match(r"(?:Sempre|Ancora)\s+", base_copy(kept))
    if adverb:
        kept = kept[adverb.end():]
    if base_copy(kept).lower() in BACK_REFS_IT:
        return None
    return kept or None


# Openings that look like a place but are not.
NOT_A_PLACE = {
    "mr:0101-maria-dei-genetrix": "a time phrase (the octave of Christmas), not a place",
}


def lead_items(order, texts, typology, *, not_a_place, stop_words=STOP_WORDS):
    """Opening-place items by ID, and the IDs of back-references with no
    earlier place on their day. A bare back-reference takes the `la` of the
    last place named that day and names that entry in `via`; an extended
    one keeps its own phrase and names its antecedent in `via` (and is
    reported as unresolved when it has none)."""
    items, unresolved, last = {}, [], {}
    for mrid, month, day in order:
        phrase = None if mrid in not_a_place else opening_phrase(texts[mrid], stop_words)
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
            if kind == "extend":
                if day_key in last:
                    item["via"] = last[day_key][1]
                else:
                    # No antecedent: keep the printed phrase, but report it.
                    unresolved.append(mrid)
            # A later bare back-reference means "at the place just named",
            # which is this one (for an extend, its own printed phrase).
            last[day_key] = (la, mrid)
        items[mrid] = item
    return items, unresolved


def validate_curated(curated, texts, current_ids, leads, texts_it=None):
    errors = []
    for mrid, entries in curated.items():
        if mrid not in current_ids:
            errors.append(f"{mrid}: not a current ID")
            continue
        for it in entries:
            if set(it) not in ({"role", "la"}, {"role", "la", "it"}):
                errors.append(f"{mrid}: curated item keys must be role, la and optionally it: {sorted(it)}")
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
            if "it" in it:
                if not isinstance(it["it"], str) or not it["it"].strip():
                    errors.append(f"{mrid}: it is empty")
                elif it["it"] not in (texts_it or {}).get(mrid, ""):
                    errors.append(f"{mrid}: it is not verbatim in the Italian elogium: {it['it']!r}")
                elif len(it["it"].split()) > MAX_WORDS_IT:
                    errors.append(f"{mrid}: it has more than {MAX_WORDS_IT} words")
    return errors

# Role cues in the body, used only to list curation candidates.
CUES = {
    "birth": re.compile(r"\b(?:natus|nata|ortus|orta|oriundus|oriunda)\b"),
    "ministry": re.compile(r"\bepiscop(?:us|i) \w+ensis\b|\bsedem\b"),
    "burial": re.compile(r"\b(?:sepultus|sepulta|tumulatus|tumulata)\b"),
    "death": re.compile(r"\b(?:obiit|obdormivit|defunctus|defuncta|occubuit)\b"),
}


def cue_matches(text, stop_words=STOP_WORDS):
    """{role: [matched cue words]} for the cues outside the opening phrase."""
    rest = base_copy(text).lower()[len(opening_phrase(text, stop_words) or ""):]
    found = {role: sorted({m.group(0) for m in cue.finditer(rest)}) for role, cue in CUES.items()}
    return {role: words for role, words in sorted(found.items()) if words}


# Opening places over MAX_WORDS that are still pure place designations.
LONG_LEAD_OK = {
    "mr:0420-anastasius-pankiewicz": "a route between two camps (Dachau to Hartheim near Linz)",
    "mr:0514-theodora-guerin": "a village name plus its state and country",
    "mr:0721-gabriel-pergaud": "a prison ship at anchor off Rochefort",
    "mr:0827-ioannes-baptista-de-souzy": "a prison ship at anchor off Rochefort",
}


# Print-only entries (no workbook entry number) and the slot they occupy in
# the Latin print, so that back-references resolve in print order.
PRINT_POSITION = {
    "mr:0104-abrunculus": 2,
    "mr:0610-marcus-antonius-durando": 9,
}


def print_order(entries, positions=PRINT_POSITION):
    """(id, month, day) in print order. An entry with no number takes the
    slot just before the entry currently numbered like its printed position;
    an unknown one goes last in its day."""
    def slot(e):
        if e["entry"] is not None:
            return e["entry"]
        return positions[e["id"]] - 0.5 if e["id"] in positions else float("inf")
    ordered = sorted(entries, key=lambda e: (e["month"], e["day"], slot(e)))
    return [(e["id"], e["month"], e["day"]) for e in ordered]


def check_typology(typology, current_ids):
    assert set(typology) == set(current_ids), (
        "data/typology.json does not match the current IDs. " + RECOVERY)


def load_misprints(repo_root):
    """Verified print misprints (data/misprints.json). Missing file: none."""
    path = repo_root / "data" / "misprints.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["misprints"]


def validate_misprints(misprints, texts_by_edition, current_ids):
    errors = []
    for r in misprints:
        if set(r) != MISPRINT_KEYS:
            errors.append(f"misprint record keys must be {sorted(MISPRINT_KEYS)}: {sorted(r)}")
            continue
        if r["id"] not in current_ids:
            errors.append(f"{r['id']}: not a current ID")
            continue
        if r["edition"] not in texts_by_edition:
            errors.append(f"{r['id']}: unknown edition {r['edition']!r}")
            continue
        count = texts_by_edition[r["edition"]].get(r["id"], "").count(r["printed"])
        if count != 1:
            errors.append(f"{r['id']}: {r['printed']!r} occurs {count} times in {r['edition']}")
    keys = [(r.get("id"), r.get("edition")) for r in misprints]
    if keys != sorted(keys, key=lambda k: (str(k[0]), str(k[1]))):
        errors.append("misprint records must be sorted by id, then edition")
    return errors


def misprint_stop_words(misprints, edition, stop_words):
    """Printed misprints (accent-stripped, lowercase) of a stop word in `edition`."""
    fold = lambda w: base_copy(w).lower()
    return {fold(r["printed"]) for r in misprints
            if r["edition"] == edition and fold(r["intended"]) in stop_words}


def with_it(item, it):
    """item with `it` inserted right after `la` (key order is output order)."""
    out = {}
    for k, v in item.items():
        if k == "it":
            continue
        out[k] = v
        if k == "la":
            out["it"] = it
    return out


def build(order, texts, typology, curated, *, not_a_place, stop_words=STOP_WORDS,
          texts_it=None, stop_words_it=STOP_WORDS_IT):
    leads, unresolved = lead_items(order, texts, typology, not_a_place=not_a_place, stop_words=stop_words)
    no_it, it_only = [], []
    if texts_it is not None:
        for mrid, _, _ in order:
            phrase = italian_phrase(texts_it.get(mrid), stop_words_it)
            if mrid not in leads:
                if phrase and mrid not in not_a_place:
                    it_only.append((mrid, phrase))
                continue
            item = leads[mrid]
            if "via" in item and item["la"] not in texts[mrid]:
                phrase = leads[item["via"]].get("it")   # a bare back-reference takes its root's it
            if phrase:
                leads[mrid] = with_it(item, phrase)
            else:
                no_it.append(mrid)
    places = {}
    for mrid, _, _ in order:
        items = [leads[mrid]] if mrid in leads else []
        for it in curated.get(mrid, []):
            cur = {"role": it["role"], "la": it["la"], "source": "curated"}
            items.append(with_it(cur, it["it"]) if "it" in it else cur)
        if items:
            places[mrid] = items
    return {
        "places": places,
        "unresolved": unresolved,
        "no_place": [mrid for mrid, _, _ in order if mrid not in places],
        "long": [(mrid, leads[mrid]["la"]) for mrid, _, _ in order
                 if mrid in leads and len(leads[mrid]["la"].split()) > MAX_WORDS],
        "candidates": {mrid: cues for mrid, cues in
                       ((mrid, cue_matches(texts[mrid], stop_words)) for mrid, _, _ in order) if cues},
        "comma": [(mrid, leads[mrid]["la"]) for mrid, _, _ in order
                  if mrid in leads and "," in leads[mrid]["la"]],
        "curated_ids": set(curated),
        "day_of": {mrid: (month, day) for mrid, month, day in order},
        "no_it": no_it,
        "it_only": it_only,
    }

def validate(result, texts, current_ids, deprecated_ids, typology, curated, *, long_ok, texts_it=None):
    places = result["places"]
    assert set(places) <= set(current_ids), f"non-current IDs: {sorted(set(places) - set(current_ids))}"
    assert not set(places) & set(deprecated_ids), "deprecated IDs must not have places"
    leads = {}
    for mrid, items in places.items():
        for it in items:
            assert it["role"] in ROLES, f"{mrid}: unknown role {it['role']!r}"
            if "via" in it:
                via = it["via"]
                assert via in texts, f"{mrid}: via {via} has no text"
                assert result["day_of"].get(via) == result["day_of"].get(mrid), (
                    f"{mrid}: via {via} is not on the same day")
                if it["la"] not in texts[mrid]:
                    # A bare back-reference takes its root's opening place.
                    root = places.get(via, [{}])[0].get("la")
                    assert it["la"] == root, f"{mrid}: la is not the root {via}'s la: {it['la']!r}"
            else:
                assert it["la"] in texts[mrid], f"{mrid}: la is not verbatim: {it['la']!r}"
            if "it" in it:
                assert texts_it is not None, f"{mrid}: it present but no Italian texts given"
                assert len(it["it"].split()) <= MAX_WORDS_IT, f"{mrid}: it has more than {MAX_WORDS_IT} words"
                last = WORD.findall(base_copy(it["it"]).lower())[-1:]
                assert not (last and last[0] in FUNCTION_WORDS_IT), (
                    f"{mrid}: it ends in {last[0]!r}, cut inside a place name: {it['it']!r}")
                bare = "via" in it and it["la"] not in texts[mrid]
                if bare:
                    root = places.get(it["via"], [{}])[0].get("it")
                    assert it["it"] == root, f"{mrid}: it is not the root {it['via']}'s it: {it['it']!r}"
                else:
                    assert it["it"] in texts_it.get(mrid, ""), f"{mrid}: it is not verbatim: {it['it']!r}"
            elif "via" in it and it["la"] not in texts[mrid]:
                root = places.get(it["via"], [{}])[0]
                assert "it" not in root, f"{mrid}: bare back-reference lacks its root's it"
            if it["source"] == "lead":
                leads[mrid] = it
                expected = ROLE_OF_TYPOLOGY[typology[mrid]]
                assert it["role"] == expected, f"{mrid}: lead role {it['role']} != {expected} from typology"
    too_long = [mrid for mrid, _ in result["long"] if mrid not in long_ok]
    assert not too_long, f"opening places over {MAX_WORDS} words, not in LONG_LEAD_OK: {too_long}"
    errors = validate_curated(curated, texts, set(current_ids), leads, texts_it)
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


def _cue_cell(cues):
    return "; ".join(f"{role} ({', '.join(words)})" for role, words in cues.items())


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
        f"{source_counts['lead']} opening places, {source_counts['curated']} curated places; "
        f"{sum(1 for it in items if 'it' in it)} with an Italian phrase.",
        "",
        "| Role | Places |",
        "| --- | --- |",
        *[f"| {r} | {role_counts[r]} |" for r in ROLES],
        "",
        "## Unresolved back-references",
        "",
        "*Ibidem* or bare *Item* with no earlier place on the same day.",
        "",
        *([f"- `{m}`" + (" (kept its own phrase)" if m in places else "") for m in result["unresolved"]]
          or ["None."]),
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
        "## Latin places without an Italian phrase",
        "",
        ", ".join(f"`{m}`" for m in result.get("no_it", [])) or "None.",
        "",
        "## Italian places without a Latin place",
        "",
        "Curation candidates: some are places the Latin rule missed.",
        "",
        *([f"- `{m}`: {it}" for m, it in result.get("it_only", [])] or ["None."]),
        "",
        "## Curation candidates",
        "",
        "Entries whose text holds a role cue outside the opening place. Add the "
        "places they state to `data/places_curated.json`.",
        "",
        "| ID | Cued roles (cue words) | Curated |",
        "| --- | --- | --- |",
        *[f"| `{m}` | {_cue_cell(cues)} | {'yes' if m in result['curated_ids'] else ''} |"
          for m, cues in result["candidates"].items()],
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
    order = print_order([e for e in entries if not e.get("deprecated")])
    deprecated = {e["id"] for e in entries if e.get("deprecated")}
    with open(repo_root / "data" / "typology.json", encoding="utf-8") as f:
        typology = json.load(f)["typology"]
    check_typology(typology, {m for m, _, _ in order})
    misprints = load_misprints(repo_root)
    curated = {}
    curated_path = repo_root / "data" / "places_curated.json"
    if curated_path.exists():
        with open(curated_path, encoding="utf-8") as f:
            curated = json.load(f)
    texts = load_texts(texts_repo)
    texts_it = load_texts(texts_repo, EDITION_IT)
    errors = validate_misprints(misprints, {EDITION_LA: texts, EDITION_IT: texts_it},
                                {m for m, _, _ in order})
    assert not errors, "invalid data/misprints.json:\n" + "\n".join(errors)
    stop_words = STOP_WORDS | misprint_stop_words(misprints, EDITION_LA, STOP_WORDS)
    stop_words_it = STOP_WORDS_IT | misprint_stop_words(misprints, EDITION_IT, STOP_WORDS_IT)
    result = build(order, texts, typology, curated, not_a_place=NOT_A_PLACE, stop_words=stop_words,
                   texts_it=texts_it, stop_words_it=stop_words_it)
    validate(result, texts, {m for m, _, _ in order}, deprecated, typology, curated,
             long_ok=LONG_LEAD_OK, texts_it=texts_it)
    (repo_root / "data" / "places.json").write_text(render_json(result["places"]), encoding="utf-8")
    (repo_root / "docs" / "places-report.md").write_text(render_report(result), encoding="utf-8")
    print(f"{len(result['places'])} entries with places; {len(result['unresolved'])} unresolved "
          f"back-references; {len(result['candidates'])} curation candidates; "
          f"{sum(1 for its in result['places'].values() for it in its if 'it' in it)} with it; "
          f"{len(result['no_it'])} without it; {len(result['it_only'])} Italian-only")


if __name__ == "__main__":
    main()
