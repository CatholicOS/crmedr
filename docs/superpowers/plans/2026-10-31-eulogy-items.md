# Eulogy Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the eulogies that do not commemorate a single person (groups, feasts, dedications, translations) an optional Wikidata item for what they commemorate as a whole, and show it on romanmartyrology.com.

**Architecture:** A curated `data/eulogy_items.json` in crmedr. It is validated and reported by a new `scripts/build_eulogy_items.py`, which also suggests group items from the persons' Wikidata statements and checks them with Jev. `extract_registry.py` copies it onto the registry entry as `item`. martyrology-api serves `item` on `EulogyOut`. martyrology-frontend carries it in its registry snapshot and shows a labelled Wikidata link. The Joseph the Worker rename and the Marian title links go first, as data work through the existing tools.

**Tech Stack:** Python 3 stdlib + unittest (crmedr), FastAPI + pydantic + pytest (martyrology-api), Next.js + next-intl + vitest (martyrology-frontend), TypeSafe Jev (`scripts/mentions_jev.py`), Wikidata (`scripts/wikidata.py`).

**Spec:** `docs/superpowers/specs/2026-10-31-eulogy-items-design.md` (approved by the curator, PR #247).

## Global Constraints

- Items only for current eulogy IDs; deprecated IDs and `same_eulogy` twins inherit nothing.
- A person is commemorated unless `data/persons.json` (Latin edition `martyrologium_romanum_2004`) gives it `"role": "mentioned"`. Each person entry counts once.
- Single-person: exactly one commemorated person and typology not in `celebratio`, `dedicatio`, `translatio`. These get no item unless the entry has a curator `note`.
- `kind` ∈ `group`, `feast`, `dedication`, `translation`. `status` ∈ `auto`, `reviewed`, `unresolved`. `unresolved`, and the "the mention links the title" decision, carry `wikidata: null` and a `note`.
- Group suggestion: an item that two or more of the commemorated persons, and at least half of them, reach by P361 or P463.
- Nothing becomes `reviewed` without research by a person or by Claude with sources, as in the person audit.
- Marian title mentions link the title or apparition item, never Q345. Their eulogies get no eulogy item.
- Wikidata: maxlag=5 with retry, never raised. Merge only high-confidence duplicates. Never `git add` all of `data/` or `docs/`.
- Edition texts are immutable.
- Every crmedr PR gets a CodeRabbit round. The API and frontend PRs merge without waiting. Ask before merging a PR the curator did not request, and before an API release.
- Repo order for the rename and for the release: martyrology-texts, crmedr, martyrology-api (pin), martyrology-frontend (snapshot).

## Review Focus

1. A group whose item lists its members only by P527 (the persons' items lack P361/P463): the membership check must not flag them. Pinned in Task 3.
2. A eulogy whose persons split evenly between two candidate groups: no suggestion, not an arbitrary pick. Pinned in Task 3.
3. Persons with no item, or `wikidata: null`: ignored by the suggestion and the check, not counted as non-members. Pinned in Task 3.
4. An ID in `data/eulogy_items.json` that was renamed or deprecated: `check` fails, naming the ID. Pinned in Task 2.
5. A snapshot entry without `item` (every single-person eulogy): the frontend renders no link and no empty label. Pinned in Task 6.

---

### Task 1: Rename `mr:0501-ioseph-sponsus-mariae` → `mr:0501-ioseph-opifex`

**Files:**
- Create: `~/private-changesets/eulogy-items/rename-0501.decided.json` (private; quotes no 2004 text)
- Modify (by the tool): martyrology-texts editions keys; crmedr `data/*.json`, `i18n/*.json`; then the API pin and the frontend snapshot.

**Interfaces:**
- Consumes: `scripts/apply_renames.py texts|crmedr <decided.json>` (crmedr-changeset/v1).
- Produces: current ID `mr:0501-ioseph-opifex`, used by Task 5.

- [ ] **Step 1:** Write the decided change-set: `{"schema": "crmedr-changeset/v1", "operations": [{"op": "rename", "id": "mr:0501-ioseph-sponsus-mariae", "new_id": "mr:0501-ioseph-opifex", "decision": "accept", "candidates": [{"new_id": "mr:0501-ioseph-opifex", "labels": {"la": "Sanctus Ioseph Opifex", "en": "Saint Joseph the Worker", "it": "San Giuseppe lavoratore"}}]}]}`. The subjects stay as they are.
- [ ] **Step 2:** Dry-run both sides: `python3 scripts/apply_renames.py texts <file> ../martyrology-texts --dry-run` and `python3 scripts/apply_renames.py crmedr <file> --dry-run`. Expected: one rename each, no errors.
- [ ] **Step 3:** Apply to texts on a branch, run its `tests/test_registry_keys.py`, and open the texts PR.
- [ ] **Step 4:** Apply to crmedr on a branch with `--regenerate ../martyrology-texts`. Then `pytest`; expected: all pass. `grep -rn ioseph-sponsus-mariae data i18n` should list only `mr:0319-ioseph-sponsus-mariae`. Open the crmedr PR and run its CodeRabbit round.
- [ ] **Step 5:** After both merge, open the API pin PR (`vendor/crmedr`, `vendor/texts`) and the frontend snapshot PR (`npm run snapshot-registry`). Ask the curator before the API release.

### Task 2: `data/eulogy_items.json`, its rules and its check

**Files:**
- Create: `scripts/build_eulogy_items.py`, `data/eulogy_items.json`, `tests/test_eulogy_items.py`
- Modify: `AGENTS.md` (a numbered step after `build_person_items.py`, in its style)

**Interfaces:**
- Produces:
  - `HAND_TYPOLOGIES = ("celebratio", "dedicatio", "translatio")`
  - `KINDS = ("group", "feast", "dedication", "translation")`
  - `STATUSES = ("auto", "reviewed", "unresolved")`
  - `ITEMS = Path("data/eulogy_items.json")`, shape `{"$comment": str, "items": {mrid: {"wikidata": str|None, "kind": str|None, "status": str, "note"?: str}}}`
  - `commemorated(persons: list[dict]) -> list[dict]`
  - `eulogy_class(persons: list[dict], typology: str|None) -> str`, returning `"single"`, `"hand"` (none commemorated, or one under HAND_TYPOLOGIES) or `"several"`
  - `check(items: dict, current_ids: set[str], classes: dict[str, str]) -> list[str]` (error strings, each naming its ID)
  - `load(repo_root) -> dict` (the `items` map, `{}` when the file is missing)
  - CLI: `build_eulogy_items.py check [repo_root]`, exit 1 on errors

- [ ] **Step 1: Write the failing tests** in `tests/test_eulogy_items.py`:

```python
P = lambda name, **kw: {"name": name, "where": "text", **kw}

def test_classes(self):
    self.assertEqual(b.eulogy_class([P("Felix")], "dies_natalis"), "single")
    self.assertEqual(b.eulogy_class([P("Felix"), P("Willibrordus", role="mentioned")], "dies_natalis"), "single")
    self.assertEqual(b.eulogy_class([P("Ioseph")], "celebratio"), "hand")
    self.assertEqual(b.eulogy_class([], "dedicatio"), "hand")
    self.assertEqual(b.eulogy_class([P("Felix"), P("Felix", n=2)], "dies_natalis"), "several")

def test_check(self):
    ids = {"mr:0101-a", "mr:0101-b", "mr:0101-c"}
    classes = {"mr:0101-a": "single", "mr:0101-b": "several", "mr:0101-c": "hand"}
    ok = {"wikidata": "Q1", "kind": "group", "status": "reviewed"}
    self.assertEqual(b.check({"mr:0101-b": ok}, ids, classes), [])
    for items, needle in [({"mr:0101-a": ok}, "mr:0101-a"),                       # single without a note
                          ({"mr:0101-gone": ok}, "mr:0101-gone"),                  # not current
                          ({"mr:0101-b": {**ok, "kind": "title"}}, "kind"),
                          ({"mr:0101-b": {**ok, "wikidata": "X1"}}, "wikidata"),
                          ({"mr:0101-c": {"wikidata": None, "status": "unresolved"}}, "note"),
                          ({"mr:0101-b": {"wikidata": None, "kind": "group", "status": "auto"}}, "auto")]:
        with self.subTest(items=items):
            self.assertTrue(any(needle in e for e in b.check(items, ids, classes)))
    noted = {"mr:0101-a": {**ok, "note": "curator: why"}}
    self.assertEqual(b.check(noted, ids, classes), [])
    title = {"mr:0101-c": {"wikidata": None, "kind": None, "status": "reviewed", "note": "the mention links the title"}}
    self.assertEqual(b.check(title, ids, classes), [])

def test_committed_items_are_valid(self):
    self.assertEqual(b.main(["check", str(ROOT)]), 0)
```

- [ ] **Step 2:** Run `python3 -m pytest tests/test_eulogy_items.py -q`. Expected: FAIL (`No module named 'build_eulogy_items'`).
- [ ] **Step 3:** Implement the interfaces above. `check` also rejects an unknown `status`, a non-null `wikidata` that is not `Q\d+`, and `auto` without a QID. Create `data/eulogy_items.json` with `$comment` and `"items": {}`. The classes come from `data/persons.json` (Latin edition) and `data/typology.json` (`["typology"]`).
- [ ] **Step 4:** Run `python3 -m pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit `scripts/build_eulogy_items.py data/eulogy_items.json tests/test_eulogy_items.py AGENTS.md`.

### Task 3: Group suggestions, the membership check and the report

**Files:**
- Modify: `scripts/build_eulogy_items.py`, `tests/test_eulogy_items.py`
- Create: `docs/eulogy-items-report.md` (generated)

**Interfaces:**
- Consumes: Task 2's `commemorated`, `eulogy_class`, `load`. Also `wikidata.Wikidata(cache_dir)._entities(qids) -> dict[qid, raw]`, `mentions_jev.TypeSafe(api_key(), cache_dir).ask(body)`, and `mentions_jev.MODEL`.
- Produces:
  - `group_links(raw: dict) -> set[str]`: the QIDs of an item's P361 and P463
  - `suggest_group(person_qids: list[str], entities: dict) -> str | None`
  - `non_members(group_qid: str, person_qids: list[str], entities: dict) -> list[str]`
  - `report(items, classes, persons_qids, entities) -> str`
  - CLI: `propose [repo_root]` (network; writes `auto` entries only for eulogies with no entry yet); `report [repo_root]` (offline); `report --check` (run by the tests)
  - `JEV_MIN = 0.5`, tuned in Step 6

- [ ] **Step 1: Write the failing tests:**

```python
def ent(*parts, members=()):  # a raw Wikidata entity with P361 values, and P527 when given
    claims = {"P361": [{"mainsnak": {"datavalue": {"value": {"id": q}}}} for q in parts]}
    if members:
        claims["P527"] = [{"mainsnak": {"datavalue": {"value": {"id": q}}}} for q in members]
    return {"claims": claims}

def test_suggest_group(self):
    E = {"Q1": ent("G"), "Q2": ent("G"), "Q3": ent()}
    self.assertEqual(b.suggest_group(["Q1", "Q2", "Q3"], E), "G")
    self.assertIsNone(b.suggest_group(["Q1"], E))                          # one is not a group
    E2 = {"Q1": ent("G"), "Q2": ent("H"), "Q3": ent("G"), "Q4": ent("H")}
    self.assertIsNone(b.suggest_group(["Q1", "Q2", "Q3", "Q4"], E2))       # a tie suggests nothing
    self.assertIsNone(b.suggest_group(["Q1", "Q2", "Q3", "Q4", "Q5"], {**E, "Q4": ent(), "Q5": ent()}))  # 2 of 5

def test_non_members(self):
    E = {"G": ent(members=["Q2"]), "Q1": ent("G"), "Q2": ent(), "Q3": ent()}
    self.assertEqual(b.non_members("G", ["Q1", "Q2", "Q3"], E), ["Q3"])  # Q2 counts through P527

def test_persons_without_an_item_are_ignored(self):
    self.assertEqual(b.non_members("G", [], {"G": ent()}), [])

def test_committed_report_is_current(self):
    self.assertEqual(b.main(["report", "--check", str(ROOT)]), 0)
```

- [ ] **Step 2:** Run the tests. Expected: FAIL on the missing functions.
- [ ] **Step 3:** Implement. `propose` reads the commemorated persons' QIDs from `data/person_items.json`, skipping `wikidata: null`. It fetches their entities and the candidate group's (cache `.cache/wikidata/`, maxlag 5). Then it asks Jev one noul per eulogy: "Is the Wikidata item `group` the group of saints that `clause` of a eulogy of the Roman Martyrology commemorates?" The state is the group's label, description and P527 member labels, plus the 400-character Latin clause around the first commemorated name. At or above `JEV_MIN`, it writes `{"wikidata": G, "kind": "group", "status": "auto"}`. Below that, it writes nothing and lists the eulogy in the report as "suggestion doubted". The report has counts by class, kind and status, non-members per eulogy, "several" eulogies with no entry, and "hand" eulogies with no entry.
- [ ] **Step 4:** Run `python3 -m pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit.
- [ ] **Step 6:** Tune `JEV_MIN` on the known cases before the full run, with `propose` limited to these eulogies (an optional ID list argument). The three should come out `auto` with these items: `mr:0702-liberatus-et-socii` → Q85977003, `mr:0104-hermes-et-caius` → Q97253965, `mr:0504-agapius-et-secundinus` → Q20901818. Record the chosen value and its reason in the commit message.

### Task 4: The registry carries `item`

**Files:**
- Modify: `scripts/extract_registry.py` (`KEY_ORDER`; new `load_items`, `add_items`; `build`; the `$comment` in `write_json`), `tests/test_registry.py`

**Interfaces:**
- Consumes: Task 2's `data/eulogy_items.json`.
- Produces: an optional registry entry key `item: {"wikidata": "Q…", "kind": "group"|"feast"|"dedication"|"translation"}`, placed after `date` in `KEY_ORDER`. It is present only when `wikidata` is non-null and `status` is not `unresolved`. Both `auto` and `reviewed` are copied.

- [ ] **Step 1: Write the failing test:** `test_item_copied_after_date` builds entries with `add_items` from `{"mr:0101-a": {"wikidata": "Q1", "kind": "group", "status": "reviewed"}, "mr:0101-b": {"wikidata": None, "status": "unresolved", "note": "n"}}`. It asserts that `mr:0101-a` has `item == {"wikidata": "Q1", "kind": "group"}` with `item` right after `date`, and that `mr:0101-b` has no `item`. Also `test_items_for_unknown_ids_fail`: `load_items` asserts the IDs are current, naming the script to run, as `load_dates` does.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement it, mirroring `load_dates` and `add_dates`. Add "Each current entry's optional item comes from data/eulogy_items.json (scripts/build_eulogy_items.py)." to the `$comment`.
- [ ] **Step 4:** Run `python3 scripts/extract_registry.py && python3 -m pytest -q`. Expected: all pass, and the registry is unchanged while the file is empty.
- [ ] **Step 5:** Commit. Then run the full `propose` from Task 3 and review every `auto` suggestion against its eulogy, with sources. Set each to `reviewed`, or remove it with a line in the PR. Run `report` and `extract_registry.py`, commit the data, and open the crmedr PR (tasks 2–4 together) with its CodeRabbit round.

### Task 5: Research the hand eulogies and the Marian titles

**Files:**
- Modify: `data/eulogy_items.json`, `data/person_items.json`, `data/mentions_curated.json` (only where the matcher marks no title), then regenerate (`extract_persons`, `extract_mentions`, `person_details`, `name_forms`, `extract_dates`, `extract_registry`, `build_eulogy_items.py report`).

**Interfaces:**
- Consumes: the "hand" list in `docs/eulogy-items-report.md`; `mr:0501-ioseph-opifex` from Task 1.
- Produces: an entry for every "hand" eulogy: an item (`reviewed`), `unresolved` with a note, or the title decision.

- [ ] **Step 1:** Joseph the Worker: `mr:0501-ioseph-opifex` → `{"wikidata": "Q105888686", "kind": "feast", "status": "reviewed"}`.
- [ ] **Step 2:** Marian titles. For each eulogy whose one commemorated person is a Marian title, find the title or apparition item on Wikidata and verify it (label, description, P31, sitelinks). These are Dei Genetrix, Guadalupe, Lourdes, Fatima, Mount Carmel, Regina, Perdolens, Rosario, and any other the "hand" list shows. Record it under the person's name in `data/person_items.json` (`reviewed`; Dei Genetrix keeps Q208542). Record the eulogy as `{"wikidata": null, "kind": null, "status": "reviewed", "note": "the mention links the title"}`. Where `extract_mentions` marks no person in the text (Fatima, Lourdes, Mount Carmel today), add a curated mention on the printed title, with `check` from `extract_mentions.check`. Expected after regenerating: every one of these mentions has a QID, and none is Q345.
- [ ] **Step 3:** The other "hand" eulogies (feasts, dedications, translations, the anonymous groups): research each one, in batches of about 15 with sources. Record an item, or `unresolved` with a note naming what was searched. Create a Wikidata item only when the eulogy names a church or group that clearly exists and has none, following [[wikidata-traditions-one-item]]: search group members (P527/P463) before creating.
- [ ] **Step 4:** Regenerate and run `python3 -m pytest -q`. Expected: all pass, and the report's "hand eulogies with no entry" is empty. Commit, then open the crmedr PR with its CodeRabbit round.

### Task 6: API and frontend

**Files:**
- Modify (martyrology-api): `src/martyrology_api/registry.py` (`IdEntry.item: Mapping[str, str] | None = None`, set in `Registry.load` from `e.get("item")`), `src/martyrology_api/models.py` (`EulogyItemOut(BaseModel)`: `wikidata: str`, `kind: Literal["group", "feast", "dedication", "translation"]`; `EulogyOut.item: EulogyItemOut | None = None`), the route that builds `EulogyOut`, tests, and `vendor/crmedr` (pin).
- Modify (martyrology-frontend): `scripts/snapshot-registry.mjs` (`buildSnapshot` adds `item` when the entry has one), `lib/snapshot.ts` (`SnapshotEntry.item?: {wikidata: string; kind: "group" | "feast" | "dedication" | "translation"}`), `lib/types.ts` (`EulogyOut.item?`), a new `components/EulogyItemLink.tsx`, `components/Eulogy.tsx` (in the `showId` hint after the subject), `components/EulogyView.tsx` (under the subject), `messages/{en,it,fr,de,es,pt}.json` (namespace `EulogyItem`: `group`, `feast`, `dedication`, `translation`), and tests.

**Interfaces:**
- Consumes: Task 4's registry `item`.
- Produces: `GET /eulogies/{id}` → `"item": {"wikidata", "kind"} | null`. `<EulogyItemLink item={…} />` renders `<a href="https://www.wikidata.org/wiki/{qid}" target="_blank" rel="noreferrer">{t(kind)}</a>`, or nothing when `item` is undefined.

- [ ] **Step 1: Write the failing tests.**
  - API: `test_eulogy_item_served` (a registry entry with `item` gives the same `item` on `EulogyOut`) and `test_eulogy_without_item_is_null`.
  - Frontend `lib/__tests__/snapshot.test.ts`: `buildSnapshot` copies `item` and omits the key when absent.
  - `components/__tests__/EulogyItemLink.test.tsx`: renders the English label "Group on Wikidata" with href `https://www.wikidata.org/wiki/Q85977003`, and renders nothing for `undefined`.
- [ ] **Step 2:** Run `uv run pytest -q` and `npm test`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement. English labels: "Group on Wikidata", "Feast on Wikidata", "Church on Wikidata" (dedication), "Translation on Wikidata". Italian: "Gruppo su Wikidata", "Festa su Wikidata", "Chiesa su Wikidata", "Traslazione su Wikidata". Fill fr/de/es/pt likewise and run `node scripts/sync-messages.mjs` if the repo uses it to check the key sets.
- [ ] **Step 4:** Run both suites. Expected: all pass. Run `npm run lint` and the type check.
- [ ] **Step 5:** After the crmedr PRs merge: open the API PR (code + pin) and merge it once CI passes. Then the frontend PR (code + `npm run snapshot-registry` against crmedr main). Ask the curator before the API release.
