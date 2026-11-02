# Mentioned Persons (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark every person a 2004 eulogy names without commemorating, link them to Wikidata, and show them in the
reader (commemorated elsewhere: linked to their eulogy; commemorated nowhere: a new accent and an index of their own).

**Architecture:** crmedr gains an additive file of mentioned persons with their printed spans; `extract_persons.py`
adds them with `role: "mentioned"`, `extract_mentions.py` marks them and writes, per mark, the eulogies that
commemorate the same item (`commemorated_in`), the one derivation of "commemorated elsewhere". A pipeline script
drafts, scores (Jev) and applies the decisions. The API passes `role` and `commemorated_in` through; the frontend tints,
labels and indexes from them.

**Tech Stack:** Python 3 stdlib + unittest (crmedr); FastAPI/Pydantic + pytest (martyrology-api); Next.js/TypeScript +
vitest (martyrology-frontend); TypeSafe Jev (`jev-1.14.0`, `https://api.typesafe.ai/v1/systemone`); wikibase-cli `wb`.

**Spec:** `docs/superpowers/specs/2026-11-02-mentioned-persons-design.md` (crmedr PR #270). Phases 2 (movements and
heresies) and 3 (religious congregations) get plans of their own after this one is live.

## Global Constraints

- Mark every named human person except Christ, the Persons of the Trinity and the Virgin Mary; unnamed persons are not marked.
- A mentioned person's mark spans the name with its epithets and attached office (*Ambrósius, epíscopus Mediolanénsis*, *Gregórius papa*); no place mark inside it, and that place is not a eulogy place.
- Inside a **commemorated** person's name nothing changes.
- "Commemorated" = a current 2004 eulogy lists the person without `role: "mentioned"` (Latin or Italian; `others` count); 1914/1749/1630 do not.
- Jev accepts at ≥ 0.90. Create a Wikidata item only when the literature gives at least one fact beyond the eulogy; else `unresolved`, indexed by name.
- Only cases scholarly research cannot settle become review cards uploaded to the server (`CHANGESETS_DIR`); their marks are left out until decided.
- Cards and audit trail live in `~/private-changesets/mentioned-persons/` (they quote the 2004 texts), never in git. Never `git add` all of `data/` or `docs/`.
- Wikidata: maxlag 5 with retry, never raised. Edition texts are immutable.
- crmedr PRs get one CodeRabbit round (`~/private-changesets/subject-identity/tools/cr_trigger2.sh crmedr N`); API and frontend PRs merge on green CI.
- Order: crmedr → API (fields) + release → frontend + snapshot + deploy (the frontend tolerates the new fields before it uses them).

## Rulings made while planning

- **Statuses:** the spec lists `jev`/`researched`/`created` as statuses. Every consumer (`build_person_items.py`,
  `person_details.py`, the frontend's `IDENTIFIED`) treats only `auto`/`reviewed` as identified, so a new status
  would silently unlink persons. Decided persons get `status: "reviewed"` plus `"decided": "jev" | "research" |
  "created"`; `unresolved` stays as is. Cost if wrong: one field rename.
- **The derivation lives on the mark:** `extract_mentions.py` writes `commemorated_in` on every mentioned person's
  mark and the same map to `data/persons_commemorated.json` (for the frontend snapshot); the API passes it through.
  Cost if wrong: an extra field to drop later.

## Review Focus

1. A mentioned person sharing a name with a commemorated person of the same eulogy (Zeno in `mr:1226-zeno-maiumae`): the two stay two persons (n), marked apart.
2. A mentioned person named twice in one eulogy, or once in the text and once in a footnote: both marks, highlighted together, one persons record.
3. A eulogy with a curated mention list (`mentions_curated.json`) that already marks a mentioned person: no duplicate mark; the curated mark gains `role` and `commemorated_in`.
4. A mentioned person with no item: kind 3, never merged in an index with a namesake elsewhere.
5. A place mark inside a mentioned span left over in `places_curated.json`: regeneration fails, naming the entry to remove.

---

## crmedr

### Task 1: The mentioned-persons file and `extract_persons.py`

**Files:**
- Create: `data/persons_mentioned.json`
- Modify: `scripts/extract_persons.py` (`main`, `validate`, new `with_mentioned`), `data/persons_curated.json` (move the seven out)
- Test: `tests/test_extract_persons.py`

**Interfaces:**
- Produces: `data/persons_mentioned.json` = `{"$comment": str, "<mrid>": [{"name": str, "n"?: int, "where": "text"|{"footnote": int}, "la": [str, ...], "it"?: [str, ...]}]}` — `la`/`it` are the printed phrases of each mark of that person, in text order (a phrase repeated in the list = its next occurrence).
- Produces: `with_mentioned(persons_by_id: dict, mentioned: dict) -> list[str]` (errors), appending `{"name", "n"?, "where", "role": "mentioned"}` (no `la`/`it`) after a eulogy's own persons.

- [ ] **Step 1: Write the failing tests** in `tests/test_extract_persons.py`:

```python
def test_mentioned_persons_are_added_with_their_role(self):
    persons = {"mr:0119-bassianus-laudis-pompeiae": [{"name": "Bassianus", "where": "text"}]}
    mentioned = {"mr:0119-bassianus-laudis-pompeiae": [
        {"name": "Ambrosius", "where": "text", "la": ["Ambrósio Mediolanénsi"], "it": ["Ambrogio di Milano"]}]}
    self.assertEqual(with_mentioned(persons, mentioned), [])
    self.assertEqual(persons["mr:0119-bassianus-laudis-pompeiae"][1],
                     {"name": "Ambrosius", "where": "text", "role": "mentioned"})

def test_a_mentioned_person_needs_a_new_name_or_n(self):
    persons = {"mr:x": [{"name": "Zeno", "where": "text"}]}
    errs = with_mentioned(persons, {"mr:x": [{"name": "Zeno", "where": "text", "la": ["Zenónis"]}]})
    self.assertIn("mr:x: 'Zeno' is already a person of the eulogy; give the mentioned one n", errs[0])
    self.assertEqual(with_mentioned({"mr:x": [{"name": "Zeno", "where": "text"}]},
                                    {"mr:x": [{"name": "Zeno", "n": 2, "where": "text", "la": ["Zenónis"]}]}), [])

def test_a_mentioned_person_needs_a_printed_phrase(self):
    errs = with_mentioned({}, {"mr:x": [{"name": "Ambrosius", "where": "text", "la": []}]})
    self.assertEqual(errs, ["mr:x: 'Ambrosius' has no printed phrase (la)"])
```

- [ ] **Step 2: Run them; expect ImportError on `with_mentioned`.** `python3 -m unittest tests.test_extract_persons -v`
- [ ] **Step 3: Implement `with_mentioned`**; in `main`, read `data/persons_mentioned.json` (skip `$` keys) after `apply_curated_variants`, call it, and exit with its errors like the curated-variants errors. A eulogy with no persons of its own still gets its mentioned ones. Update `COMMENT` and the module docstring to name the file.
- [ ] **Step 4: Move the seven** (`Henricus` in 0303, `Symeon` in 0417, `Cunegundis` in 0713, `Willibrordus` in 1003, `Eusebius`, `Nestabius`, `Zeno` in 1226) from `persons_curated.json` into `persons_mentioned.json` with their phrases (from the current `mentions.json` spans). For each of those five eulogies, drop its `persons_curated.json` entry when extraction alone gives the same commemorated list (compare `data/persons.json` before/after); otherwise keep the entry without the mentioned persons.
- [ ] **Step 5: Run** `python3 scripts/extract_persons.py ../martyrology-texts` then `python3 -m unittest discover -s tests`. Expected: `data/persons.json` unchanged except key order inside those eulogies (diff shows only moves); all tests pass.
- [ ] **Step 6: Commit** `data/persons_mentioned.json data/persons_curated.json data/persons.json scripts/extract_persons.py tests/test_extract_persons.py docs/persons-report.md` — "Persons: mentioned persons in their own file, added to the extraction with role mentioned (#230)".

### Task 2: Marks of mentioned persons in `extract_mentions.py`

**Files:**
- Modify: `scripts/extract_mentions.py` (`build_edition`, `extract`, `with_unlisted_persons` callers, `validate`, new `with_mentioned_marks`, new `commemorated_items`, `COMMENT`)
- Create (generated): `data/persons_commemorated.json`
- Test: `tests/test_extract_mentions.py`

**Interfaces:**
- Consumes: `persons.json` records with `role: "mentioned"`; `persons_mentioned.json` phrases (Task 1).
- Produces: `commemorated_items(persons_editions: dict, person_items: dict) -> dict[str, list[str]]` — QID → sorted current eulogy IDs that list it without `role`, over both 2004 editions' persons (and `others` of their marks).
- Produces: a mentioned person's mark = the usual person mark + `"role": "mentioned"`, `"commemorated_in": [ids]` (empty list = commemorated nowhere; the eulogy itself never listed).
- Produces: `data/persons_commemorated.json` = `{"$comment": str, "items": {qid: [ids]}}`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_a_mentioned_person_is_marked_on_its_phrase(self):
    text = "Laude Pompéia, sancti Bassiáni, qui ab Ambrósio Mediolanénsi ordinátus est."
    ms = with_mentioned_marks([], [{"name": "Ambrosius", "where": "text", "la": ["Ambrósio Mediolanénsi"]}],
                              {"text": text}, "la", person_qid=lambda p: "Q43746", commemorated={"Q43746": ["mr:1207-ambrosius"]})
    self.assertEqual([(text[m["start"]:m["end"]], m["role"], m["commemorated_in"]) for m in ms],
                     [("Ambrósio Mediolanénsi", "mentioned", ["mr:1207-ambrosius"])])

def test_a_place_inside_a_mentioned_span_is_an_error(self):
    errs = validate_mentioned_spans([{"kind": "person", "role": "mentioned", "where": "text", "start": 40, "end": 61},
                                     {"kind": "place", "where": "text", "start": 49, "end": 61, "qid": "Q490"}], "mr:x")
    self.assertEqual(errs, ["mr:x: a place mark (Q490) lies inside a mentioned person's name; remove it from data/places_curated.json"])

def test_repeated_phrases_take_the_next_occurrence(self): ...  # "Henríci" twice → two marks, start2 > start1
def test_a_curated_mark_of_a_mentioned_person_is_kept_not_doubled(self): ...  # curated list has Willibrordus → one mark, with role
def test_commemorated_items_ignore_mentioned_and_the_same_eulogy(self): ...  # Willibrord mentioned in 1003, commemorated in 1107 → {"Q160714": ["mr:1107-willibrordus"]}
def test_bassianus_lists_no_milan(self):  # data test against data/places.json
    self.assertNotIn("Mediolanénsi", [p["la"] for p in places["mr:0119-bassianus-laudis-pompeiae"]])
```

- [ ] **Step 2: Run; expect ImportError / failures.** `python3 -m unittest tests.test_extract_mentions -v`
- [ ] **Step 3: Implement** `with_mentioned_marks(ms, mentioned, sources, lang, person_qid, commemorated) -> list` (find each phrase in its `where` source left to right; a phrase not found is an error, as for curated persons), `validate_mentioned_spans(ms, mrid) -> list[str]`, `commemorated_items(...)`. In `build_edition`: pass only non-mentioned persons to the matcher and to `with_unlisted_persons`; call `with_mentioned_marks` after `with_events`, skipping a person a curated list already marks (that mark gains `role` and `commemorated_in`); run `validate_mentioned_spans` per eulogy. `extract()` writes `data/persons_commemorated.json`. The Italian edition uses the `it` phrases.
- [ ] **Step 4: Remove** the Milan entry of `mr:0119-bassianus-laudis-pompeiae` from `data/places_curated.json`; run `python3 scripts/registry_places.py`, `python3 scripts/extract_registry.py`, `python3 scripts/extract_mentions.py ../martyrology-texts --review <scratch>/mentions-review.json`; run all tests. Expected: the seven mentioned persons marked with `role`; `persons_commemorated.json` written; tests pass.
- [ ] **Step 5: Commit** the scripts, tests, `data/mentions.json`, `data/persons_commemorated.json`, `data/places_curated.json`, `data/places.json`, `data/martyrology_ids.json`, changed `registry/*.md`, `docs/mentions-report.md` — "Mentions: mentioned persons marked on their phrase, with the eulogies that commemorate them; no place inside their name (#230)".

### Task 3: Person items for mentioned persons

**Files:**
- Modify: `scripts/build_person_items.py` (`validate`/`check` accept `decided`; `propose` leaves mentioned persons to the pipeline; report counts)
- Test: `tests/test_build_person_items.py`

**Interfaces:**
- Produces: an item entry may carry `"decided": "jev" | "research" | "created"` (only with `status: "reviewed"`); `propose` never puts a mentioned person on a review card and never changes their entry.

- [ ] **Step 1: Failing tests:** `test_decided_is_valid_only_on_reviewed` (`{"status": "auto", "decided": "jev"}` → error naming the person); `test_propose_skips_mentioned_persons` (a mentioned person with no entry gets no card and no entry); `test_report_counts_mentioned_by_decided`.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement**; update the module docstring.
- [ ] **Step 4: Run all tests; pass.** `python3 scripts/build_person_items.py check` passes.
- [ ] **Step 5: Commit** — "Person items: mentioned persons are decided by the mentioned-persons pipeline (decided: jev, research, created)".

### Task 4: The pipeline script: briefs and proposal checks

**Files:**
- Create: `scripts/mentioned_persons.py` (subcommands `brief`, `check`), `tests/test_mentioned_persons.py`

**Interfaces:**
- `brief <MM> <texts_repo> <out.json>`: per eulogy of month MM: `id`, Latin text, footnotes, Italian text and footnotes, its persons (name, n, role), its current marks as `[kind, where, start, end, form]`. Written outside any git work tree (refuse otherwise: `body_places._in_a_repository`).
- Proposal format (what extraction returns): `{"<mrid>": [{"name": str (Latin nominative), "n"?: int, "where": ..., "la": [phrases], "it": [phrases], "who": str (one line: who this is), "kind": "saint" | "other"}]}`.
- `check <proposals.json> <texts_repo>` → exit 1 listing problems: a phrase not found in its `where`; a phrase overlapping a commemorated person's mark; a name in `EXCLUDED` (Christ, Iesus, Dominus, Deus, Spiritus Sanctus, Trinitas, Maria/Virgo when the Virgin); a name+n already a person of the eulogy.

- [ ] **Step 1: Failing tests** for each `check` rule (one test per rule, using a two-eulogy fixture) and `test_brief_refuses_a_git_work_tree`.
- [ ] **Step 2: Run; fail.** **Step 3: Implement** (reuse `extract_mentions.load_edition`, `mentions_text.utf16`). **Step 4: Pass.**
- [ ] **Step 5: Commit** — "Mentioned persons: briefs for extraction and proposal checks (#230)".

### Task 5: Candidates and Jev

**Files:**
- Modify: `scripts/mentioned_persons.py` (subcommands `candidates`, `jev`); `tests/test_mentioned_persons.py`

**Interfaces:**
- `candidates <proposals.json> <out.json>` (network, cached under the out file's directory): per person, first the items of persons of the same `name_key` that `persons_commemorated.json` lists (route `"commemorated"`), then `wbsearchentities` (la, en, it; limit 7) with label, description, birth/death years (route `"search"`).
- `jev <candidates.json> <out.json>`: one Choice per person over the candidate QIDs plus `"none"`; state = the eulogy's Latin sentence holding the phrase, the Italian phrase, `who`, and each candidate's label/description/years. Reuse `mentions_jev.api_key`, `http_post`, `cache_key`, `MODEL`. Output per person: `{"choice": qid|"none", "p": float, "accepted": p >= 0.90 and choice != "none"}`.

- [ ] **Step 1: Failing tests:** `test_commemorated_route_comes_first`; `test_jev_request_lists_none`; `test_accepts_only_at_or_above_090` (0.89 → not accepted, 0.90 → accepted); network calls injected (no network in tests).
- [ ] **Steps 2–4: Run fail, implement, pass.**
- [ ] **Step 5: Commit** — "Mentioned persons: Wikidata candidates and Jev's choice (#230)".

### Task 6: Apply and review cards

**Files:**
- Modify: `scripts/mentioned_persons.py` (subcommands `apply`, `cards`); `tests/test_mentioned_persons.py`

**Interfaces:**
- Decisions file (written by the run, Task 7): `{"<mrid>|<name>[#n]": {"wikidata": qid|null, "decided": "jev"|"research"|"created"|null, "status": "reviewed"|"unresolved"|"doubt", "note"?: str, "proposal": {...}}}`.
- `apply <decisions.json>`: adds non-`doubt` persons to `data/persons_mentioned.json` and their entries to `data/person_items.json` (`reviewed` + `decided`, or `unresolved`); never overwrites an existing entry with a different QID (error); `doubt` entries are skipped.
- `cards <decisions.json> <out.json>`: the `doubt` entries as a `crmedr-changeset/v1` change-set, op `resolve_person`, `reasoning` = the research note, for upload.

- [ ] **Step 1: Failing tests:** `test_apply_writes_mentioned_and_items`; `test_apply_skips_doubts`; `test_apply_refuses_a_conflicting_qid`; `test_cards_hold_only_doubts`.
- [ ] **Steps 2–4.** **Step 5: Commit** — "Mentioned persons: apply decisions; cards only for doubts research cannot settle (#230)". Then push, open the crmedr PR for Tasks 1–6, run the CodeRabbit round, fix valid findings, merge.

### Task 7: The run (operational, month by month)

No new code; each month is a commit on a branch `persons/mentioned-MM`, batched into a few PRs.

- [ ] **Step 1: Briefs.** `python3 scripts/mentioned_persons.py brief MM ../martyrology-texts ~/private-changesets/mentioned-persons/brief-MM.json` for 01–12.
- [ ] **Step 2: Extraction.** One subagent per month reads its brief and writes `proposals-MM.json` in the proposal format, applying the Global Constraints' scope rules (every named person; not Christ, Trinity, Virgin; office included in the span). `check` must pass; fix and rerun until it does.
- [ ] **Step 3: Candidates + Jev.** `candidates` then `jev` per month.
- [ ] **Step 4: Research** every person Jev did not accept: a subagent per batch of ~40 researches each (eulogy, hagiography, standard references, Wikidata) and returns `research-MM.json`: chosen QID, or `create` with sourced statements, or `unresolved` (no fact beyond the eulogy), or `doubt` (two candidates or a disputed identity the literature cannot settle) with the reason.
- [ ] **Step 5: Wikidata.** For chosen items missing signals, add them sourced (`wb add-claim`/`add-reference`, maxlag 5, retry). For `create`, `wb create-entity` with P31 Q5, labels la/en/it, description, P1343 Q125252554, and the sourced facts. Record QIDs into `decisions-MM.json`.
- [ ] **Step 6: Apply** `python3 scripts/mentioned_persons.py apply decisions-MM.json`; regenerate (`extract_persons.py`, `registry_places.py`, `extract_registry.py`, `extract_mentions.py`, `person_details.py`); run all tests; commit with explicit paths.
- [ ] **Step 7: Cards.** After all months, `cards` over the doubts into `~/private-changesets/mentioned-persons/crmedr-mentioned-persons-doubts.json`; upload it to `CHANGESETS_DIR` (the curator approved uploading doubts in the spec).
- [ ] **Step 8:** PRs, CodeRabbit rounds, merge. Audit `mr:0727-ecclesius` (John I) in the January–July pass: a commemorated entry that is only mentioned moves to `persons_mentioned.json`.

## martyrology-api

### Task 8: `role` and `commemorated_in` on person marks

**Files:**
- Modify: `src/martyrology_api/models.py` (`MentionBase`), `src/martyrology_api/mentions.py` (`served`)
- Test: `tests/test_mentions.py`, `tests/test_openapi.py`

**Interfaces:**
- `MentionBase.role: Literal["mentioned"] | None = None` and `MentionBase.commemorated_in: list[str] | None = None` (canonical IDs). `served`: null both for places and events; for a person, `commemorated_in` only when `role == "mentioned"`.

- [ ] **Step 1: Failing tests:** `test_a_mentioned_person_is_served_with_role_and_commemorated_in`; `test_a_place_has_no_role_or_commemorated_in`; the OpenAPI snapshot test updated.
- [ ] **Steps 2–4.** `uv run pytest -q` passes.
- [ ] **Step 5:** Commit, PR; then the pin PR (vendor/crmedr, Dockerfile `CRMEDR_REF`, version bump in `pyproject.toml`, `__init__.py`, `uv.lock`), merge on green, `gh release create`, check `/healthz`.

## martyrology-frontend

### Task 9: Types, snapshot, tint and popup

**Files:**
- Modify: `lib/types.ts` (mention `role?`, `commemorated_in?`), `lib/persons.ts` (`PersonMention.role?: "mentioned"`), `lib/entities.ts` (`EulogyLink.mentioned?: true`), `scripts/snapshot-registry.mjs` (`buildPersons` passes `role`), `components/markup/MentionPiece.tsx` (TINT/WITHIN `uncommemorated`), `app/[locale]/read/[edition]/[mm]/page.module.css` (or wherever `.person` lives: `.uncommemorated`, `.withinUncommemorated`, light and dark), `components/markup/MentionPersonCard.tsx`, `messages/*.json` (six languages)
- Test: `lib/__tests__/` (snapshot, entities), component tests beside the existing ones

**Interfaces:**
- Kind-3 test: `mention.kind === "person" && mention.role === "mentioned" && !mention.commemorated_in?.length`.
- Popup: kind 2 shows `Markup.commemoratedOn` ("Commemorated on {date}", linked, one per eulogy); kind 3 shows `Markup.notCommemorated` ("Not commemorated in the Martyrology") and `Markup.alsoMentionedIn` with the other eulogies of the item; a commemorated person's "Other eulogies" list marks the mentioning ones.

- [ ] **Step 1: Failing tests:** tint class for kind 3; popup texts for kinds 2 and 3; `buildPersons` keeps `role`; `eulogyLinks` sets `mentioned`.
- [ ] **Steps 2–4.** `npx tsc --noEmit && npm test` pass.
- [ ] **Step 5: Commit** — "Reader: mentioned persons: commemorated elsewhere links, a new accent for those commemorated nowhere".

### Task 10: Index split and the index of persons not commemorated

**Files:**
- Modify: `lib/names-index.ts` (`NameLine.mentioned: boolean`; persons with no commemorated line left out), the names pages under `app/[locale]/read/[edition]/names/` (two groups per heading: "Commemorated" / "Mentioned")
- Create: `lib/mentioned-index.ts`, `app/[locale]/read/[edition]/mentioned/page.tsx` and `[letter]/page.tsx` (same layout as names), a link beside the places and names indexes, `messages/*.json`
- Test: `lib/__tests__/names-index.test.ts`, `lib/__tests__/mentioned-index.test.ts`

**Interfaces:**
- `mentionedIndex(catalog, snap, edition, locale): NamesIndexData | null` — persons whose every line is mentioned and whose QID no eulogy commemorates (or no QID; key `name:<name>#<n|1>@<eulogy>`, never merged).

- [ ] **Step 1: Failing tests:** Willibrord has a "mentioned" line under his heading; a kind-3 person is absent from `namesIndex` and present in `mentionedIndex`; two no-item namesakes in two eulogies are two headings.
- [ ] **Steps 2–4.** **Step 5:** Commit, PR; then the snapshot PR (`npm run snapshot-registry`), merge on green, deploy (`gh workflow run deploy.yml --ref main`), check the live pages.
