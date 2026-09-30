# Italian Place Phrases and Misprints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Italian (CEI 2004) place phrase as `places[].it` next to `la`, and record verified print misprints in `data/misprints.json`, which also feeds the stop-word lists.

**Architecture:** `scripts/extract_places.py` gains:
- a misprints loader and validator, which replace the hard-coded `MISPRINTED_STOP_WORDS`;
- an Italian opening-phrase extractor (Italian stop words, a comma-segment rule, *Sempre / Ancora* and "nello stesso luogo");
- an alignment step in `build()`, where the Latin decides the item, a bare Latin back-reference takes the root's `it`, and every other item takes its own Italian phrase.

Stop words are passed explicitly instead of being read from a global. `extract_typology.load_texts` gains an edition parameter.

**Tech Stack:** Python 3 standard library only.

**Spec:** `docs/superpowers/specs/2026-09-30-places-italian-design.md` (builds on `docs/superpowers/specs/2026-09-30-places-extraction-design.md`).

## Global Constraints

- Item key order: `role`, `la`, `it` (when present), `source`, `via` (when present).
- `it` appears verbatim in its Italian text (own, or the `via` entry's for a bare back-reference), at most 20 words (`MAX_WORDS_IT = 20`). `la` rules are unchanged (12 words, `LONG_LEAD_OK`).
- The Latin decides whether an item exists; `it` is only ever added to an item with `la`. Every existing `la` stays exactly as it is.
- `data/misprints.json` records have exactly the keys `id`, `edition`, `printed`, `intended`, `verified`. The edition is `martyrologium_romanum_2004` or `martyrologium_romanum_2004_it_IT`. `printed` occurs exactly once in that entry's text. Records are sorted by `id`, then `edition`.
- No other text of either edition in any committed file. Tests use made-up Latin and Italian; the 5-word overlap scan covers both the Latin and the Italian texts.
- Standard library only. Test command: `python3 -m unittest discover -s tests -v` from the repo root.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An entry with no Italian text** (`mr:0104-abrunculus` is absent from the CEI edition). No `it`, no crash, listed as a Latin place without an Italian phrase. Pinned in Task 3.
2. **The curly apostrophe in Italian elisions** ("nell’odierna", "dell’odierna"). The first word of the segment must read as *nell*, so a modern hint is kept. Pinned in Task 2.
3. **Accented words inside cut patterns** ("più tardi"). Matching happens on the accent-stripped copy, so the clause is still cut. Pinned in Task 2.
4. **A misprint recorded for one edition.** It must not change stop words for the other language. Pinned in Task 1.
5. **A bare Latin back-reference whose root has no `it`.** Neither item gets `it`, and validation accepts that. Pinned in Task 3.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `data/misprints.json` (create) | The three verified misprints |
| `scripts/extract_typology.py` (modify) | `load_texts(texts_repo, edition=…)` |
| `scripts/extract_places.py` (modify) | Misprints; stop words passed explicitly; Italian phrase; alignment; validation; report; CLI |
| `tests/test_places.py` (modify) | Tests for the above |
| `data/places.json`, `docs/places-report.md`, `data/martyrology_ids.json` (regenerated) | Output |
| `AGENTS.md`, `README.md`, `docs/canonicalization-report.md` (modify) | Docs |

---

### Task 1: Misprints as data; stop words passed explicitly

**Files:**
- Create: `data/misprints.json`
- Modify: `scripts/extract_typology.py` (`load_texts`), `scripts/extract_places.py`
- Test: `tests/test_places.py`

**Interfaces:**
- Produces:
  - `EDITION_LA = "martyrologium_romanum_2004"`, `EDITION_IT = "martyrologium_romanum_2004_it_IT"`
  - `load_misprints(repo_root: Path) -> list[dict]` (missing file → `[]`)
  - `validate_misprints(misprints: list[dict], texts_by_edition: dict[str, dict[str, str]], current_ids: set[str]) -> list[str]` (errors)
  - `misprint_stop_words(misprints: list[dict], edition: str, stop_words: set[str]) -> set[str]`
  - `opening_phrase(text, stop_words=STOP_WORDS)`, `lead_items(order, texts, typology, *, not_a_place, stop_words=STOP_WORDS)`, `cue_matches(text, stop_words=STOP_WORDS)`, `build(order, texts, typology, curated, *, not_a_place, stop_words=STOP_WORDS)`
  - `extract_typology.load_texts(texts_repo, edition="martyrologium_romanum_2004")`

- [ ] **Step 1: Write the failing tests**

In `tests/test_places.py`, replace the existing test method `test_printed_misprint_of_an_honorific_ends_the_phrase` with:

```python
    def test_printed_misprint_of_an_honorific_ends_the_phrase(self):
        text = "In vico Ficto item in Fictia, betárum mártyrum Fictarum."
        self.assertIsNone(p.opening_phrase(text))
        self.assertEqual(p.opening_phrase(text, p.STOP_WORDS | {"betarum"}), "In vico Ficto item in Fictia")
```

and add before `class CuratedTest`:

```python
MISPRINTS = [
    {"id": "mr:0101-a", "edition": "martyrologium_romanum_2004", "printed": "betárum",
     "intended": "beatárum", "verified": "print"},
    {"id": "mr:0101-b", "edition": "martyrologium_romanum_2004_it_IT", "printed": "desposizione",
     "intended": "deposizione", "verified": "print"},
]
MTEXTS = {
    "martyrologium_romanum_2004": {"mr:0101-a": "Fictopoli, betárum Fictarum.", "mr:0101-b": "Fictopoli, sancti Ficti."},
    "martyrologium_romanum_2004_it_IT": {"mr:0101-a": "A Fictopoli, beate Fitte.", "mr:0101-b": "A Fictopoli, desposizione di san Fitto."},
}


class MisprintTest(unittest.TestCase):
    def test_valid_records(self):
        self.assertEqual(p.validate_misprints(MISPRINTS, MTEXTS, {"mr:0101-a", "mr:0101-b"}), [])

    def test_invalid_records(self):
        ids = {"mr:0101-a", "mr:0101-b"}
        bad = [dict(MISPRINTS[0], printed="betorum")]                          # not in the text
        self.assertTrue(p.validate_misprints(bad, MTEXTS, ids))
        twice = {**MTEXTS, "martyrologium_romanum_2004": {"mr:0101-a": "betárum, betárum."}}
        self.assertTrue(p.validate_misprints(MISPRINTS[:1], twice, ids))      # occurs twice
        self.assertTrue(p.validate_misprints([dict(MISPRINTS[0], edition="x")], MTEXTS, ids))
        self.assertTrue(p.validate_misprints([dict(MISPRINTS[0], id="mr:0102-z")], MTEXTS, ids))
        self.assertTrue(p.validate_misprints([{"id": "mr:0101-a"}], MTEXTS, ids))
        self.assertTrue(p.validate_misprints(list(reversed(MISPRINTS)), MTEXTS, ids))   # unsorted

    def test_stop_words_per_edition(self):
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_LA, p.STOP_WORDS), {"betarum"})
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_LA, {"sancti"}), set())
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_IT, {"deposizione"}), {"desposizione"})

    def test_load_misprints(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(p.load_misprints(Path(d)), [])
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "misprints.json").write_text(json.dumps({"misprints": MISPRINTS}), encoding="utf-8")
            self.assertEqual(p.load_misprints(Path(d)), MISPRINTS)

    def test_repository_file_is_valid_shape(self):
        import json
        path = Path(__file__).resolve().parent.parent / "data" / "misprints.json"
        records = json.load(open(path, encoding="utf-8"))["misprints"]
        self.assertEqual([(r["id"], r["edition"]) for r in records],
                         sorted((r["id"], r["edition"]) for r in records))
        self.assertTrue(all(set(r) == p.MISPRINT_KEYS for r in records))
        self.assertEqual({r["printed"] for r in records}, {"betárum", "desposizione", "comemorazione"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected:
- `test_printed_misprint_of_an_honorific_ends_the_phrase` FAILS: `opening_phrase` takes one argument, and `betarum` is still a hard-coded stop word.
- `MisprintTest` ERRORS with `AttributeError` (`validate_misprints`, `misprint_stop_words`, `load_misprints`) or `FileNotFoundError` (`data/misprints.json`).

- [ ] **Step 3: Implement**

Create `data/misprints.json`:

```json
{
  "$comment": "Verified misprints in the printed 2004 editions of the Roman Martyrology. printed occurs exactly once in the entry's text of that edition (a CLBDR edition ID, as in martyrology-texts), so a frontend can attach a footnote. Hand-maintained; see docs/canonicalization-report.md.",
  "misprints": [
    {
      "id": "mr:0927-francisca-xaveria-fenollosa-alcayna",
      "edition": "martyrologium_romanum_2004",
      "printed": "betárum",
      "intended": "beatárum",
      "verified": "page image and OCR layer (print 11*)"
    },
    {
      "id": "mr:1013-comganus",
      "edition": "martyrologium_romanum_2004_it_IT",
      "printed": "desposizione",
      "intended": "deposizione",
      "verified": "print"
    },
    {
      "id": "mr:1014-venantius",
      "edition": "martyrologium_romanum_2004_it_IT",
      "printed": "comemorazione",
      "intended": "commemorazione",
      "verified": "print"
    }
  ]
}
```

In `scripts/extract_typology.py`, change `load_texts` to take the edition:

```python
def load_texts(texts_repo, edition="martyrologium_romanum_2004"):
    folder = texts_repo / "data" / "editions" / edition
    texts = {}
    for month in range(1, 13):
        with open(folder / f"{month:02d}.json", encoding="utf-8") as f:
            texts.update(json.load(f))
    return texts
```

In `scripts/extract_places.py`:

1. Delete the `MISPRINTED_STOP_WORDS` block and the `STOP_WORDS |= set(MISPRINTED_STOP_WORDS)` line (the four comment lines and dict above it included).
2. After `BACK_REFS = …`, add:

```python
EDITION_LA = "martyrologium_romanum_2004"
EDITION_IT = "martyrologium_romanum_2004_it_IT"
MISPRINT_KEYS = {"id", "edition", "printed", "intended", "verified"}
```

3. Replace `def opening_phrase(text):` and its first loop with a version that takes the stop words (the rest of the body is unchanged):

```python
def opening_phrase(text, stop_words=STOP_WORDS):
    copy = base_copy(text)
    for i, m in enumerate(WORD.finditer(copy)):
        w = m.group(0)
        if w.lower() in stop_words and (w[0].islower() or i == 0):
            phrase = text[:m.start()].strip(TRIM)
            break
    else:
        return None
```

4. `lead_items`: change the signature to `def lead_items(order, texts, typology, *, not_a_place, stop_words=STOP_WORDS):` and its call to `opening_phrase(texts[mrid], stop_words)`.
5. `cue_matches`: change to `def cue_matches(text, stop_words=STOP_WORDS):` and its body's call to `opening_phrase(text, stop_words)`.
6. `build`: change the signature to `def build(order, texts, typology, curated, *, not_a_place, stop_words=STOP_WORDS):`, pass `stop_words=stop_words` to `lead_items`, and use `cue_matches(texts[mrid], stop_words)`.
7. Add after `check_typology`:

```python
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
```

8. In `main()`, after `check_typology(…)`:

```python
    misprints = load_misprints(repo_root)
```

and replace the lines from `texts = load_texts(texts_repo)` through the `validate(…)` call with:

```python
    texts = load_texts(texts_repo)
    texts_it = load_texts(texts_repo, EDITION_IT)
    errors = validate_misprints(misprints, {EDITION_LA: texts, EDITION_IT: texts_it},
                                {m for m, _, _ in order})
    assert not errors, "invalid data/misprints.json:\n" + "\n".join(errors)
    stop_words = STOP_WORDS | misprint_stop_words(misprints, EDITION_LA, STOP_WORDS)
    result = build(order, texts, typology, curated, not_a_place=NOT_A_PLACE, stop_words=stop_words)
    validate(result, texts, {m for m, _, _ in order}, deprecated, typology, curated, long_ok=LONG_LEAD_OK)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Regenerate and check nothing changed**

Run: `python3 scripts/extract_places.py ../martyrology-texts && git status --short data docs`
Expected: `4261 entries with places; …`, and `git status` shows only `data/misprints.json` as new: `data/places.json` and `docs/places-report.md` are unchanged.

- [ ] **Step 6: Commit**

```bash
git add data/misprints.json scripts/extract_typology.py scripts/extract_places.py tests/test_places.py
git commit -m "feat: record verified print misprints in data/misprints.json (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Italian opening phrase

**Files:**
- Modify: `scripts/extract_places.py` (add after `split_lead`)
- Test: `tests/test_places.py`

**Interfaces:**
- Consumes: `base_copy`, `WORD`, `TRIM`
- Produces: `STOP_WORDS_IT: set[str]`, `LOCATIVE_IT: set[str]`, `MAX_WORDS_IT = 20`, `italian_phrase(text: str | None, stop_words=STOP_WORDS_IT) -> str | None`. It returns `None` for no phrase and for a bare back-reference.

- [ ] **Step 1: Write the failing tests**

Add before `class CuratedTest`:

```python
class ItalianPhraseTest(unittest.TestCase):
    def test_lowercase_honorific_and_markers_end_the_phrase(self):
        self.assertEqual(p.italian_phrase("A Fittopoli in Fittia, san Fitto, vescovo."), "A Fittopoli in Fittia")
        self.assertEqual(p.italian_phrase("Nel cenobio di Fittaco, beata Fitta."), "Nel cenobio di Fittaco")
        self.assertEqual(p.italian_phrase("A Fittopoli, anniversario della morte di san Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, martirio dei santi Fitti."), "A Fittopoli")

    def test_capitalized_saint_in_a_place_name_stays(self):
        self.assertEqual(p.italian_phrase("A San Fittorino nelle Fittie, beato Fitto."), "A San Fittorino nelle Fittie")

    def test_capitalized_stop_word_at_start_means_no_phrase(self):
        self.assertIsNone(p.italian_phrase("Memoria di san Fitto, vescovo."))
        self.assertIsNone(p.italian_phrase("Parimenti si commemorano i santi Fitti."))

    def test_modern_hints_after_a_comma_are_kept(self):
        self.assertEqual(p.italian_phrase("A Fittopoli in Fittia, nell’odierna Fittonia, san Fitto."),
                         "A Fittopoli in Fittia, nell’odierna Fittonia")
        self.assertEqual(p.italian_phrase("A Fittopoli, ora in Fittonia, sempre in Fittia, beato Fitto."),
                         "A Fittopoli, ora in Fittonia, sempre in Fittia")

    def test_clauses_after_a_comma_are_cut(self):
        self.assertEqual(p.italian_phrase("A Fittopoli, dove si era rifugiato, san Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, trent’anni più tardi, beato Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, sotto il medesimo re, beato Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("Nel cenobio di Fittaco, da lui fondato, san Fitto."), "Nel cenobio di Fittaco")
        self.assertEqual(p.italian_phrase("A Fittopoli, trecentosei santi martiri."), "A Fittopoli")

    def test_sempre_and_back_references(self):
        self.assertEqual(p.italian_phrase("Sempre a Fittopoli, san Fitto."), "a Fittopoli")
        self.assertEqual(p.italian_phrase("Ancora a Fittopoli, beato Fitto."), "a Fittopoli")
        self.assertIsNone(p.italian_phrase("Nello stesso luogo, san Fitto."))
        self.assertIsNone(p.italian_phrase("Nella stessa città, beata Fitta."))
        self.assertIsNone(p.italian_phrase("Sempre nello stesso luogo, san Fitto."))
        self.assertIsNone(p.italian_phrase("Nello stesso luogo, nello stesso giorno e anno, beati Fitti."))

    def test_no_text(self):
        self.assertIsNone(p.italian_phrase(None))
        self.assertIsNone(p.italian_phrase(""))

    def test_misprinted_stop_word(self):
        text = "A Fittopoli in Fittia desposizione di san Fitto."
        self.assertEqual(p.italian_phrase(text, p.STOP_WORDS_IT | {"desposizione"}), "A Fittopoli in Fittia")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `ItalianPhraseTest` errors with `AttributeError: module 'extract_places' has no attribute 'italian_phrase'`.

- [ ] **Step 3: Implement**

Add after `split_lead` in `scripts/extract_places.py`:

```python
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
MAX_WORDS_IT = 20


def italian_phrase(text, stop_words=STOP_WORDS_IT):
    """The Italian opening phrase, or None when there is none or it is a
    bare back-reference ("Nello stesso luogo")."""
    if not text:
        return None
    copy = base_copy(text)
    for i, m in enumerate(WORD.finditer(copy)):
        w = m.group(0)
        if w.lower() in stop_words and (w[0].islower() or i == 0):
            phrase = text[:m.start()].strip(TRIM)
            break
    else:
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
```

(`solennita` is listed without the accent because matching uses `base_copy(...).lower()`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py
git commit -m "feat: Italian opening-phrase extraction for places (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Align `it` with the Latin items; validation; report; run on real data

**Files:**
- Modify: `scripts/extract_places.py` (`validate_curated`, `build`, `validate`, `render_report`, `main`)
- Test: `tests/test_places.py`
- Regenerated: `data/places.json`, `docs/places-report.md`

**Interfaces:**
- Consumes: `italian_phrase`, `STOP_WORDS_IT`, `MAX_WORDS_IT`, `misprint_stop_words`, `EDITION_IT`
- Produces:
  - `with_it(item: dict, it: str) -> dict` (rebuilds the key order)
  - `build(..., texts_it=None, stop_words_it=STOP_WORDS_IT)`. The result gains `no_it` (IDs) and `it_only` ([(id, phrase)]).
  - `validate(..., texts_it=None)`
  - `validate_curated(curated, texts, current_ids, leads, texts_it=None)`

- [ ] **Step 1: Write the failing tests**

Add before `class CuratedTest`:

```python
class ItalianAlignmentTest(unittest.TestCase):
    ORDER = [("mr:0105-a", 1, 5), ("mr:0105-b", 1, 5), ("mr:0105-c", 1, 5), ("mr:0105-e", 1, 5)]
    TX = {
        "mr:0105-a": "Fictopoli in Fictia, sancti Fictitii A.",
        "mr:0105-b": "Ibídem, beáti Ficti B.",
        "mr:0105-c": "Ficticastro, sancti Ficti C.",
        "mr:0105-e": "Sancti Fictitii E.",
    }
    IT = {
        "mr:0105-a": "A Fittopoli in Fittia, ora in Fittonia, san Fitto A.",
        "mr:0105-b": "Nello stesso luogo, beato Fitto B.",
        "mr:0105-e": "A Fittocastro, san Fitto E.",
    }
    TY = {k: "dies_natalis" for k in TX}

    def build(self, it=None, curated=None):
        return p.build(self.ORDER, self.TX, self.TY, curated or {}, not_a_place={},
                       texts_it=self.IT if it is None else it)

    def test_alignment(self):
        r = self.build()
        a, b = r["places"]["mr:0105-a"][0], r["places"]["mr:0105-b"][0]
        self.assertEqual(list(a), ["role", "la", "it", "source"])
        self.assertEqual(a["it"], "A Fittopoli in Fittia, ora in Fittonia")
        self.assertEqual(list(b), ["role", "la", "it", "source", "via"])
        self.assertEqual(b["it"], a["it"])                           # bare Latin back-reference: root's it
        self.assertNotIn("it", r["places"]["mr:0105-c"][0])        # no Italian text
        self.assertEqual(r["no_it"], ["mr:0105-c"])
        self.assertEqual(r["it_only"], [("mr:0105-e", "A Fittocastro")])

    def test_root_without_it(self):
        r = self.build(it={"mr:0105-b": "Nello stesso luogo, beato Fitto B."})
        self.assertNotIn("it", r["places"]["mr:0105-a"][0])
        self.assertNotIn("it", r["places"]["mr:0105-b"][0])
        p.validate(r, self.TX, set(self.TX), set(), self.TY, {}, long_ok={}, texts_it=self.IT)

    def test_validate_it(self):
        ids = set(self.TX)
        r = self.build()
        p.validate(r, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        bad = self.build(); bad["places"]["mr:0105-a"][0]["it"] = "A Fittonia"            # not verbatim
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        bad = self.build(); bad["places"]["mr:0105-b"][0]["it"] = "Nello stesso luogo"    # not the root's it
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        long_it = {"mr:0105-a": " ".join(["A Fittia"] * 11) + ", san Fitto."}
        bad = self.build(it=long_it)
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=long_it)

    def test_curated_it(self):
        tx = {"mr:0105-a": "Fictopoli, sancti Ficti, qui in Fictonia natus est."}
        it = {"mr:0105-a": "A Fittopoli, san Fitto, nato in Fittonia."}
        ok = {"mr:0105-a": [{"role": "birth", "la": "in Fictonia", "it": "in Fittonia"}]}
        self.assertEqual(p.validate_curated(ok, tx, {"mr:0105-a"}, {}, it), [])
        bad = {"mr:0105-a": [{"role": "birth", "la": "in Fictonia", "it": "in Fittlandia"}]}
        self.assertTrue(p.validate_curated(bad, tx, {"mr:0105-a"}, {}, it))
        r = p.build([("mr:0105-a", 1, 5)], tx, {"mr:0105-a": "dies_natalis"}, ok, not_a_place={}, texts_it=it)
        self.assertEqual(r["places"]["mr:0105-a"][1],
                         {"role": "birth", "la": "in Fictonia", "it": "in Fittonia", "source": "curated"})

    def test_report_sections(self):
        report = p.render_report(self.build())
        self.assertIn("## Latin places without an Italian phrase", report)
        self.assertIn("`mr:0105-c`", report)
        self.assertIn("## Italian places without a Latin place", report)
        self.assertIn("- `mr:0105-e`: A Fittocastro", report)

    def test_without_italian_texts_nothing_changes(self):
        r = p.build(self.ORDER, self.TX, self.TY, {}, not_a_place={})
        self.assertFalse(any("it" in it for its in r["places"].values() for it in its))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: `ItalianAlignmentTest` errors with `TypeError: build() got an unexpected keyword argument 'texts_it'`, and `validate_curated` with a positional-argument `TypeError`.

- [ ] **Step 3: Implement**

In `scripts/extract_places.py`:

1. Replace `validate_curated` with:

```python
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
```

2. Add before `build`:

```python
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
```

3. Replace `build` with:

```python
def build(order, texts, typology, curated, *, not_a_place, stop_words=STOP_WORDS,
          texts_it=None, stop_words_it=STOP_WORDS_IT):
    leads, unresolved = lead_items(order, texts, typology, not_a_place=not_a_place, stop_words=stop_words)
    no_it, it_only = [], []
    if texts_it is not None:
        for mrid, _, _ in order:
            phrase = italian_phrase(texts_it.get(mrid), stop_words_it)
            if mrid not in leads:
                if phrase:
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
```

4. In `validate`, change the signature to `def validate(result, texts, current_ids, deprecated_ids, typology, curated, *, long_ok, texts_it=None):`. Inside the item loop, after the existing `via` / verbatim `la` block and before `if it["source"] == "lead":`, add:

```python
            if "it" in it:
                assert texts_it is not None, f"{mrid}: it present but no Italian texts given"
                assert len(it["it"].split()) <= MAX_WORDS_IT, f"{mrid}: it has more than {MAX_WORDS_IT} words"
                bare = "via" in it and it["la"] not in texts[mrid]
                if bare:
                    root = places.get(it["via"], [{}])[0].get("it")
                    assert it["it"] == root, f"{mrid}: it is not the root {it['via']}'s it: {it['it']!r}"
                else:
                    assert it["it"] in texts_it.get(mrid, ""), f"{mrid}: it is not verbatim: {it['it']!r}"
            elif "via" in it and it["la"] not in texts[mrid]:
                root = places.get(it["via"], [{}])[0]
                assert "it" not in root, f"{mrid}: bare back-reference lacks its root's it"
```

and change the last two lines to:

```python
    errors = validate_curated(curated, texts, set(current_ids), leads, texts_it)
    assert not errors, "invalid curated places:\n" + "\n".join(errors)
```

5. In `render_report`, before the `"## Curation candidates",` line, add:

```python
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
```

and change the counts line to report `it` too:

```python
        f"{len(places)} entries with at least one place; "
        f"{source_counts['lead']} opening places, {source_counts['curated']} curated places; "
        f"{sum(1 for it in items if 'it' in it)} with an Italian phrase.",
```

6. In `main()`, replace the `stop_words = …`, `result = build(…)` and `validate(…)` lines with:

```python
    stop_words = STOP_WORDS | misprint_stop_words(misprints, EDITION_LA, STOP_WORDS)
    stop_words_it = STOP_WORDS_IT | misprint_stop_words(misprints, EDITION_IT, STOP_WORDS_IT)
    result = build(order, texts, typology, curated, not_a_place=NOT_A_PLACE, stop_words=stop_words,
                   texts_it=texts_it, stop_words_it=stop_words_it)
    validate(result, texts, {m for m, _, _ in order}, deprecated, typology, curated,
             long_ok=LONG_LEAD_OK, texts_it=texts_it)
```

and add to the final `print` the number of places with `it` and the two mismatch counts:

```python
    print(f"{len(result['places'])} entries with places; {len(result['unresolved'])} unresolved "
          f"back-references; {len(result['candidates'])} curation candidates; "
          f"{sum(1 for its in result['places'].values() for it in its if 'it' in it)} with it; "
          f"{len(result['no_it'])} without it; {len(result['it_only'])} Italian-only")
```

Update the module docstring's first paragraph to say each place is quoted from the Latin (`la`) and the Italian CEI edition (`it`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Run on the real data**

Run: `python3 scripts/extract_places.py ../martyrology-texts`
Expected: `4261 entries with places; 3 unresolved back-references; 548 curation candidates; ~4257 with it; ~4 without it; ~10 Italian-only`. Then check that no `la` changed:

```bash
python3 - <<'EOF'
import json, subprocess
old = json.loads(subprocess.run(["git", "show", "HEAD:data/places.json"], capture_output=True, text=True).stdout)["places"]
new = json.load(open("data/places.json"))["places"]
strip = lambda d: {k: [{f: v for f, v in it.items() if f != "it"} for it in its] for k, its in d.items()}
assert strip(new) == old, "an la or item changed"
print("only it added")
EOF
```

Expected: `only it added`.

- [ ] **Step 6: Scan every `it`**

```bash
python3 - <<'EOF'
import json, re
pl = json.load(open("data/places.json"))["places"]
its = [(k, it["it"]) for k, v in pl.items() for it in v if "it" in it]
print("with comma:"); [print(" ", k, "|", s) for k, s in its if "," in s]
print("over 16 words:"); [print(" ", k, "|", s) for k, s in its if len(s.split()) > 16]
EOF
sed -n '/## Latin places without an Italian phrase/,/## Curation candidates/p' docs/places-report.md
```

Read every line. Each comma segment must be a locative or a modern-country hint. Each `it` must be a place designation. Each mismatch must be explained. Fix any rule error with a new test in `ItalianPhraseTest` and re-run Steps 4–6.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py data/places.json docs/places-report.md
git commit -m "feat: Italian place phrases (places[].it) aligned with the Latin (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Registry, documentation, final checks

**Files:**
- Regenerated: `data/martyrology_ids.json`
- Modify: `AGENTS.md`, `README.md`, `docs/canonicalization-report.md`

- [ ] **Step 1: Regenerate the registry**

```bash
python3 - <<'EOF'
import json, sys, subprocess
from pathlib import Path
sys.path.insert(0, "scripts")
import extract_registry as r
root = Path(".")
d = json.load(open("data/martyrology_ids.json", encoding="utf-8"))
cur = [e for e in d["entries"] if not e.get("deprecated")]
dep = [e for e in d["entries"] if e.get("deprecated")]
ids = {e["id"] for e in cur}
typ, pl = r.load_typology(root, ids), r.load_places(root, ids)
r.check_place_roles(pl, typ)
cur = r.add_places(r.add_typology(cur, typ), pl)
r.write_json(cur, dep, root); r.write_markdown(cur, root)
new = json.load(open("data/martyrology_ids.json"))
assert {e["id"]: e["places"] for e in new["entries"] if "places" in e} == pl
old = json.loads(subprocess.run(["git", "show", "HEAD:data/martyrology_ids.json"], capture_output=True, text=True).stdout)
strip = lambda d: [{k: ([{f: v for f, v in it.items() if f != "it"} for it in val] if k == "places" else val)
                    for k, val in e.items()} for e in d["entries"]]
assert strip(new) == strip(old)
print("registry ok")
EOF
git status --short registry
```

Expected: `registry ok`; no change under `registry/`.

- [ ] **Step 2: Docs**

- **AGENTS.md:** replace the paragraph starting `**One exception: place designations.**` with:

  ```markdown
  **One exception: place designations.** Place designations are factual and may be quoted verbatim in `places[].la` (Latin editio typica altera 2004) and `places[].it` (Italian CEI edition 2004) in `data/places.json`. No other text of either edition is stored. `scripts/extract_places.py` enforces part of this in code: every `la` / `it` must appear verbatim in its elogium, `la` at most 12 words (longer opening places need a commented `LONG_LEAD_OK` entry) and `it` at most 20, and an opening place is cut at a comma that starts a clause. It cannot tell every narrative phrase from a place, so `docs/places-report.md` lists each Latin opening place that still contains a comma for review.
  ```

- **AGENTS.md "Where hand-corrections live":** add:

  ```markdown
  - `data/misprints.json` — verified misprints in the printed 2004 editions (Latin and Italian), one word each; they also count as stop words in place extraction
  ```

- **README.md:**
  - In "Copyright and the absence of texts", change the exception sentence to: `Place designations are the one exception: they are factual and are quoted verbatim, in Latin and in Italian, in the places data.`
  - In "Repository contents", extend the `data/places.json` item with `, and the same place in the Italian CEI edition (\`it\`), which often names the modern place`.
  - Add the item:

    ```markdown
    - [`data/misprints.json`](data/misprints.json) — verified misprints in the printed 2004 editions (Latin and Italian): entry, edition, printed and intended word, for footnoting when the texts are displayed
    ```

- **`docs/canonicalization-report.md`, Places section:** after the paragraph about body places, add:

  ```markdown
  Each place may also carry `it`: the same place designation quoted from the Italian
  (CEI) edition, which often gives the modern name and country ("A Ramosch in Rezia,
  nel territorio dell'odierna Svizzera") — a hint for resolving the modern place, not
  a verified fact (see the country-code corrections above). The Latin decides whether
  a place exists; a bare Latin back-reference takes its root's `it`. In the Italian
  phrase a comma segment is kept only when it is a locative or a modern-country
  hint, and a leading *Sempre / Ancora* ("also") is dropped.
  ```

  and add to the Counts line: `, <with it> with an Italian phrase`, using the number from Task 3, Step 5.

- **`docs/canonicalization-report.md`, the misprint paragraph** (the one starting `**Misprint in the editio altera 2004 (print-verified)**`): replace it with:

  ```markdown
  **Misprints in the 2004 prints (verified)**, recorded in `data/misprints.json` for
  footnoting when the texts are displayed; place extraction treats each as the word
  intended:
  - Latin editio altera, September 27, entry 11\* (mr:0927-francisca-xaveria-fenollosa-alcayna):
    "betárum mártyrum" for *beatárum* (the subjects are women), verified on the page
    image and in its OCR layer.
  - Italian (CEI) edition, October 13 (mr:1013-comganus): "desposizione" for
    *deposizione*.
  - Italian (CEI) edition, October 14 (mr:1014-venantius): "comemorazione" for
    *commemorazione*.
  ```

- [ ] **Step 3: Final verification**

Run: `python3 -m unittest discover -s tests -v && git diff --check`, then the overlap scan over **both** editions:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "scripts")
from pathlib import Path
from extract_subjects import fold
import extract_typology as t
grams = set()
for ed in ("martyrologium_romanum_2004", "martyrologium_romanum_2004_it_IT"):
    for v in t.load_texts(Path("../martyrology-texts"), ed).values():
        w = fold(v).split(); grams.update(" ".join(w[i:i+5]) for i in range(len(w) - 4))
for f in ["tests/test_places.py", "tests/test_registry.py", "tests/test_typology.py"]:
    w = fold(open(f).read()).split()
    print(f, sorted({" ".join(w[i:i+5]) for i in range(len(w) - 4)} & grams))
EOF
```

Expected: all tests pass; no whitespace errors; each file prints `[]`.

- [ ] **Step 4: Commit**

```bash
git add data/martyrology_ids.json AGENTS.md README.md docs/canonicalization-report.md
git commit -m "docs: Italian place phrases, misprints record; registry with places[].it (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
