# Subject identity: places as evidence — Implementation Plan (crmedr)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the subject cards the eulogy's places as evidence (place agreement, a place route, one genitive per place item), add the subject rename as its own operation, and rebuild January's undecided cards, then February.

**Architecture:** A new `scripts/eulogy_places.py` resolves each eulogy's printed places to gazetteer items. `build_person_items.py` annotates each candidate with its place agreement after the evidence bar has ranked it (order and auto untouched), and `expand` gains a place route through a new `Wikidata.saints_by_place`. `rename_candidates.py` mines a QID-keyed genitive map from the current IDs and writes a `relabel` op beside each `rename`; `subject_jev.py`/`suggest_subjects.py` ask Jev about it and gain a `prefill` step; `apply_renames.py` applies `relabel`; `scripts/subject_month.py merge` rebuilds a month keeping its decisions.

**Tech Stack:** Python 3.12 stdlib, `unittest`; Wikidata API and SPARQL through `scripts/wikidata.py` (cached in `.cache/wikidata/`); TypeSafe Jev through `scripts/subject_jev.py`.

**Spec:** `docs/superpowers/specs/2026-10-25-subject-identity-places-design.md` (addendum to `docs/superpowers/specs/2026-10-18-subject-identity-design.md`). The frontend half is `martyrology-frontend/docs/superpowers/plans/2026-10-25-subject-identity-places-cards.md`.

## Global Constraints

- The auto bar is unchanged: `_required(person)` stays `["human", "status", "name"] + (["death"] if dies_natalis)`; `place` is never required.
- The candidate order is unchanged by place agreement: `place` is added after `evaluate` has sorted, and never re-sorts.
- Place properties: P19 `birth_place`, P20 `death_place`, P119 `burial_place`, P937 `work_places`, read with `current_qids` (no deprecated rank, no P582 end).
- Agreement: same item, or one P131 step either way (from `Wikidata.items(...)[qid]["admin_qids"]`).
- Genitive certainty: certain only with ≥ 2 current IDs giving it and none giving another; `PLACE_GENITIVES` stays the certain override.
- A decided op (`decision` not None) or a prefilled one (`op.prefilled`) is never rewritten by any step.
- Briefs, records and month change-sets quote the 2004 text: written only outside a git tree (`~/private-changesets/subject-identity/MM/`), never committed.
- Standard library only; tests run with `python3 -m unittest discover -s tests` (currently 1,079, all OK).

## Review Focus

1. `make_op` and `expand` recompute `evidence` for carried-over candidates, which would drop `place`: the annotation must run last and be idempotent (Task 3 test `test_annotate_twice_and_after_recompute`).
2. A scoped gazetteer key (`phrase@mrid`) and an unresolved phrase (`wikidata: null`): resolved per eulogy, unresolved left out (Task 2 test `test_scoped_and_unresolved`).
3. Rome-sized places: the place query returns hundreds of saints; it must add nothing and not fail (Task 4 test `test_too_many_saints_adds_nothing`).
4. A January eulogy with a decided `rename` (labels on its candidate) and a new undecided `relabel`: applying must keep the rename's labels until the relabel is decided (Task 7 test `test_undecided_relabel_keeps_rename_labels`).
5. A rebuilt month missing an old undecided op's ID (the person left `persons.json`): merge drops it and says so; a missing *decided* op is an error (Task 9 test `test_missing_ids`).

---

### Task 1: Person summaries read their places

**Files:**
- Modify: `scripts/wikidata.py` (`summarize_person`, l.~227)
- Test: `tests/test_person_items.py` (`SummarizePersonTest`)

**Interfaces:**
- Produces: `summarize_person(raw)` gains keys `birth_place`, `death_place`, `burial_place`, `work_places`: `list[str]` of QIDs (empty when none).

- [ ] **Step 1: Write the failing test** `test_places_current_only`: an entity with P20 `Q490` (normal), P20 `Q220` (deprecated), P119 `Q1` with a P582 qualifier, P19 `Q2`, P937 `Q3` and `Q4` gives `death_place == ["Q490"]`, `burial_place == []`, `birth_place == ["Q2"]`, `work_places == ["Q3", "Q4"]`. Build the claims with the file's `item()` helper style (rank and qualifiers set on the statement dict).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_person_items -k places_current` — Expected: FAIL (KeyError `death_place`).
- [ ] **Step 3: Implement** the four keys with `current_qids(claims, "P19")` etc.
- [ ] **Step 4: Run** the test file — Expected: OK.
- [ ] **Step 5: Commit** `wikidata: person summaries read P19, P20, P119, P937`.

### Task 2: The eulogy's places as items

**Files:**
- Create: `scripts/eulogy_places.py`
- Modify: `scripts/subject_records.py` (`brief`: each eulogy gains `places`)
- Test: `tests/test_eulogy_places.py`, `tests/test_subject_records.py`

**Interfaces:**
- Consumes: `gazetteer_text.lookup(gazetteer, la, mrid)`.
- Produces: `eulogy_places(places_doc: dict, gazetteer: dict) -> dict[str, list[dict]]`, `{mrid: [{"role", "la", "qid", "label"}]}` in `places_doc` order, one entry per (role, qid); `load(repo_root) -> dict[str, list[dict]]` reading `data/places.json` and `data/gazetteer.json`.

- [ ] **Step 1: Write the failing tests:** `test_resolved_in_order` (two places, death then burial, resolved to `Q490`, `Q220`, labels from the gazetteer); `test_scoped_and_unresolved` (a `"In ecclesia@mr:0101-x"` gazetteer key wins over the bare phrase for `mr:0101-x`; a phrase whose entry has `wikidata: None` is left out; a phrase with no entry is left out); `test_one_per_role_and_item` (the same role and item twice gives one entry); `test_sites_are_not_the_item` (an entry with `sites` contributes only its `wikidata`); in `test_subject_records.py`, `test_brief_lists_place_items` (a brief eulogy carries `places: [{"role", "la", "qid", "label"}]`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_eulogy_places` — Expected: ImportError.
- [ ] **Step 3: Implement** `eulogy_places` and `load`; `brief(...)` gains a `places` argument (the `eulogy_places` map) and writes each eulogy's list.
- [ ] **Step 4: Run** — Expected: OK.
- [ ] **Step 5: Commit** `eulogy places: each eulogy's printed places as gazetteer items`.

### Task 3: Place agreement on the person cards

**Files:**
- Modify: `scripts/build_person_items.py` (new constants and functions; `main` calls them after `propose` and after `expand`)
- Test: `tests/test_person_items.py` (new `PlaceAgreementTest`)

**Interfaces:**
- Consumes: Task 1 keys; Task 2 `eulogy_places.load(repo_root)`; `client.items(qids) -> {qid: {"admin_qids": [...], "label": ...}}`.
- Produces:
  - `ROLE_PROPS = {"death": ("death_place", "burial_place"), "burial": ("burial_place", "death_place"), "translation": ("burial_place", "death_place"), "birth": ("birth_place",), "ministry": ("work_places", "death_place"), "religious_life": ("work_places", "death_place"), "foundation": ("work_places", "death_place")}`; `VIA = {"death_place": "P20", "burial_place": "P119", "birth_place": "P19", "work_places": "P937"}`.
  - `place_agreement(places: list[dict], c: dict, admin: dict[str, list[str]]) -> list[dict]`: `[{"role", "qid", "label", "via"}]`, the eulogy place's qid and label, the first property of the role's tuple that agrees.
  - `annotate_places(ops: list[dict], by_eulogy: dict[str, list[dict]], client) -> None`: sets `op["places"] = [{"role", "label", "qid"}]` and, per candidate, `c["places"]` (empty list when none) and `"place"` in `c["evidence"]` exactly when `c["places"]` is non-empty, appended last; also `c["place_labels"] = {"death_place": [labels], …}` for non-empty properties (labels from `client.items`). One `client.items` call for every QID involved; a `WikidataError` leaves the ops un-annotated and is reported like `not_processed`.

- [ ] **Step 1: Write the failing tests** with a `FakeClient.items` returning `admin_qids`:
  - `test_same_item` (eulogy death `Q490`, candidate `death_place ["Q490"]` → `[{"role": "death", "qid": "Q490", "label": "Bologna", "via": "P20"}]`);
  - `test_one_step_either_way` (candidate P20 a hermitage whose `admin_qids` holds `Q490`; and eulogy place a hermitage inside the candidate's P20 town) both agree; two steps apart does not;
  - `test_role_outside_table` (eulogy role `mention`, candidate P20 equal) → `[]`;
  - `test_order_and_auto_unchanged`: an `evaluate` result with `auto` set and candidates `[A, B]`, B agreeing and A not, keeps `auto` and the order `[A, B]` after `annotate_places`; a non-auto op stays non-auto;
  - `test_annotate_twice_and_after_recompute`: annotating twice gives the same op; recomputing `evidence(person, c)` (which drops `place`) then annotating restores it.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_person_items -k Place` — Expected: FAIL (NameError).
- [ ] **Step 3: Implement** `place_agreement` and `annotate_places`; in `main`, load `eulogy_places.load(repo_root)` and call `annotate_places(review["operations"], ...)` after `propose`, `expand` and `verify-suggestions`, before `validate`.
- [ ] **Step 4: Run** the whole suite — Expected: OK, 1,079 + new.
- [ ] **Step 5: Commit** `person items: place agreement on each candidate, shown, not counted`.

### Task 4: The place route

**Files:**
- Modify: `scripts/wikidata.py` (new `saints_by_place`), `scripts/build_person_items.py` (`_expansion`)
- Test: `tests/test_wikidata_expand.py`, `tests/test_person_items.py` (`ExpandTest`)

**Interfaces:**
- Consumes: Task 2 places: `expand(review, items, records, client, places=None)` gains `places: dict[str, list[dict]]` (from `eulogy_places.load`, passed by `main`), and `_expansion(op, record, items, client, ops=None, places=())` receives the op's eulogy's list.
- Produces: `Wikidata.saints_by_place(qids: list[str], given: list[str], matches=None) -> list[dict]`, summaries tagged `source: "place"`, at most `MAX_SPARQL`; `MAX_PLACE_SAINTS = 200`: when the query returns more distinct persons than this, it returns `[]`.

- [ ] **Step 1: Write the failing tests:** `test_saints_by_place` (Fake SPARQL rows for two saints with P20 the place, one matching the given name → only that one, `source == "place"`); `test_too_many_saints_adds_nothing` (201 distinct persons → `[]`, no error); `ExpandTest.test_place_route` (an op whose eulogy has a death place gets a `source: "place"` candidate appended after the existing ones, evidence computed).
- [ ] **Step 2: Run** the two test files — Expected: FAIL (AttributeError).
- [ ] **Step 3: Implement** `saints_by_place` (SPARQL: `VALUES ?place {…}`, `?p wdt:P31 wd:Q5; wdt:P411 ?s; (wdt:P20|wdt:P119) ?place`, labels in `NAME_LANGS`; names filtered in Python as `saints_by_death_day` does) and call it in `_expansion` for the eulogy's places with role `death`, `burial` or `translation`, after the death-day route.
- [ ] **Step 4: Run** the suite — Expected: OK.
- [ ] **Step 5: Commit** `person items: a place route for candidates`.

### Task 5: Jev sees the places

**Files:**
- Modify: `scripts/subject_jev.py` (`_person_candidate`, `person_request`)
- Test: `tests/test_subject_jev.py` (`PersonRequestTest`)

**Interfaces:**
- Consumes: `op["places"]`, `c["places"]`, `c["place_labels"]` (Task 3).
- Produces: person request `state["places"] = [{"role", "label"}]`; each `state["candidates"][qN]` gains `places` (the agreement, without `qid`) and `place_labels`.

- [ ] **Step 1: Write the failing test** `test_places_in_state`: an op with places and a candidate with agreement → both present in the request state; an op without `places` → `state["places"] == []`, candidates without the keys sent as empty.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_subject_jev` — Expected: FAIL.
- [ ] **Step 3: Implement.** The questions do not change.
- [ ] **Step 4: Run** — Expected: OK.
- [ ] **Step 5: Commit** `jev: the eulogy's places and each candidate's in the person request`.

### Task 6: One genitive per place item

**Files:**
- Modify: `scripts/rename_candidates.py` (`genitive_slug`, `_build`, `load_context`, `main`)
- Create: `docs/rename-genitives-report.md` (generated)
- Test: `tests/test_rename_candidates.py` (new `GenitiveMapTest`)

**Interfaces:**
- Consumes: Task 2 `eulogy_places`.
- Produces:
  - `mine_genitives(entries: list[dict], places: dict[str, list[dict]]) -> dict[str, Counter]`: for each current entry and each of its places, the ID slug's last k tokens (k = 3, 2, 1, the first that matches) equal to `slug` of the first k words of the place's `la` with `æ` → `ae`; `{qid: Counter(genitive)}`.
  - `certain_genitives(mined) -> tuple[dict[str, str], dict[str, list[str]]]`: `(certain, conflicts)`; certain = one genitive given by ≥ 2 IDs; conflicts = items with two or more genitives (sorted).
  - `link_places(record: dict, places: list[dict]) -> dict`: a copy of the record whose `places[i]` gain `qid` when the folded `printed` is contained in one place's folded `la`.
  - `genitive_slug(place, certain=None)`: `PLACE_GENITIVES` first (certain), then `certain[place["qid"]]` (certain), then the record's genitive, then the locative (uncertain), as now.
  - `Context` gains `genitives: dict[str, str]`; `load_context` fills it; `main` writes the report (items with their genitives and counts, the conflicts first).

- [ ] **Step 1: Write the failing tests:** `test_mined_from_ids` (`mr:0101-a-bononiae`, `mr:0202-b-bononiae` with places `Bonóniæ` → `Q1891`: `{"Q1891": Counter({"bononiae": 2})}`); `test_one_id_is_not_certain`; `test_two_genitives_conflict` (`romae` ×2 and `urbis` ×1 for one item → not certain, listed); `test_certain_from_map` (`genitive_slug({"qid": "Q1891", ...}, {"Q1891": "bononiae"}) == ("bononiae", True)`); `test_override_wins` (`PLACE_GENITIVES`); `test_link_places` (printed `Bonóniæ` in `In urbe Bonóniæ` → `qid`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_rename_candidates -k Genitive` — Expected: FAIL.
- [ ] **Step 3: Implement**; `_build` links the record's places before choosing the primary place.
- [ ] **Step 4: Run** the suite — Expected: OK. Then `python3 scripts/rename_candidates.py` as its `main` documents, on January's records, and read the report's head (conflicts) — Expected: a report written, no exception.
- [ ] **Step 5: Commit** `renames: one genitive per place item, mined from the IDs`.

### Task 7: The subject rename (`relabel`)

**Files:**
- Modify: `scripts/rename_candidates.py` (`build_changeset`), `scripts/apply_renames.py` (`renames`, new `relabels`, `_write_labels`), `scripts/subject_jev.py` (new `relabel_request`, `relabel_suggestion`), `scripts/suggest_subjects.py` (`request_for`, `ask_op`, `in_scope`)
- Test: `tests/test_rename_candidates.py`, `tests/test_apply_renames.py`, `tests/test_subject_jev.py`, `tests/test_suggest_subjects.py`

**Interfaces:**
- Produces:
  - The op: `{"op": "relabel", "id": mrid, "uid": "labels:" + mrid, "current": {"la", "en", "it"}, "labels": candidates[0]["labels"], "candidates": [{"labels": {...}, "from_id": new_id}] (one per distinct label set of the rename candidates, the current labels last with "from_id": null), "decision": None, "edited": None}`, written right after its eulogy's `rename`.
  - Decisions: `accept` → `op["labels"]`; `edit` → `edited["labels"]` (all three); `reject` → keep the current labels.
  - `apply_renames.relabels(changeset) -> dict[str, dict]`: `{mrid: labels}` of the decided relabels; `renames()` takes a decided relabel's labels for its eulogy, else the rename candidate's (today's behaviour); a relabel with no rename writes labels under the current ID.
  - `relabel_request(op, record, la_clause, vernacular)` (a `clarity_*` Score per candidate and a `pick` Choice, the rename request's wording with "subject" for "ID"); `relabel_suggestion(op, answers) -> dict` like `rename_suggestion` (`edited` holds the picked labels).

- [ ] **Step 1: Write the failing tests:** `test_relabel_after_rename` (build_changeset writes a relabel after each rename, current labels last); `test_relabel_overrides`; `test_relabel_without_rename` (labels set under the current ID); `test_reject_keeps_current`; `test_undecided_relabel_keeps_rename_labels`; `test_relabel_request_and_suggestion`; `test_suggest_asks_relabel`.
- [ ] **Step 2: Run** the four test files — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite — Expected: OK.
- [ ] **Step 5: Commit** `subject identity: the subject rename as its own operation (relabel)`.

### Task 8: Prefill as a step

**Files:**
- Modify: `scripts/suggest_subjects.py` (new `prefill` command and `prefill_ops`)
- Test: `tests/test_suggest_subjects.py` (new `PrefillTest`)

**Interfaces:**
- Produces: `prefill_ops(ops: list[dict], threshold: float = 0.9) -> dict[str, int]` (counts by kind); `PREFILL_ORDER = ("twin", "papa", "surname", "epithet", "place-adjective", "place-genitive")`. Rules, never on an op with `decision` set:
  - `rename`: the candidate of the first category of `PREFILL_ORDER` present, only when exactly one candidate has it, it is not `weak` (a `place-genitive` need not be `certain`, as in the curator's January practice) → `decision "accept"` if it is `new_id`, else `"edit"` with `edited.new_id`; `prefilled: "rule"`.
  - `resolve_person`: `jev.probability >= threshold`, decision accept or edit, the item a candidate with `human` and `status` evidence → the Jev decision; `prefilled: "jev"`.
  - `relabel`: `jev.probability >= threshold` → its decision; `prefilled: "jev"`.
- CLI: `suggest_subjects.py prefill <changeset.json> [--threshold X]`, path outside a git tree.

- [ ] **Step 1: Write the failing tests:** one per rule, plus `test_decided_untouched` and `test_weak_or_uncertain_not_prefilled`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite — Expected: OK.
- [ ] **Step 5: Commit** `suggest subjects: prefill as a script step`.

### Task 9: Rebuild a month, keeping its decisions

**Files:**
- Create: `scripts/subject_month.py`
- Test: `tests/test_subject_month.py`

**Interfaces:**
- Produces: `merge(old: dict, rebuilt: dict) -> tuple[dict, list[str]]`: ops keyed by `uid` (else `id`); an old op with `decision` not None or `prefilled` is kept as it was; every other op is the rebuilt one; rebuilt ops new to the month are appended in the rebuilt order; an old undecided op absent from the rebuilt file is dropped and named in the returned notes; an old decided op absent from it raises `ValueError`. CLI: `subject_month.py merge <old.json> <rebuilt.json> <out.json>` (outside a git tree), printing the counts and notes.

- [ ] **Step 1: Write the failing tests:** `test_decided_and_prefilled_kept` (byte-equal as JSON); `test_undecided_rebuilt`; `test_new_ops_appended`; `test_missing_ids` (undecided dropped with a note; decided → ValueError).
- [ ] **Step 2: Run** — Expected: ImportError.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite — Expected: OK.
- [ ] **Step 5: Commit** `subject month: rebuild a month's cards, keeping its decisions`.

---

## Runbook (after the tasks, with the curator)

January (`MM=01`), in `~/private-changesets/subject-identity/01/`:

1. `python3 scripts/build_person_items.py propose` (repo), then `expand records-01.json`, then `export 01 persons-01.json` (after `expand`, so the export carries the expanded and annotated cards); the annotation runs inside `propose` and `expand` (retry on Wikidata lag per the maxlag routine).
2. `python3 scripts/rename_candidates.py …` on `records-01.json` → `renames-01.json` (renames and relabels; a relabel carries the Wikidata `hint` when its eulogy has one person with a decided item, the labels fetched in one call; a Wikidata failure only leaves the hints out, with a warning).
3. Combine as January was combined (renames, relabels, persons, by eulogy) → `rebuilt-01.json`, without Jev yet.
4. `subject_month.py merge crmedr-subjects-01.json rebuilt-01.json crmedr-subjects-01.v3.json` (relabels are merged as any op: the subject follows the decided ID at apply and on the card); check: every op ID of the old file present unless named in the notes. Then `suggest_subjects.py suggest crmedr-subjects-01.v3.json records-01.json <texts> --min-confidence 0` (without `--persons`, so renames get Jev too; relabels are never asked, Jev's rename pick chooses the pairing; decided and prefilled cards are skipped), and only then `suggest_subjects.py prefill crmedr-subjects-01.v3.json` (renames by rule, persons by Jev; a relabel is never prefilled). Jev is asked after the merge, never before.
5. Back up the server copy, upload as `crmedr-subjects-01.json` (curator runs the `sudo install`), and drop `persons-review-01` from the public bundles (frontend plan, Task F1).

February: `subject_records.py brief 02a|02b`, research agents write `records-02.json` (the brief now lists each eulogy's place items), `subject_records.py check`, then steps 1–3 with `MM=02`, `suggest` on the combined file as in step 4 (no merge), `prefill`, and step 5: upload `crmedr-subjects-02.json`. After the curator decides February: `suggest_subjects.py evaluate`, then March to December.
