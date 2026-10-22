# Date Estimates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Jev century estimate for each current eulogy without a curated or death date, calibrated on the death-dated ones, written into `data/dates.json` as `source: "estimate"` at the curator's threshold.

**Architecture:** `scripts/dates_jev.py` builds the request and reads the answer (pure functions). `scripts/estimate_dates.py` runs it: `evaluate` asks Jev on the death-dated eulogies and prints agreement by threshold; `estimate` asks the rest and writes `data/date_estimates.json` (picks and probabilities, no text). `extract_dates.py` turns estimates at or above `ESTIMATE_MIN` into dates.

**Tech Stack:** Python 3 standard library, `unittest`; TypeSafe via `mentions_jev.TypeSafe` (cached in `.cache/typesafe/`).

**Spec:** `docs/superpowers/specs/2026-10-22-eulogy-dates-design.md`, *The era estimate*. Step 2 of its *Order of work*.

## Global Constraints

- Sent to TypeSafe per eulogy: the first sentence of the 2004 Latin and of the English (`subject_jev._sentences` / `_window`, at most 400 characters), the typology, `printed_by` (the bound year or null). Never a whole eulogy.
- Model `mentions_jev.MODEL`; one Choice question `century` with options `bc`, `c1` … `c21`, `cannot_tell`.
- `data/date_estimates.json` and any report hold IDs, picks and numbers only, never text.
- Century n: `from` 100(n−1)+1, `to` 100n; `bc`: `{"to": -1}`. Cut at the bound (`to` = min(to, bound)); a century with `from` > bound is dropped.
- Precedence: curated > wikidata > estimate > edition. An estimate below `ESTIMATE_MIN`, or `cannot_tell`, is not a date.
- Calibration truth: the pick agrees when its century range overlaps the death date's range; "within one" when an adjacent century does.

## Review Focus

1. An English text missing for a eulogy: the request is sent with an empty `english_clause`, not skipped (`test_request_without_english`).
2. A Latin text missing (a `same_eulogy` twin carries it): `latin_texts` supplies the twin's; no text at all → no request (`test_no_latin_no_request`).
3. An answer naming an option not offered, or malformed: no estimate (`test_bad_answer`).
4. A `bc` pick with a bound: stays `{"to": -1}` (`test_bc_with_bound`).
5. An estimate for an ID that is no longer current: ignored by `extract_dates.py` with a report line, not a crash (`test_stale_estimate_ignored`).

---

### Task 1: `scripts/dates_jev.py`

**Interfaces — produces:**
- `OPTIONS: list[str]` = `["bc", "c1", …, "c21", "cannot_tell"]`; `CRITERIA: dict[str, str]` (one plain sentence per option, e.g. `c4`: "the 4th century (AD 301–400)").
- `century_range(option: str) -> dict | None` — `{"from", "to"}` (`bc`: `{"to": -1}`), None for `cannot_tell`.
- `request_for(la_text: str, en_text: str | None, typology: str | None, bound: int | None) -> dict | None` — `{"model", "state": {"latin_clause", "english_clause", "typology", "printed_by"}, "questions": {"century": {"type": "choice", "instructions", "criteria"}}}`; None when `la_text` is empty.
- `estimate_of(answer: dict) -> dict | None` — `{"century", "probability", "confidence"}` via `subject_jev._choice`; None when malformed.
- `agrees(option: str, date: dict) -> tuple[bool, bool]` — (overlaps, overlaps within one century).

- [ ] Tests (`tests/test_dates_jev.py`): `test_century_ranges` (c1 → 1–100, c4 → 301–400, c21 → 2001–2100, bc → {to: -1}, cannot_tell → None); `test_request_shape` (23 criteria, state keys, clause ≤ 400 and is the first sentence); `test_request_without_english`; `test_no_latin_no_request`; `test_estimate_of`; `test_bad_answer`; `test_agrees` (c4 vs year 304 → (True, True); c5 vs 304 → (False, True); c7 vs 304 → (False, False); bc vs year -50 → (True, True)).
- [ ] RED, implement, GREEN, commit `"dates: the Jev century request"`.

### Task 2: `scripts/estimate_dates.py`

**Interfaces — consumes** Task 1; `extract_typology.load_texts`/`latin_texts`, `extract_places.EDITION_EN`, `mentions_jev.TypeSafe`/`api_key`, `data/dates.json`, `data/edition_bounds.json`, `data/typology.json`. **Produces:**
- `evaluate /path/to/martyrology-texts [repo_root]`: asks Jev on every eulogy whose date has `source: "wikidata"`; prints, for thresholds `[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]`, covered count, agreement and within-one agreement, then the disagreements as `id pick p= truth`.
- `estimate /path/to/martyrology-texts [repo_root]`: asks Jev on every current eulogy whose date source is neither `curated` nor `wikidata`; writes `data/date_estimates.json` = `{"$comment", "model", "estimates": {id: {"century", "probability", "confidence"}}}` (sorted, `indent=1`). Stops before asking when there is no key and requests are uncached (as `suggest_places.require_key`).
- `rows_for(ids, texts, typology, bounds, client) -> dict[str, dict | None]`, `calibration(rows, truths, thresholds) -> str` (pure; tested with a fake client).
- [ ] Tests (`tests/test_estimate_dates.py`): `test_calibration_table` (three rows, one agreeing, one within one, one wrong, at 0.5 and 0.9); `test_estimate_scope` (curated and wikidata IDs not asked); `test_no_key_stops` (fake client without key, uncached → TypeSafeError, nothing written).
- [ ] RED, implement, GREEN, commit `"dates: estimate_dates.py evaluate and estimate"`.
- [ ] Run `evaluate`; report the table to the curator. **Stop for the curator's threshold** unless one is obvious; record it as `ESTIMATE_MIN`.

### Task 3: estimates into `data/dates.json`

**Interfaces — consumes** `data/date_estimates.json`; **produces** `ESTIMATE_MIN: float` in `extract_dates.py`; `estimate_date(est: dict, bound: int | None) -> dict | None`; `build_dates(…, estimates)` with the precedence above; the report gains an "estimate" count and a stale-estimate list.
- [ ] Tests (in `tests/test_dates.py`): `test_estimate_below_threshold_ignored`; `test_estimate_cut_at_bound` (c17 with bound 1630 → 1601–1630); `test_estimate_after_bound_dropped` (c18, bound 1630 → the edition date); `test_bc_with_bound`; `test_wikidata_over_estimate`; `test_stale_estimate_ignored`.
- [ ] RED, implement, GREEN; run `estimate`, `extract_dates.py`, `extract_registry.py`; full suite; AGENTS.md (the `estimate_dates.py` item); commit `"dates: Jev estimates at the curator's threshold"`.
