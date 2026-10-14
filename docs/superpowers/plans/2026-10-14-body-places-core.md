# Body places, crmedr core (places, sub-project 4, plan 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give crmedr everything body places need before any proposal exists: the thirteen roles, curated-item validation for the new keys, `scripts/body_places.py` (check proposals into an `add_place` change-set, apply decisions), a recall check, `roles` on place mentions, and the registry fed from `data/places.json`.

**Architecture:** Body places are curated items in `data/places_curated.json` (`source: "curated"` in `data/places.json`). `validate_curated` (extract_places.py) is the single rule set; `body_places.py check` reuses it for proposals. `extract_mentions.py` marks each item's printing (chosen by `occurrence`), one mention per printed span carrying a `roles` list. `registry_places.py` now copies `data/places.json` into the registry, so new places reach it without the workbook.

**Tech Stack:** Python 3 stdlib, `unittest`. Private texts at `../martyrology-texts` (needed only to regenerate data, never by the tests).

**Spec:** `docs/superpowers/specs/2026-10-14-body-places-design.md`

## Global Constraints

- Roles, in this order: `death, burial, translation, dedication, cult, birth, education, religious_life, ministry, foundation, exile, journey, mention`.
- Curated item keys: `role`, `la` required; `it`, `person`, `n`, `occurrence`, `occurrence_it` optional. `la` ≤ 12 words (`MAX_WORDS`), `it` ≤ 20 (`MAX_WORDS_IT`), both verbatim.
- `occurrence` (≥ 1) is required when `la` is printed more than once in the Latin text; `occurrence_it` likewise for `it` in the Italian. Counting is of exact, non-overlapping printings (`str.find` from the end of the previous one).
- An item's Latin printing must not overlap the opening place's printing (the first printing of the lead's `la`).
- `person` / `n` must match a person of that eulogy in `data/persons.json` (edition `martyrologium_romanum_2004`; a person without `n` is `n` 1). `n` ≥ 2 and only with `person`.
- No two items of one eulogy share (`la`, `occurrence` or 1, `role`, `person`, `n`).
- Change-set: `crmedr-changeset/v1`, op `add_place`, file `data/places_review.json`, with a top-level `rejected` list.
- Mentions: one place mention per printed span; `roles` = list of `{role}` (+ `name`, `n` from the item's `person`, `n`), in item order; file key order `kind, where, start, end, check, qid, roles`.
- No eulogy text is stored anywhere in the repository; only place designations, IDs and names.
- Never `git add` whole `data/` or `docs/`; add files by name. Run `python3 -m unittest discover -s tests` after any script change.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf
  ```

## Review Focus

- A body item with the same `la` as the opening place, printed twice: valid only with `occurrence: 2`; with no `occurrence` it is an error (it would be the lead's printing) — test in Task 1.
- Two items on one printing (born and buried at a town printed once): one mention with two roles, not an `add_mention` — test in Task 4.
- A proposal batch where one proposal is bad: the good ones become ops, the bad ones are reported, nothing else in the change-set changes — test in Task 2.
- A decision export with one invalid edit: nothing is applied — test in Task 2.
- The existing four curated places and every lead still produce the same mentions as before (only `roles` added) — verified on real data in Task 4.

---

### Task 1: Roles and curated-item validation

**Files:**
- Modify: `scripts/extract_places.py` (`ROLES` line 29; `validate_curated` ~263; `build` ~435; `main` ~606)
- Test: `tests/test_places.py` (`CuratedTest` ~455, `BuildTest`)

**Interfaces:**
- Produces: `ROLES` (13 roles); `occurrences(text, form) -> list[int]` (start offsets of exact, non-overlapping printings); `validate_curated(curated, texts, current_ids, leads, texts_it=None, persons=None) -> list[str]`; `CURATED_KEYS = ("role", "la", "it", "person", "n", "occurrence", "occurrence_it")`; `load_persons(repo_root) -> {mrid: [{"name", "n"?, "where"}]}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_places.py`, replace `class CuratedTest` with:

```python
class CuratedTest(unittest.TestCase):
    TEXT = {"mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus, Fictopoli in Fictia sepultus est."}
    TEXT_IT = {"mr:0101-a": "A Fictopoli in Fictia, san Fictizio, nato in Fictonia, sepolto a Fictopoli."}
    LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"}}
    PERSONS = {"mr:0101-a": [{"name": "Fictitius", "where": "text"}, {"name": "Fictitius", "n": 2, "where": "text"}]}

    def errors(self, items, mrid="mr:0101-a"):
        return p.validate_curated({mrid: items}, self.TEXT, {"mr:0101-a"}, self.LEADS, self.TEXT_IT, self.PERSONS)

    def test_verbatim_item_is_valid(self):
        self.assertEqual(self.errors([{"role": "birth", "la": "in Fictonia", "it": "in Fictonia"}]), [])

    def test_new_roles(self):
        for role in ("education", "religious_life", "foundation", "exile", "journey", "mention"):
            self.assertEqual(self.errors([{"role": role, "la": "in Fictonia"}]), [], role)

    def test_empty_la_is_rejected(self):
        for la in ("", "   "):
            errors = self.errors([{"role": "birth", "la": la}])
            self.assertEqual(len(errors), 1)
            self.assertIn("empty", errors[0])

    def test_invalid_items(self):
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictlandia"}]))
        self.assertTrue(self.errors([{"role": "nativity", "la": "in Fictonia"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia", "note": "x"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia"}], mrid="mr:0102-x"))
        long_text = {"mr:0101-a": "Fictopoli, sancti Ficti, " + " ".join(["in Fictia"] * 7) + "."}
        self.assertTrue(p.validate_curated({"mr:0101-a": [{"role": "birth", "la": " ".join(["in Fictia"] * 7)}]},
                                           long_text, {"mr:0101-a"}, {}))

    def test_repeated_la_needs_an_occurrence(self):
        msg = "\n".join(self.errors([{"role": "burial", "la": "Fictopoli in Fictia"}]))
        self.assertIn("printed 2 times", msg)
        self.assertEqual(self.errors([{"role": "burial", "la": "Fictopoli in Fictia", "occurrence": 2}]), [])
        self.assertIn("no printing 3", "\n".join(
            self.errors([{"role": "burial", "la": "Fictopoli in Fictia", "occurrence": 3}])))

    def test_the_opening_printing_is_taken(self):
        self.assertIn("overlaps the opening place", "\n".join(
            self.errors([{"role": "burial", "la": "Fictopoli in Fictia", "occurrence": 1}])))
        self.assertIn("overlaps the opening place", "\n".join(
            self.errors([{"role": "birth", "la": "in Fictia,", "occurrence": 1}])))

    def test_occurrence_it(self):
        self.assertIn("occurrence_it without it", "\n".join(
            self.errors([{"role": "birth", "la": "in Fictonia", "occurrence_it": 1}])))
        self.assertIn("no printing 2", "\n".join(
            self.errors([{"role": "birth", "la": "in Fictonia", "it": "in Fictonia", "occurrence_it": 2}])))

    def test_person_and_n(self):
        self.assertEqual(self.errors([{"role": "birth", "la": "in Fictonia", "person": "Fictitius", "n": 2}]), [])
        self.assertIn("no person Nemo", "\n".join(
            self.errors([{"role": "birth", "la": "in Fictonia", "person": "Nemo"}])))
        self.assertIn("no person Fictitius#3", "\n".join(
            self.errors([{"role": "birth", "la": "in Fictonia", "person": "Fictitius", "n": 3}])))
        self.assertIn("n needs a person", "\n".join(self.errors([{"role": "birth", "la": "in Fictonia", "n": 2}])))

    def test_duplicates(self):
        item = {"role": "birth", "la": "in Fictonia"}
        self.assertIn("duplicate", "\n".join(self.errors([dict(item), dict(item)])))
        self.assertEqual(self.errors([dict(item), dict(item, role="education")]), [])

    def test_occurrences(self):
        self.assertEqual(p.occurrences("aXbXXc", "X"), [1, 3, 4])
        self.assertEqual(p.occurrences("aXXXb", "XX"), [1])
        self.assertEqual(p.occurrences("abc", "X"), [])
```

In `BuildTest`, add:

```python
    def test_curated_new_keys_are_copied(self):
        cur = {"mr:0101-a": [{"role": "birth", "la": "in Fictonia", "person": "Fictitius", "occurrence": 1}]}
        r = p.build(self.ORDER, self.TX, self.TY, cur, not_a_place={})
        self.assertEqual(r["places"]["mr:0101-a"][1],
                         {"role": "birth", "la": "in Fictonia", "source": "curated", "person": "Fictitius", "occurrence": 1})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_places 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|FAILED"`
Expected: FAIL/ERROR in the new `CuratedTest` tests and `test_curated_new_keys_are_copied`.

- [ ] **Step 3: Implement**

In `scripts/extract_places.py`:

```python
ROLES = ["death", "burial", "translation", "dedication", "cult", "birth", "education", "religious_life",
         "ministry", "foundation", "exile", "journey", "mention"]
```

Add near `validate_curated`:

```python
CURATED_KEYS = ("role", "la", "it", "person", "n", "occurrence", "occurrence_it")


def occurrences(text, form):
    """Start offsets of the exact, non-overlapping printings of form in text."""
    out, start = [], text.find(form) if form else -1
    while start >= 0:
        out.append(start)
        start = text.find(form, start + len(form))
    return out


def _printing(text, form, n, what, mrid):
    """(start, end) of the nth printing of form, or an error message."""
    found = occurrences(text, form)
    if n is None:
        if len(found) > 1:
            return None, f"{mrid}: {what} {form!r} is printed {len(found)} times; give its occurrence"
        n = 1
    if not isinstance(n, int) or n < 1 or n > len(found):
        return None, f"{mrid}: {what} {form!r} has no printing {n}"
    return (found[n - 1], found[n - 1] + len(form)), None
```

Replace `validate_curated` with:

```python
def validate_curated(curated, texts, current_ids, leads, texts_it=None, persons=None):
    errors = []
    for mrid, entries in curated.items():
        if mrid not in current_ids:
            errors.append(f"{mrid}: not a current ID")
            continue
        lead = leads.get(mrid)
        lead_at = occurrences(texts[mrid], lead["la"])[:1] if lead else []
        lead_span = (lead_at[0], lead_at[0] + len(lead["la"])) if lead_at else None
        names = {(p["name"], p.get("n", 1)) for p in (persons or {}).get(mrid, [])}
        seen = set()
        for it in entries:
            if not {"role", "la"} <= set(it) <= set(CURATED_KEYS):
                errors.append(f"{mrid}: curated item keys must be role, la and optionally "
                              f"{', '.join(CURATED_KEYS[2:])}: {sorted(it)}")
                continue
            if it["role"] not in ROLES:
                errors.append(f"{mrid}: unknown role {it['role']!r}")
            if not isinstance(it["la"], str) or not it["la"].strip():
                errors.append(f"{mrid}: la is empty")
                continue
            if it["la"] not in texts[mrid]:
                errors.append(f"{mrid}: la is not verbatim in the elogium: {it['la']!r}")
                continue
            if len(it["la"].split()) > MAX_WORDS:
                errors.append(f"{mrid}: la has more than {MAX_WORDS} words")
            span, error = _printing(texts[mrid], it["la"], it.get("occurrence"), "la", mrid)
            if error:
                errors.append(error)
            elif lead_span and span[0] < lead_span[1] and lead_span[0] < span[1]:
                errors.append(f"{mrid}: la {it['la']!r} overlaps the opening place")
            if "it" in it:
                text_it = (texts_it or {}).get(mrid, "")
                if not isinstance(it["it"], str) or not it["it"].strip():
                    errors.append(f"{mrid}: it is empty")
                elif it["it"] not in text_it:
                    errors.append(f"{mrid}: it is not verbatim in the Italian elogium: {it['it']!r}")
                elif len(it["it"].split()) > MAX_WORDS_IT:
                    errors.append(f"{mrid}: it has more than {MAX_WORDS_IT} words")
                else:
                    _, error = _printing(text_it, it["it"], it.get("occurrence_it"), "it", mrid)
                    if error:
                        errors.append(error)
            elif "occurrence_it" in it:
                errors.append(f"{mrid}: occurrence_it without it")
            if "n" in it and "person" not in it:
                errors.append(f"{mrid}: n needs a person")
            elif "person" in it and persons is not None and (it["person"], it.get("n", 1)) not in names:
                who = it["person"] + (f"#{it['n']}" if "n" in it else "")
                errors.append(f"{mrid}: no person {who} in data/persons.json")
            key = (it["la"], it.get("occurrence", 1), it["role"], it.get("person"), it.get("n"))
            if key in seen:
                errors.append(f"{mrid}: duplicate item {it['role']} {it['la']!r}")
            seen.add(key)
    return errors
```

(The old "la repeats the opening place" check is replaced by the overlap check: a body item may name the opening place's town again at another printing.)

In `build`, replace the curated-item copy:

```python
        for it in curated.get(mrid, []):
            cur = {"role": it["role"], "la": it["la"], "source": "curated"}
            cur |= {k: it[k] for k in ("person", "n", "occurrence", "occurrence_it") if k in it}
            items.append(with_it(cur, it["it"]) if "it" in it else cur)
```

(`with_it` puts `it` right after `la`, so the order is `role, la, it, source, person, n, occurrence, occurrence_it`.) Update the `BuildTest` expectation in Step 1 if `with_it` is involved (it is not there: no `it`).

Add:

```python
def load_persons(repo_root):
    """The Latin 2004 persons of each eulogy (data/persons.json); missing file: none."""
    path = repo_root / "data" / "persons.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["editions"].get(EDITION_LA, {})
```

In `validate(...)` (the module's result validator) add a `persons=None` keyword and pass it on: `errors = validate_curated(curated, texts, set(current_ids), leads, texts_it, persons)`. In `main()`, call `validate(..., texts_it=texts_it, persons=load_persons(repo_root))`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_places 2>&1 | tail -1 && python3 -m unittest discover -s tests 2>&1 | tail -1`
Expected: `OK`, `OK`.

- [ ] **Step 5: Regenerate places and check the real data**

Run: `python3 scripts/extract_places.py ../martyrology-texts && git diff --stat data/places.json docs/places-report.md`
Expected: it runs (the four curated places pass the new rules); `data/places.json` changes only in its `roles` list; the report's role table gains six rows with 0. If a curated place fails (e.g. a repeated `la` now needs `occurrence`), add the `occurrence` to `data/places_curated.json` and rerun; ledger it.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py data/places.json docs/places-report.md data/places_curated.json
git commit -m "places: thirteen roles; curated items take person, n, occurrence (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 2: `scripts/body_places.py` (check and apply)

**Files:**
- Create: `scripts/body_places.py`
- Create: `data/places_review.json` (empty change-set)
- Test: `tests/test_body_places.py`

**Interfaces:**
- Consumes: `extract_places.validate_curated`, `ROLES`, `load_persons`; `extract_places.load_texts`-style loaders (see Step 3); `extract_places.lead_items` is not needed (leads come from `data/places.json`).
- Produces:
  - `op_id(p) -> str` — `"{eulogy}#{role}#{la}"` plus `"#{occurrence}"` when given and `"#{person}"` (+ `"#{n}"`) when given.
  - `item_of(p) -> dict` — the curated item of a proposal or edited decision (keys from `CURATED_KEYS` only).
  - `check(proposals, curated, review, texts, texts_it, leads, persons) -> (ops_added: int, failures: list[str])` — mutates `review["operations"]`.
  - `apply(exported, curated, review, texts, texts_it, leads, persons) -> int` (decisions applied) — raises `ValueError` on any invalid decision, leaving `curated` and `review` untouched.
  - `main(argv) -> int`.

A proposal (input, written by the proposal pass) is `{"eulogy": "mr:…", "role": …, "la": …, "it"?: …, "person"?: …, "n"?: …, "occurrence"?: …, "occurrence_it"?: …, "confidence": "high"|"medium"|"low", "reasoning": "…"}`. The proposals file is `{"proposals": [ … ]}`.

An op is `{"op": "add_place", "id": op_id, "eulogy": …, <item keys>, "confidence": …, "reasoning": …, "decision": null, "edited": null}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_body_places.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import body_places as bp  # noqa: E402

TEXTS = {"mr:0101-a": "Fictopoli, sancti Fictitii, qui in Fictonia natus et Romæ educatus est."}
TEXTS_IT = {"mr:0101-a": "A Fictopoli, san Fictizio, nato in Fictonia ed educato a Roma."}
LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli", "source": "lead"}}
PERSONS = {"mr:0101-a": [{"name": "Fictitius", "where": "text"}]}


def prop(**kw):
    return {"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictonia", "it": "in Fictonia",
            "confidence": "high", "reasoning": "natus"} | kw


def run_check(proposals, curated=None, review=None):
    curated = {} if curated is None else curated
    review = bp.new_changeset() if review is None else review
    n, failures = bp.check(proposals, curated, review, TEXTS, TEXTS_IT, LEADS, PERSONS)
    return n, failures, review


class CheckTest(unittest.TestCase):
    def test_valid_proposal_becomes_an_op(self):
        n, failures, review = run_check([prop()])
        self.assertEqual((n, failures), (1, []))
        op = review["operations"][0]
        self.assertEqual(op["op"], "add_place")
        self.assertEqual(op["id"], "mr:0101-a#birth#in Fictonia")
        self.assertEqual({k: op[k] for k in ("eulogy", "role", "la", "it", "confidence", "decision", "edited")},
                         {"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictonia", "it": "in Fictonia",
                          "confidence": "high", "decision": None, "edited": None})

    def test_bad_proposals_are_reported_good_ones_kept(self):
        n, failures, review = run_check([prop(), prop(la="in Fictlandia"), prop(role="nativity", la="Romæ", it="a Roma"),
                                         prop(eulogy="mr:0909-x"), prop(confidence="sure", la="Romæ", it="a Roma")])
        self.assertEqual(n, 1)
        self.assertEqual(len(failures), 4)
        self.assertTrue(any("not verbatim" in f for f in failures))
        self.assertTrue(any("unknown role" in f for f in failures))
        self.assertTrue(any("not a current ID" in f for f in failures))
        self.assertTrue(any("confidence" in f for f in failures))

    def test_existing_ops_curated_and_rejected_are_not_requeued(self):
        review = bp.new_changeset()
        run_check([prop()], review=review)
        review["operations"][0]["decision"] = "accept"  # an existing op is left exactly as it is
        n, failures, _ = run_check([prop(), prop(role="education", la="Romæ", it="a Roma")],
                                   curated={"mr:0101-a": [{"role": "education", "la": "Romæ", "it": "a Roma"}]},
                                   review=review)
        self.assertEqual((n, failures), (0, []))
        self.assertEqual(review["operations"][0]["decision"], "accept")
        review2 = bp.new_changeset()
        review2["rejected"] = [bp.op_id(prop())]
        self.assertEqual(run_check([prop()], review=review2)[0], 0)

    def test_duplicate_proposals_in_one_batch(self):
        n, failures, _ = run_check([prop(), prop()])
        self.assertEqual(n, 1)

    def test_op_id_parts(self):
        self.assertEqual(bp.op_id(prop(occurrence=2, person="Fictitius", n=2)),
                         "mr:0101-a#birth#in Fictonia#2#Fictitius#2")


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.review = bp.new_changeset()
        run_check([prop(), prop(role="education", la="Romæ", it="a Roma", confidence="low")], review=self.review)
        self.curated = {"mr:0101-x": [{"role": "birth", "la": "Fictiae"}]}

    def export(self, **decisions):
        ops = []
        for o in self.review["operations"]:
            d = decisions.get(o["role"])
            ops.append(dict(o, decision=d[0], edited=d[1]) if d else dict(o))
        return {"schema": bp.SCHEMA, "operations": ops}

    def apply(self, exported):
        return bp.apply(exported, self.curated, self.review, TEXTS, TEXTS_IT, LEADS, PERSONS)

    def test_accept_edit_reject_and_undecided(self):
        n = self.apply(self.export(birth=("accept", None)))
        self.assertEqual(n, 1)
        self.assertEqual(self.curated["mr:0101-a"], [{"role": "birth", "la": "in Fictonia", "it": "in Fictonia"}])
        self.assertEqual([o["role"] for o in self.review["operations"]], ["education"])
        n = self.apply(self.export(education=("edit", {"role": "religious_life", "person": "Fictitius"})))
        self.assertEqual(self.curated["mr:0101-a"][1],
                         {"role": "religious_life", "la": "Romæ", "it": "a Roma", "person": "Fictitius"})
        self.assertEqual(self.review["operations"], [])

    def test_reject_is_remembered(self):
        self.apply(self.export(birth=("reject", None)))
        self.assertIn("mr:0101-a#birth#in Fictonia", self.review["rejected"])
        self.assertNotIn("mr:0101-a", self.curated)

    def test_one_invalid_decision_applies_nothing(self):
        before_c, before_r = repr(self.curated), repr(self.review)
        with self.assertRaisesRegex(ValueError, "not verbatim"):
            self.apply(self.export(birth=("accept", None), education=("edit", {"la": "Parisiis"})))
        self.assertEqual((repr(self.curated), repr(self.review)), (before_c, before_r))

    def test_unknown_decision_and_schema(self):
        with self.assertRaisesRegex(ValueError, "unknown decision"):
            self.apply(self.export(birth=("maybe", None)))
        with self.assertRaisesRegex(ValueError, "not a crmedr-changeset/v1"):
            self.apply({"schema": "x", "operations": []})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_body_places 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'body_places'`.

- [ ] **Step 3: Implement**

Look at how `build_gazetteer.py` builds `new_changeset` and `SCHEMA` (`grep -n "def new_changeset\|^SCHEMA" scripts/build_gazetteer.py`) and mirror its shape (same keys: `schema`, `generated_at`, `operations`), adding `"rejected": []`. Look at how `extract_places.main` loads texts (`load_texts`, `latin_texts`, `EDITION_IT`) and reuse those imports.

Create `scripts/body_places.py`:

```python
#!/usr/bin/env python3
"""Body places: check the proposal pass into the add_place change-set, and apply its review.

A body place is a place a eulogy names outside its opening place, with its role
(see ROLES in extract_places.py). Proposals come from a model reading the texts;
nothing is decided until a person reviews it in martyrology-frontend.

Usage:
  python3 scripts/body_places.py check <proposals.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py apply <exported.json> /path/to/martyrology-texts [repo_root]

check validates each proposal with the rules of data/places_curated.json
(validate_curated) and queues the valid ones as add_place ops in
data/places_review.json; it prints the failures. apply writes accepted and
edited items into data/places_curated.json and remembers rejected ones; an
invalid decision applies nothing. Rerun scripts/extract_places.py afterwards.
"""
import copy
import datetime
import json
import sys
from pathlib import Path

from extract_places import CURATED_KEYS, EDITION_IT, latin_texts, load_persons, load_texts, validate_curated

SCHEMA = "crmedr-changeset/v1"
CONFIDENCE = ("high", "medium", "low")
REVIEW = "data/places_review.json"
CURATED = "data/places_curated.json"


def new_changeset():
    return {"schema": SCHEMA, "generated_at": datetime.date.today().isoformat(), "operations": [], "rejected": []}


def item_of(p):
    return {k: p[k] for k in CURATED_KEYS if k in p and p[k] is not None}


def op_id(p):
    parts = [p["eulogy"], p["role"], p["la"]]
    if p.get("occurrence"):
        parts.append(str(p["occurrence"]))
    if p.get("person"):
        parts.append(p["person"])
        if p.get("n"):
            parts.append(str(p["n"]))
    return "#".join(parts)


def _item_errors(mrid, item, curated, texts, texts_it, leads, persons):
    """validate_curated on the eulogy's existing items plus this one; only errors this item adds."""
    others = curated.get(mrid, [])
    base = set(validate_curated({mrid: others}, texts, set(texts), leads, texts_it, persons)) if others else set()
    return [e for e in validate_curated({mrid: others + [item]}, texts, set(texts), leads, texts_it, persons)
            if e not in base]


def check(proposals, curated, review, texts, texts_it, leads, persons):
    queued = {o["id"] for o in review["operations"]}
    rejected = set(review.get("rejected", []))
    done = {op_id(dict(it, eulogy=m)) for m, items in curated.items() for it in items}
    failures, added = [], 0
    for p in proposals:
        mrid = p.get("eulogy")
        if mrid not in texts:
            failures.append(f"{mrid}: not a current ID with a Latin text")
            continue
        if p.get("confidence") not in CONFIDENCE:
            failures.append(f"{mrid}: confidence must be one of {', '.join(CONFIDENCE)}")
            continue
        item = item_of(p)
        if not {"role", "la"} <= set(item):
            failures.append(f"{mrid}: a proposal needs role and la")
            continue
        oid = op_id(dict(item, eulogy=mrid))
        if oid in queued or oid in rejected or oid in done:
            continue
        errors = _item_errors(mrid, item, curated, texts, texts_it, leads, persons)
        if errors:
            failures += errors
            continue
        review["operations"].append({"op": "add_place", "id": oid, "eulogy": mrid, **item,
                                     "confidence": p["confidence"], "reasoning": p.get("reasoning", ""),
                                     "decision": None, "edited": None})
        queued.add(oid)
        added += 1
    review["operations"].sort(key=lambda o: o["id"])
    return added, failures


def apply(exported, curated, review, texts, texts_it, leads, persons):
    if exported.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    new_curated, new_review = copy.deepcopy(curated), copy.deepcopy(review)
    new_review.setdefault("rejected", [])
    errors, decided = [], set()
    for op in exported.get("operations", []):
        if op.get("op") != "add_place" or op.get("decision") is None:
            continue
        mrid = op["eulogy"]
        if op["decision"] == "reject":
            new_review["rejected"].append(op["id"])
        elif op["decision"] in ("accept", "edit"):
            item = item_of(op)
            if op["decision"] == "edit":
                item = item_of(item | (op.get("edited") or {}))
            item_errors = _item_errors(mrid, item, new_curated, texts, texts_it, leads, persons)
            if item_errors:
                errors += [f"{op['id']}: {e}" for e in item_errors]
                continue
            new_curated.setdefault(mrid, []).append(item)
        else:
            errors.append(f"{op['id']}: unknown decision {op['decision']!r}")
            continue
        decided.add(op["id"])
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    new_review["operations"] = [o for o in new_review["operations"] if o["id"] not in decided]
    new_review["rejected"] = sorted(set(new_review["rejected"]))
    curated.clear()
    curated.update(dict(sorted(new_curated.items())))
    review.clear()
    review.update(new_review)
    return len(decided)


def _load(repo_root, texts_repo):
    entries = json.loads((repo_root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    places = json.loads((repo_root / "data" / "places.json").read_text(encoding="utf-8"))["places"]
    leads = {m: it for m, items in places.items() for it in items if it["source"] == "lead"}
    current = {e["id"] for e in entries if not e.get("deprecated")}
    texts = {m: t for m, t in load_texts(texts_repo).items() if m in current}
    texts_it = latin_texts(entries, load_texts(texts_repo, EDITION_IT))
    curated_path, review_path = repo_root / CURATED, repo_root / REVIEW
    curated = json.loads(curated_path.read_text(encoding="utf-8")) if curated_path.exists() else {}
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else new_changeset()
    return curated, review, texts, texts_it, leads, load_persons(repo_root)


def _write(repo_root, curated, review):
    (repo_root / CURATED).write_text(json.dumps(curated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review["generated_at"] = datetime.date.today().isoformat()
    (repo_root / REVIEW).write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    if len(argv) < 3 or argv[0] not in ("check", "apply"):
        sys.exit(__doc__)
    cmd, path, texts_repo = argv[0], Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
    curated, review, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if cmd == "check":
        added, failures = check(doc["proposals"], curated, review, texts, texts_it, leads, persons)
        _write(repo_root, curated, review)
        print("\n".join(failures))
        print(f"{added} queued; {len(failures)} failed; {len(review['operations'])} awaiting review")
        return 1 if failures else 0
    try:
        n = apply(doc, curated, review, texts, texts_it, leads, persons)
    except ValueError as e:
        sys.exit(str(e))
    _write(repo_root, curated, review)
    print(f"{n} decisions applied; {len(review['operations'])} awaiting review; "
          "now run scripts/extract_places.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Notes for the implementer:
- `texts` doubles as the current-ID set inside `_item_errors` (`set(texts)`), so an ID without a Latin text fails as "not a current ID".
- If `latin_texts` / `load_texts` have different names or signatures in `extract_places.py` / `extract_typology.py`, use what `extract_places.main` uses and ledger it.
- `chmod +x scripts/body_places.py` (the other scripts are executable).

Create the empty change-set:

```bash
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import body_places as bp
open("data/places_review.json", "w", encoding="utf-8").write(json.dumps(bp.new_changeset(), ensure_ascii=False, indent=2) + "\n")
EOF
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_body_places -v 2>&1 | tail -3 && python3 -m unittest discover -s tests 2>&1 | tail -1`
Expected: `OK` (10 tests), `OK`.

- [ ] **Step 5: Smoke-run `check` on the real texts**

```bash
SP=/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad
cp data/places_review.json $SP/review-backup.json
echo '{"proposals": [{"eulogy": "mr:0711-benedictus", "role": "birth", "la": "Núrsiæ in Umbria", "confidence": "high", "reasoning": "natus"}]}' > $SP/smoke.json
python3 scripts/body_places.py check $SP/smoke.json ../martyrology-texts; cp $SP/review-backup.json data/places_review.json
```
Expected: `1 queued; 0 failed` (if the Latin is printed differently, adjust the smoke phrase to the printed one; the point is that the loaders work). The change-set is restored afterwards.

- [ ] **Step 6: Commit**

```bash
git add scripts/body_places.py tests/test_body_places.py data/places_review.json
git commit -m "body_places: check proposals into the add_place change-set and apply its review (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 3: The recall check in the places report

**Files:**
- Modify: `scripts/extract_places.py` (`build` result, `render_report`, `main`)
- Test: `tests/test_places.py`

**Interfaces:**
- Produces: `unrecorded(texts, places, known) -> {mrid: [la, ...]}` — for each eulogy, the `known` Latin place designations printed in its text at a printing no item covers (an item covers the printing it points at; a lead covers the first printing of its `la`); `known` is a collection of strings. `render_report` gains a "Places named but not recorded" section from `result["unrecorded"]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_places.py`:

```python
class UnrecordedTest(unittest.TestCase):
    def test_known_places_outside_items_are_listed(self):
        texts = {"mr:0101-a": "Fictopoli, sancti Ficti, qui Romæ natus et Fictopoli sepultus est."}
        places = {"mr:0101-a": [{"role": "death", "la": "Fictopoli", "source": "lead"}]}
        known = ["Fictopoli", "Romæ", "Parisiis"]
        self.assertEqual(p.unrecorded(texts, places, known), {"mr:0101-a": ["Fictopoli", "Romæ"]})
        places["mr:0101-a"] += [{"role": "birth", "la": "Romæ", "source": "curated"},
                                {"role": "burial", "la": "Fictopoli", "source": "curated", "occurrence": 2}]
        self.assertEqual(p.unrecorded(texts, places, known), {})

    def test_a_known_place_inside_a_longer_item_is_covered(self):
        texts = {"mr:0101-a": "Fictopoli in Fictia, sancti Ficti."}
        places = {"mr:0101-a": [{"role": "death", "la": "Fictopoli in Fictia", "source": "lead"}]}
        self.assertEqual(p.unrecorded(texts, places, ["Fictia"]), {})

    def test_report_section(self):
        r = p.build(BuildTest.ORDER, BuildTest.TX, BuildTest.TY, {}, not_a_place={})
        r["unrecorded"] = {"mr:0101-a": ["in Fictonia"]}
        self.assertIn("## Places named but not recorded", p.render_report(r))
        self.assertIn("- `mr:0101-a`: in Fictonia", p.render_report(r))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_places 2>&1 | grep -E "^(FAIL|ERROR):|FAILED"`
Expected: errors for `unrecorded` and the report section.

- [ ] **Step 3: Implement**

In `scripts/extract_places.py`:

```python
def _covered(text, items):
    """Spans of the printings the eulogy's items point at (a lead: its la's first printing)."""
    spans = []
    for it in items:
        found = occurrences(text, it["la"])
        n = it.get("occurrence", 1)
        if 0 < n <= len(found):
            spans.append((found[n - 1], found[n - 1] + len(it["la"])))
    return spans


def unrecorded(texts, places, known):
    """{id: [la]}: known place designations printed in a eulogy at a printing no item covers."""
    out = {}
    for mrid, text in texts.items():
        spans = _covered(text, places.get(mrid, []))
        missing = sorted({la for la in known for s in occurrences(text, la)
                          if not any(a <= s and s + len(la) <= b for a, b in spans)})
        if missing:
            out[mrid] = missing
    return dict(sorted(out.items()))
```

In `render_report`, after the "Curation candidates" table add:

```python
        "",
        "## Places named but not recorded",
        "",
        "Places the gazetteer knows, printed in a eulogy where no place item covers them: "
        "candidates for body places (see `scripts/body_places.py`).",
        "",
        *([f"- `{m}`: {', '.join(las)}" for m, las in result.get("unrecorded", {}).items()] or ["None."]),
```

(insert these list items before the `"## Entries with no place"` items, keeping one blank line between sections.)

In `main()`, after `result = build(...)` and `validate(...)`:

```python
    gazetteer_path = repo_root / "data" / "gazetteer.json"
    known = json.loads(gazetteer_path.read_text(encoding="utf-8"))["places"] if gazetteer_path.exists() else {}
    known = [la for la, g in known.items() if g.get("wikidata") and len(la) > 3]
    result["unrecorded"] = unrecorded({m: texts[m] for m, _, _ in latin_order}, result["places"], known)
```

(`len(la) > 3` keeps very short keys from flooding the list; ledger the count it removes.)

- [ ] **Step 4: Run tests and regenerate**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -1 && python3 scripts/extract_places.py ../martyrology-texts && grep -c "^- \`mr:" docs/places-report.md && git diff --stat data/places.json`
Expected: `OK`; the extractor runs; the report has the new section (a count of listed eulogies printed); `data/places.json` unchanged by this task. Read a few listed lines to see the net is sensible (e.g. a see adjective, a birthplace); if it is flooded by one short or generic key, ledger a ruling and filter that key.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py docs/places-report.md
git commit -m "places report: places the gazetteer knows, named but not recorded (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 4: `roles` on place mentions

**Files:**
- Modify: `scripts/extract_mentions.py` (`eulogy_mentions` place loop ~146; `curated_mention` ~366; `validate` ~418; `to_file` ~449; `from_file` ~349)
- Modify: `scripts/mentions_text.py` (add `nth_place`)
- Modify: `data/mentions.json`, `docs/mentions-report.md` (regenerated)
- Test: `tests/test_extract_mentions.py`, `tests/test_mentions_text.py`

**Interfaces:**
- Consumes: `extract_places.ROLES`, `extract_places.occurrences`.
- Produces: `mentions_text.nth_place(text, form, n) -> (start, end) | None` (nth exact printing, else nth folded printing); place mentions carry `roles`.

- [ ] **Step 1: Read the tests' helpers**

Run: `grep -n "def \|class " tests/test_extract_mentions.py | head -40` and read how `eulogy_mentions` is called in the existing place tests (the fixtures for `places`, `place_qid`, `person_qid`). Use the same call shape below.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_mentions_text.py`:

```python
class NthPlaceTest(unittest.TestCase):
    def test_nth_printing(self):
        text = "Romæ natus, Romæ sepultus."
        self.assertEqual(mt.nth_place(text, "Romæ", 1), (0, 4))
        self.assertEqual(mt.nth_place(text, "Romæ", 2), (12, 16))
        self.assertIsNone(mt.nth_place(text, "Romæ", 3))

    def test_folded_fallback(self):
        self.assertEqual(mt.nth_place("Sempre a Roma, e a Roma.", "A Roma", 2), (17, 23))
```

(use the module alias the file already uses for `mentions_text`; check its imports.)

Add to `tests/test_extract_mentions.py` (adapt the call to the file's existing helper; `qid` lookups return None):

```python
class PlaceRolesTest(unittest.TestCase):
    def mentions(self, text, places):
        ms, review, _ = em.eulogy_mentions(text, [], places, [], lang="la",
                                           place_qid=lambda la: None, person_qid=lambda k: None)
        return [m for m in ms if m["kind"] == "place"], review

    def test_lead_and_body_roles(self):
        ms, review = self.mentions("Fictopoli, sancti Ficti, qui Romæ natus est.",
                                   [{"role": "death", "la": "Fictopoli", "source": "lead"},
                                    {"role": "birth", "la": "Romæ", "source": "curated", "person": "Fictus"}])
        self.assertEqual([(m["form"], m["roles"]) for m in ms],
                         [("Fictopoli", [{"role": "death"}]), ("Romæ", [{"role": "birth", "name": "Fictus"}])])
        self.assertEqual(review, [])

    def test_two_items_on_one_printing_share_a_mention(self):
        ms, review = self.mentions("Fictopoli, sancti Ficti, qui Romæ natus et sepultus est.",
                                   [{"role": "death", "la": "Fictopoli", "source": "lead"},
                                    {"role": "birth", "la": "Romæ", "source": "curated"},
                                    {"role": "burial", "la": "Romæ", "source": "curated"}])
        self.assertEqual([m["roles"] for m in ms], [[{"role": "death"}], [{"role": "birth"}, {"role": "burial"}]])
        self.assertEqual(review, [])

    def test_occurrence_picks_the_printing(self):
        ms, _ = self.mentions("Romæ, sancti Ficti, qui Romæ natus est.",
                              [{"role": "death", "la": "Romæ", "source": "lead"},
                               {"role": "birth", "la": "Romæ", "source": "curated", "occurrence": 2}])
        self.assertEqual([(m["start"], m["roles"][0]["role"]) for m in ms], [(0, "death"), (24, "birth")])

    def test_unfound_body_place_is_proposed(self):
        _, review = self.mentions("Fictopoli, sancti Ficti.",
                                  [{"role": "death", "la": "Fictopoli", "source": "lead"},
                                   {"role": "birth", "la": "Romæ", "source": "curated"}])
        self.assertEqual([(r["op"], r["kind"]) for r in review], [("add_mention", "place")])

    def test_file_round_trip_keeps_roles(self):
        m = {"kind": "place", "where": "text", "start": 0, "end": 4, "form": "Romæ", "qid": "Q220",
             "roles": [{"role": "birth", "name": "Fictus", "n": 2}]}
        out = em.to_file(m, "Romæ natus")
        self.assertEqual(list(out), ["kind", "where", "start", "end", "check", "qid", "roles"])
        self.assertEqual(em.from_file(out, "Romæ natus")["roles"], m["roles"])

    def test_validate_rejects_an_unknown_role(self):
        m = {"kind": "place", "where": "text", "start": 0, "end": 4, "form": "Romæ", "qid": None,
             "roles": [{"role": "nativity"}]}
        errors = em.validate({"la": {"mr:0101-a": [m]}}, lambda e, i, w: "Romæ natus")
        self.assertTrue(any("role" in e for e in errors), errors)
```

(the name `em` is whatever alias the file uses for `extract_mentions`.)

- [ ] **Step 3: Run them to verify they fail**

Run: `python3 -m unittest tests.test_mentions_text tests.test_extract_mentions 2>&1 | grep -E "^(FAIL|ERROR):|FAILED"`
Expected: failures/errors in the new tests only.

- [ ] **Step 4: Implement**

In `scripts/mentions_text.py`:

```python
def nth_place(text, form, n):
    """The nth printing of a place designation in `text`: as printed, else after folding."""
    start, k = text.find(form), 0
    while start >= 0:
        k += 1
        if k == n:
            return start, start + len(form)
        start = text.find(form, start + len(form))
    folded, index = fold_map(text)
    target = fold_map(form)[0]
    start, k = (folded.find(target) if target else -1), 0
    while start >= 0:
        k += 1
        if k == n:
            return to_print(index, start, start + len(target))
        start = folded.find(target, start + len(target))
    return None
```

In `scripts/extract_mentions.py`, import `nth_place` with the other `mentions_text` names, and `ROLES` from `extract_places`. Add:

```python
def role_of(item):
    """A place item's entry in its mention's roles."""
    out = {"role": item["role"]}
    if "person" in item:
        out["name"] = item["person"]
        if "n" in item:
            out["n"] = item["n"]
    return out
```

Replace the place loop in `eulogy_mentions`:

```python
    for item in places:
        form = item.get(lang)
        if not form:
            continue
        if item["source"] == "lead":
            span, how = find_place(text, form, spans("place", "text")), "as printed"
            if span is None and "via" in item:
                span, how = back_ref_span(text, lang), "back-reference"
        else:
            span = nth_place(text, form, item.get("occurrence" if lang == "la" else "occurrence_it", 1))
            how = "as printed"
        same = next((m for m in mentions if m["kind"] == "place" and span == (m["start"], m["end"])), None)
        if same is not None:
            same["roles"].append(role_of(item))
            continue
        if span is None or not free(span, spans("place", "text")):
            ask("add_mention", "place", "text", None, f"the place as printed ({form}) was not found",
                qid=place_qid(item["la"]))
            continue
        add("place", "text", span, how, qid=place_qid(item["la"]), roles=[role_of(item)])
```

`to_file`: after `out["qid"] = m["qid"]` add `if m.get("roles"): out["roles"] = m["roles"]`.
`from_file`: after `out["qid"] = m.get("qid")` add `if m.get("roles"): out["roles"] = m["roles"]`.
`curated_mention`: for a place, set `out["roles"]` to `[role_of(it) for it in items if out["form"] is not None and it.get(lang) == out["form"]]`, or `[role_of(item)]` when only the single-item fallback found `item`; leave it out when empty.
`validate`: after the person/name check add:

```python
                for r in m.get("roles", []):
                    if m["kind"] != "place" or r.get("role") not in ROLES:
                        errors.append(f"{tag}: role {r.get('role')!r} is not a place role")
```

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -1`
Expected: `OK`. (Existing tests that compare whole place mentions may now need `roles` in their expectations: update those expectations only, not behaviour, and ledger how many.)

- [ ] **Step 6: Regenerate mentions and verify only `roles` changed**

```bash
SP=/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad
git show HEAD:data/mentions.json > $SP/mentions-before.json
python3 scripts/extract_mentions.py ../martyrology-texts --review $SP/mentions-review.json
python3 - <<'EOF'
import json
SP = "/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad"
old = json.load(open(f"{SP}/mentions-before.json"))["editions"]
new = json.load(open("data/mentions.json"))["editions"]
strip = lambda d: {e: {i: [{k: v for k, v in m.items() if k != "roles"} for m in ms] for i, ms in by.items()} for e, by in d.items()}
assert strip(old) == strip(new), "mentions changed beyond roles"
places = [m for by in new.values() for ms in by.values() for m in ms if m["kind"] == "place"]
print(len(places), "place mentions;", sum(1 for m in places if not m.get("roles")), "without roles")
EOF
git diff --stat docs/mentions-report.md
```
Expected: the assertion holds; every place mention has `roles` (0 without, or a few curated mentions whose form matches no item: list them and ledger); the report unchanged or only counts. `docs/mentions-changeset.md` must not be added to git if it changes (it is the private change-set note; check `git status`).

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_mentions.py scripts/mentions_text.py tests/test_extract_mentions.py tests/test_mentions_text.py data/mentions.json docs/mentions-report.md
git commit -m "mentions: each place mark carries its roles (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 5: The registry takes `places` from `data/places.json`

**Files:**
- Modify: `scripts/registry_places.py` (`load`, `main`)
- Test: `tests/test_registry_places.py`

**Interfaces:**
- Consumes: `extract_registry.load_places(repo_root, current_ids)`, `extract_registry.add_places(entries, places)`.
- Produces: `load(repo_root)` returns entries whose current entries' `places` are those of `data/places.json`.

- [ ] **Step 1: Write the failing test**

Add to `CheckTest` in `tests/test_registry_places.py`:

```python
    def test_places_come_from_places_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel in ("data/martyrology_ids.json", "data/gazetteer.json", "data/countries_curated.json",
                        "data/places.json"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, root / rel)
            shutil.copytree(ROOT / "registry", root / "registry")
            places = json.loads((root / "data/places.json").read_text(encoding="utf-8"))
            places["places"]["mr:0101-basilius"].append({"role": "birth", "la": "Cæsaréæ", "source": "curated"})
            (root / "data/places.json").write_text(json.dumps(places, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
            self.assertEqual(rp.main(["--check", str(root)]), 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rp.main([str(root)]), 0)
            reg = json.loads((root / "data/martyrology_ids.json").read_text(encoding="utf-8"))
            e = next(x for x in reg["entries"] if x["id"] == "mr:0101-basilius")
            self.assertEqual(e["places"][-1]["la"], "Cæsaréæ")
```

Also add `"data/places.json"` to the copied files in `test_check_reports_a_stale_country`.

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_registry_places 2>&1 | grep -E "^(FAIL|ERROR):|FAILED"`
Expected: FAIL in `test_places_come_from_places_json` (`--check` returns 0: places.json is not read).

- [ ] **Step 3: Implement**

In `load`:

```python
def load(repo_root):
    data = repo_root / "data"
    registry = json.loads((data / "martyrology_ids.json").read_text(encoding="utf-8"))
    gazetteer = json.loads((data / "gazetteer.json").read_text(encoding="utf-8"))["places"]
    curated = json.loads((repo_root / CURATED).read_text(encoding="utf-8"))["countries"]
    entries = registry["entries"]
    places = reg.load_places(repo_root, {e["id"] for e in entries if not e.get("deprecated")})
    return reg.add_places(entries, places), gazetteer, curated
```

Update the module docstring: it now also copies `data/places.json` into the registry (rerun after `extract_places.py`). In `main`, the `changed` computation compares against the entries as loaded; keep it, since the stale-file list is what matters.

- [ ] **Step 4: Run tests and the real check**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -1 && python3 scripts/registry_places.py --check; echo rc=$?`
Expected: `OK`; `rc=0` if the registry already matches `data/places.json` (Tasks 1-4 did not add places). If it reports differences (e.g. key order of items), run `python3 scripts/registry_places.py`, inspect `git diff --stat`, and ledger.

- [ ] **Step 5: Commit**

```bash
git add scripts/registry_places.py tests/test_registry_places.py
git commit -m "registry_places: take places from data/places.json (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 6: Documentation

**Files:**
- Modify: `AGENTS.md`, `docs/canonicalization-report.md`

- [ ] **Step 1: AGENTS.md**

- Step 4 (`extract_places.py`): mention that `data/places_curated.json` holds body places (any place the eulogy names outside its opening place), with roles from the thirteen, optional `person` / `n` / `occurrence` / `occurrence_it`, and that the report lists "places named but not recorded".
- Add a pipeline step after `extract_places.py` (renumber): **`scripts/body_places.py`** — checks the model's body-place proposals into `data/places_review.json` (`crmedr-changeset/v1`, op `add_place`, reviewed in martyrology-frontend) and applies the review into `data/places_curated.json`; rejected items are remembered. Run lines: `python3 scripts/body_places.py check <proposals.json> /path/to/martyrology-texts`; `python3 scripts/body_places.py apply <exported.json> /path/to/martyrology-texts`; then `extract_places.py`, `build_gazetteer.py propose`, `registry_places.py`, `extract_mentions.py`.
- `registry_places.py` step: it also copies `data/places.json` into the registry.
- `extract_mentions.py` step: place mentions carry `roles` (`{role, name?, n?}`), one mention per printed span.
- Hand-corrections: `data/places_curated.json` line updated to "body places (reviewed through `body_places.py`) and hand-entered places".

- [ ] **Step 2: canonicalization-report.md**

In the Places section, after "Countries from opening places (October 2026)", add `### Every place named, with its role (October 2026)`: the decisions (every place the eulogy names; a role belongs to one eulogy's item, never to the place; fine-grained roles, merge later; `person` / `n` in group eulogies; the model proposes, a script checks, a person decides; country stays with the opening place), the role table (role, covers) from the spec, the item keys and their rules (verbatim, limits, `occurrence`, no overlap with the opening place, no duplicates), and `roles` on mentions. Also update the Places section's role list where it enumerates the seven roles.

- [ ] **Step 3: Check and commit**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -1 && python3 scripts/registry_places.py --check && python3 scripts/build_gazetteer.py check`
Expected: `OK`, rc 0, `ok: …`.

```bash
git add AGENTS.md docs/canonicalization-report.md
git commit -m "docs: body places, roles and the add_place review (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```
