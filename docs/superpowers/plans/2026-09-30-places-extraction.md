# Place Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each current registry entry an optional `places` list: the Latin place phrases its elogium states, quoted exactly as printed, each with a role.

**Architecture:** A new stdlib script, `scripts/extract_places.py`, extracts the opening place of each 2004 elogium (up to the first lowercase honorific or marker word). It resolves *Item / Ibidem* back-references within the day, maps the role from `data/typology.json`, adds hand-curated body places from `data/places_curated.json`, and writes `data/places.json` plus a review report. `scripts/extract_registry.py` merges `places` after `typology`.

**Tech Stack:** Python 3 standard library only (`json`, `re`, `unicodedata`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-09-30-places-extraction-design.md`

## Global Constraints

- Roles, exactly: `death`, `burial`, `translation`, `dedication`, `cult`, `birth`, `ministry`.
- Typology → role: `dies_natalis`→`death`, `depositio`→`burial`, `translatio`→`translation`, `inventio`→`translation`, `dedicatio`→`dedication`, `ordinatio`→`ministry`, `celebratio`→`cult`, `commemoratio`→`cult`.
- Item keys, in order: `role`, `la`, `source` (`lead` | `curated`), and `via` when present.
- `la` is quoted **exactly as printed** (accents, ligatures, case), trimmed of spaces and trailing `,` `;` `:`. It must appear verbatim in the elogium it came from: its own text, or the `via` entry's text for a bare back-reference.
- `la` is at most 12 words, unless the ID is in `LONG_LEAD_OK` (commented).
- **No other elogium text** in any committed file. Tests use made-up Latin; a 5-word overlap scan against the real texts must find nothing in the tests.
- Only current entries; entries with no place get no key.
- Standard library only. Test command: `python3 -m unittest discover -s tests -v` from the repo root.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Bare back-reference as the first place-bearing entry of a day** (7 in the real data). It must be reported as unresolved and get no place, not borrow the previous day's place. Pinned in Task 2.
2. **Back-reference chains** (*Ibidem* after *Ibidem*, 3 in the real data). `via` must name the entry whose printed phrase supplies `la`, so the verbatim check holds. Pinned in Task 2.
3. **Ligature stop words** (*sanctæ*, *beátæ*). They must end the phrase exactly like *sanctae*, and character offsets must stay aligned. Pinned in Task 1.
4. **A trailing time clause** (", eodem die et anno"). It isn't part of the place and must be stripped, including when it follows *Ibidem*. Pinned in Task 1.
5. **Stale or extra keys in `data/places.json`** when the registry is regenerated. Fail loudly with the recovery message; a missing file means no places. Pinned in Task 4.

## Refinements found while probing the real data (fold into the spec in Task 5)

- A trailing ", eodem die et anno" is stripped from the opening phrase.
- `NOT_A_PLACE`: `mr:0101-maria-dei-genetrix` opens with a time phrase ("In octava Nativitatis Domini…"), not a place.
- *Ibidem* followed by more words ("Ibidem in coemeterio …") keeps its printed phrase and records the antecedent in `via`.
- `via` always names the entry whose printed phrase supplies `la` (the root of a back-reference chain).
- Real counts: 4,276 entries have an opening phrase, 363 have none; 46 bare back-references; 7 unresolved; 4 phrases over 12 words; 548 curation candidates.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/extract_places.py` (create) | Constants; opening-phrase extraction; back-reference resolution; curated validation; cue candidates; build/validate/render; CLI |
| `tests/test_places.py` (create) | Unit tests for the above |
| `data/places_curated.json` (create) | `{}` at first; hand-entered body places |
| `data/places.json`, `docs/places-report.md` (generated) | Output and review report |
| `scripts/extract_registry.py` (modify) | `load_places`, `add_places`; shared recovery message |
| `tests/test_registry.py` (modify) | Registry merge tests |
| `data/martyrology_ids.json` (regenerated) | Registry with `places` |
| `AGENTS.md`, `README.md`, `docs/canonicalization-report.md`, the spec (modify) | Docs and the quoting exception |

---

### Task 1: Opening-phrase extraction

**Files:**
- Create: `scripts/extract_places.py`
- Test: `tests/test_places.py`

**Interfaces:**
- Produces:
  - `ROLES: list[str]`, `ROLE_OF_TYPOLOGY: dict[str, str]`, `MAX_WORDS = 12`
  - `base_copy(text: str) -> str`: same length as `text`; accents stripped per character; ligatures and case kept
  - `opening_phrase(text: str) -> str | None`: the printed opening phrase, trimmed, time tail stripped; `None` if there is none
  - `split_lead(phrase: str) -> tuple[str, str | None]`: `("back", None)` for bare *Item* / *Ibidem*; `("extend", phrase)` for *Ibidem* + more; otherwise `("place", la)` with a leading *Item* removed

- [ ] **Step 1: Write the failing tests**

Create `tests/test_places.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_places as p  # noqa: E402


class OpeningPhraseTest(unittest.TestCase):
    def test_base_copy_keeps_length_case_and_ligatures(self):
        self.assertEqual(p.base_copy("Fictópoli Sanctórum sanctæ"), "Fictopoli Sanctorum sanctæ")
        self.assertEqual(len(p.base_copy("Fictópoli ǽ")), len("Fictópoli ǽ"))

    def test_lowercase_honorific_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli in Fictia, sancti Fictitii, episcopi."),
                         "Fictopoli in Fictia")

    def test_capitalized_saint_in_a_place_name_stays(self):
        self.assertEqual(
            p.opening_phrase("In monasterio Sancti Ficti ad Fictum flumen, depositio beati Fictitii."),
            "In monasterio Sancti Ficti ad Fictum flumen")

    def test_capitalized_stop_word_at_start_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Sancti Fictitii, episcopi."))
        self.assertIsNone(p.opening_phrase("Memória sancti Fictitii, episcopi."))

    def test_printed_accents_kept_and_ligature_stop_word(self):
        self.assertEqual(p.opening_phrase("Fictópoli in Gállia, sanctæ Fictæ, vírginis."),
                         "Fictópoli in Gállia")
        self.assertEqual(p.opening_phrase("Fictópoli, beátæ Fictæ."), "Fictópoli")

    def test_marker_word_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli, translátio sancti Ficti."), "Fictopoli")

    def test_time_tail_is_stripped(self):
        self.assertEqual(p.opening_phrase("Fictopoli item in Fictia, eódem die et anno, beáti Ficti."),
                         "Fictopoli item in Fictia")
        self.assertEqual(p.opening_phrase("Ibídem, eódem die et anno, beáti Ficti."), "Ibídem")

    def test_no_stop_word_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Fictis transactis temporibus Fictus nascitur."))

    def test_split_lead(self):
        self.assertEqual(p.split_lead("Ibídem"), ("back", None))
        self.assertEqual(p.split_lead("Item"), ("back", None))
        self.assertEqual(p.split_lead("Item Fictópoli"), ("place", "Fictópoli"))
        self.assertEqual(p.split_lead("Item, in Fictia"), ("place", "in Fictia"))
        self.assertEqual(p.split_lead("Ibídem in cœmetério Ficti"), ("extend", "Ibídem in cœmetério Ficti"))
        self.assertEqual(p.split_lead("Fictopoli in Fictia"), ("place", "Fictopoli in Fictia"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'extract_places'`.

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/extract_places.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all `OpeningPhraseTest` tests pass, and the existing suites still pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py
git commit -m "feat: opening-place extraction for places (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Back-references, roles, curated places and candidates

**Files:**
- Modify: `scripts/extract_places.py` (append)
- Test: `tests/test_places.py` (add a class)

**Interfaces:**
- Consumes: `opening_phrase`, `split_lead`, `ROLE_OF_TYPOLOGY`, `ROLES`, `MAX_WORDS`, `base_copy`
- Produces:
  - `NOT_A_PLACE: dict[str, str]` (ID → reason)
  - `lead_items(order: list[tuple[str, int, int]], texts: dict[str, str], typology: dict[str, str], *, not_a_place: dict[str, str]) -> tuple[dict[str, dict], list[str]]`, returning `(items_by_id, unresolved_ids)`. `order` is `(id, month, day)` in print order.
  - `validate_curated(curated: dict[str, list[dict]], texts: dict[str, str], current_ids: set[str], leads: dict[str, dict]) -> list[str]`, returning error messages (empty = valid).
  - `cue_roles(text: str) -> list[str]`: sorted roles cued outside the opening phrase.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_places.py`, before the `if __name__` block:

```python
DAY1 = [("mr:0101-a", 1, 1), ("mr:0101-b", 1, 1), ("mr:0101-c", 1, 1), ("mr:0101-d", 1, 1), ("mr:0101-e", 1, 1)]
TEXTS = {
    "mr:0101-a": "Fictopoli in Fictia, sancti Fictitii A.",
    "mr:0101-b": "Ibídem, beáti Ficti B.",
    "mr:0101-c": "Ibídem, sanctæ Fictæ C.",
    "mr:0101-d": "Ibídem in cœmetério Ficti, sancti Ficti D.",
    "mr:0101-e": "Sancti Fictitii E., episcopi.",
    "mr:0102-f": "Item, sancti Ficti F.",
    "mr:0102-g": "In octava Ficti, sancti Ficti G.",
}
TYP = {k: "dies_natalis" for k in TEXTS}
TYP["mr:0101-b"] = "depositio"


class LeadItemsTest(unittest.TestCase):
    def run_leads(self, order=None, not_a_place=None):
        order = order or DAY1 + [("mr:0102-f", 1, 2), ("mr:0102-g", 1, 2)]
        return p.lead_items(order, TEXTS, TYP, not_a_place=not_a_place or {})

    def test_place_and_back_references(self):
        items, unresolved = self.run_leads()
        self.assertEqual(items["mr:0101-a"], {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"})
        self.assertEqual(items["mr:0101-b"],
                         {"role": "burial", "la": "Fictopoli in Fictia", "source": "lead", "via": "mr:0101-a"})

    def test_chain_points_to_the_root(self):
        items, _ = self.run_leads()
        self.assertEqual(items["mr:0101-c"]["via"], "mr:0101-a")
        self.assertEqual(items["mr:0101-c"]["la"], "Fictopoli in Fictia")

    def test_extended_ibidem_keeps_its_phrase(self):
        items, _ = self.run_leads()
        self.assertEqual(items["mr:0101-d"],
                         {"role": "death", "la": "Ibídem in cœmetério Ficti", "source": "lead", "via": "mr:0101-a"})

    def test_no_place_and_unresolved_first_of_day(self):
        items, unresolved = self.run_leads()
        self.assertNotIn("mr:0101-e", items)
        self.assertNotIn("mr:0102-f", items)
        self.assertEqual(unresolved, ["mr:0102-f"])

    def test_not_a_place(self):
        items, _ = self.run_leads(not_a_place={"mr:0102-g": "a time phrase"})
        self.assertNotIn("mr:0102-g", items)

    def test_every_typology_maps_to_a_role(self):
        for value, role in p.ROLE_OF_TYPOLOGY.items():
            items, _ = p.lead_items([("mr:0101-a", 1, 1)], TEXTS, {"mr:0101-a": value}, not_a_place={})
            self.assertEqual(items["mr:0101-a"]["role"], role)
            self.assertIn(role, p.ROLES)


class CuratedTest(unittest.TestCase):
    TEXT = {"mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus est."}
    LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"}}

    def errors(self, items, mrid="mr:0101-a"):
        return p.validate_curated({mrid: items}, self.TEXT, {"mr:0101-a"}, self.LEADS)

    def test_verbatim_item_is_valid(self):
        self.assertEqual(self.errors([{"role": "birth", "la": "in Fictonia"}]), [])

    def test_invalid_items(self):
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictlandia"}]))
        self.assertTrue(self.errors([{"role": "nativity", "la": "in Fictonia"}]))
        self.assertTrue(self.errors([{"role": "death", "la": "Fictopoli in Fictia"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia", "note": "x"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia"}], mrid="mr:0102-x"))
        long_text = {"mr:0101-a": "Fictopoli, sancti Ficti, " + " ".join(["in Fictia"] * 7) + "."}
        self.assertTrue(p.validate_curated({"mr:0101-a": [{"role": "birth", "la": " ".join(["in Fictia"] * 7)}]},
                                           long_text, {"mr:0101-a"}, {}))


class CueTest(unittest.TestCase):
    def test_cues_outside_the_opening_phrase(self):
        text = "Fictopoli, sancti Ficti, qui in Fictonia natus, episcopus Fictensis, ibi obiit."
        self.assertEqual(p.cue_roles(text), ["birth", "death", "ministry"])
        self.assertEqual(p.cue_roles("Fictopoli, sancti Ficti, martyris."), [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: the new classes error with `AttributeError: module 'extract_places' has no attribute 'lead_items'` (and `validate_curated`, `cue_roles`).

- [ ] **Step 3: Write the minimal implementation**

Append to `scripts/extract_places.py`:

```python
# Openings that look like a place but are not.
NOT_A_PLACE = {
    "mr:0101-maria-dei-genetrix": "a time phrase (the octave of Christmas), not a place",
}


def lead_items(order, texts, typology, *, not_a_place):
    """Opening-place items by ID, and the IDs of back-references with no
    earlier place on their day. `via` names the entry whose printed phrase
    supplies `la`."""
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
            if kind == "place":
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py
git commit -m "feat: resolve place back-references, roles, curated places and cues (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Build, validate, outputs, and run on real data

**Files:**
- Modify: `scripts/extract_places.py` (append)
- Create: `data/places_curated.json` (`{}`)
- Test: `tests/test_places.py` (add a class)
- Generated: `data/places.json`, `docs/places-report.md`

**Interfaces:**
- Consumes: `lead_items`, `validate_curated`, `cue_roles`, `NOT_A_PLACE`, `ROLES`, `ROLE_OF_TYPOLOGY`, `MAX_WORDS`
- Produces:
  - `LONG_LEAD_OK: dict[str, str]`
  - `build(order, texts, typology, curated, *, not_a_place) -> dict`, with keys `places` ({id: [items]}), `unresolved`, `no_place`, `long` ([(id, la)]), `candidates` ({id: [roles]}), `curated_ids` (set)
  - `validate(result, texts, current_ids, deprecated_ids, typology, curated, *, long_ok) -> None`, which raises `AssertionError`
  - `render_json(places) -> str`, `render_report(result) -> str`
  - `load_texts` re-exported from `extract_typology`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_places.py`, before the `if __name__` block:

```python
class BuildTest(unittest.TestCase):
    ORDER = [("mr:0101-a", 1, 1), ("mr:0101-b", 1, 1), ("mr:0101-e", 1, 1)]
    TX = {
        "mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus est.",
        "mr:0101-b": "Ibídem, beáti Ficti B.",
        "mr:0101-e": "Sancti Fictitii E., episcopi.",
    }
    TY = {"mr:0101-a": "dies_natalis", "mr:0101-b": "depositio", "mr:0101-e": "celebratio"}
    CUR = {"mr:0101-a": [{"role": "birth", "la": "in Fictonia"}]}

    def build(self, curated=None):
        return p.build(self.ORDER, self.TX, self.TY, self.CUR if curated is None else curated, not_a_place={})

    def test_build(self):
        r = self.build()
        self.assertEqual(r["places"]["mr:0101-a"], [
            {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"},
            {"role": "birth", "la": "in Fictonia", "source": "curated"},
        ])
        self.assertEqual(r["no_place"], ["mr:0101-e"])
        self.assertEqual(r["candidates"], {"mr:0101-a": ["birth"]})
        self.assertEqual(r["curated_ids"], {"mr:0101-a"})

    def test_validate(self):
        ids = set(self.TX)
        r = self.build()
        p.validate(r, self.TX, ids, {"mr:0199-old"}, self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["places"]["mr:0101-a"][0]["role"] = "burial"   # disagrees with typology
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["places"]["mr:0101-b"][0]["la"] = "Fictlandia"   # not verbatim in the via text
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        with self.assertRaises(AssertionError):
            p.validate(r, self.TX, ids, {"mr:0101-a"}, self.TY, self.CUR, long_ok={})
        with self.assertRaises(AssertionError):
            p.validate(r, self.TX, ids, set(), self.TY, {"mr:0101-a": [{"role": "x", "la": "y"}]}, long_ok={})

    def test_long_lead_needs_allow_list(self):
        tx = {"mr:0101-a": " ".join(["In Fictia"] * 7) + ", sancti Ficti."}
        order, ty = [("mr:0101-a", 1, 1)], {"mr:0101-a": "dies_natalis"}
        r = p.build(order, tx, ty, {}, not_a_place={})
        self.assertEqual([k for k, _ in r["long"]], ["mr:0101-a"])
        with self.assertRaises(AssertionError):
            p.validate(r, tx, {"mr:0101-a"}, set(), ty, {}, long_ok={})
        p.validate(r, tx, {"mr:0101-a"}, set(), ty, {}, long_ok={"mr:0101-a": "reason"})

    def test_render_json(self):
        import json
        out = json.loads(p.render_json(self.build()["places"]))
        self.assertEqual(out["roles"], p.ROLES)
        self.assertEqual(list(out["places"]), ["mr:0101-a", "mr:0101-b"])

    def test_report(self):
        report = p.render_report(self.build())
        self.assertIn("| death | 1 |", report)
        self.assertIn("## Curation candidates", report)
        self.assertIn("| `mr:0101-a` | birth | yes |", report)
        self.assertIn("`mr:0101-e`", report)
        self.assertNotIn("Fictitii", report)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `BuildTest` errors with `AttributeError: module 'extract_places' has no attribute 'build'`.

- [ ] **Step 3: Write the minimal implementation**

Add `from extract_typology import load_texts` to the imports of `scripts/extract_places.py` (after `from pathlib import Path`, separated by a blank line), then append:

```python
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
```

Create `data/places_curated.json` with the content `{}` followed by a newline.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Run on the real data**

Run: `python3 scripts/extract_places.py ../martyrology-texts`
Expected: `4228 entries with places; 7 unresolved back-references; 548 curation candidates`, give or take a few for the exact entry counts. The 4,276 opening phrases, minus the 7 unresolved, minus `NOT_A_PLACE`, and minus any others the run reveals. Record the actual numbers.

- [ ] **Step 6: Review against the Latin**

Read every opening place over 12 words (report section), and print a random sample of 100 opening places with their IDs:

```bash
python3 - <<'EOF'
import json, random
pl = json.load(open("data/places.json"))["places"]
random.seed(12)
for k in random.sample(sorted(pl), 100):
    print(k, "|", pl[k][0]["la"], "|", pl[k][0]["role"], pl[k][0].get("via", ""))
EOF
```

For each one that is not a pure place designation, fix the rule (with a test) or add the ID to `NOT_A_PLACE` with the reason. Re-run Step 5 afterwards.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py data/places_curated.json data/places.json docs/places-report.md
git commit -m "feat: extract_places CLI; generate data/places.json and report (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Merge places into the registry

**Files:**
- Modify: `scripts/extract_registry.py` (`load_typology` message, add `load_places` / `add_places`, `main`)
- Test: `tests/test_registry.py` (add a class)
- Regenerated: `data/martyrology_ids.json`

**Interfaces:**
- Consumes: `data/places.json` (`{"places": {id: [items]}}`)
- Produces:
  - `RECOVERY: str` (shared hint)
  - `load_places(repo_root: Path, current_ids: set[str]) -> dict[str, list]`. Returns `{}` if the file is missing; raises `AssertionError` (with `RECOVERY`) if a key isn't a current ID.
  - `add_places(entries: list[dict], places: dict) -> list[dict]`. Inserts `"places"` after `"typology"`, or after `"country"` if the entry has no typology. It's idempotent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`, before the `if __name__` block:

```python
PLACES = {"mr:0101-fictitius": [{"role": "death", "la": "Fictopoli", "source": "lead"}]}


class RegistryPlacesTest(unittest.TestCase):
    def test_add_places_after_typology(self):
        e = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        out = r.add_places(e, PLACES)
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country",
                                        "typology", "places", "note"])

    def test_add_places_without_typology_goes_after_country(self):
        out = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(list(out[0])[5:7], ["country", "places"])

    def test_add_places_is_idempotent_and_skips_placeless(self):
        once = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(r.add_places(once, PLACES), once)
        self.assertNotIn("places", r.add_places([dict(ENTRY)], {})[0])

    def test_load_places(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius"}), {})
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "places.json").write_text(json.dumps({"places": PLACES}), encoding="utf-8")
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius", "mr:0102-x"}), PLACES)
            with self.assertRaisesRegex(AssertionError, "move data/places.json aside"):
                r.load_places(Path(d), {"mr:0102-x"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `RegistryPlacesTest` errors with `AttributeError: module 'extract_registry' has no attribute 'add_places'`.

- [ ] **Step 3: Implement**

In `scripts/extract_registry.py`, replace the body of the stale-typology assertion in `load_typology` so both loaders share one recovery hint. Add above `load_typology`:

```python
# extract_typology.py and extract_places.py read the current IDs from the
# registry, so after an ID change the registry must be regenerated once
# without their outputs.
RECOVERY = (
    "To recover: move data/{name} aside, run scripts/extract_registry.py, "
    "run scripts/extract_{script}.py, then run scripts/extract_registry.py again."
)
```

and change the assertion in `load_typology` to:

```python
    assert set(typology) == set(current_ids), (
        "data/typology.json does not match the current IDs. "
        + RECOVERY.format(name="typology.json", script="typology"))
```

(delete the two comment lines that preceded the old assertion). Then add after `add_typology`:

```python
def load_places(repo_root, current_ids):
    """Places stated by each current eulogy (data/places.json, generated by
    extract_places.py). Missing file: no places."""
    path = repo_root / "data" / "places.json"
    if not path.exists():
        return {}
    places = json.load(open(path, encoding="utf-8"))["places"]
    assert set(places) <= set(current_ids), (
        "data/places.json has IDs that are not current. "
        + RECOVERY.format(name="places.json", script="places"))
    return places


def add_places(entries, places):
    """Insert "places" after "typology" (or "country"); key order is output order."""
    out = []
    for e in entries:
        if e["id"] not in places:
            out.append(e)
            continue
        anchor = "typology" if "typology" in e else "country"
        row = {}
        for k, v in e.items():
            if k == "places":
                continue
            row[k] = v
            if k == anchor:
                row["places"] = places[e["id"]]
        out.append(row)
    return out
```

In `main()`, after the `add_typology` line:

```python
    entries = add_places(entries, load_places(repo_root, {e["id"] for e in entries}))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass, including the existing stale-typology test (its regex still matches the recovery steps).

- [ ] **Step 5: Regenerate the registry from the existing JSON**

```bash
python3 - <<'EOF'
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import extract_registry as r
root = Path(".")
d = json.load(open("data/martyrology_ids.json", encoding="utf-8"))
cur = [e for e in d["entries"] if not e.get("deprecated")]
dep = [e for e in d["entries"] if e.get("deprecated")]
cur = r.add_places(cur, r.load_places(root, {e["id"] for e in cur}))
r.write_json(cur, dep, root)
r.write_markdown(cur, root)
EOF
git status --short registry
python3 - <<'EOF'
import json, subprocess
old = json.loads(subprocess.run(["git", "show", "HEAD:data/martyrology_ids.json"], capture_output=True, text=True).stdout)
new = json.load(open("data/martyrology_ids.json"))
strip = lambda d: {**d, "entries": [{k: v for k, v in e.items() if k != "places"} for e in d["entries"]]}
assert strip(new) == old, "registry changed beyond places"
places = json.load(open("data/places.json"))["places"]
assert {e["id"]: e["places"] for e in new["entries"] if "places" in e} == places
assert not any("places" in e for e in new["entries"] if e.get("deprecated"))
E = new["entries"]
assert new["entry_count"] == len(E) == new["current_count"] + new["deprecated_count"]
keys = [set(json.load(open(f"i18n/{l}.json"))) for l in ("la", "it", "en")]
assert keys[0] == keys[1] == keys[2]
print("registry ok")
EOF
```

Expected: `git status` shows no change under `registry/` (no places column), then `registry ok`.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_registry.py tests/test_registry.py data/martyrology_ids.json
git commit -m "feat: merge places into the registry JSON (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Documentation, quoting policy, spec refinements

**Files:**
- Modify: `AGENTS.md`, `README.md`, `docs/canonicalization-report.md`, `docs/superpowers/specs/2026-09-30-places-extraction-design.md`

- [ ] **Step 1: The quoting exception in `AGENTS.md`**

After the paragraph that starts `**The copyrighted eulogy texts are deliberately absent.**`, add:

```markdown
**One exception: place designations.** Place designations are factual and may be quoted verbatim in `places[].la` (`data/places.json`). No other elogium text is stored. `scripts/extract_places.py` enforces this: every `la` must appear verbatim in its elogium and be at most 12 words (longer opening places need a commented `LONG_LEAD_OK` entry).
```

In the pipeline list, add after the `extract_typology.py` item:

```markdown
4. **`scripts/extract_places.py`** reads `data/martyrology_ids.json`, `data/typology.json`, `data/places_curated.json` and the private `martyrology-texts` repo (Latin editio altera 2004), and writes `data/places.json` (the places each current eulogy states, with roles) and `docs/places-report.md` (including the curation candidates). `extract_registry.py` merges `data/places.json` after `typology`.
   - Run: `python3 scripts/extract_places.py /path/to/martyrology-texts` (stdlib only)
```

In "Where hand-corrections live", add:

```markdown
- `data/places_curated.json` — hand-entered body places (birth, see, burial or death elsewhere); `NOT_A_PLACE` / `LONG_LEAD_OK` in `scripts/extract_places.py`
```

- [ ] **Step 2: `README.md`**

In "Copyright and the absence of texts", append the sentence: `Place designations are the one exception: they are factual and are quoted verbatim in the places data.` In "Repository contents", after the `data/typology.json` item, add:

```markdown
- [`data/places.json`](data/places.json) — the places each current eulogy states, quoted as printed in the Latin editio altera 2004, each with a role (`death`, `burial`, `translation`, `dedication`, `cult`, `birth`, `ministry`); also merged into `data/martyrology_ids.json`. Body places are curated in [`data/places_curated.json`](data/places_curated.json); report and curation candidates in [`docs/places-report.md`](docs/places-report.md)
```

- [ ] **Step 3: "Places" section in `docs/canonicalization-report.md`**

Insert before `## Post-2004 official variations`, with the real counts from Task 3:

```markdown
## Places (September 2026)

Current entries may carry `places`: the places the elogium states, each quoted
exactly as printed in the Latin editio altera 2004 (`la`) and given a role:
`death`, `burial`, `translation`, `dedication`, `cult` (where the saint is
venerated or commemorated), `birth`, `ministry` (see or field of work). Place
designations are factual and are the one piece of elogium text the repository
quotes.

The **opening place** is extracted by `scripts/extract_places.py`: the text before
the first lowercase honorific or marker word (the print capitalizes a saint inside
a place name, "in monasterio Sancti N.", but not the subject's honorific), without
a trailing "eodem die et anno". Its role follows `typology` (dies_natalis → death,
depositio → burial, translatio/inventio → translation, dedicatio → dedication,
ordinatio → ministry, celebratio/commemoratio → cult). A leading *Item* is dropped;
*Ibidem* and a bare *Item* take the place of the nearest earlier entry of the same
day, named in `via`.

**Body places** (birth, see, burial or death elsewhere) are hand-curated in
`data/places_curated.json`; `docs/places-report.md` lists the candidate entries
whose text holds a role cue. A later step resolves each distinct place to a
Wikidata item and a modern country (#12).

Counts: <entries with places> entries with places, <unresolved> unresolved
back-references, <candidates> curation candidates.
```

Replace each `<…>` with the number printed in Task 3, Step 5.

- [ ] **Step 4: Spec refinements**

In `docs/superpowers/specs/2026-09-30-places-extraction-design.md`, under "Extracting the opening place", add a bullet list at the end of the "Then:" list:

```markdown
- A trailing ", eodem die et anno" (on the same day and year) is stripped.
- `NOT_A_PLACE` lists openings that are not places (`mr:0101-maria-dei-genetrix`:
  "In octava Nativitatis Domini…", a time phrase), each with the reason.
- *Ibidem* followed by more words ("Ibidem in coemeterio …") keeps its printed
  phrase and records the antecedent in `via`.
- `via` always names the entry whose printed phrase supplies `la`, i.e. the root of
  a chain of back-references.
```

and replace "about 3,460 entries with a real opening place" with the real count from Task 3.

- [ ] **Step 5: Final verification**

Run: `python3 -m unittest discover -s tests -v && git diff --check`
Then the overlap scan of the tests:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "scripts")
from pathlib import Path
from extract_subjects import fold
import extract_typology as t
tx = t.load_texts(Path("../martyrology-texts"))
grams = set()
for v in tx.values():
    w = fold(v).split(); grams.update(" ".join(w[i:i+5]) for i in range(len(w) - 4))
for f in ["tests/test_places.py", "tests/test_registry.py"]:
    w = fold(open(f).read()).split()
    print(f, sorted({" ".join(w[i:i+5]) for i in range(len(w) - 4)} & grams))
EOF
```

Expected: all tests pass; no whitespace errors; both files print `[]`.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md README.md docs/canonicalization-report.md docs/superpowers/specs/2026-09-30-places-extraction-design.md
git commit -m "docs: places data, quoting exception, extraction rules (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
