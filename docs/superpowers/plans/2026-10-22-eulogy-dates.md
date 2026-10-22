# Eulogy Dates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each current eulogy an optional `date` (year or range, basis, source) from curated dates, its subjects' death dates and the older editions, and copy it onto the registry.

**Architecture:** A new offline generator `scripts/extract_dates.py` writes `data/dates.json` from committed files only; its `bounds` subcommand, the one step that reads martyrology-api, writes the committed `data/edition_bounds.json` first. `extract_registry.py` merges `data/dates.json` as a `date` key after `places`. A report lists the checks and the undated feasts for the curator.

**Tech Stack:** Python 3 standard library, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-22-eulogy-dates-design.md`. This plan is step 1 of its *Order of work*. Steps 2 (the era estimate) and 3 (the era-sensitive places) get their own plans after this lands: step 2 needs dates to calibrate against, step 3 needs both.

## Global Constraints

- Standard library only; `extract_dates.py` (no subcommand) and `--check` run offline from committed files.
- Years are integers, negative before Christ, matching `person_details.json`. There is no year 0.
- `basis` ∈ {`death`, `deposition`, `translation`, `dedication`, `event`}; `source` ∈ {`wikidata`, `edition`, `curated`, `estimate`} (`estimate` is written by step 2, not here).
- Typology → basis: `dies_natalis` → `death`, `depositio` → `deposition`, `translatio` → `translation`, `dedicatio` → `dedication`; `celebratio`, `commemoratio`, `ordinatio` → no basis.
- Precedence: curated (a curated `null` removes the date) > wikidata > edition.
- Edition years: 1630 (`martyrologium_romanum_1630`), 1914 (`martyrologium_romanum_1914_en_unofficial`); the oldest wins. (Ruled in Task 3: the `martyrologium_romanum_1749` folder is a 1913 printing with later additions and bounds nothing.)
- A date never has both `year` and `from`/`to`; `from`/`to` may each be absent (open bound), never both.
- Key order in a date: `year`, `from`, `to`, `circa`, `basis`, `source`, `note`.
- The registry markdown (`registry/*.md`) is unchanged; only `data/martyrology_ids.json` gains `date`.
- Edition-bound files store only ID → year, never text.

## Review Focus

1. A person with a death date who is one of several, where the others have none: the date comes from the dated ones only (Task 1 test `test_some_persons_undated`).
2. A person item whose QID has no entry in `person_details.json` (details not refreshed after `build_person_items.py apply`): skipped, not a crash (Task 1 test `test_item_without_details`).
3. A `same_eulogy` link to a deprecated cross-day ID that only a 1749 edition prints: the bound is 1749 (Task 2 test `test_bound_through_deprecated_twin`).
4. A curated date for an ID that is no longer current (renamed): the run fails naming it, as `ENTRY_NOTES` does (Task 3 test `test_curated_unknown_id_fails`).
5. BC century precision and a circa death: −100…−1 for the 1st century BC; `circa: true` kept (Task 1 tests `test_bc_century`, `test_circa_kept`).

---

### Task 1: Dates from death dates, with ranges and basis

**Files:**
- Create: `scripts/extract_dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Produces:
  - `BASIS_OF_TYPOLOGY: dict[str, str]` (the mapping above).
  - `life_range(died: dict) -> tuple[int, int, bool]` — `died` is a `person_details` `died` value (`{"year", "precision": "year"|"decade"|"century", "circa"}`); returns `(first, last, circa)`. Decade: `year` to `year + 9`. Century: n = ceil(|year| / 100); AD: `100(n−1)+1` to `100n`; BC: `−100n` to `−100(n−1)−1`.
  - `death_date(persons: list[dict], items: dict, details: dict) -> dict | None` — `persons` is the eulogy's list from `persons.json`, `items` its dict from `person_items.json` (keyed by `persons_text.person_key`), `details` the whole `person_details.json`. Returns `{"year"} | {"from","to"}` plus `"circa": True` when any contributing date is circa, or `None`. Several ranges: `from` = min of firsts, `to` = max of lasts; collapses to `year` when first == last.
  - `with_basis(date: dict, typology: str | None) -> dict` — adds `basis` from `BASIS_OF_TYPOLOGY` unless the date already has one; returns a date in the key order above.

- [ ] **Step 1: Write the failing tests** in `tests/test_dates.py` (class `DeathDateTest`), using small inline fixtures:
  - `test_year_precision`: one person, died `{"year": 304, "precision": "year", "circa": False}` → `{"year": 304}`.
  - `test_decade`: 1930 decade → `{"from": 1930, "to": 1939}`.
  - `test_ad_century`: year 400 century → `{"from": 301, "to": 400}`; year 1401 century → `{"from": 1401, "to": 1500}`.
  - `test_bc_century`: year −100 century → `{"from": -100, "to": -1}`.
  - `test_circa_kept`: circa year 250 → `{"year": 250, "circa": True}`.
  - `test_several_persons_range`: deaths 304 and 310 → `{"from": 304, "to": 310}`.
  - `test_some_persons_undated`: two persons, one with no item → the other's year.
  - `test_item_without_details`: item QID missing from details → `None`.
  - `test_repeated_name_key`: persons `Felix` and `Felix` with `n: 2`; items keyed `Felix` and `Felix#2` → both used.
  - `test_basis_from_typology`: `with_basis({"year": 304}, "depositio")` → `{"year": 304, "basis": "deposition"}`; `"commemoratio"` → no `basis`; an existing `basis` is kept.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_dates -v` — Expected: FAIL (`ModuleNotFoundError: extract_dates`).

- [ ] **Step 3: Implement** the four names above in `scripts/extract_dates.py` (module docstring in the style of the other generators: what it reads, writes, usage).

- [ ] **Step 4: Run** `python3 -m unittest tests.test_dates -v` — Expected: PASS.

- [ ] **Step 5: Commit** `git add scripts/extract_dates.py tests/test_dates.py && git commit -m "dates: a eulogy's date from its subjects' death dates"`

### Task 2: Edition bounds

**Files:**
- Modify: `scripts/extract_dates.py`
- Create: `data/edition_bounds.json` (generated)
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: the registry's current entries (`data/martyrology_ids.json`, with `same_eulogy`).
- Produces:
  - `EDITION_YEARS = (("martyrologium_romanum_1630", 1630), ("martyrologium_romanum_1749", 1749), ("martyrologium_romanum_1914_en_unofficial", 1914))`.
  - `edition_keys(api_root: Path) -> dict[str, set[str]]` — the IDs of each edition's `data/editions/<edition>/*.json` (month files; day values are `{"elogia": {id: text}}`, other top-level values are skipped).
  - `edition_bounds(entries: list[dict], keys: dict[str, set[str]]) -> dict[str, int]` — for each current entry, the year of the oldest edition whose keys contain its ID or one of its `same_eulogy` IDs.
  - CLI `python3 scripts/extract_dates.py bounds /path/to/martyrology-api [repo_root]` writes `data/edition_bounds.json` = `{"$comment": ..., "bounds": {id: year}}` sorted by ID, `indent=1`.

- [ ] **Step 1: Write the failing tests** (class `EditionBoundsTest`): `test_oldest_edition_wins` (ID in 1749 and 1630 → 1630); `test_bound_through_deprecated_twin` (ID absent everywhere, its `same_eulogy` deprecated ID in 1749 → 1749); `test_absent_everywhere` (no key); `test_edition_keys_skips_non_day_values` (a temp month file with a string top-level value and one day → that day's IDs).
- [ ] **Step 2: Run** them — Expected: FAIL.
- [ ] **Step 3: Implement** the names above and the `bounds` subcommand.
- [ ] **Step 4: Run** the tests — Expected: PASS. Then `python3 scripts/extract_dates.py bounds ../martyrology-api` — Expected: about 1,945 bounds (1,710 at 1630, 231 at 1749, 4 at 1914; the measurement of 2026-10-22).
- [ ] **Step 5: Commit** the script, the test and `data/edition_bounds.json`: `"dates: edition bounds from the 1630, 1749 and 1914 editions"`.

### Task 3: `data/dates.json`, curated dates, checks, report

**Files:**
- Modify: `scripts/extract_dates.py`
- Create: `data/dates_curated.json`, `data/dates.json` (generated), `docs/dates-report.md` (generated)
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: Tasks 1–2; `data/typology.json` (`["typology"]`), `data/persons.json` (`["editions"]["martyrologium_romanum_2004"]`), `data/person_items.json` (`["persons"]`), `data/person_details.json`.
- Produces:
  - `build_dates(current_ids: set[str], typology: dict, persons: dict, items: dict, details: dict, bounds: dict, curated: dict) -> dict[str, dict]` — per the precedence; `source` set to `curated` / `wikidata` / `edition` (an edition date is `{"to": bound}`); basis via `with_basis` (a curated date's own `basis` wins). Raises `ValueError` naming curated IDs not in `current_ids`.
  - `checks(dates: dict, wikidata_dates: dict, bounds: dict) -> dict[str, list]` — `"after_bound"`: IDs whose wikidata date's latest year (`year` or `to`) > its bound, as `(id, year, bound)`; `"wide"`: wikidata ranges with `to − from > 300`, as `(id, from, to)`. `wikidata_dates` is the death date computed before precedence, so a curated override does not hide a check.
  - `data/dates_curated.json` = `{"$comment": ..., "dates": {"mr:0101-maria-dei-genetrix": {"year": 431, "basis": "event", "note": "Council of Ephesus"}}}`.
  - `data/dates.json` = `{"$comment": ..., "dates": {id: date}}` sorted by ID, `indent=1`.
  - `docs/dates-report.md`: counts by source and by basis; the two check lists; the undated `celebratio` and `commemoratio` IDs (IDs only) as curation candidates.
  - CLI `python3 scripts/extract_dates.py [--check] [repo_root]`; `--check` returns 1 when `data/dates.json` or the report differs from what it would write (same pattern as `registry_places.main`).

- [ ] **Step 1: Write the failing tests** (class `BuildDatesTest`): `test_curated_wins` (curated 431 over a death date); `test_curated_null_removes`; `test_wikidata_over_edition`; `test_edition_only` → `{"to": 1630, "basis": "death", "source": "edition"}` for a `dies_natalis`; `test_curated_unknown_id_fails`; `test_after_bound_check` (death 1700, bound 1630 → listed); `test_wide_check` (304 and 900 → listed); `test_check_sees_curated_overridden` (curated date over a death date of 1700 with bound 1630 → still in `after_bound`); `test_committed_dates_are_current` (`main(["--check", ROOT]) == 0`).
- [ ] **Step 2: Run** them — Expected: FAIL.
- [ ] **Step 3: Implement**, create `data/dates_curated.json`, run `python3 scripts/extract_dates.py`. Expected output counts close to: wikidata 904, edition ≈1,530, curated 1; the `after_bound` list ≈7.
- [ ] **Step 4: Run** `python3 -m unittest tests.test_dates -v` — Expected: PASS.
- [ ] **Step 5: Commit** script, test, `data/dates_curated.json`, `data/dates.json`, `docs/dates-report.md`: `"dates: data/dates.json with curated dates, checks and a report"`.

### Task 4: The registry's `date` key, docs

**Files:**
- Modify: `scripts/extract_registry.py` (`KEY_ORDER`, `build`, a `load_dates` / `add_dates` pair beside `load_places` / `add_places`, the `write_json` `$comment`)
- Modify: `tests/test_registry.py` (`REGISTRY_INPUTS` gains `data/dates.json`)
- Modify: `data/martyrology_ids.json`, `AGENTS.md`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `data/dates.json` (Task 3).
- Produces: `KEY_ORDER` with `"date"` right after `"places"`; `load_dates(repo_root, current_ids) -> dict` (missing file → `{}`; IDs not current → assertion with `RECOVERY`); `add_dates(entries, dates) -> list` (sets or removes `date`, via `with_key`).

- [ ] **Step 1: Write the failing tests** in `tests/test_registry.py`: `test_add_dates_inserts_after_places` (entry with `places` gets `date` after it); `test_add_dates_removes_stale` (an entry with a `date` not in dates loses it); `test_dates_with_unknown_id_fail` (load_dates on a temp root with a non-current ID raises `AssertionError`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_registry -v` — Expected: FAIL.
- [ ] **Step 3: Implement**; in `build`, `add_dates` runs after `add_places` and before `registry_places.apply`. The `$comment` gains one sentence: each current entry's optional `date` comes from `data/dates.json` (scripts/extract_dates.py). Run `python3 scripts/extract_registry.py`.
- [ ] **Step 4: Run** the whole suite `python3 -m unittest discover -s tests` — Expected: all pass (969 before this plan, plus the new tests). `registry/*.md` must be unchanged: `git diff --stat registry/` empty.
- [ ] **Step 5: AGENTS.md**: add a pipeline item for `scripts/extract_dates.py` after `person_details.py` (what it reads and writes, `bounds` reads martyrology-api, rerun after `build_person_items.py apply` + `person_details.py`, or an edit of `data/dates_curated.json`, then `extract_registry.py`); add `data/dates_curated.json` to *Where hand-corrections live*.
- [ ] **Step 6: Commit** `git add scripts/extract_registry.py tests/test_registry.py data/martyrology_ids.json AGENTS.md && git commit -m "registry: each current eulogy's optional date"`
