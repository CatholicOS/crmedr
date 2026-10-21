# Jev on the Gazetteer Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jev suggestions (calibrated, then pre-filled at the curator's threshold) on the 1,406 queued
`resolve_place` cards, a second Wikidata search for places with no usable candidate, and the frontend
card that shows and takes them.

**Architecture:** crmedr gains `scripts/gazetteer_jev.py` (one TypeSafe request per card and its
reading, pattern of `subject_jev.py`) and `scripts/suggest_places.py` (`suggest`, `evaluate`,
`prefill`; pattern of `suggest_subjects.py`), plus a `search-more` subcommand in
`build_gazetteer.py`. martyrology-frontend's `PlaceCard` shows `op.jev` as `PersonCard` does. The runs
(calibration, suggestions, research, pre-fill) follow the runbook at the end.

**Tech Stack:** Python 3 standard library + unittest (crmedr); Next.js/React/TypeScript + vitest
(martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-21-gazetteer-jev-design.md`

## Global Constraints

- crmedr scripts: standard library only; tests with `python3 -m unittest discover tests`.
- The model and client come from `mentions_jev.py` (`MODEL`, `TypeSafe`, `api_key`, `TypeSafeError`,
  `KeyRefused`); answers cached in `.cache/typesafe/` (git-ignored).
- Sent per card: `la`, `it`, one Latin and one English clause of one eulogy (each at most
  `subject_jev.MAX_CLAUSE` = 400 characters), and the candidates' `wikidata`, `label`, `description`,
  `country`, `types`, `la`, `p9314`. No coordinates.
- `op["jev"]` never overwrites `suggested`, `decision` or `edited` (except `prefill`, which writes
  `decision`/`edited` on undecided cards only).
- `op["jev"]` holds no 2004 text: `data/gazetteer_review.json` is public and bundled by the frontend.
- `jev` shape, exactly: `{"decision"?: "accept"|"edit"|"reject", "wikidata"?: "Q…", "country"?: "XX",
  "reason"?: str, "kind": "place"|"people"|"relative"|"not_place", "probability": float,
  "confidence": float, "model": str}`. `decision` is absent only on a card with no candidates that Jev
  reads as a `place`: there is nothing to pick, and a reject would turn a real place away.
- Reasons, exactly: `"Jev: none of the candidates is this place"`, `"Jev: a nationality or people, not a
  place"`, `"Jev: the place depends on its eulogy"`, `"Jev: not a place"`.
- An accept is Jev picking the card's default (`suggested.wikidata`, else `candidates[0].wikidata`), as
  `build_gazetteer._resolve` reads an accept.
- Pre-fill: only an item pick (accept/edit) whose `probability` ≥ the threshold and whose candidate has a
  `country`; the op gets `"prefilled": "jev"`. Never a reject, never a decided card.
- Frontend: Jev's hint under the candidates, "Take the suggestion" first in the button row; the reject
  form replaces the row (as on `PersonCard`).

## Review Focus

1. A place phrase not found verbatim in its eulogy's Latin (ligature or accent differences) → the clause
   falls back to a folded match, then to the first sentence; never an exception (Task 1).
2. Jev picks a candidate with no `country` → the suggestion is written, the frontend's Take is disabled,
   and `prefill` skips it (Tasks 1, 4, 5).
3. A card the curator already decided → `suggest` leaves its decision alone and `prefill` skips it
   (Tasks 2, 4).
4. `search-more` changes a card's candidates → its stale `jev` is removed, so a re-run of `suggest` asks
   anew (Task 3).
5. No key and uncached requests → `suggest`/`evaluate` stop before writing anything (Task 2).

---

## File Structure

| File | Responsibility |
|---|---|
| `crmedr/scripts/gazetteer_jev.py` (new) | clauses, the request for one place card, reading its answers into `jev` |
| `crmedr/scripts/suggest_places.py` (new) | load texts; `suggest`, `evaluate`, `prefill` over a change-set; CLI |
| `crmedr/scripts/build_gazetteer.py` | `search-more` subcommand |
| `crmedr/scripts/wikidata.py` | `candidates(text, language="it")` takes a search language |
| `crmedr/tests/test_gazetteer_jev.py`, `tests/test_suggest_places.py` (new), `tests/test_gazetteer.py` | tests |
| `martyrology-frontend/lib/changeset.ts` | `PlaceJev`; `jev?`, `prefilled?` on `ResolvePlaceOp` |
| `martyrology-frontend/lib/place-review.ts` (new) | `placeDefaultQid`, `placeJevRecord` |
| `martyrology-frontend/components/PlaceCard.tsx` | hint, kind, Take, pre-filled chip |
| `martyrology-frontend/components/ReviewPage.tsx` | "pre-filled only" filter |
| `martyrology-frontend/messages/*.json` | the new strings, six languages |

crmedr work goes on branch `feat/gazetteer-jev`; frontend work on `feat/place-card-jev`.

---

### Task 1: `gazetteer_jev.py`: clauses, request, reading

**Files:**
- Create: `crmedr/scripts/gazetteer_jev.py`
- Test: `crmedr/tests/test_gazetteer_jev.py`

**Interfaces:**
- Consumes: `subject_jev._sentences`, `subject_jev._window`, `subject_jev.MAX_CLAUSE`;
  `gazetteer_text.fold`, `gazetteer_text.parse_italian`; `mentions_jev.MODEL`.
- Produces:
  - `KINDS = ("place", "people", "relative", "not_place")`, `KIND_CRITERIA: dict[str, str]`,
    `KIND_REASONS: dict[str, str]` (people/relative/not_place → the Global Constraints' reasons),
    `NONE_REASON = "Jev: none of the candidates is this place"`.
  - `latin_clause(la_text: str, la: str) -> str`
  - `english_clause(en_text: str, op: dict) -> str`
  - `place_request(op: dict, la_clause: str, en_clause: str) -> dict` (a TypeSafe body
    `{"model", "state", "questions"}`; questions `kind` always, `pick` only when the op has candidates;
    pick options `c0..cN` in candidate order, plus `none`)
  - `default_qid(op: dict) -> str | None` (`suggested.wikidata`, else `candidates[0].wikidata`)
  - `place_suggestion(op: dict, answers: dict, model: str = MODEL) -> dict | None`

- [ ] **Step 1: Write the failing tests** in `tests/test_gazetteer_jev.py`, with a fixture op of two
  candidates (`Q1` "Tyburn", country GB; `Q2` "Tyburn stream", country null) and `la` "Tybúrni":

```python
def test_latin_clause_holds_the_phrase(self):
    text = "Romæ, sancti X. Tybúrni in Anglia, beati Y, presbyteri."
    self.assertEqual(gj.latin_clause(text, "Tybúrni"), "Tybúrni in Anglia, beati Y, presbyteri.")

def test_latin_clause_folded_match(self):          # Review Focus 1
    self.assertIn("Tyburni", gj.latin_clause("Primo. Tyburni in Anglia, beati Y.", "Tybúrni"))

def test_latin_clause_falls_back_to_the_first_sentence(self):
    self.assertEqual(gj.latin_clause("Primo. Secundo.", "Nusquam"), "Primo.")

def test_english_clause_names_a_candidate_or_italian_head(self):
    en = "At Rome, Saint X. At Tyburn in London, Blessed Y, priest."
    self.assertEqual(gj.english_clause(en, OP), "At Tyburn in London, Blessed Y, priest.")

def test_request_shape(self):
    body = gj.place_request(OP, "la clause", "en clause")
    self.assertEqual(set(body["questions"]), {"kind", "pick"})
    self.assertEqual(list(body["questions"]["pick"]["criteria"]), ["c0", "c1", "none"])
    self.assertNotIn("coords", json.dumps(body["state"]))
    self.assertEqual(body["state"]["candidates"]["c0"]["wikidata"], "Q1")

def test_request_without_candidates_asks_kind_only(self):
    self.assertEqual(set(gj.place_request(dict(OP, candidates=[]), "", "")["questions"]), {"kind"})

def test_pick_default_is_accept(self):
    s = gj.place_suggestion(OP, answers("c0", "place", 0.93))
    self.assertEqual((s["decision"], s["wikidata"], s["country"], s["kind"]), ("accept", "Q1", "GB", "place"))

def test_pick_other_is_edit_without_country(self):   # Review Focus 2
    s = gj.place_suggestion(OP, answers("c1", "place", 0.8))
    self.assertEqual((s["decision"], s["wikidata"]), ("edit", "Q2"))
    self.assertNotIn("country", s)

def test_none_is_reject(self):
    s = gj.place_suggestion(OP, answers("none", "place", 0.7))
    self.assertEqual((s["decision"], s["reason"]), ("reject", gj.NONE_REASON))

def test_non_place_kind_is_reject_with_its_reason(self):
    s = gj.place_suggestion(OP, answers("c0", "people", 0.9))
    self.assertEqual((s["decision"], s["reason"], s["kind"]), ("reject", gj.KIND_REASONS["people"], "people"))

def test_kind_only_place_has_no_decision(self):
    s = gj.place_suggestion(dict(OP, candidates=[]), {"kind": choice("place", 0.88)})
    self.assertEqual((s["kind"], s["probability"]), ("place", 0.88))
    self.assertNotIn("decision", s)

def test_kind_only_people_is_reject(self):
    s = gj.place_suggestion(dict(OP, candidates=[]), {"kind": choice("people", 0.9)})
    self.assertEqual((s["decision"], s["reason"]), ("reject", gj.KIND_REASONS["people"]))

def test_unknown_option_is_none(self):
    self.assertIsNone(gj.place_suggestion(OP, answers("c9", "place", 0.9)))
```

`answers(pick, kind, p)` / `choice(option, p)` are test helpers building TypeSafe choice answers in the
shape `subject_jev._choice` reads (copy that shape from `tests/test_subject_jev.py`).

- [ ] **Step 2: Run** `python3 -m unittest tests.test_gazetteer_jev` → FAIL (module missing).
- [ ] **Step 3: Implement** the Interfaces above. The `kind` criteria, exactly:
  `place`: "a settlement, site, building, region or country: a place one could find on a map";
  `people`: "a nationality or a people (anglus, polonus, a tribe named as people), not a place";
  `relative`: "a place named only in relation to the eulogy (this city, the same monastery), which the
  phrase alone does not identify"; `not_place`: "not a place at all". The `pick` instructions name the
  phrase, the Italian forms and both clauses, and say to answer none when no candidate is the place.
  The probability and confidence of a reject from a non-place kind are the kind answer's; otherwise the
  pick's. Reuse `subject_jev._choice` for reading a choice.
- [ ] **Step 4: Run** the tests → PASS.
- [ ] **Step 5: Commit** `feat(gazetteer): Jev request and reading for place cards`.

### Task 2: `suggest_places.py suggest`

**Files:**
- Create: `crmedr/scripts/suggest_places.py`
- Test: `crmedr/tests/test_suggest_places.py`

**Interfaces:**
- Consumes: Task 1; `suggest_subjects.load_data`-style loading via `extract_typology.latin_texts`,
  `load_texts`, `extract_places.EDITION_EN`; `mentions_jev.TypeSafe`.
- Produces:
  - `load_texts_for(texts_repo: Path, repo_root: Path) -> {"la": {mrid: str}, "en": {mrid: str}}`
  - `request_for(op: dict, texts: dict) -> dict | None` (the first occurrence whose Latin text exists
    gives both clauses; None when no occurrence has a Latin text)
  - `ask(op: dict, texts: dict, client) -> tuple[dict | None, str | None]` (suggestion, error)
  - `require_key(ops, texts, client) -> None` (raises `TypeSafeError` before any write when a request
    is uncached and there is no key)
  - `suggest_ops(ops: list[dict], texts: dict, client) -> dict` (counts: suggested, skipped, errors;
    writes or replaces `jev` on every answered card, removes it where no answer)
  - CLI: `python3 suggest_places.py suggest <changeset.json> /path/to/martyrology-texts [--repo R]`

- [ ] **Step 1: Write the failing tests** (a `StubClient` as in `tests/test_suggest_subjects.py`):

```python
def test_suggest_writes_jev_whatever_the_probability(self):
    ops = [op_with_candidates()]
    counts = sp.suggest_ops(ops, TEXTS, StubClient(answers("c0", "place", 0.41)))
    self.assertEqual(counts["suggested"], 1)
    self.assertEqual(ops[0]["jev"]["probability"], 0.41)

def test_decided_card_keeps_its_decision(self):          # Review Focus 3
    op = dict(op_with_candidates(), decision="reject", edited={"reason": "x"})
    sp.suggest_ops([op], TEXTS, StubClient(answers("c0", "place", 0.99)))
    self.assertEqual((op["decision"], op["edited"]), ("reject", {"reason": "x"}))

def test_suggested_is_never_touched(self):
    op = dict(op_with_candidates(), suggested={"wikidata": "Q2", "country": "GB"})
    sp.suggest_ops([op], TEXTS, StubClient(answers("c0", "place", 0.9)))
    self.assertEqual(op["suggested"], {"wikidata": "Q2", "country": "GB"})

def test_no_key_stops_before_writing(self):              # Review Focus 5
    with self.assertRaises(mj.TypeSafeError):
        sp.require_key([op_with_candidates()], TEXTS, StubClient(None, key=None, cached=False))

def test_no_latin_text_skips(self):
    counts = sp.suggest_ops([dict(op_with_candidates(), occurrences=["mr:9999-x"])], TEXTS, StubClient(None))
    self.assertEqual(counts["skipped"], 1)
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_suggest_places` → FAIL.
- [ ] **Step 3: Implement**; the CLI calls `require_key` first, then `suggest_ops`, then writes the file
  (indent=1, `ensure_ascii=False`, trailing newline, as `build_gazetteer.write_state` writes the queue).
- [ ] **Step 4: Run** → PASS; also `python3 -m unittest discover tests` → OK.
- [ ] **Step 5: Commit** `feat(gazetteer): suggest_places.py suggest`.

### Task 3: `build_gazetteer.py search-more`

**Files:**
- Modify: `crmedr/scripts/wikidata.py` (`candidates(self, text, language="it")`, passing `language`
  to `_search`)
- Modify: `crmedr/scripts/build_gazetteer.py` (new `search_more`, subcommand, usage line)
- Test: `crmedr/tests/test_gazetteer.py` (the existing `FakeClient` gains `language` in `candidates`)

**Interfaces:**
- Consumes: `gather_candidates`, `evaluate`, `latin_nominatives`, `parse_italian`.
- Produces: `search_more(review: dict, index: dict, client) -> int` (cards whose candidates changed).
  A card is searched when it has no candidates and `jev.kind == "place"`, or when `jev.decision ==
  "reject"` with `jev.reason == NONE_REASON` and `jev.kind == "place"`. Queries: each Italian head
  (`parse_italian(it)["heads"]`) with its qualifier dropped (the text after " di ", " del ", " della ",
  " in "), searched in `it`; each Latin nominative (`latin_nominatives(la)`) searched in `la` and `it`.
  New candidates are merged after the existing ones (no duplicate QID), the card re-evaluated with
  `evaluate` (its `failed`, `claims`, `candidates` replaced), and `jev` removed when the candidates
  changed. A card that `evaluate` now passes as `auto` stays queued: the curator decides it.

- [ ] **Step 1: Write the failing tests**:

```python
def test_search_more_finds_by_the_head_without_qualifier(self):
    review = {"operations": [no_candidate_op("Béthlehem Iudæ", ["Betlemme di Giuda"], kind="place")]}
    client = FakeClient(search={("Betlemme", "it"): [BETHLEHEM]})
    self.assertEqual(bg.search_more(review, INDEX, client), 1)
    op = review["operations"][0]
    self.assertEqual([c["wikidata"] for c in op["candidates"]], [BETHLEHEM["wikidata"]])
    self.assertNotIn("jev", op)                      # Review Focus 4

def test_search_more_skips_non_places(self):
    review = {"operations": [no_candidate_op("anglus", ["inglese"], kind="people")]}
    self.assertEqual(bg.search_more(review, INDEX, FakeClient(search={})), 0)

def test_search_more_keeps_jev_when_nothing_new(self):
    review = {"operations": [no_candidate_op("X", ["X"], kind="place")]}
    bg.search_more(review, INDEX, FakeClient(search={}))
    self.assertIn("jev", review["operations"][0])
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_gazetteer` → FAIL.
- [ ] **Step 3: Implement** as in Interfaces; the CLI prints `"<n> cards gained candidates; <m> queued"`
  and writes the state with `write_state`.
- [ ] **Step 4: Run** the full suite → OK.
- [ ] **Step 5: Commit** `feat(gazetteer): search-more for places Jev reads as places`.

### Task 4: `suggest_places.py evaluate` (calibration)

**Files:**
- Modify: `crmedr/scripts/suggest_places.py`
- Test: `crmedr/tests/test_suggest_places.py`

**Interfaces:**
- Produces:
  - `THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]`
  - `calibration_set(round1_ops: list[dict], gazetteer: dict) -> list[tuple[dict, str | None]]`: for
    each round-1 op whose `id` is `reviewed` or `auto` in the gazetteer and whose settled `wikidata` is
    among its candidates: (the op with `suggested` removed, the settled QID) as a positive; and, when at
    least one other candidate remains, (the op without the settled candidate and without `suggested`,
    None) as a negative.
  - `evaluate_ops(pairs, texts, client) -> list[dict]` rows `{id, expected, picked, probability,
    negative: bool}` (`picked` is the suggestion's `wikidata`, None for a reject)
  - `report(rows, thresholds) -> str`: per threshold, positives and negatives separately: answered at or
    above it, agreeing, and the agreement rate; then the disagreements at 0.9, one per line.
  - CLI: `python3 suggest_places.py evaluate <round1.json> /path/to/martyrology-texts [--repo R]` (the
    gazetteer from `--repo`'s `data/gazetteer.json`).

- [ ] **Step 1: Write the failing tests**:

```python
def test_calibration_set_positive_and_negative(self):
    pairs = sp.calibration_set([round1_op(cands=["Q1", "Q2"], suggested="Q1")], {"P": {"wikidata": "Q1", "status": "reviewed"}})
    self.assertEqual([(len(op["candidates"]), exp) for op, exp in pairs], [(2, "Q1"), (1, None)])
    self.assertTrue(all("suggested" not in op for op, _ in pairs))

def test_calibration_set_skips_settled_outside_candidates(self):
    self.assertEqual(sp.calibration_set([round1_op(cands=["Q2"])], {"P": {"wikidata": "Q1", "status": "reviewed"}}), [])

def test_report_counts_agreement_per_threshold(self):
    rows = [{"id": "a", "expected": "Q1", "picked": "Q1", "probability": 0.95, "negative": False},
            {"id": "b", "expected": None, "picked": "Q3", "probability": 0.92, "negative": True}]
    out = sp.report(rows, [0.9])
    self.assertIn("0.9  positives 1/1 agree (100.0%)  negatives 0/1 agree (0.0%)", out)
```

- [ ] **Step 2–4:** run → FAIL; implement; run the full suite → OK.
- [ ] **Step 5: Commit** `feat(gazetteer): evaluate Jev on round 1, with negatives`.

### Task 5: `suggest_places.py prefill`

**Files:**
- Modify: `crmedr/scripts/suggest_places.py`
- Test: `crmedr/tests/test_suggest_places.py`

**Interfaces:**
- Produces: `prefill_ops(ops: list[dict], threshold: float) -> dict` (counts: accept, edit, skipped);
  CLI `python3 suggest_places.py prefill <changeset.json> --threshold X`.
  Writes `{"decision": "accept"}` when Jev picked the default, else `{"decision": "edit", "edited":
  {"wikidata": Q, "country": C}}` (the shape `PlaceCard` and `_resolve` use), and `"prefilled": "jev"`.

- [ ] **Step 1: Write the failing tests**:

```python
def test_prefill_item_picks_at_the_threshold(self):
    ops = [card(jev=pick("Q1", "accept", 0.9, country="GB")), card(jev=pick("Q2", "edit", 0.95, country="FR"))]
    sp.prefill_ops(ops, 0.9)
    self.assertEqual((ops[0]["decision"], ops[0]["prefilled"]), ("accept", "jev"))
    self.assertEqual(ops[1]["edited"], {"wikidata": "Q2", "country": "FR"})

def test_prefill_never_rejects(self):
    op = card(jev={"decision": "reject", "reason": "Jev: not a place", "kind": "not_place", "probability": 0.99})
    sp.prefill_ops([op], 0.5)
    self.assertIsNone(op.get("decision"))

def test_prefill_skips_below_threshold_no_country_and_decided(self):   # Review Focus 2, 3
    ops = [card(jev=pick("Q1", "accept", 0.89, country="GB")),
           card(jev=pick("Q2", "edit", 0.99)),
           dict(card(jev=pick("Q1", "accept", 0.99, country="GB")), decision="reject", edited={"reason": "x"})]
    sp.prefill_ops(ops, 0.9)
    self.assertEqual([o.get("decision") for o in ops], [None, None, "reject"])
    self.assertTrue(all("prefilled" not in o for o in ops))
```

- [ ] **Step 2–4:** run → FAIL; implement; run the full suite → OK.
- [ ] **Step 5: Commit** `feat(gazetteer): prefill Jev's item picks at a threshold`; push the branch and
  open the crmedr PR (body: what, tests, that the runs follow the runbook).

### Task 6: frontend: types, `place-review.ts`, `PlaceCard`

**Files:**
- Modify: `martyrology-frontend/lib/changeset.ts`
- Create: `martyrology-frontend/lib/place-review.ts`
- Modify: `martyrology-frontend/components/PlaceCard.tsx`, `messages/{en,it,fr,de,es,pt}.json`
  (`Map.place`: `jevSuggests` "Jev suggests: {what} ({confidence}%)", `jevNone` "no item",
  `jevKind.place|people|relative|not_place` ("Jev reads this as a place", …), `take` "Take the suggestion", `prefilled` "pre-filled by Jev";
  translated in each language)
- Test: `martyrology-frontend/components/__tests__/PlaceCard.test.tsx`, `lib/__tests__/place-review.test.ts`

**Interfaces:**
- Produces: `interface PlaceJev { decision?: "accept" | "edit" | "reject"; wikidata?: string; country?:
  string; reason?: string; kind: "place" | "people" | "relative" | "not_place"; probability: number;
  confidence: number; model: string }`; `ResolvePlaceOp.jev?: PlaceJev`, `ResolvePlaceOp.prefilled?:
  "jev"`; `placeDefaultQid(op): string`; `placeJevRecord(op): DecisionRecord | null` (accept →
  `{decision: "accept"}` when the pick is the default; edit → `{decision: "edit", edited: {wikidata,
  country}}`, null without a country; reject → `{decision: "reject", edited: {reason}}`; null without a decision).

- [ ] **Step 1: Write the failing tests**: `placeJevRecord` for accept, edit, edit without country
  (null), reject; `PlaceCard` renders "Jev suggests: Q1 Tyburn (93%)" after the candidates; Take is the
  first button of the row and records `placeJevRecord`; Take is disabled when the record is null; a
  kind-only `jev` (no decision) shows "Jev reads this as a place" and no Take; the kind note shows for
  `people`; "pre-filled by Jev" shows when `op.prefilled === "jev"`; the reject form
  replaces the row (Take hidden).
- [ ] **Step 2: Run** `npx vitest run components/__tests__/PlaceCard.test.tsx lib/__tests__/place-review.test.ts` → FAIL.
- [ ] **Step 3: Implement**; Take also moves the selection and country to the pick (as `PersonCard`'s
  Take does).
- [ ] **Step 4: Run** `npx tsc --noEmit && npm run -s lint && npm test -s` → all pass.
- [ ] **Step 5: Commit** `feat(review): Jev on place cards`.

### Task 7: frontend: "pre-filled only" filter

**Files:**
- Modify: `martyrology-frontend/components/ReviewPage.tsx`, `messages/*.json` (`Review.filters.prefilledOnly`)
- Test: `martyrology-frontend/components/__tests__/ReviewPage.test.tsx`

**Interfaces:**
- Produces: a checkbox beside "undecided only", shown when any op has `prefilled`; when checked, only ops
  with `prefilled` are listed; part of `pageKey`.

- [ ] **Step 1: Write the failing test**: a change-set with one pre-filled and one plain op; checking the
  box lists only the pre-filled one.
- [ ] **Step 2–4:** run → FAIL; implement; `npx tsc --noEmit && npm run -s lint && npm test -s` → pass.
- [ ] **Step 5: Commit** `feat(review): filter on pre-filled cards`; push and open the frontend PR.

---

## Runbook (after the PRs merge; the controller runs these, not subagents)

1. **Calibrate:** `python3 scripts/suggest_places.py evaluate data/gazetteer-review.decided.json ../martyrology-texts`.
   Report to the curator; **stop** until the curator picks the threshold.
2. **Suggest:** `python3 scripts/suggest_places.py suggest data/gazetteer_review.json ../martyrology-texts`.
3. **Second search:** `python3 scripts/build_gazetteer.py search-more`, then `suggest` again (it asks only
   the cards whose `jev` was removed; the rest are cached).
4. **Research:** cards still without a usable candidate that Jev reads as places go to Claude research
   agents in half-month batches, writing `suggested`/`reasoning`/`confidence` (reasoning ≤300 characters,
   no quotation of four or more words of the 2004 text); `build_gazetteer.py verify-suggestions`. Proposed
   new Wikidata items are listed to the curator; **none is created before the curator approves the
   batch.**
5. **Pre-fill:** `python3 scripts/suggest_places.py prefill data/gazetteer_review.json --threshold <chosen>`;
   `build_gazetteer.py check`; commit the queue in a crmedr PR.
6. **Frontend:** refresh `changesets/gazetteer-review.json` with `npm run import-changeset` (as for the
   earlier gazetteer queues), PR, merge, `gh workflow run deploy.yml --ref main`.
7. **After the curator's review:** export → `build_gazetteer.py apply <exported.json>` → `extract_places`,
   `registry_places`, `extract_mentions` → API pin release → frontend `npm run snapshot-registry`.
