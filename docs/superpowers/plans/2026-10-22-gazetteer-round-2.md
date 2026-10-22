# Gazetteer Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the curator's page-1 decisions, give peoples items, re-ask Jev with the page-1 conventions, and let Jev decide the picks at ≥ 0.95 (status `jev`), pre-filling 0.90–0.95.

**Architecture:** `build_gazetteer.py` gains the status `jev` and a `decide-jev` command built on `_resolve`; `gazetteer_jev.py` asks the pick for peoples too and states the page-1 conventions; the 89 people cards get research suggestions; the frontend counts `jev` as identified and gets the new queue.

**Tech Stack:** Python 3 stdlib, `unittest`; TypeScript/Vitest in martyrology-frontend.

**Spec:** `docs/superpowers/specs/2026-10-22-gazetteer-round-2-design.md`.

## Global Constraints

- The state sent to Jev is unchanged (`latin_clause`, `english_clause` as today); only instructions and criteria change.
- `jev` entries: same shape as `reviewed` (a `country`, `country: null`, or `countries` ≥ 2); never calibration truth.
- `decide-jev` touches only cards whose `decision` is null or whose `prefilled` is `"jev"`; never a reject; the pick must be one of the card's candidates; a country is Jev's `country`, else the suggestion's `countries` when `suggested.wikidata` is the pick, else the candidate's `countries` (≥ 2); otherwise the card is not decided.
- Thresholds: decide ≥ 0.95; pre-fill [0.90, 0.95); stop and report if positive agreement at 0.95 < 97%.
- Page-1 decisions: the first 50 ops of the export only (the others in the export are unconfirmed pre-fills).
- Research reasoning: at most 300 characters, may quote the place, never the eulogy.

## Review Focus

1. A `jev` pick of a candidate with `countries` and no `country` (Frisia-like): decided with `countries` (`test_decide_with_candidate_countries`).
2. A card the curator pre-fill-confirmed in the browser but not exported: unknowable here; the queue is replaced only after the curator's go-ahead (process, not code).
3. A pick whose candidate is absent from the card (stale `jev`): not decided (`test_decide_needs_a_candidate`).
4. `decide-jev` producing an invalid entry (bad country): nothing is written (`test_decide_is_all_or_nothing`).
5. People kind without candidates: still the old reject suggestion with its reason (`test_people_without_candidates`).

---

### Task 1: status `jev` and `decide-jev` (crmedr)

**Interfaces — produces:** `STATUSES = ["auto", "reviewed", "jev", "unresolved"]`; `validate` treats `jev` as `reviewed` for `country: null` and `countries`; `decide_jev(gazetteer, review, index, client, threshold) -> dict` (counts `decided`, `skipped`), all-or-nothing, removes decided ops from `review["operations"]`; CLI `build_gazetteer.py decide-jev --threshold X [repo_root]`.
- [ ] Tests (`tests/test_gazetteer.py`, class `DecideJevTest`): `test_decide_at_threshold` (pick 0.96 decided as `jev`, 0.94 left), `test_decide_skips_curator_decisions` (a card with `decision` and no `prefilled` untouched), `test_decide_replaces_a_prefill`, `test_decide_with_candidate_countries`, `test_decide_with_suggested_countries`, `test_decide_needs_a_candidate`, `test_decide_never_rejects`, `test_decide_is_all_or_nothing`, `test_jev_status_validates` (country null and countries accepted for `jev`).
- [ ] RED → implement → GREEN; commit `"gazetteer: status jev and decide-jev"`.

### Task 2: page-1 decisions applied

- [ ] Write `/tmp/.../page1.decided.json` = the export with only its first 50 ops' decisions kept (others `decision: null, edited: null`); `build_gazetteer.py apply` it. Expected: 50 decisions applied, 1,359 queued; `check` ok; `registry_places.py`, `extract_mentions.py` regenerated; suite green. Commit `"gazetteer: the curator's page-1 decisions"`.

### Task 3: peoples (research)

- [ ] Brief per undecided card of kind `people` (89): id, Italian forms, occurrence IDs. Three research subagents (Bash + `wb`), each returning `{id: {wikidata, country | countries, confidence, reasoning}}` for the people's or kingdom's item and its homeland countries today, or `{none: reason}`.
- [ ] Write them as `suggested` / `confidence` / `reasoning`; `build_gazetteer.py verify-suggestions` ok; commit `"gazetteer queue: peoples' items (research)"`.

### Task 4: Jev conventions and re-ask

**Interfaces — produces:** in `gazetteer_jev.py`, `PICK_INSTRUCTIONS` adds the people and monastery conventions; `place_suggestion` asks/reads the pick when the kind is `place` or `people` (a `people` kind without candidates, or picking none, stays a reject with its reason).
- [ ] Tests (`tests/test_gazetteer_jev.py`): `test_people_pick_is_read` (kind people + pick c0 → accept/edit of c0), `test_people_without_candidates`, `test_instructions_state_conventions` (the instructions mention a people's item and a monastery adjective).
- [ ] RED → GREEN; commit.
- [ ] `suggest_places.py suggest data/gazetteer_review.json ../martyrology-texts`; `evaluate` on a combined calibration file (round-1 ops + page-1 ops); read the 0.95 positives line. If < 97%: stop, report. Else commit the queue `"gazetteer queue: Jev asked again with the page-1 conventions"`.

### Task 5: decide and pre-fill

- [ ] `build_gazetteer.py decide-jev --threshold 0.95`; `suggest_places.py prefill data/gazetteer_review.json --threshold 0.90` (after clearing stale `prefilled` decisions below 0.90); `check`, `registry_places.py`, `extract_mentions.py`, `extract_dates.py`, `extract_registry.py`; suite; AGENTS.md (status `jev`, `decide-jev`); commit; PR.

### Task 6: frontend

- [ ] `scripts/snapshot-registry.mjs`: `IDENTIFIED` gains `"jev"`; test in `lib/__tests__/snapshot.test.ts` (`a jev place is identified`); the new queue copied (indent 1); suite; PR. Deploy only on the curator's go-ahead.
