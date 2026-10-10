# Persons who share a name in one eulogy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each martyr of a name repeated in one eulogy's footnote list a person of their own, numbered `n`, with their own Wikidata decision, mark and index heading.

**Architecture:** A person is still keyed by eulogy and name. The 2nd, 3rd… person of a name carries `n` and is keyed `name#n` (`persons_text.person_key`). crmedr's three scripts change: `extract_persons.py` numbers the repeats, `extract_mentions.py` places them in order and proposes `add_mention` for leftover matches, and `build_person_items.py` keys decisions by `name#n` and keeps two persons of one eulogy off one item. In martyrology-frontend, the snapshot builder, the names index and the two review cards read `n`.

**Tech Stack:** Python 3 standard library and `unittest` (crmedr); Next.js, TypeScript, next-intl and Vitest (martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-10-repeated-person-names-design.md`

## Global Constraints

- `n` is written only when it is 2 or more; a person without `n` has `n = 1`.
- The person key is `<name>` when `n = 1` and `<name>#<n>` otherwise. Every existing key, decision and review op keeps its id.
- The printed name stays the plain name everywhere it is shown; the ordinal is never part of the name.
- Within one footnote's list, every occurrence of a name is a person. Across the text and the footnotes, a repeat is the same person, as now.
- No eulogy text is stored in crmedr (AGENTS.md). Tests use invented Latin or short name lists, never the 2004 text.
- crmedr scripts are standard library only. Run its tests with `python3 -m unittest discover -s tests` from the crmedr root.
- Mention review change-sets quote the 2004 text: write them only outside both repositories (the scratchpad), never into `crmedr/` or `martyrology-frontend/changesets/`.
- Out of scope: ablative names ("Felice", "Hilarione") and the missing Saturninus iunior (CatholicOS/crmedr#81); any martyrology-api code.

## Review Focus

1. **A name repeated across the text and a footnote:** a subject named again in a footnote list stays one person, with no `n`. Pinned in Task 2 (`test_a_subject_named_again_in_a_footnote_is_one_person`).
2. **A curated `n` that is wrong** (`n: 1`, `"2"`, a gap, or a duplicate): `extract_persons.py` refuses to write. Pinned in Task 2 (`test_the_numbering_of_a_name_is_checked`).
3. **A decided second person placed before the undecided first:** a decision for `Felix#2` must not let Felix 2 take the first "Felix". Pinned in Task 3 (`test_a_decided_second_person_does_not_take_the_first_match`).
4. **One change-set giving two persons of a eulogy the same item:** `apply` refuses it, and nothing is written. Pinned in Task 4 (`test_apply_refuses_one_item_for_two_persons_of_a_eulogy`).
5. **The index ordering an unidentified second person before the first** when their name sorts after "m" (because the eulogy id is in the key): the `name:<name>#<n>@<eulogy>` key keeps the first one first. Pinned in Task 6 (`keeps the first of the name first`).

---

## Part A — crmedr (branch `feat/repeated-person-names`, already holds the spec)

### File map

- `scripts/persons_text.py`: `person_key`; reading *alius/alia/alter/altera/adhuc* before a name.
- `scripts/extract_persons.py`: numbering repeats in `eulogy_persons`; the numbering check in `validate`.
- `scripts/extract_mentions.py`: placing by `n`, leftover `add_mention`s, `n` on mentions and ops, QIDs by key.
- `scripts/build_person_items.py`: keys `name#n`, `n` on ops, and the one-item-per-person rule.
- `tests/test_persons.py`, `tests/test_extract_mentions.py`, `tests/test_person_items.py`.
- `AGENTS.md`, regenerated `data/persons.json`, `data/mentions.json`, `data/person_items.json`, `data/person_items_review.json`, `docs/*-report.md`.

### Task 1: `person_key`, and names after *alius*

**Files:**
- Modify: `scripts/persons_text.py` (`LEADING_DESCRIPTORS` at line 96; new function after `name_key`)
- Test: `tests/test_persons.py`

**Interfaces:**
- Produces: `persons_text.person_key(p: dict) -> str | None`. Returns `p["name"]` when `p.get("n", 1) == 1`, else `f"{name}#{n}"`. It reads the name with `p.get("name")`, so it returns `None` for a dict without a name.
- Produces: `footnote_names` now reads "alius Felix", "alia X", "alter X", "altera X" and "adhuc Rogatianus alius" as the name.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_persons.py`, before `if __name__ == "__main__":`)

```python
class RepeatedNamesTest(unittest.TestCase):
    """Persons who share a name in one eulogy (2026-10-10 spec)."""

    def test_person_key(self):
        self.assertEqual(pt.person_key({"name": "Felix", "where": "text"}), "Felix")
        self.assertEqual(pt.person_key({"name": "Felix", "n": 2, "where": "text"}), "Felix#2")
        self.assertIsNone(pt.person_key({"kind": "place"}))

    def test_a_name_after_alius_or_adhuc_is_read(self):
        names, skipped = pt.footnote_names(
            "Quorum nomina: Felix; alius Felix, Emeritus; Rogatianus, alius Rogatianus, adhuc Rogatianus alius, "
            "Iulia altera.")
        self.assertEqual(names, ["Felix", "Felix", "Emeritus", "Rogatianus", "Rogatianus", "Rogatianus", "Iulia"])
        self.assertEqual(skipped, [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_persons.RepeatedNamesTest -v`
Expected: FAIL. `test_person_key` fails with `AttributeError: module 'persons_text' has no attribute 'person_key'`. In `test_a_name_after_alius_or_adhuc_is_read`, the "alius" names are missing, because a segment opening with a lowercase word is dropped.

- [ ] **Step 3: Implement**

In `scripts/persons_text.py`, add the words to `LEADING_DESCRIPTORS` (they open a segment before the name; "alius" after the name already ends it):

```python
LEADING_DESCRIPTORS = {"necnon", "atque", "ac", "et", "filii", "filius", "filia", "filiae", "eius", "eorum",
                       "earum", "episcopi", "episcopus", "presbyteri", "presbyter", "sacerdotes", "sacerdos",
                       "diaconi", "diaconus", "religiosi", "religiosae", "laici", "laicus", "catechistae",
                       "catechista", "uxor", "coniux", "coniuges", "frater", "fratres", "soror", "sorores",
                       "virgo", "virgines", "monachi", "monachus", "moniales", "seminarista", "seminaristae",
                       # another of a name just listed: "alius Felix", "adhuc Rogatianus alius"
                       "alius", "alia", "alter", "altera", "adhuc"}
```

Directly after `def name_key(...)`, add:

```python
def person_key(p):
    """A person's key within their eulogy: the name, or "name#n" for the nth person of a
    name the eulogy repeats (n from 2; a person without n is the first)."""
    name, n = p.get("name"), p.get("n", 1)
    return name if n == 1 else f"{name}#{n}"
```

- [ ] **Step 4: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/persons_text.py tests/test_persons.py
git commit -m "persons: person_key, and read a name after alius or adhuc"
```

### Task 2: Number the repeats in `extract_persons.py`

**Files:**
- Modify: `scripts/extract_persons.py` (`eulogy_persons` lines 53-80, `validate` lines 87-108)
- Test: `tests/test_persons.py`

**Interfaces:**
- Consumes: `persons_text.name_key`.
- Produces: `eulogy_persons` returns persons as `{"name", "n"?, "where"}`, with keys in that order and `n` only from 2. `validate` reports the numbering errors.

- [ ] **Step 1: Write the failing tests** (append to `RepeatedNamesTest` in `tests/test_persons.py`)

```python
    def test_every_occurrence_in_one_footnote_list_is_a_person(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text":
                 "Quorum nomina: Felix, Secunda; alius Felix, Rogatus; Felix, Secunda."}]
        persons, _ = ep.eulogy_persons("mr:0212-x-et-socii", "", "…", foot, {}, {})  # no subject: footnote only
        self.assertEqual(persons, [
            {"name": "Felix", "where": {"footnote": 1}},
            {"name": "Secunda", "where": {"footnote": 1}},
            {"name": "Felix", "n": 2, "where": {"footnote": 1}},
            {"name": "Rogatus", "where": {"footnote": 1}},
            {"name": "Felix", "n": 3, "where": {"footnote": 1}},
            {"name": "Secunda", "n": 2, "where": {"footnote": 1}},
        ])

    def test_a_subject_named_again_in_a_footnote_is_one_person(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Paulus Miki, Thomas."},
                {"mark": "2", "after": "y", "text": "Quorum nomina: Thomas, Paulus Miki."}]
        persons, _ = ep.eulogy_persons("mr:0206-paulus-miki-et-socii", "Sancti Paulus Miki et socii", "…",
                                       foot, {}, {})
        self.assertEqual(persons, [{"name": "Paulus Miki", "where": "text"},
                                   {"name": "Thomas", "where": {"footnote": 1}}])

    def test_the_numbering_of_a_name_is_checked(self):
        import extract_persons as ep
        foot = {"mr:0212-x": [{"mark": "1", "after": "x", "text": "Quorum nomina: Felix; alius Felix; Felix."}]}

        def errors(persons):
            return ep.validate({"mr:0212-x": persons}, foot, {"mr:0212-x"})

        f1 = {"name": "Felix", "where": {"footnote": 1}}
        self.assertEqual(errors([f1, dict(f1, n=2), dict(f1, n=3)]), [])
        self.assertTrue(errors([f1, dict(f1, n=3)]))             # a gap
        self.assertTrue(errors([f1, dict(f1, n=2), dict(f1, n=2)]))  # a duplicate
        self.assertTrue(errors([dict(f1, n=1)]))                  # n is written only from 2
        self.assertTrue(errors([f1, dict(f1, n="2")]))            # not an integer
        self.assertTrue(errors([f1, dict(f1, n=True)]))           # nor a boolean
        self.assertTrue(errors([dict(f1, name="Felix#2")]))       # # is the key's separator
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_persons.RepeatedNamesTest -v`
Expected:
- The first test fails: only one Felix and one Secunda are listed.
- The subject test passes already. It pins today's behaviour.
- The numbering test fails: a valid `n: 2` and `n: 3` are reported as "a name appears twice".

- [ ] **Step 3: Implement `eulogy_persons`**

Replace the start of `eulogy_persons` up to the end of `add` in `scripts/extract_persons.py` with:

```python
def eulogy_persons(mrid, subject, text, footnotes, lexicon, curated):
    if mrid in curated:
        return [dict(p) for p in curated[mrid]], {"uncertain": [], "skipped": [], "socii_without_names": False}
    persons = []
    first = {}  # name_key -> where the name was first listed
    count = {}  # name_key -> the persons of that name so far
    subjects = subject_names(mrid, subject)

    def add(name, where):
        # A fuller or shorter form of a subject is the subject, in the subject's form.
        if any(_same_person(name, s) for s in subjects if s != name):
            return
        key = name_key(name)
        # Named again in the text, or after the text or another footnote: the same person.
        # Named again in the same footnote's list: another person of that name.
        if key in first and (where == "text" or first[key] != where):
            return
        first.setdefault(key, where)
        count[key] = count.get(key, 0) + 1
        p = {"name": name}
        if count[key] > 1:
            p["n"] = count[key]
        p["where"] = where
        persons.append(p)
```

The rest of the function (from `for n in subjects:`) stays as it is.

- [ ] **Step 4: Implement the check in `validate`**

In `validate`, replace:

```python
        keys = [name_key(p["name"]) for p in persons]
        if len(set(keys)) != len(keys):
            errors.append(f"{mrid}: a name appears twice")
```

with:

```python
        numbered = {}  # name_key -> the n of each of its persons
        for p in persons:
            n = p.get("n", 1)
            if "n" in p and (type(n) is not int or n < 2):
                errors.append(f"{mrid}: {p['name']!r} has n {n!r}: n is an integer from 2, absent for the first")
                continue
            if "#" in p["name"]:
                errors.append(f"{mrid}: {p['name']!r} contains '#', which separates a person key's n")
            numbered.setdefault(name_key(p["name"]), []).append(n)
        for key, ns in numbered.items():
            if sorted(ns) != list(range(1, len(ns) + 1)):
                errors.append(f"{mrid}: the persons named {key!r} are numbered {sorted(ns)}, not 1, 2, 3…")
```

- [ ] **Step 5: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass. That includes the existing `ValidateTest.test_rejects_bad_data`, where "Thomas" in both the text and footnote 1 is numbered `[1, 1]` and still fails.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_persons.py tests/test_persons.py
git commit -m "persons: every occurrence of a name in one footnote list is a person, numbered n"
```

### Task 3: Place persons by `n` in `extract_mentions.py`

**Files:**
- Modify: `scripts/extract_mentions.py` (`eulogy_mentions` lines 53-136, `from_file`, `curated_mention`, `build_edition`'s `person_qid`, `to_file`, `op_key`, `review_ops`, `apply_decisions`)
- Test: `tests/test_extract_mentions.py`

**Interfaces:**
- Consumes: `persons_text.person_key` (Task 1); persons with `n` (Task 2).
- Produces: internal and file mentions are `{kind, where, start, end, form|check, name, n?, qid}`, with `n` only from 2. Review items and `add_mention` ops carry `n` after `name`. The `person_qid` callable now takes a person key.

- [ ] **Step 1: Write the failing tests**

In `tests/test_extract_mentions.py`, replace `test_an_ambiguous_match_is_marked_and_reviewed` with:

```python
    def test_a_further_match_is_proposed_as_the_same_person_and_nothing_is_removed(self):
        text = "Romæ, sanctórum Felícis presbýteri et Felícis diáconi."
        ms, review, _ = mentions_of(text, persons=[{"name": "Felix", "where": "text"}])
        second = text.index("Felícis", text.index("Felícis") + 1)
        self.assertEqual([(m["start"], m["name"]) for m in ms], [(text.index("Felícis"), "Felix")])
        self.assertEqual([(r["op"], r["kind"], r["start"], r["name"]) for r in review],
                         [("add_mention", "person", second, "Felix")])
        self.assertNotIn("n", review[0])
```

Then append a new class after `EulogyMentionsTest`:

```python
class RepeatedNamesTest(unittest.TestCase):
    NOTE = "Quorum nómina: Felix, Emeritus; álius Felix, Rogatus; Felix."

    def test_persons_of_one_name_take_its_matches_in_order(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}},
                   {"name": "Felix", "n": 3, "where": {"footnote": 1}}]
        ms, review, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE], qids={"Felix#2": "Q2"})
        starts = [i for i in range(len(self.NOTE)) if self.NOTE.startswith("Felix", i)]
        self.assertEqual([(m["start"], m.get("n"), m["qid"]) for m in ms],
                         [(starts[0], None, None), (starts[1], 2, "Q2"), (starts[2], 3, None)])
        self.assertEqual(list(ms[1]), ["kind", "where", "start", "end", "form", "name", "n", "qid"])
        self.assertEqual(review, [])

    def test_a_decided_second_person_does_not_take_the_first_match(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}}]
        ms, _, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE], qids={"Felix#2": "Q2"})
        self.assertEqual([m.get("n") for m in sorted(ms, key=lambda m: m["start"])], [None, 2])

    def test_a_match_after_the_last_person_of_a_name_is_proposed_as_that_person(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}}]
        ms, review, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE])
        third = self.NOTE.rindex("Felix")
        self.assertEqual(len(ms), 2)
        self.assertEqual([(r["op"], r["start"], r["name"], r["n"]) for r in review],
                         [("add_mention", third, "Felix", 2)])
        self.assertIn("matched again", review[0]["reasoning"])
```

Append to `BuildEditionTest`:

```python
    def test_a_curated_second_person_takes_the_qid_decided_for_its_key(self):
        text = "Romæ, sanctórum Felícis et Felícis."
        s = text.rindex("Felícis")
        curated = {"mr:0101-felix": [{"kind": "person", "where": "text", "start": s, "end": s + 7,
                                      "check": em.check("Felícis"), "name": "Felix", "n": 2, "qid": None}]}
        out, _, _ = em.build_edition("la", {"mr:0101-felix": text}, {}, {}, {}, {},
                                     {"mr:0101-felix": {"Felix": {"wikidata": "Q1", "status": "auto"},
                                                        "Felix#2": {"wikidata": "Q2", "status": "auto"}}},
                                     curated)
        self.assertEqual([(m["n"], m["qid"]) for m in out["mr:0101-felix"]], [(2, "Q2")])
```

Append to `RenderTest`:

```python
    def test_a_second_person_keeps_n_in_the_file(self):
        text = "Romæ, sanctórum Felícis et Felícis."
        s = text.rindex("Felícis")
        m = {"kind": "person", "where": "text", "start": s, "end": s + 7, "form": "Felícis", "name": "Felix", "n": 2,
             "qid": None}
        self.assertEqual(list(em.to_file(m, text)), ["kind", "where", "start", "end", "check", "name", "n", "qid"])
        self.assertEqual(em.from_file(em.to_file(m, text), text), m)
```

Append to `ReviewOpsTest`:

```python
    def test_an_add_for_a_second_person_carries_n_and_a_spanless_one_ends_its_id_with_the_key(self):
        notes = "Quorum nómina: Paulus et Ioánnes."
        review = {"mr:x": [{"op": "add_mention", "kind": "person", "where": {"footnote": 1}, "start": None,
                            "end": None, "form": None, "name": "Felix", "n": 2, "reasoning": "Felix was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: notes)[0]
        self.assertEqual(op["id"], f"{ED}|mr:x|footnote:1|Felix#2")
        self.assertEqual((op["name"], op["n"]), ("Felix", 2))
        self.assertEqual(list(op)[9:11], ["name", "n"])
```

Append to `ApplyDecisionsTest`:

```python
    def test_an_added_second_person_keeps_n(self):
        exported = {"operations": [self.op("add_mention", kind="person", name="Nemo", n=2, start=13, end=20,
                                           form="Nemínis")]}
        mentions = {ED: {"mr:x": [stored("place", 0, 4, "Romæ", qid="Q220")]}}
        curated = {}
        em.apply_decisions(curated, mentions, exported)
        added = curated[ED]["mr:x"][1]
        self.assertEqual((added["name"], added["n"]), ("Nemo", 2))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_extract_mentions -v`
Expected: the new tests FAIL. Today the extractor emits a `remove_mention`, mentions carry no `n`, the QID is looked up by name, and the op id ends in `Felix`.

- [ ] **Step 3: Implement placing and leftovers in `eulogy_mentions`**

In `scripts/extract_mentions.py`, add the import:

```python
from persons_text import person_key
```

Update the docstring sentence that ends "…one with a decided item first." so it ends: "…one with a decided item first; persons sharing a name, in `n` order."

Replace the person loop's head and its `if found:` branch (the lines from `for p in sorted(persons, …` to the first `continue`) with:

```python
    last = {}  # name -> the highest n among the persons of that name
    for p in persons:
        last[p["name"]] = max(last.get(p["name"], 1), p.get("n", 1))
    # A name is decided when any of its persons is: its persons keep their n order among themselves.
    decided = {p["name"] for p in persons if person_qid(person_key(p))}
    for p in sorted(persons, key=lambda p: (-len(p["name"]), p["name"] not in decided, p.get("n", 1))):
        name, where = p["name"], p["where"]
        nth = {"n": p["n"]} if "n" in p else {}
        src = source(where)
        if src is None:
            continue  # extract_persons.py validates footnote numbers
        both = spans("place", where) + spans("person", where)
        found = find_person(src, name, both)
        if found:
            span, how, more = found
            add("person", where, span, how, name=name, **nth, qid=person_qid(person_key(p)))
            if more and p.get("n", 1) == last[name]:
                # Matched again after the last person of the name: the same person named twice,
                # or a stem match on another word. The curator decides.
                while again := find_person(src, name, spans("place", where) + spans("person", where)):
                    spans("person", where).append(again[0])  # later names are not proposed over it
                    ask("add_mention", "person", where, again[0],
                        f"{name} matched again: mark it if it names this person once more", name=name, **nth)
            continue
```

In the `inside` branch, change the `ask("add_mention", …, name=name)` call to pass `name=name, **nth`. Do the same for the final `ask("add_mention", "person", where, partial_span(src, name, both), f"{name} was not found", name=name)`.

- [ ] **Step 4: Carry `n` through the file format and the QIDs**

In `from_file`, replace the person branch with:

```python
    if m["kind"] == "person":
        out["name"] = m.get("name")
        if "n" in m:
            out["n"] = m["n"]
```

In `to_file`, replace the person branch with:

```python
    if m["kind"] == "person":
        out["name"] = m["name"]
        if "n" in m:
            out["n"] = m["n"]
```

In `curated_mention`, update the docstring ("a person's by its key") and change `out["qid"] = person_qid(m.get("name"))` to:

```python
        out["qid"] = person_qid(person_key(out))
```

In `build_edition`, rename the inner function's parameter so it reads as a key:

```python
        def person_qid(key, decided=decided):
            return decided.get(key, {}).get("wikidata")
```

In `op_key`, change `return r.get("name")` to `return person_key(r)`, and update the docstring: "the person's key (name, or name#n)".

In `review_ops`, replace:

```python
            if r["op"] == "add_mention" and r["kind"] == "person":
                op["name"] = r["name"]
```

with:

```python
            if r["op"] == "add_mention" and r["kind"] == "person":
                op["name"] = r["name"]
                if "n" in r:
                    op["n"] = r["n"]
```

In `apply_decisions`, replace:

```python
            if op["kind"] == "person":
                m["name"] = op["name"]
```

with:

```python
            if op["kind"] == "person":
                m["name"] = op["name"]
                if op.get("n"):
                    m["n"] = op["n"]
```

- [ ] **Step 5: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_mentions.py tests/test_extract_mentions.py
git commit -m "mentions: place persons of one name in n order; propose leftover matches instead of removing the first"
```

### Task 4: Key decisions by `name#n` in `build_person_items.py`, one item per person

**Files:**
- Modify: `scripts/build_person_items.py` (`person_index` 185-197, `make_op` 206-214, `_decided` 217-218, `propose` 243-297, `apply_decisions` 326-350, `validate` 377-397)
- Test: `tests/test_person_items.py`

**Interfaces:**
- Consumes: `persons_text.person_key` (Task 1); persons with `n` (Task 2).
- Produces: index keys and op ids `"<eulogy>|<name>#<n>"`; index entries and `resolve_person` ops carrying `n` after `name`; `person_items.json` keys `"Felix#2"`.

- [ ] **Step 1: Write the failing tests** (append before `if __name__ == "__main__":` in `tests/test_person_items.py`)

```python
class RepeatedNamesTest(unittest.TestCase):
    """Two persons of one name in one eulogy (2026-10-10 spec)."""

    DOC = {"editions": {"martyrologium_romanum_2004": {"mr:0212-x": [
        {"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}},
        {"name": "Secunda", "where": {"footnote": 1}}, {"name": "Secunda", "n": 2, "where": {"footnote": 1}}]}}}
    ENTRIES = [{"id": "mr:0212-x", "month": 2, "day": 12}]

    def index(self):
        return bp.person_index(self.DOC, self.ENTRIES, {"mr:0212-x": "dies_natalis"}, {"mr:0212-x": "Sancti X"})

    def test_the_index_keys_a_second_person_by_name_and_n(self):
        index = self.index()
        self.assertEqual(sorted(index), ["mr:0212-x|Felix", "mr:0212-x|Felix#2", "mr:0212-x|Secunda",
                                         "mr:0212-x|Secunda#2"])
        self.assertEqual(index["mr:0212-x|Felix#2"]["n"], 2)
        self.assertNotIn("n", index["mr:0212-x|Felix"])
        self.assertEqual(index["mr:0212-x|Felix#2"]["companions"], ["Secunda"])

    def test_propose_decides_and_queues_each_person_under_its_key(self):
        items, review = {}, bp.new_changeset([])
        client = FakeClient({"Felix": [cand("Q1", ["Felix"], died="0304-02-12")], "Secunda": []})
        bp.propose(items, review, self.index(), client)
        # Both Felixes matched the same item: neither is automatic.
        queued = {op["id"]: op for op in review["operations"]}
        self.assertIn("mr:0212-x|Felix#2", queued)
        self.assertIn("mr:0212-x|Felix", queued)
        self.assertEqual(queued["mr:0212-x|Felix#2"]["n"], 2)
        self.assertEqual(list(queued["mr:0212-x|Felix#2"])[5:8], ["subject", "name", "n"])
        self.assertIn("another person of this eulogy", queued["mr:0212-x|Felix#2"]["failed"][-1])
        self.assertNotIn("mr:0212-x", items)

    def test_an_item_already_decided_for_another_person_of_the_eulogy_is_not_automatic(self):
        items = {"mr:0212-x": {"Felix": {"wikidata": "Q1", "status": "reviewed"}}}
        review = bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [cand("Q1", ["Felix"], died="0304-02-12")],
                                                            "Secunda": []}))
        self.assertIn("mr:0212-x|Felix#2", {op["id"] for op in review["operations"]})
        self.assertEqual(items["mr:0212-x"], {"Felix": {"wikidata": "Q1", "status": "reviewed"}})

    def test_apply_writes_a_second_person_under_its_key(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [], "Secunda": []}))
        exported = json.loads(json.dumps(review))
        for op in exported["operations"]:
            if op["id"] == "mr:0212-x|Felix#2":
                op["decision"], op["edited"] = "edit", {"wikidata": "Q2"}
        bp.apply_decisions(items, review, exported, self.index(), FakeClient(by_qid={"Q2": cand("Q2", ["Felix"])}))
        self.assertEqual(items, {"mr:0212-x": {"Felix#2": {"wikidata": "Q2", "status": "reviewed"}}})

    def test_apply_refuses_one_item_for_two_persons_of_a_eulogy(self):
        client = FakeClient(by_qid={"Q2": cand("Q2", ["Felix"])})
        # Within one change-set:
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [], "Secunda": []}))
        exported = json.loads(json.dumps(review))
        for op in exported["operations"]:
            if op["name"] == "Felix":
                op["decision"], op["edited"] = "edit", {"wikidata": "Q2"}
        with self.assertRaises(ValueError) as e:
            bp.apply_decisions(items, review, exported, self.index(), client)
        self.assertIn("Q2", str(e.exception))
        self.assertEqual(items, {})
        # Against a decision already in the file:
        items = {"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "reviewed"}}}
        exported["operations"] = [op for op in exported["operations"] if op["id"] == "mr:0212-x|Felix#2"]
        with self.assertRaises(ValueError):
            bp.apply_decisions(items, review, exported, self.index(), client)
        self.assertEqual(items, {"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "reviewed"}}})

    def test_check_accepts_a_second_person_and_reports_a_shared_item(self):
        index = self.index()
        self.assertEqual(bp.validate({"mr:0212-x": {"Felix#2": {"wikidata": "Q2", "status": "auto"}}}, index), [])
        self.assertTrue(bp.validate({"mr:0212-x": {"Felix#3": {"wikidata": "Q3", "status": "auto"}}}, index))
        errors = bp.validate({"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "auto"},
                                            "Felix#2": {"wikidata": "Q2", "status": "reviewed"}}}, index)
        self.assertTrue(any("Q2" in e for e in errors))
```

The eulogy is `dies_natalis` on `02-12`, so `died="0304-02-12"` makes the candidate pass every rule of `evaluate`: without the new rule, the match would be automatic.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_person_items.RepeatedNamesTest -v`
Expected: FAIL. `person_index` has a single `mr:0212-x|Felix` key, so later tests hit `KeyError` or wrong assertions.

- [ ] **Step 3: Implement keys and `n`**

In `scripts/build_person_items.py`, change the import line `from persons_text import name_key` to:

```python
from persons_text import name_key, person_key
```

Replace `person_index` with:

```python
def person_index(persons_doc, entries, typology, subjects):
    by_id = {e["id"]: e for e in entries}
    out = {}
    for mrid, persons in persons_doc["editions"][EDITION].items():
        e = by_id[mrid]
        for p in persons:
            out[f"{mrid}|{person_key(p)}"] = {
                "eulogy": mrid, "name": p["name"], **({"n": p["n"]} if "n" in p else {}), "where": p["where"],
                "day": f"{e['month']:02d}-{e['day']:02d}", "typology": typology.get(mrid),
                "subject": subjects.get(mrid, ""),
                # Each other name once: a repeated name is one companion to search with.
                "companions": list(dict.fromkeys(q["name"] for q in persons if q["name"] != p["name"])),
            }
    return out
```

In `make_op`, replace the copied fields so `n` follows `name`:

```python
    op = {"op": "resolve_person", "id": key, **{k: person[k] for k in
          ("eulogy", "day", "typology", "subject", "name", "n", "where", "companions") if k in person},
          "failed": result["failed"], "candidates": result["candidates"]}
```

Replace `_decided` with:

```python
def _decided(items, person):
    return person_key(person) in items.get(person["eulogy"], {})
```

In `propose`, replace `person["name"]` with `person_key(person)` wherever it is a key into `items`:
- `e = items.get(person["eulogy"], {}).get(person_key(person))`;
- `del items[person["eulogy"]][person_key(person)]`;
- `items.setdefault(person["eulogy"], {})[person_key(person)] = {"wikidata": qid, "status": "auto"}`.

`_one_word(person["name"])` stays on the name.

In `apply_decisions`, change the final write to:

```python
        items.setdefault(index[key]["eulogy"], {})[person_key(index[key])] = entry
```

- [ ] **Step 4: Implement the one-item-per-person rule**

Add after `SHARED = …`:

```python
SAME_EULOGY = "the same item ({qid}) is matched for another person of this eulogy"


def _holders(items, extra=()):
    """Who holds each item within a eulogy, {(eulogy, QID): {person keys}}: the decisions in
    `items`, plus `extra` (eulogy, person key, QID) triples not written yet."""
    out = {}
    for mrid, persons in items.items():
        for key, e in persons.items():
            if e.get("wikidata"):
                out.setdefault((mrid, e["wikidata"]), set()).add(key)
    for mrid, key, qid in extra:
        out.setdefault((mrid, qid), set()).add(key)
    return out
```

In `propose`, replace the final `for key, result in pending.items():` loop with:

```python
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), r["auto"]["wikidata"])
                            for k, r in pending.items()])
    for key, result in pending.items():
        person, qid = index[key], result["auto"]["wikidata"]
        if len(held[(person["eulogy"], qid)]) > 1:
            result["failed"].append(SAME_EULOGY.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        elif _one_word(person["name"]) and qid in shared:
            result["failed"].append(SHARED.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        else:
            items.setdefault(person["eulogy"], {})[person_key(person)] = {"wikidata": qid, "status": "auto"}
            ops.pop(key, None)
```

`held` is computed after the withdrawal loop above it, so a withdrawn automatic match no longer counts.

In `apply_decisions`, directly before `if errors:`, add:

```python
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), e["wikidata"])
                            for k, e in decided.items() if e["wikidata"]])
    for (mrid, qid), keys in sorted(held.items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} would be the item of more than one person ({', '.join(sorted(keys))})")
```

In `validate`, change `names.setdefault(p["eulogy"], set()).add(p["name"])` to `names.setdefault(p["eulogy"], set()).add(person_key(p))`. Before `for op in ops:`, add:

```python
    for (mrid, qid), keys in sorted(_holders(items).items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} is the item of more than one person ({', '.join(sorted(keys))})")
```

- [ ] **Step 5: Run all the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all pass, including the existing `SharedItemTest` and `ProposeApplyTest`, whose keys contain no `#`.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_person_items.py tests/test_person_items.py
git commit -m "person items: key a second person of a name as name#n; one item per person of a eulogy"
```

### Task 5: Regenerate the data, document, open the crmedr PR

**Files:**
- Modify: `AGENTS.md` (pipeline steps 6 to 8)
- Regenerate: `data/persons.json`, `docs/persons-report.md`, `data/person_items.json`, `data/person_items_review.json`, `docs/person-items-report.md`, `data/mentions.json`, `docs/mentions-report.md`, and `data/person_details.json` if new items were decided

- [ ] **Step 1: Document `n` in AGENTS.md**

- In step 6 (`extract_persons.py`), after "(the saints and blessed … the text or the nth footnote)", add: "; a name repeated within one footnote's list is a further person, numbered `n` from 2 in printed order".
- In step 7 (`build_person_items.py`), add the sentence: "Decisions are keyed by name, or `name#n` for the nth person of a repeated name; two persons of one eulogy never share an item."
- In step 8's "Matching" bullet, after "Places are placed first, then longer names before shorter ones", add: ", persons of one name in `n` order; a match left over after the last of them is proposed as an `add_mention`".

- [ ] **Step 2: Regenerate the persons**

Run: `python3 scripts/extract_persons.py ../martyrology-texts`
Expected: it writes `data/persons.json` with no validation error.

Then check the numbering:

```bash
python3 -c "
import json; d=json.load(open('data/persons.json'))['editions']['martyrologium_romanum_2004']
for k in ['mr:0212-martyres-abitinenses','mr:0602-pothinus-et-socii','mr:1217-quinquaginta-milites-eleutheropolis']:
    print(k, [(p['name'], p.get('n')) for p in d[k] if p.get('n')])"
```

Expected: the Abitinian martyrs include `('Felix', 2)`, `('Felix', 3)`, `('Rogatianus', 2)`, `('Rogatianus', 3)`, `('Rogatus', 2)`, `('Secunda', 2)`, `('Ianuaria', 2)` and `('Matrona', 2)`. Pothinus includes `('Iulia', 2)`, `('Aemilia', 2)` or `('Æmilia', 2)`, and `('Pompeia', 2)`. Run `git diff --stat data/persons.json` and look at the diff. Any change outside the seven eulogies in the spec should come from the new *alius/adhuc* reading; look at each one and confirm it.

- [ ] **Step 3: Identify the new persons**

Run: `python3 scripts/build_person_items.py propose` (network; Wikidata, cached)
Expected: new `#n` keys in `person_items.json` or `person_items_review.json`, and no existing decision changed. Check with `git diff data/person_items.json | grep '^-' | grep -v '^---'`, which should print no removed decision except a withdrawn `auto` the report explains.

Then run: `python3 scripts/build_person_items.py check`
Expected: no errors.

- [ ] **Step 4: Regenerate the mentions**

Run:

```bash
python3 scripts/extract_mentions.py ../martyrology-texts \
  --review /tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-martyrology-frontend/bb1b5383-994b-4fae-8fca-e9115defcd82/scratchpad/mentions-review.json
```

Expected: `data/mentions.json` is written without error. The review change-set (outside the repo) contains no `remove_mention` whose reasoning says "matched more than once".

Then check the Abitinian footnote:

```bash
python3 -c "
import json; d=json.load(open('data/mentions.json'))['editions']['martyrologium_romanum_2004']['mr:0212-martyres-abitinenses']
print([(m['name'], m.get('n')) for m in d if m['kind']=='person' and m['name'] in ('Felix','Rogatianus')])"
```

Expected: `('Felix', None)`, `('Felix', 2)`, `('Felix', 3)`, `('Rogatianus', None)`, `('Rogatianus', 2)` and `('Rogatianus', 3)`, in print order.

- [ ] **Step 5: Refresh the portraits if new items were decided**

If Step 3 wrote any new `auto` QID, run `python3 scripts/person_details.py` (network). Otherwise skip this step and say so in the PR.

- [ ] **Step 6: Run all the tests and commit**

```bash
python3 -m unittest discover -s tests
git add AGENTS.md data/ docs/
git status --short   # nothing outside data/, docs/ and AGENTS.md; no review change-set in the repo
git commit -m "data: number the persons who share a name in one eulogy, and their marks and items"
```

- [ ] **Step 7: Push and open the PR**

```bash
git push -u origin feat/repeated-person-names
gh pr create --base main --title "Persons who share a name in one eulogy" --body "…"
```

The body should give the spec path, what changes in each script, the regenerated counts (persons added, new `#n` items: automatic and queued), and "Out of scope: #81". End it with the attribution lines from the session.

---

## Part B — martyrology-frontend (branch `feat/repeated-person-names`, from `main`)

Start this after Part A's PR is merged, or rebase it onto crmedr's `main` before refreshing the snapshot in Task 8.

### File map

- `lib/persons.ts`: `PersonMention.n`.
- `scripts/snapshot-registry.mjs`: `buildPersons` reads `name#n`.
- `lib/names-index.ts`: the heading key of an unidentified `n ≥ 2` person.
- `lib/changeset.ts`: `ResolvePersonOp.n`, `AddMentionOp.n`.
- `components/PersonCard.tsx`, `components/MentionCard.tsx`, `messages/{en,de,es,fr,it,pt}.json`: the ordinal.
- Tests: `lib/__tests__/snapshot.test.ts`, `lib/__tests__/names-index.test.ts`, `components/__tests__/PersonCard.test.tsx`, `components/__tests__/MentionCard.test.tsx`.

### Task 6: The snapshot and the names index read `n`

**Files:**
- Modify: `lib/persons.ts:5-9`, `scripts/snapshot-registry.mjs` (`buildPersons`, around line 293), `lib/names-index.ts` (`IndexPerson.key` doc at line 17, the key at line 65)
- Test: `lib/__tests__/snapshot.test.ts`, `lib/__tests__/names-index.test.ts`

**Interfaces:**
- Produces: `PersonMention { name: string; n?: number; where; wikidata? }`. Snapshot persons are `{name, n?, where, wikidata?}`, in that key order.

- [ ] **Step 1: Write the failing tests**

Append inside `describe("buildPersons", …)` in `lib/__tests__/snapshot.test.ts`:

```ts
  it("reads a second person of a name under name#n, and keeps n", () => {
    const doc = { editions: { martyrologium_romanum_2004: { "mr:0212-x": [
      { name: "Felix", where: { footnote: 1 } }, { name: "Felix", n: 2, where: { footnote: 1 } },
    ] } } };
    const items = { persons: { "mr:0212-x": { "Felix#2": { wikidata: "Q2", status: "reviewed" } } } };
    expect(buildPersons(doc, items).editions.martyrologium_romanum_2004["mr:0212-x"]).toEqual([
      { name: "Felix", where: { footnote: 1 } },
      { name: "Felix", n: 2, where: { footnote: 1 }, wikidata: "Q2" },
    ]);
  });
```

Append inside `describe("namesIndex", …)` in `lib/__tests__/names-index.test.ts`:

```ts
  describe("persons who share a name in one eulogy", () => {
    const felixes = (name: string): PersonsSnapshot => ({
      editions: { [ED]: {
        "mr:0212-x": [{ name, where: { footnote: 1 } }, { name, n: 2, where: { footnote: 1 } }],
        "mr:0310-z": [{ name, where: "text" }],
      } },
      labels: {},
    });
    const days = [cat("mr:0212-x", "Sancti X", "02-12"), cat("mr:0310-z", "Sancti Z", "03-10")];
    const headings = (s: PersonsSnapshot, name: string) =>
      namesIndex(days, s, ED, "en")!.letters.flatMap((l) => l.persons).filter((p) => p.name === name);

    it("gives an unidentified second person a heading of their own", () => {
      expect(headings(felixes("Felix"), "Felix").map((p) => p.lines.map((l) => l.id))).toEqual([
        ["mr:0212-x", "mr:0310-z"],  // the first Felix still shares a heading with another eulogy's
        ["mr:0212-x"],
      ]);
    });

    it("keeps the first of the name first", () => {
      expect(headings(felixes("Zitas"), "Zitas").map((p) => p.lines.length)).toEqual([2, 1]);
    });

    it("files an identified second person under their item", () => {
      const s = felixes("Felix");
      s.editions[ED]["mr:0212-x"][1].wikidata = "Q2";
      const [first, second] = headings(s, "Felix");
      expect([first.qid, second.qid]).toEqual([null, "Q2"]);
    });
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts`
Expected:
- The `buildPersons` test fails: `n` is missing and there is no QID.
- The two unidentified-person tests fail: Felix 2 merges into the first heading.
- The identified-person test should pass already. It pins grouping by QID.
- TypeScript may also flag `n` on `PersonMention` in the test file. Vitest doesn't type-check, but `tsc` would.

- [ ] **Step 3: Implement**

In `lib/persons.ts`:

```ts
/** A saint or blessed a eulogy names: the Latin name, which person of that name in the eulogy (`n`, from 2;
 *  absent for the first), where it is printed, and the Wikidata item crmedr decided. */
export interface PersonMention {
  name: string;
  n?: number;
  where: "text" | { footnote: number };
  wikidata?: string;
}
```

In `scripts/snapshot-registry.mjs` `buildPersons`, update the JSDoc types (`{name: string, n?: number, where: unknown}`) and replace the map body with:

```js
      editions[edition][id] = persons.map((p) => {
        // crmedr keys the nth person of a name the eulogy repeats as "name#n".
        const e = itemsDoc.persons[id]?.[p.n ? `${p.name}#${p.n}` : p.name];
        const qid = e && IDENTIFIED.has(e.status) ? e.wikidata : null;
        if (qid) used.add(qid);
        return { name: p.name, ...(p.n ? { n: p.n } : {}), where: p.where, ...(qid ? { wikidata: qid } : {}) };
      });
```

In `lib/names-index.ts`, change the `IndexPerson.key` doc comment to:

```ts
  /** The QID; else `name:<name>`, or `name:<name>#<n>@<eulogy>` for the nth (from 2) person of a name in a eulogy. */
```

Replace `const key = p.wikidata ?? \`name:${p.name}\`;` with:

```ts
      // An unidentified namesake in another eulogy may be the same saint: one heading. The 2nd, 3rd… of a
      // name in one eulogy are other persons: a heading each, its key after the first's (a longer string).
      const key = p.wikidata ?? (p.n ? `name:${p.name}#${p.n}@${c.id}` : `name:${p.name}`);
```

Update the function's doc comment: "one heading per person (by QID, else by the Latin name, apart for the 2nd, 3rd… of a name in one eulogy)".

- [ ] **Step 4: Run the tests and the type check**

Run: `npx vitest run lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts && npx tsc --noEmit`
Expected: all pass, and `tsc` reports no errors.

- [ ] **Step 5: Commit**

```bash
git add lib/persons.ts scripts/snapshot-registry.mjs lib/names-index.ts lib/__tests__/snapshot.test.ts lib/__tests__/names-index.test.ts
git commit -m "names index: a second person of a name in one eulogy is a person of their own"
```

### Task 7: The review cards show the ordinal

**Files:**
- Modify: `lib/changeset.ts` (`ResolvePersonOp` near line 113, `AddMentionOp` at line 248), `components/PersonCard.tsx:63`, `components/MentionCard.tsx:82`, `messages/{en,de,es,fr,it,pt}.json` (`Review.person`)
- Test: `components/__tests__/PersonCard.test.tsx`, `components/__tests__/MentionCard.test.tsx`

**Interfaces:**
- Consumes: crmedr ops with `n` (Part A).
- Produces: the message `Review.person.ordinal` with argument `{n}`.

- [ ] **Step 1: Write the failing tests**

Append inside `describe("PersonCard", …)`:

```ts
  it("says which person of the name it is, from the second", () => {
    renderCard(op({ id: "mr:0212-x|Felix#2", name: "Felix", n: 2 }));
    expect(screen.getByText("the 2nd of this name in this eulogy")).toBeInTheDocument();
  });

  it("says nothing of the first", () => {
    renderCard(op());
    expect(screen.queryByText(/of this name in this eulogy/)).toBeNull();
  });
```

Append inside `describe("MentionCard", …)`:

```ts
  it("says which person of the name an add_mention marks, from the second", () => {
    renderCard(add({ name: "Fictinus", n: 3 }));
    expect(screen.getByText("the 3rd of this name in this eulogy")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run components/__tests__/PersonCard.test.tsx components/__tests__/MentionCard.test.tsx`
Expected: the two "says which person" tests FAIL; "says nothing of the first" passes.

- [ ] **Step 3: Implement**

In `lib/changeset.ts`, `ResolvePersonOp`, update the id doc to `` /** `<eulogy>|<name>`, or `<eulogy>|<name>#<n>` for the nth person of a name. */ `` and add after `name: string;`:

```ts
  /** Which person of the name in the eulogy, from 2; absent for the first. */
  n?: number;
```

In `AddMentionOp`, add the same `n?: number;` with the same comment.

In `messages/en.json`, `Review.person`, add after `"companions"`:

```json
      "ordinal": "the {n, selectordinal, one {#st} two {#nd} few {#rd} other {#th}} of this name in this eulogy",
```

Add the same key to the other locales:
- de: `"ordinal": "die {n}. Person dieses Namens in diesem Elogium",`
- es: `"ordinal": "la {n}.ª persona con este nombre en este elogio",`
- fr: `"ordinal": "{n, selectordinal, one {la #re} other {la #e}} personne de ce nom dans cet éloge",`
- it: `"ordinal": "la {n}ª persona con questo nome in questo elogio",`
- pt: `"ordinal": "a {n}ª pessoa com este nome neste elogio",`

In `components/PersonCard.tsx`, replace line 63 with:

```tsx
      <p className="text-base font-semibold">
        {op.name}
        {op.n && <span className="ml-2 text-sm font-normal text-slate-600 dark:text-slate-400">{t("ordinal", { n: op.n })}</span>}
      </p>
```

`t` is the card's `useTranslations("Review.person")` (line 28).

In `components/MentionCard.tsx`, replace line 82 with:

```tsx
      {op.name && (
        <p className="mb-1 text-slate-700 dark:text-slate-300">
          <span lang="la">{op.name}</span>
          {op.op === "add_mention" && op.n && <span className="ml-2 text-xs text-slate-600 dark:text-slate-400">{p("ordinal", { n: op.n })}</span>}
        </p>
      )}
```

`p` is the existing `useTranslations("Review.person")` in that component.

- [ ] **Step 4: Run all the tests, the type check and lint**

Run: `npx vitest run && npx tsc --noEmit && npx eslint components/PersonCard.tsx components/MentionCard.tsx lib/changeset.ts`
Expected: all pass. Also check that every `messages/*.json` parses: `for l in en de es fr it pt; do node -e "JSON.parse(require('fs').readFileSync('messages/$l.json','utf8'))" || echo BAD $l; done` should print nothing.

- [ ] **Step 5: Commit**

```bash
git add lib/changeset.ts components/PersonCard.tsx components/MentionCard.tsx messages/ components/__tests__/PersonCard.test.tsx components/__tests__/MentionCard.test.tsx
git commit -m "review: show which person of a repeated name a card is about"
```

### Task 8: Refresh the persons snapshot and open the frontend PR

**Files:**
- Regenerate: `data/persons-snapshot.json`, `data/persons-editions.json`, plus whatever else `snapshot-registry` rewrites from crmedr's `main`

- [ ] **Step 1: Refresh from crmedr's main**

Make sure `../crmedr` is on `main` with Part A merged (`git -C ../crmedr log --oneline -1`), then run `npm run snapshot-registry`.
Expected: it ends with the persons count line and reports no error.

Check:

```bash
node -e "
const s=require('./data/persons-snapshot.json').editions.martyrologium_romanum_2004['mr:0212-martyres-abitinenses'];
console.log(s.filter(p=>p.n).map(p=>p.name+'#'+p.n).join(' '))"
```

Expected: `Felix#2 Felix#3 Rogatianus#2 Rogatianus#3 Rogatus#2 Secunda#2 Ianuaria#2 Matrona#2`, in printed order.

- [ ] **Step 2: Run everything and commit**

```bash
npx vitest run && npx tsc --noEmit && npm run lint
git add data/
git commit -m "data: refresh the persons snapshot from crmedr (repeated names numbered)"
```

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin feat/repeated-person-names
gh pr create --base main --title "Persons who share a name in one eulogy" --body "…"
```

The body should link the crmedr PR and the spec in crmedr, list the changes in Tasks 6 to 8, and end with the session's attribution lines.

- [ ] **Step 4: After merge**

Deploy with `gh workflow run deploy.yml --ref main` and watch it with `gh run watch`. martyrology-api only needs its vendored crmedr refreshed at crmedr's next release; no code change.
