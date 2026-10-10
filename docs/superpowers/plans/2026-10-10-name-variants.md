# A person known by more than one name — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a person's other names (`also`), read from *seu / vel / sive / qui et* or curated. Mark the whole "X seu Y" phrase, search Wikidata under every name, and give each other name a "see" entry in the index of names.

**Architecture:**
- `persons_text.py` reads variants from footnote lists and from text companions, and returns them through out-parameters, as `printed_twice` and `marked` already do.
- `extract_persons.py` also reads variants after a text person's printed form. It merges every variant into the person as `also` (full names), adds the curated variants, and reports the variants it couldn't read.
- `extract_mentions.py` matches any of a person's names, and widens the mark over the variant.
- `build_person_items.py` searches and matches under every name.
- In martyrology-frontend, the snapshot carries `also`. The names index builds "see" entries, and `NamesIndex` renders them as links to the heading's letter page and anchor.

**Tech Stack:** Python 3 standard library with `unittest` (crmedr); Next.js, TypeScript, next-intl and Vitest (martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-10-name-variants-design.md`

## Global Constraints

- **The main name, keys, `n` and decisions are unchanged.** A variant is never a new person.
- **`also` lists full Latin nominatives in printed order.** It is written only when non-empty. It never holds the person's own name (compared by `name_key`), never holds a repeat, and no entry contains `#`.
- **Keys go in the order `name`, `n`?, `also`?, `where`.**
- **No printed form is stored or reported:** reports name the eulogy and the person's main name only.
- **Persons only;** places are #86. **No API code change.**
- **Mention review change-sets quote the 2004 text:** write them only to the scratchpad, never into either repository.
- **Tests:** crmedr with `python3 -m unittest discover -s tests` (from its root); frontend with `npx vitest run`, `npx tsc --noEmit` and `npm run lint`.

## Review Focus

1. **A variant whose words were already taken by another person's mark:** widening must not overlap it. Keep the narrow span. Pinned in Task 3 (`test_a_variant_already_marked_is_not_covered_twice`).
2. **A variant that names another person of the same eulogy:** the curated check refuses a variant equal to the person's own name. A variant equal to *another* person's name is allowed, and it must not make the extractor mark that other person's words for this one. Pinned in Task 3 (`test_the_main_name_is_matched_before_a_variant`).
3. **A footnote "qui et" with no name before it** (the list opening "qui et X"): adds nothing and doesn't crash. Pinned in Task 1 (`test_qui_et_with_no_name_before_adds_nothing`).
4. **The undeclined surname as a variant** ("Sordi seu Cacciafronte"): kept as printed, as the full name "Ioannes Cacciafronte". Pinned in Task 2 (`test_a_text_subjects_variant_after_seu`).
5. **A letter of the index that holds only "see" entries:** it appears in the letter bar in alphabetical order, with no person heading. Pinned in Task 6 (`files a see-only letter in order`).

---

## Part A — crmedr (branch `feat/name-variants`, already holds the spec)

### Task 1: Read variants in `persons_text.py`

**Files:**
- Modify: `scripts/persons_text.py` (`REPEAT_WORDS` area; `footnote_names`; `text_companions`; a new `full_variant`)
- Test: `tests/test_persons.py`

**Interfaces:**
- Produces:
  - `footnote_names(text, printed_twice=None, marked=None, variants=None)`: `variants` is a dict filled with `{position in names: [variant as printed, nominative]}`.
  - `text_companions(text, lexicon, marked=None, variants=None, unread=None)`: `variants` is `{position in names: [variant nominative]}`, and `unread` is a list of the main names whose variant couldn't be read.
  - `full_variant(name, variant) -> str`.
  - `VARIANT_WORDS = {"seu", "vel", "sive"}`.

- [ ] **Step 1: Write the failing tests** (append to `class RepeatedNamesTest` in `tests/test_persons.py`, or add `class VariantsTest(unittest.TestCase)` before `class SamePersonTest`)

```python
class VariantsTest(unittest.TestCase):
    """A person known by more than one name (2026-10-10 name-variants spec)."""

    def test_full_variant(self):
        self.assertEqual(pt.full_variant("Mamas", "Mames"), "Mames")
        self.assertEqual(pt.full_variant("Ioannes Sordi", "Cacciafronte"), "Ioannes Cacciafronte")
        self.assertEqual(pt.full_variant("Ioannes Cayx", "Ioannes Dumas"), "Ioannes Dumas")

    def test_footnote_variants_after_seu_vel_and_qui_et(self):
        variants = {}
        names, skipped = pt.footnote_names(
            "Quorum nomina: Dativus, qui et Sanator, Felix; Maximianus seu Maximus, Telica vel Tazelita, Victor.",
            variants=variants)
        self.assertEqual(names, ["Dativus", "Felix", "Maximianus", "Telica", "Victor"])
        self.assertEqual(skipped, [])
        self.assertEqual(variants, {0: ["Sanator"], 2: ["Maximus"], 3: ["Tazelita"]})

    def test_qui_et_with_no_name_before_adds_nothing(self):
        variants = {}
        names, _ = pt.footnote_names("Quorum nomina: qui et Sanator, Felix.", variants=variants)
        self.assertEqual((names, variants), (["Felix"], {}))

    def test_text_companion_variants_and_unread_ones(self):
        lex = {pt.name_key(w): w for w in ["Marina", "Margarita", "Theodorus", "Petrus"]}
        variants, unread = {}, []
        names, uncertain = pt.text_companions(
            "Romæ, sanctórum Marínæ seu Margarítæ, Theodóri seu Ficténtis et Petri, mártyrum.", lex,
            variants=variants, unread=unread)
        self.assertEqual((names, uncertain), (["Marina", "Theodorus", "Petrus"], []))
        self.assertEqual((variants, unread), ({0: ["Margarita"]}, ["Theodorus"]))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_persons.VariantsTest -v`
Expected: FAIL with `AttributeError` (`full_variant`), and with `TypeError` (unexpected keyword `variants`).

- [ ] **Step 3: Implement**

Add after `REPEAT_WORDS`:

```python
# Words that give another name of the person just named: "Maximianus seu Maximus", "Telica vel
# Tazelita"; a footnote segment "qui et Sanator" gives one too (VARIANT_OPENING).
VARIANT_WORDS = {"seu", "vel", "sive"}
VARIANT_INSIDE = re.compile(r"\s+(?:seu|vel|sive)\s+", re.I)
VARIANT_OPENING = re.compile(r"^(?:qui|quae|quæ)\s+et\s+", re.I)


def full_variant(name, variant):
    """A variant as a whole name: one with fewer words than the name stands for its last words
    ("Ioannes Sordi" seu "Cacciafronte" is "Ioannes Cacciafronte")."""
    words, alt = name.split(), variant.split()
    return " ".join(words[:max(0, len(words) - len(alt))] + alt)
```

In `footnote_names`:
- Add the parameter `variants=None` and document it: "variants: {position in names: [other names]} when given".
- In the segment loop, replace the line `parts = [p.strip() for p in _split_et(seg) if p.strip()]` with:

```python
            opening = VARIANT_OPENING.match(seg)
            if opening:
                # "Dativus, qui et Sanator": another name of the person just read.
                alt = _name_at_start(seg[opening.end():])
                if alt and last is not None and variants is not None:
                    variants.setdefault(len(names) - 1, []).append(alt)
                continue
            seg, *alts = VARIANT_INSIDE.split(seg, maxsplit=1)
            before = len(names)
            parts = [p.strip() for p in _split_et(seg) if p.strip()]
```

- After the inner `for name, part in read:` loop (still inside the segment loop), add:

```python
            alt = _name_at_start(alts[0]) if alts else None
            if alt and len(names) > before and variants is not None:
                variants.setdefault(len(names) - 1, []).append(alt)  # "Maximianus seu Maximus"
```

In `text_companions`:
- Add the parameters `variants=None, unread=None`, and document them: "`variants`: {position in names: [other names]}; `unread`: the names whose other name could not be read".
- Declare `variant_of = None` with the other state.
- Make `close()` attach to a variant:

```python
    def close():
        nonlocal variant_of
        if current:
            if variant_of is None:
                names.append(" ".join(current))
            elif variants is not None:
                variants.setdefault(variant_of, []).append(" ".join(current))
            current.clear()
        variant_of = None
```

- At the top of the branch `if token[0].islower() and f not in PARTICLES:`, add:

```python
            if f in VARIANT_WORDS and (current or names):
                close()
                variant_of = len(names) - 1  # "Marinae seu Margaritae": another name of hers
                continue
```

- Replace the block that starts `nom = nominative(token, lexicon)` up to `current.append(nom)` with:

```python
        nom = nominative(token, lexicon)
        if nom is None and variant_of is not None and not _genitive_ending(name_key(token)):
            nom = token  # an undeclined other name ("Sordi seu Cacciafronte"), as printed
        if nom is None:
            if variant_of is not None:
                if unread is not None:
                    unread.append(names[variant_of])  # the other name is not guessed
                variant_of = None
            else:
                uncertain.append(token)  # the whole name is dropped, never half-written
            current.clear()
            after_particle, skipping = False, True
            continue
        current.append(nom)
```

`close()` is a closure that assigns `variant_of`, so the `nonlocal` is needed. `variant_of` is defined in `text_companions` before `close()`.

- [ ] **Step 4: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/persons_text.py tests/test_persons.py
git commit -m "persons: read another name after seu, vel, sive or qui et"
```

### Task 2: `also` in `extract_persons.py`, curated variants, report

**Files:**
- Modify: `scripts/extract_persons.py` (`eulogy_persons`, `validate`, `render_report`, `main`; new `text_variants`, `_with_also`, `apply_curated_variants`)
- Create: `data/persons_variants_curated.json`
- Test: `tests/test_persons.py`

**Interfaces:**
- Consumes: Task 1's `footnote_names(..., variants=)`, `text_companions(..., variants=, unread=)`, `full_variant` and `VARIANT_WORDS`; `mentions_text.find_person`.
- Produces:
  - persons `{"name", "n"?, "also"?, "where"}`;
  - `issues["variants_unread"]`, a list of main names;
  - `apply_curated_variants(persons_by_id, curated) -> list[str]` (the errors).

- [ ] **Step 1: Write the failing tests** (append to `VariantsTest`)

```python
    def test_footnote_variants_become_also_and_qui_et_is_no_person(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Dativus, qui et Sanator, Maximianus seu Maximus."}]
        persons, issues = ep.eulogy_persons("mr:0212-x-et-socii", "", "…", foot, {}, {})
        self.assertEqual(persons, [
            {"name": "Dativus", "also": ["Sanator"], "where": {"footnote": 1}},
            {"name": "Maximianus", "also": ["Maximus"], "where": {"footnote": 1}},
        ])
        self.assertEqual(issues["variants_unread"], [])

    def test_a_text_subjects_variant_after_seu(self):
        import extract_persons as ep
        lex = {pt.name_key(w): w for w in ["Ioannes", "Kinga", "Cunegundis"]}
        persons, _ = ep.eulogy_persons("mr:0316-ioannes-sordi", "Sanctus Ioannes Sordi",
                                       "Mántuæ, sancti Ioánnis Sordi seu Cacciafronte, epíscopi.", [], lex, {})
        self.assertEqual(persons, [{"name": "Ioannes Sordi", "also": ["Ioannes Cacciafronte"], "where": "text"}])
        persons, _ = ep.eulogy_persons("mr:0724-kinga", "Sancta Kinga",
                                       "In Polónia, sanctæ Kingæ seu Cunegúndis, vírginis.", [], lex, {})
        self.assertEqual(persons, [{"name": "Kinga", "also": ["Cunegundis"], "where": "text"}])

    def test_an_unread_text_variant_is_an_issue_not_a_guess(self):
        import extract_persons as ep
        # Found as "Theodóri"; "Ficténtis" is a genitive the lexicon does not know: reported, not guessed.
        # (Mamas himself is not found at all, "Mamántis" being irregular: his variant is curated, Task 5.)
        lex = {pt.name_key("Theodorus"): "Theodorus"}
        persons, issues = ep.eulogy_persons("mr:0101-theodorus", "Sanctus Theodorus",
                                            "Romæ, sancti Theodóri seu Ficténtis, mártyris.", [], lex, {})
        self.assertEqual((persons, issues["variants_unread"]), ([{"name": "Theodorus", "where": "text"}], ["Theodorus"]))

    def test_curated_variants_are_added_and_checked(self):
        import extract_persons as ep
        by_id = {"mr:0817-mamas": [{"name": "Mamas", "where": "text"}]}
        self.assertEqual(ep.apply_curated_variants(by_id, {"$comment": "x", "mr:0817-mamas": {"Mamas": ["Mames"]}}), [])
        self.assertEqual(by_id["mr:0817-mamas"], [{"name": "Mamas", "also": ["Mames"], "where": "text"}])
        self.assertEqual(ep.apply_curated_variants(by_id, {"mr:0817-mamas": {"Mamas": ["Mames"]}}), [])  # no repeat
        self.assertEqual(by_id["mr:0817-mamas"][0]["also"], ["Mames"])
        for bad in ({"mr:0817-mamas": {"Nemo": ["X"]}}, {"mr:9999-x": {"Mamas": ["X"]}},
                    {"mr:0817-mamas": {"Mamas": ["Mamas"]}}, {"mr:0817-mamas": {"Mamas": ["Mam#es"]}},
                    {"mr:0817-mamas": {"Mamas": [""]}}, {"mr:0817-mamas": {"Mamas": "Mames"}}):
            self.assertTrue(ep.apply_curated_variants({"mr:0817-mamas": [{"name": "Mamas", "where": "text"}]}, bad), bad)

    def test_validate_checks_also(self):
        import extract_persons as ep
        foot = {"mr:0212-x": [{"mark": "1", "after": "x", "text": "Quorum nomina: Dativus, qui et Sanator."}]}
        d = {"name": "Dativus", "where": {"footnote": 1}}
        ok = ep.validate({"mr:0212-x": [dict(d, also=["Sanator"])]}, foot, {"mr:0212-x"})
        self.assertEqual(ok, [])
        for also in ([], ["Dativus"], ["Sanator", "Sanator"], ["Sa#nator"], "Sanator"):
            self.assertTrue(ep.validate({"mr:0212-x": [dict(d, also=also)]}, foot, {"mr:0212-x"}), also)

    def test_the_report_lists_unread_variants_without_the_printed_form(self):
        import extract_persons as ep
        report = ep.render_report({"mr:0817-mamas": [{"name": "Mamas", "where": "text"}]},
                                  {"mr:0817-mamas": {"uncertain": [], "skipped": [], "printed_twice": [],
                                                     "variants_unread": ["Mamas"], "socii_without_names": False}})
        self.assertIn("- mr:0817-mamas: Mamas", report)
        self.assertNotIn("Mamétis", report)
```

Also update `EulogyPersonsTest.test_subjects_then_text_then_footnote_without_repeats` so that its expected `issues` is `{"uncertain": [], "skipped": [], "printed_twice": [], "variants_unread": [], "socii_without_names": False}`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_persons -v 2>&1 | grep -E "^(FAIL|ERROR)"`
Expected: the new `VariantsTest` tests and the updated `issues` test FAIL. There is no `also`, and no `apply_curated_variants` yet.

- [ ] **Step 3: Implement**

Imports, in `scripts/extract_persons.py`:

```python
import re
from mentions_text import find_person
from persons_text import (WORD, _genitive_ending, footnote_names, full_variant, name_key, nominative, person_key,
                          subject_names, text_companions, without_parentheses)
```

(`nominative` is already in `persons_text`. Keep any names the module imports today.)

Helpers, after `_same_person`:

```python
# The other name printed right after a person in the text: "Mamántis seu Mamétis".
VARIANT_AFTER = re.compile(r"\s*,?\s*(?:seu|vel|sive)\s+((?:[^\W\d_][\w'’\-]*)(?:\s+[^\W\d_][\w'’\-]*)*)")


def text_variants(text, name, lexicon):
    """A text person's other name printed right after them, as a whole nominative name, and
    whether one is printed but could not be read (a genitive the lexicon does not know). The
    variant's capitalized words only; an undeclined word ("Cacciafronte") is taken as printed."""
    found = find_person(text or "", name)
    if not found:
        return [], False
    m = VARIANT_AFTER.match(text, found[0][1])
    if not m:
        return [], False
    words = []
    for w in m.group(1).split():
        if not w[:1].isupper():
            break
        nom = nominative(w, lexicon)
        if nom is None and _genitive_ending(name_key(w)):
            return [], True
        words.append(nom or w)
    return ([full_variant(name, " ".join(words))] if words else []), False


def _with_also(p, variants):
    """The person with `variants` added to `also`, in order, without repeats or their own name;
    keys in the order name, n, also, where."""
    also = list(dict.fromkeys(v for v in [*p.get("also", []), *variants] if name_key(v) != name_key(p["name"])))
    out = {k: v for k, v in p.items() if k not in ("also", "where")}
    if also:
        out["also"] = also
    out["where"] = p["where"]
    return out
```

In `eulogy_persons`:
- Change the curated-branch issues to `{"uncertain": [], "skipped": [], "printed_twice": [], "variants_unread": [], "socii_without_names": False}`.
- Add `holder = {}  # name_key -> the position of the first person of that name`.
- Give `add` the signature `add(name, where, marked=False, also=())`.
- Where `add` returns because the name is the same person, merge first: `if also and key in holder: persons[holder[key]] = _with_also(persons[holder[key]], also)` and then `return`. Do it for both returns, the text one and the footnote one.
- Where `add` appends, record `holder.setdefault(key, len(persons))` and append `_with_also(p, also)`.
- For the text companions, pass `variants=tvars, unread=unread_text` (both fresh) and call `add(n, "text", marked=i in marks, also=[full_variant(n, v) for v in tvars.get(i, [])])`.
- For each footnote, pass `variants=fvars` (fresh for each footnote) and call `add(n, {"footnote": i}, marked=j in marks, also=[full_variant(n, v) for v in fvars.get(j, [])])`.
- Before `return`, read the text persons' printed variants:

```python
    variants_unread = list(unread_text)
    for i, p in enumerate(persons):
        if p["where"] != "text":
            continue
        found, unread = text_variants(text, p["name"], lexicon)
        if found:
            persons[i] = _with_also(p, found)
        elif unread and p["name"] not in variants_unread:
            variants_unread.append(p["name"])
```

- Return issues as `{"uncertain": uncertain, "skipped": skipped, "printed_twice": printed_twice, "variants_unread": variants_unread, "socii_without_names": ...}`.

Initialise `unread_text = []` before the `if socii:` block, so it exists when the eulogy has no companions.

In `validate`, inside `for p in persons:` and after the `n` checks, add:

```python
            if "also" in p:
                also = p["also"]
                if (not isinstance(also, list) or not also or len(set(map(name_key, also))) != len(also)
                        or any(not isinstance(v, str) or not v.strip() or "#" in v
                               or name_key(v) == name_key(p["name"]) for v in also)):
                    errors.append(f"{mrid}: {p['name']!r} has a bad also {also!r}: other names, each once, "
                                  "never their own, without '#'")
```

Add `apply_curated_variants` after `validate`:

```python
def apply_curated_variants(persons_by_id, curated):
    """Adds data/persons_variants_curated.json ({eulogy: {person key: [names]}}) to the persons'
    `also`, in order and without repeats; it never replaces a eulogy's persons. Returns the errors."""
    errors = []
    for mrid, by_key in curated.items():
        if mrid.startswith("$"):
            continue
        persons = persons_by_id.get(mrid, [])
        for key, names in by_key.items():
            i = next((i for i, p in enumerate(persons) if person_key(p) == key), None)
            if i is None:
                errors.append(f"{mrid}: {key!r} is not a person of this eulogy")
                continue
            if not isinstance(names, list) or not all(
                    isinstance(v, str) and v.strip() and "#" not in v
                    and name_key(v) != name_key(persons[i]["name"]) for v in names):
                errors.append(f"{mrid}: {key!r}: variants must be a list of other names, without '#'")
                continue
            persons[i] = _with_also(persons[i], names)
    return errors
```

In `render_report`, add this section after the "printed twice" one:

```python
        ("Persons whose other name (after seu, vel or sive) was not read: add it in "
         "data/persons_variants_curated.json",
         [f"{m}: {name}" for m, i in issues.items() for name in i.get("variants_unread", [])]),
```

In `main`, after the loop that builds `persons_by_id` and before `validate`:

```python
    variants_path = repo_root / "data" / "persons_variants_curated.json"
    curated_variants = json.loads(variants_path.read_text(encoding="utf-8")) if variants_path.exists() else {}
    variant_errors = apply_curated_variants(persons_by_id, curated_variants)
    if variant_errors:
        sys.exit("invalid curated variants:\n" + "\n".join(variant_errors))
    # A variant curated since is no longer unread.
    for mrid, iss in issues.items():
        named = {p["name"] for p in persons_by_id.get(mrid, []) if p.get("also")}
        iss["variants_unread"] = [n for n in iss.get("variants_unread", []) if n not in named]
```

Then drop the eulogies left without an issue, so a eulogy whose only issue was a variant curated since is not listed:

```python
    issues = {mrid: iss for mrid, iss in issues.items() if any(iss.values())}
```

Create `data/persons_variants_curated.json`:

```json
{
  "$comment": "Curators' other names for persons of data/persons.json: {eulogy: {person key (name, or name#n): [other names as Latin nominatives, in printed order]}}. Added to the extracted variants (also) by scripts/extract_persons.py; it never replaces a eulogy's persons. See docs/superpowers/specs/2026-10-10-name-variants-design.md.",
  "mr:0817-mamas": { "Mamas": ["Mames"] }
}
```

- [ ] **Step 4: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_persons.py tests/test_persons.py data/persons_variants_curated.json
git commit -m "persons: also, a person's other names, read or curated; report the unread ones"
```

### Task 3: Marks over "X seu Y" in `extract_mentions.py`

**Files:**
- Modify: `scripts/extract_mentions.py` (the person loop of `eulogy_mentions`; a new `with_variant`)
- Test: `tests/test_extract_mentions.py`

**Interfaces:**
- Consumes: persons with `also` (Task 2).
- Produces: `with_variant(src, span, taken) -> tuple[int, int]`.

- [ ] **Step 1: Write the failing tests** (add `class VariantsTest` after `RepeatedNamesTest`)

```python
class VariantsTest(unittest.TestCase):
    def test_a_mark_spans_the_name_and_its_variant(self):
        text = "In Polónia, sanctæ Kingæ seu Cunegúndis, vírginis."
        ms, review, _ = mentions_of(text, persons=[{"name": "Kinga", "also": ["Cunegundis"], "where": "text"}])
        self.assertEqual([m["form"] for m in ms], ["Kingæ seu Cunegúndis"])
        self.assertEqual(review, [])

    def test_a_person_printed_only_under_a_variant_is_marked(self):
        text = "Romæ, sanctæ Cunegúndis, vírginis."
        ms, _, _ = mentions_of(text, persons=[{"name": "Kinga", "also": ["Cunegundis"], "where": "text"}])
        self.assertEqual([(m["form"], m["name"]) for m in ms], [("Cunegúndis", "Kinga")])

    def test_the_main_name_is_matched_before_a_variant(self):
        text = "Romæ, sanctæ Margarítæ, et sanctæ Marínæ, vírginum."
        ms, _, _ = mentions_of(text, persons=[{"name": "Marina", "also": ["Margarita"], "where": "text"}])
        self.assertEqual([m["form"] for m in ms], ["Marínæ"])

    def test_a_variant_already_marked_is_not_covered_twice(self):
        text = "Romæ, sanctórum Dativi seu Sanatóris et Sanatóris."
        persons = [{"name": "Sanator", "where": "text"}, {"name": "Dativus", "also": ["Sanator"], "where": "text"}]
        ms, _, _ = mentions_of(text, persons=persons)
        self.assertEqual(sorted(m["form"] for m in ms), ["Dativi", "Sanatóris"])
        self.assertEqual(em.validate({"ed": {"mr:x": ms}}, lambda e, m, w: text), [])

    def test_a_footnote_mark_spans_qui_et(self):
        note = "Quorum nómina: Dativus, qui et Sanator, Felix."
        ms, _, _ = mentions_of("Romæ.", persons=[{"name": "Dativus", "also": ["Sanator"], "where": {"footnote": 1}}],
                               notes=[note])
        self.assertEqual([m["form"] for m in ms], ["Dativus, qui et Sanator"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_extract_mentions.VariantsTest -v`
Expected: FAIL. Marks cover only the main form, a variant-only person isn't marked, and the qui-et span is narrow. `test_the_main_name_is_matched_before_a_variant` and `test_a_variant_already_marked_is_not_covered_twice` may already pass: they pin behaviour that must survive.

- [ ] **Step 3: Implement**

Add after the imports:

```python
# The other name printed right after a person: "Kingae seu Cunegundis", "Dativus, qui et Sanator".
CONNECTIVE = re.compile(r"\s*,?\s*(?:seu|vel|sive|qui\s+et|qu(?:ae|æ)\s+et)\s+", re.I)
NAME_WORD = re.compile(r"[^\W\d_][\w'’\-]*")
SPACES = re.compile(r"[ \t]+")


def with_variant(src, span, taken):
    """A person's span widened over the other name printed right after it (its capitalized words),
    unless those words are taken by another mention."""
    m = CONNECTIVE.match(src, span[1])
    if not m:
        return span
    end, pos = None, m.end()
    while (w := NAME_WORD.match(src, pos)) and w.group(0)[0].isupper():
        end = w.end()
        gap = SPACES.match(src, end)
        if not gap:
            break
        pos = gap.end()
    wide = (span[0], end) if end else span
    return wide if wide == span or free((span[1], wide[1]), taken) else span
```

(`re` and `free` are already imported in `extract_mentions.py`. Check with `grep -n "^import re\|free" scripts/extract_mentions.py`, and add `import re` if it's missing.)

In the person loop of `eulogy_mentions`:
- Replace `found = find_person(src, name, both)` with:

```python
        names = [name, *p.get("also", [])]
        found = next((f for f in (find_person(src, nm, both) for nm in names) if f), None)
```

- In the `if found:` branch, widen the span before `add`, and only when the person has other names:

```python
            span, how, _ = found
            if p.get("also"):
                span = with_variant(src, span, spans("place", where) + spans("person", where))
            add("person", where, span, how, name=name, **nth, qid=person_qid(person_key(p)))
```

- In the leftover loop, search every name:

```python
                while again := next((f for f in (find_person(src, nm, spans("place", where) + spans("person", where))
                                                 for nm in names) if f), None):
```

- In the `inside` and `partial_span` fallbacks, keep the main name only, as now.

- [ ] **Step 4: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_mentions.py tests/test_extract_mentions.py
git commit -m "mentions: match a person under any of their names; mark the whole 'X seu Y'"
```

### Task 4: Search and match under every name in `build_person_items.py`

**Files:**
- Modify: `scripts/build_person_items.py` (`evidence`, `gather`, `person_index`, `make_op`)
- Test: `tests/test_person_items.py`

**Interfaces:**
- Consumes: persons with `also` (Task 2).
- Produces: index entries and `resolve_person` ops carrying `also` after `n`.

- [ ] **Step 1: Write the failing tests** (append `class VariantsTest(unittest.TestCase)` at the end of the file)

```python
class VariantsTest(unittest.TestCase):
    DOC = {"editions": {"martyrologium_romanum_2004": {"mr:0724-kinga": [
        {"name": "Kinga", "also": ["Cunegundis"], "where": "text"}]}}}
    ENTRIES = [{"id": "mr:0724-kinga", "month": 7, "day": 24}]

    def index(self):
        return bp.person_index(self.DOC, self.ENTRIES, {"mr:0724-kinga": "dies_natalis"}, {"mr:0724-kinga": "Sancta Kinga"})

    def test_the_index_and_the_op_carry_also(self):
        person = self.index()["mr:0724-kinga|Kinga"]
        self.assertEqual(person["also"], ["Cunegundis"])
        op = bp.make_op("mr:0724-kinga|Kinga", person, {"failed": [], "candidates": []}, None)
        self.assertEqual(list(op)[5:8], ["subject", "name", "also"])

    def test_the_search_tries_each_name_and_a_variant_satisfies_the_name_rule(self):
        searched = []

        class Client(FakeClient):
            def person_candidates(self, name, languages=("la", "it", "en")):
                searched.append(name)
                return [cand("Q1", ["Cunegundis"], died="1292-07-24")] if name == "Cunegundis" else []

        person = self.index()["mr:0724-kinga|Kinga"]
        cands = bp.gather(person, Client())
        self.assertIn("Cunegundis", searched)
        self.assertEqual(bp.evaluate(person, cands)["auto"]["wikidata"], "Q1")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_person_items.VariantsTest -v`
Expected: FAIL. The index has no `also` (`KeyError`), and the search never tries Cunegundis.

- [ ] **Step 3: Implement**

In `person_index`, after the `n` entry, add `**({"also": p["also"]} if "also" in p else {})`.

In `make_op`, extend the field tuple: `("eulogy", "day", "typology", "subject", "name", "n", "also", "where", "companions")`. It still uses `if k in person`.

In `evidence`, replace the name test with:

```python
    names = c.get("names", []) + [c.get("label", "")]
    if any(name_matches(nm, names) for nm in [person["name"], *person.get("also", [])]):
        ev.append("name")
```

Replace `gather` with:

```python
def gather(person, client):
    seen = {}
    terms = dict.fromkeys(t for nm in [person["name"], *person.get("also", [])] for t in search_terms(nm))
    for term in terms:
        for c in client.person_candidates(term, SEARCH_LANGUAGES):
            seen.setdefault(c["wikidata"], c)
    return list(seen.values())
```

- [ ] **Step 4: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_person_items.py tests/test_person_items.py
git commit -m "person items: search and match a person under each of their names"
```

### Task 5: Regenerate, document, open the crmedr PR

**Files:**
- Modify: `AGENTS.md` (pipeline step 6)
- Regenerate: `data/persons.json`, `docs/persons-report.md`, `data/person_items.json`, `data/person_items_review.json`, `docs/person-items-report.md`, `data/mentions.json`, `docs/mentions-report.md`

- [ ] **Step 1:** In `AGENTS.md` step 6, after the clause about repeated names, add: "; a person's other names (after *seu, vel, sive* or *qui et*, or curated in `data/persons_variants_curated.json`) are kept as `also`". Also add `data/persons_variants_curated.json` to the "Where hand-corrections live" persons bullet.
- [ ] **Step 2:** Run `python3 scripts/extract_persons.py ../martyrology-texts`. Expected: no error.
  - Check `mr:0212-martyres-abitinenses`: Dativus has `also: ["Sanator"]`, and there is no "Sanator" person; Maximianus has `also: ["Maximus"]`; Telica has `also: ["Tazelita"]`.
  - Check `mr:0817-mamas`: `also: ["Mames"]` (curated).
  - `git diff --stat data/persons.json` should show only additions of `also`, and the removal of Sanator.
  - List every eulogy whose persons changed in some other way, and justify each one.
- [ ] **Step 3:** Run `python3 scripts/build_person_items.py propose` (network), then `python3 scripts/build_person_items.py check`.
  - Expected: Sanator's queued op is dropped (his person is gone), and no existing decision changes.
  - The review ops of persons with `also` carry it.
  - If Wikidata refuses requests, rerun later; note it in the PR if it still fails.
- [ ] **Step 4:** Run `python3 scripts/extract_mentions.py ../martyrology-texts --review <scratchpad>/mentions-review-variants.json`. Expected:
  - the Kinga, Marina and Abitinian Dativus marks span "X seu Y";
  - `docs/mentions-report.md` counts are not lower than before, except where two marks became one.
- [ ] **Step 5:** Run all the tests, then commit and open the PR:

```bash
python3 -m unittest discover -s tests
git add AGENTS.md data/ docs/
git commit -m "data: persons' other names (also), their marks and searches"
git push -u origin feat/name-variants
gh pr create --base main --title "A person known by more than one name" --body "…"
```

The body should give the spec path, the changes in each script, the counts (persons with `also`, Sanator removed, the curated Mames), the unread variants left for curation, "Places: #86", and the session's attribution lines.

---

## Part B — martyrology-frontend (branch `feat/name-variants`, from `main`)

### Task 6: Snapshot `also`, and "see" entries in the names index

**Files:**
- Modify: `lib/persons.ts`, `scripts/snapshot-registry.mjs` (`buildPersons`), `lib/names-index.ts`
- Test: `lib/__tests__/snapshot.test.ts`, `lib/__tests__/names-index.test.ts`

**Interfaces:**
- Produces:
  - `PersonMention.also?: string[]`;
  - `export interface SeeEntry { name: string; key: string; target: string; letter: string }`, where `key` is the heading's key;
  - `NamesLetter.see?: SeeEntry[]`;
  - `export function headingId(key: string): string`;
  - `export type NamesEntry = { person: IndexPerson } | { see: SeeEntry }`;
  - `export function letterEntries(l: NamesLetter): NamesEntry[]`.

- [ ] **Step 1: Write the failing tests**

In `lib/__tests__/snapshot.test.ts`, inside `describe("buildPersons", …)`:

```ts
  it("copies a person's other names", () => {
    const doc = { editions: { martyrologium_romanum_2004: { "mr:0817-mamas": [
      { name: "Mamas", also: ["Mames"], where: "text" },
    ] } } };
    expect(buildPersons(doc, { persons: {} }).editions.martyrologium_romanum_2004["mr:0817-mamas"]).toEqual([
      { name: "Mamas", also: ["Mames"], where: "text" },
    ]);
  });
```

In `lib/__tests__/names-index.test.ts`, inside the top-level `describe("namesIndex", …)`, import `headingId` and `letterEntries` from `@/lib/names-index`, then add:

```ts
  describe("other names", () => {
    const vs: PersonsSnapshot = {
      editions: { [ED]: {
        "mr:0817-mamas": [{ name: "Mamas", also: ["Mames"], where: "text" }],
        "mr:0818-mamas": [{ name: "Mamas", also: ["Mames"], where: "text" }],
        "mr:0720-marina": [{ name: "Marina", also: ["Margarita", "Marina"], where: "text", wikidata: "Q1" }],
        "mr:0610-margarita": [{ name: "Margarita", where: "text" }],
        "mr:0724-kinga": [{ name: "Kinga", also: ["Cunegundis"], where: "text" }],
      } },
      labels: {},
    };
    const days = [cat("mr:0817-mamas", "Sanctus Mamas", "08-17"), cat("mr:0818-mamas", "Sanctus Mamas", "08-18"),
      cat("mr:0720-marina", "Sancta Marina", "07-20"), cat("mr:0610-margarita", "Sancta Margarita", "06-10"),
      cat("mr:0724-kinga", "Sancta Kinga", "07-24")];
    const r = () => namesIndex(days, vs, ED, "en")!;
    const see = (letter: string) => r().letters.find((l) => l.letter === letter)?.see ?? [];

    it("gives each other name one see entry to the heading, under its own letter", () => {
      expect(see("M").map((s) => [s.name, s.target])).toEqual([["Mames", "Mamas"], ["Margarita", "Marina"]]);
      expect(see("M")[0].key).toBe("name:Mamas");
      expect(see("M")[1]).toMatchObject({ key: "Q1", letter: "M" });
    });

    it("drops an other name that is the heading itself", () => {
      expect(see("M").some((s) => s.name === "Marina")).toBe(false);
    });

    it("files a see-only letter in order", () => {
      expect(r().letters.map((l) => l.letter)).toEqual(["C", "K", "M"]);
      expect(r().letters[0]).toMatchObject({ letter: "C", persons: [] });
      expect(see("C")).toEqual([{ name: "Cunegundis", key: "name:Kinga", target: "Kinga", letter: "K" }]);
    });

    it("lists a letter's headings and see entries in one order, a heading before an entry of its name", () => {
      const m = r().letters.find((l) => l.letter === "M")!;
      expect(letterEntries(m).map((e) => ("person" in e ? `H:${e.person.name}` : `S:${e.see.name}`)))
        .toEqual(["H:Mamas", "S:Mames", "H:Margarita", "S:Margarita", "H:Marina"]);
    });

    it("makes a heading id from its key, with what an id can't hold replaced", () => {
      expect(headingId("name:Felix#2@mr:0212-x")).toBe("p-name-Felix-2-mr-0212-x");
      expect(headingId("Q42")).toBe("p-Q42");
    });
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts`
Expected: FAIL. `also` isn't copied, there are no `see` entries, and `headingId` and `letterEntries` don't exist yet.

- [ ] **Step 3: Implement**

In `lib/persons.ts`, add to `PersonMention`, after `n?`: `/** The person's other names, Latin nominatives (crmedr's also). */ also?: string[];`.

In `buildPersons`:
- Add `also?: string[]` to both JSDoc types.
- Make the returned object `{ name: p.name, ...(p.n ? { n: p.n } : {}), ...(p.also?.length ? { also: p.also } : {}), where: p.where, ...(qid ? { wikidata: qid } : {}) }`.

In `lib/names-index.ts`:

```ts
/** A cross-reference from a person's other name to their heading: "Mames → see Mamas". */
export interface SeeEntry {
  name: string;
  /** The heading's key. */
  key: string;
  /** The heading's name. */
  target: string;
  /** The heading's letter, whose page holds it. */
  letter: string;
}

export type NamesEntry = { person: IndexPerson } | { see: SeeEntry };

/** A heading's element id, from its key: what an id can't hold becomes "-". */
export function headingId(key: string): string {
  return `p-${key.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}
```

Give `NamesLetter` an optional `see?: SeeEntry[]`.

In `namesIndex`:
- While walking the mentions, after computing `key`, record the other names: `for (const v of p.also ?? []) wanted.push({ name: v, key });`. Declare `const wanted: { name: string; key: string }[] = [];` before the loop.
- After `persons.sort(...)`, build the letters as now. Then add the "see" entries:

```ts
  const heading = new Map(persons.map((p) => [p.key, p]));
  const seen = new Set<string>();
  const see: SeeEntry[] = [];
  for (const w of wanted) {
    const h = heading.get(w.key);
    const id = `${w.name}\u0000${w.key}`;
    if (!h || seen.has(id) || collator.compare(w.name, h.name) === 0) continue;
    seen.add(id);
    see.push({ name: w.name, key: w.key, target: h.name, letter: filingLetter(h.name, collator) });
  }
  see.sort((a, b) => collator.compare(a.name, b.name) || collator.compare(a.target, b.target));
  for (const s of see) {
    const letter = filingLetter(s.name, collator);
    let l = byLetter.get(letter);
    if (!l) {
      l = { letter, persons: [] };
      byLetter.set(letter, l);
      letters.push(l);
    }
    (l.see ??= []).push(s);
  }
  // A letter made by see entries alone goes in its place: letters sort by their first name.
  const first = (l: NamesLetter) =>
    [l.persons[0]?.name, l.see?.[0]?.name].filter((n): n is string => !!n).sort(collator.compare)[0];
  letters.sort((a, b) => collator.compare(first(a), first(b)));
```

Add `letterEntries`:

```ts
/** A letter's headings and see entries in one order: by name, a heading before a see entry of the same name. */
export function letterEntries(l: NamesLetter): NamesEntry[] {
  const collator = new Intl.Collator("la", { sensitivity: "base" });
  const out: NamesEntry[] = [];
  const see = l.see ?? [];
  let j = 0;
  for (const person of l.persons) {
    while (j < see.length && collator.compare(see[j].name, person.name) < 0) out.push({ see: see[j++] });
    out.push({ person });
  }
  while (j < see.length) out.push({ see: see[j++] });
  return out;
}
```

The persons keep their own order (it has tie-breaks). The see entries are merged in by name.

- [ ] **Step 4: Run the tests and the type check**

Run: `npx vitest run lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts && npx tsc --noEmit`
Expected: all pass. The letter order of the existing tests is unchanged.

- [ ] **Step 5: Commit**

```bash
git add lib/persons.ts scripts/snapshot-registry.mjs lib/names-index.ts lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts
git commit -m "names index: see entries from a person's other names to their heading"
```

### Task 7: Render the "see" entries; the review card shows `also`

**Files:**
- Modify: `components/NamesIndex.tsx`, `components/PersonCard.tsx`, `lib/changeset.ts` (`ResolvePersonOp.also?`), `messages/{en,de,es,fr,it,pt}.json`
- Test: `components/__tests__/NamesIndex.test.tsx`, `components/__tests__/PersonCard.test.tsx`

**Interfaces:**
- Consumes: Task 6's `headingId`, `letterEntries` and `SeeEntry`.
- Produces: the messages `Names.see` and `Review.person.also`.

- [ ] **Step 1: Write the failing tests**

In `components/__tests__/NamesIndex.test.tsx`, add:

```ts
  it("gives each heading an id from its key, and links a see entry to its heading's letter page", () => {
    const withSee: NamesIndexData = { ...index, letters: [
      index.letters[0],
      { letter: "C", persons: [], see: [{ name: "Cunegundis", key: "Q9", target: "Theodorus", letter: "T" }] },
      index.letters[1],
    ] };
    renderIndex(withSee, false, "C");
    const link = screen.getByRole("link", { name: "Theodorus" });
    expect(link).toHaveAttribute("href", `/en/read/${ED}/names/t#p-Q9`);
    expect(link.closest("p")).toHaveTextContent("Cunegundis → see Theodorus");
    expect(screen.getByText("Cunegundis")).toHaveAttribute("lang", "la");
    renderIndex(withSee, false, "T");
    expect(document.getElementById("p-Q9")).not.toBeNull();
  });
```

In `components/__tests__/PersonCard.test.tsx`, inside `describe("PersonCard", …)`:

```ts
  it("shows the person's other names", () => {
    renderCard(op({ name: "Kinga", also: ["Cunegundis"] }));
    expect(screen.getByText("Also: Cunegundis")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run components/__tests__/NamesIndex.test.tsx components/__tests__/PersonCard.test.tsx`
Expected: FAIL. No see entries are rendered, there are no ids, and there is no "Also" line.

- [ ] **Step 3: Implement**

Messages:
- `Names.see`, added after `"wikidata"` (mind the comma): en "see", it "vedi", de "siehe", es "véase", fr "voir", pt "ver".
- `Review.person.also`, added after `"ordinal"`: en "Also: {names}", it "Anche: {names}", de "Auch: {names}", es "También: {names}", fr "Aussi : {names}", pt "Também: {names}".

In `lib/changeset.ts`, `ResolvePersonOp`, add after `n?`: `/** The person's other names. */ also?: string[];`.

In `components/PersonCard.tsx`, after the name paragraph, add:

```tsx
      {op.also && op.also.length > 0 && (
        <p className="mb-1 text-sm text-slate-700 dark:text-slate-300">{t("also", { names: op.also.join(", ") })}</p>
      )}
```

In `components/NamesIndex.tsx`:
- Import `headingId`, `letterEntries`, `fnAnchor` and `NamesIndexData` from `@/lib/names-index`, and `letterSlug` from `@/lib/letters`.
- Replace `{shown.persons.map((p) => (` with `{letterEntries(shown).map((e) => "see" in e ? (` followed by the see rendering, then `) : (() => { const p = e.person; return (` around the existing person block, closing with `); })())}`. Or factor the person block into a small inner component `PersonBlock`, which reads better. The see rendering:

```tsx
              <p key={`see-${e.see.name}-${e.see.key}`} className="mb-4">
                <span lang={lang} className="italic">{e.see.name}</span>
                {` → ${t("see")} `}
                <Link href={`/read/${ed}/names/${letterSlug(e.see.letter)}#${headingId(e.see.key)}`} className="font-semibold underline">
                  <span lang={lang}>{e.see.target}</span>
                </Link>
              </p>
```

- Give the person block's `div` the `id={headingId(p.key)}`.

- [ ] **Step 4: Run all the tests, the type check and lint; check the messages parse**

Run: `npx vitest run && npx tsc --noEmit && npm run lint && for l in en de es fr it pt; do node -e "JSON.parse(require('fs').readFileSync('messages/$l.json','utf8'))" || echo BAD $l; done`
Expected: all pass, and nothing is printed for the messages.

- [ ] **Step 5: Commit**

```bash
git add components/NamesIndex.tsx components/PersonCard.tsx lib/changeset.ts messages/ components/__tests__/NamesIndex.test.tsx components/__tests__/PersonCard.test.tsx
git commit -m "names index: render see entries; the person card shows other names"
```

### Task 8: Refresh the snapshot; PR

- [ ] **Step 1:** After the crmedr PR is merged, put `../crmedr` on `main` and run `npm run snapshot-registry`. Check with `node -e "console.log(require('./data/persons-snapshot.json').editions.martyrologium_romanum_2004['mr:0817-mamas'])"`. Expected: `also: ['Mames']`.
- [ ] **Step 2:** Run `npx vitest run && npx tsc --noEmit && npm run lint`, then commit `data/` with the message "data: refresh the persons snapshot (other names)".
- [ ] **Step 3:** Push the branch and open the PR. The body links the crmedr PR and the spec, lists Tasks 6 to 8, and ends with the session's attribution lines. Deploy after merge only when the user asks.
