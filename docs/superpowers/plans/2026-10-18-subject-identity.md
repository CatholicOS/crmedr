# Subject identity (crmedr pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For one month at a time, build an identity record per subject from the 2004 Latin, derive rule-built rename candidates (with categories and labels) and expanded Wikidata candidates from it, and attach Jev suggestions, as private change-sets the curator reviews.

**Architecture:** Follows `scripts/body_places.py` (brief → model-written proposals → `check`) for the records, and `scripts/mentions_jev.py` + `scripts/suggest_mentions.py` for Jev. Code applies the minting rules and owns every value written; agents only write records, Jev only ranks and picks. Records and change-sets quote the 2004 texts: written outside any git work tree, uploaded by hand to the server's `CHANGESETS_DIR`.

**Tech Stack:** Python 3 standard library only; `unittest` (`python3 -m unittest discover -s tests`); Wikidata API + SPARQL via `scripts/wikidata.py`; TypeSafe System One HTTP API via `mentions_jev.TypeSafe`.

**Spec:** `docs/superpowers/specs/2026-10-18-subject-identity-design.md`

**Out of this plan:** the martyrology-frontend work (rename candidates with category and score, grouping a eulogy's operations, "Jev suggests" on rename cards) is a second plan, written once Task 6's change-set shape is frozen. Until then the existing rename card works: `new_id` is the top candidate, the others are listed in `reasoning`, and the curator can edit the ID.

## Global Constraints

- Standard library only; every script runnable as `python3 scripts/<name>.py`; tests import from `scripts/` via `sys.path.insert` like `tests/test_mentions_jev.py`.
- Anything quoting the 2004 texts (briefs, records, change-sets, Jev requests' cache) is refused inside any git work tree: reuse `body_places._in_a_repository`.
- The 2004 Latin is the prime reference for minting; Wikidata may supply evidence only, marked `"source": "wikidata"`.
- R1: a place printed as an adjective (of the person, the role, or a place noun) → that adjective in the nominative, agreeing with the subject; genitive only when the print gives a locative/ablative/genitive. One form per place and per kind across the corpus.
- R2: clerics take role + place (`mr:0101-eugendus-abbas-condatiscensis`). CLERIC_ROLES = `episcopus, archiepiscopus, presbyter, diaconus, subdiaconus, abbas, abbatissa, prior`. Others take the place alone. Higher tiers win: surname, cognomen/twin, `-papa`. A cleric with no place: role alone, flagged weak. Class words `martyr, virgo, confessor` only when nothing else is printed, flagged weak.
- Never a numeric slug token; one name form per ID; twins (same `same_eulogy` group or same person item) share one discriminator.
- Categories (exact strings): `surname`, `place-genitive`, `place-adjective`, `role`, `role-place`, `epithet`, `twin`, `papa`, `biblical-title`.
- Jev model pinned: `mentions_jev.MODEL` (`jev-1.14.0`). One clause of Latin (and English or Italian) per card may be sent (curator, 2026-10-18); never a whole eulogy.
- No suggestion is ever applied by itself; `decision`/`edited` are never written by these scripts.

## Review Focus

- A printed place form that occurs twice in a eulogy (two saints, two sees): the record must name which occurrence (`occurrence` index), and `check` must reject an ambiguous citation instead of taking the first. → Task 1.
- A feminine subject with an `-anus`/`-inus` adjective (*Ancyrana*): agreement must follow the subject's gender from the Latin subject's honorific (*Sancta*). → Task 2.
- A candidate slug already used by another eulogy of the same day, or by a different saint on a twin day: must be dropped, not suggested. → Task 3.
- A companion whose decision is `unresolved` or whose item is not human: no relative expansion from it. → Task 5.
- A TypeSafe answer naming a candidate id not in the request (stale cache, model drift): no suggestion, error counted, run continues. → Task 7.

---

### Task 1: Identity records — brief and check

**Files:**
- Create: `scripts/subject_records.py`
- Test: `tests/test_subject_records.py`

**Interfaces:**
- Consumes: `extract_typology.load_texts`, `latin_texts`; `body_places._in_a_repository`, `half_month`.
- Produces:
  - `ROLE_FORMS: dict[str, set[str]]` — nominative role → folded printed forms (`"abbas": {"abbas","abbatis","abbati","abbatem","abbate"}` …, every role in CLERIC_ROLES plus `monachus, eremita, papa, martyr, virgo, confessor, rex, regina, propheta, patriarcha, iudex, levita`).
  - `GRAMMAR = ("adjective-person", "adjective-noun", "locative", "genitive", "ablative")`; `PLACE_KINDS = ("see", "monastery", "death", "burial", "cult", "origin")`; `KINDS = ("person", "celebration", "group")`.
  - `brief(first: str, last: str, texts: dict, texts_it: dict, texts_en: dict, persons: dict, subjects_la: dict, entries: list, items: dict) -> list[dict]` — per current eulogy MMDD in range: `id, la_text, it_text, en_text, subject_la, persons, same_eulogy, person_items` (decided items of its persons).
  - `check_record(record: dict, la_text: str) -> list[str]` — error strings, empty when valid.
  - Record shape (what agents write, one per subject name):
    `{"id": mrid, "name": str, "kind": str, "surname": str|null, "feminine": bool, "roles": [{"role": str, "printed": str, "occurrence": int}], "places": [{"kind": str, "printed": str, "occurrence": int, "grammar": str, "nominative": str, "adjective": str|null, "genitive": str|null, "en": str, "it": str}], "cognomen": {"value": str, "source": "text"|"twin"|"wikidata"}|null, "relations": [{"name": str, "relation": str}], "death_year": int|null, "role_en": str|null, "role_it": str|null}`
    (`printed` is the exact substring of `la_text`; `occurrence` its 0-based index among identical substrings; `adjective` the nominative adjective agreeing with the subject when grammar is adjective-*).

- [ ] **Step 1: Write the failing tests**

```python
TEXT = "In monastério Condatiscénsi in Gállia, sancti Eugéndi, abbátis Condatiscénsis, ..."
def rec(**kw): return {"id": "mr:0101-eugendus", "name": "Eugendus", "kind": "person", "surname": None,
    "feminine": False, "roles": [{"role": "abbas", "printed": "abbátis", "occurrence": 0}],
    "places": [{"kind": "monastery", "printed": "Condatiscénsis", "occurrence": 0, "grammar": "adjective-person",
                "nominative": "Condatiscum", "adjective": "condatiscensis", "en": "Condat", "it": "Condat"}],
    "cognomen": None, "relations": [], "death_year": None, "role_en": "abbot", "role_it": "abate", **kw}

class CheckRecord(unittest.TestCase):
    def test_valid(self): self.assertEqual(sr.check_record(rec(), TEXT), [])
    def test_printed_not_in_text(self):
        r = rec(); r["places"][0]["printed"] = "Condatisci"
        self.assertIn("places[0]: printed form not in the text", sr.check_record(r, TEXT))
    def test_occurrence_out_of_range(self):
        r = rec(); r["places"][0]["occurrence"] = 1   # "Condatiscénsis" occurs once
        self.assertIn("places[0]: occurrence 1 of 1", sr.check_record(r, TEXT))
    def test_role_form_mismatch(self):
        r = rec(); r["roles"][0]["role"] = "episcopus"
        self.assertIn("roles[0]: abbátis is not a form of episcopus", sr.check_record(r, TEXT))
    def test_bad_enums(self):
        r = rec(kind="saint"); r["places"][0]["grammar"] = "adjective"
        errs = sr.check_record(r, TEXT)
        self.assertIn("kind: saint", errs); self.assertIn("places[0]: grammar adjective", errs)
    def test_adjective_required_for_adjective_grammar(self):
        r = rec(); r["places"][0]["adjective"] = None
        self.assertIn("places[0]: adjective missing", sr.check_record(r, TEXT))
    def test_adjective_stem_must_match_printed(self):
        r = rec(); r["places"][0]["adjective"] = "pictaviensis"
        self.assertIn("places[0]: adjective pictaviensis does not match Condatiscénsis", sr.check_record(r, TEXT))
```

Also a `Brief` test: two eulogies of 01-01 and one of 01-16 with `half_month("01","a")` → only the 01-01 ids, each with `la_text`, `person_items`.

- [ ] **Step 2:** Run `python3 -m unittest tests.test_subject_records -v` — FAIL (module missing).
- [ ] **Step 3: Implement** `check_record` and `brief` in `scripts/subject_records.py`, plus `main`: `brief <MMa|MMb> <out.json> /path/to/martyrology-texts [repo_root]` (refuses a path in a work tree, like body_places) and `check <records.json> /path/to/martyrology-texts [repo_root]` (prints errors per record, exits 1 if any; writes nothing). Fold with `gazetteer_text.fold` for comparisons. Adjective stem match: fold both, strip the inflection (`-ensis|-ensi|-ensem|-ense|-ensium|-anus|-ani|-ano|-anum|-ana|-anae|-inus|-ini|-ina|-inae`), compare stems.
- [ ] **Step 4:** Run the tests — PASS; then `python3 -m unittest discover -s tests` — all PASS.
- [ ] **Step 5: Commit** `git add scripts/subject_records.py tests/test_subject_records.py && git commit -m "subject records: brief and check (#74)"`

### Task 2: Latin forms for discriminators

**Files:**
- Create: `scripts/rename_candidates.py` (forms part)
- Test: `tests/test_rename_candidates.py`

**Interfaces:**
- Produces:
  - `adjective_slug(adjective: str, feminine: bool) -> str` — folded, lowercase; `-anus/-ana`, `-inus/-ina` follow `feminine`; `-ensis` unchanged.
  - `genitive_slug(record_place: dict) -> tuple[str|None, bool]` — (slug, certain): the corpus genitive from `PLACE_GENITIVES` (seeded from the bare-name pass's PLACE map: `trevirorum, arvernorum, carnutum, cenomanorum, lemovicum, pictavorum, turonum, hierosolymorum`, keyed by folded nominative) → certain; else the record's `genitive` folded → not certain (the op's confidence drops to low); else `(None, False)` and the place-genitive candidate is skipped.
  - `CLERIC_ROLES`, `WEAK_ROLES = {"martyr", "virgo", "confessor"}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ensis(self): self.assertEqual(rc.adjective_slug("Condatiscénsis", False), "condatiscensis")
def test_feminine_anus(self): self.assertEqual(rc.adjective_slug("Ancyránus", True), "ancyrana")
def test_known_genitive(self): self.assertEqual(rc.genitive_slug({"nominative": "Treviri", "genitive": None}), ("trevirorum", True))
def test_record_genitive_uncertain(self): self.assertEqual(rc.genitive_slug({"nominative": "Metae", "genitive": "Metarum"}), ("metarum", False))
def test_no_genitive(self): self.assertEqual(rc.genitive_slug({"nominative": "X", "genitive": None}), (None, False))
```

- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement the three items above.
- [ ] **Step 4:** Run — PASS.
- [ ] **Step 5: Commit** `"rename candidates: Latin forms (R1)"`

### Task 3: Rename and label candidates

**Files:**
- Modify: `scripts/rename_candidates.py`
- Test: `tests/test_rename_candidates.py`

**Interfaces:**
- Consumes: Task 1 record shape; Task 2 forms.
- Produces:
  - `Context(taken: dict[str, set[str]], twins: dict[str, list[str]], ids: set[str])` — `taken[MMDD]` = slugs in use that day; `twins[mrid]` = its same-saint IDs (same_eulogy group ∪ eulogies sharing a decided person item); `ids` = all current IDs. `load_context(repo_root) -> Context`.
  - `candidates(record: dict, mrid: str, subject_la: str, ctx: Context) -> list[dict]` — each `{"new_id": str, "category": str, "weak": bool, "labels": {"la": str, "en": str, "it": str}, "basis": str}`; ordered by the rule tiers (twin, surname, epithet/papa, then role-place / place-adjective / place-genitive / role); 1 to 4 items; the rule's first choice first.
  - `rejected(record, mrid, ctx) -> list[tuple[str, str]]` — (slug, reason) for dropped ones, for the report.

- [ ] **Step 1: Write the failing tests** (fixtures: the Eugendus record of Task 1; Basilius with twin `mr:0614-basilius-magnus`; a bishop "Hilarius" with *epíscopi Pictaviénsis*; a monk with a place; a martyr with nothing; a surname case; a day where `mr:0101-eugendus-abbas-condatiscensis` is taken)

```python
def test_cleric_role_place_first(self):
    c = rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX)
    self.assertEqual(c[0]["new_id"], "mr:0101-eugendus-abbas-condatiscensis")
    self.assertEqual(c[0]["category"], "role-place")
    self.assertEqual(c[0]["labels"]["la"], "Sanctus Eugendus abbas Condatiscensis")
    self.assertEqual(c[0]["labels"]["en"], "Saint Eugendus, abbot of Condat")
    self.assertEqual(c[0]["labels"]["it"], "Sant’Eugendo, abate di Condat")
def test_twin_wins(self):
    c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", CTX)
    self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0101-basilius-magnus", "twin"))
def test_non_cleric_place_alone(self):
    self.assertEqual(rc.candidates(MONK, "mr:0106-nilammo", "Sanctus Nilammo", CTX)[0]["category"], "place-genitive")
def test_weak_class_word(self):
    c = rc.candidates(MARTYR, "mr:0101-magnus", "Sanctus Magnus", CTX)
    self.assertEqual((c[0]["new_id"], c[0]["weak"]), ("mr:0101-magnus-martyr", True))
def test_surname_no_place(self):
    self.assertEqual([x["category"] for x in rc.candidates(LEGO, "mr:0101-x", "Beatus Ioannes", CTX)][0], "surname")
def test_taken_slug_dropped(self):
    ctx = CTX._replace(taken={"0101": {"eugendus-abbas-condatiscensis"}})
    ids = [x["new_id"] for x in rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", ctx)]
    self.assertNotIn("mr:0101-eugendus-abbas-condatiscensis", ids)
def test_never_numeric(self):
    for x in rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX):
        self.assertFalse(any(t.isdigit() for t in x["new_id"].split("-")[1:]))
```

- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement `Context` (a `NamedTuple`), `load_context` (registry `data/martyrology_ids.json`, `data/person_items.json`), `candidates`, `rejected`. English label: `"<honorific> <English name>, <role_en> of <place en>"` with the English name from `i18n/en.json` minus its honorific; Italian likewise from `i18n/it.json` with `it_label` from `extract_subjects` applied; when the record has no `role_en`/place, the label adds only what the slug adds.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"rename candidates: rule tiers, categories, labels (R2, R3)"`

### Task 4: Wikidata expansions

**Files:**
- Modify: `scripts/wikidata.py`
- Test: `tests/test_gazetteer.py` style — create `tests/test_wikidata_expand.py` with a fake `fetch` returning recorded JSON.

**Interfaces:**
- Produces (methods on `Wikidata`, all returning `summarize_person` dicts plus `"source"`):
  - `relatives(qid: str) -> list[dict]` — targets of P3373, P1038, P26, P40, P25, P22 and members of its P361 groups (via SPARQL `?m wdt:P361 wd:<group>`), `source` = `"companion:<Pnnn>"`.
  - `saints_by_death_day(month: int, day: int, given: list[str], year: int|None = None) -> list[dict]` — SPARQL: `?p wdt:P31 wd:Q5; wdt:P411 ?s; wdt:P570 ?d` with `?s` in `SAINT_STATUSES` (move the set from `build_person_items` into `wikidata.py` and import it back), `MONTH(?d)=month && DAY(?d)=day`, label or alias (la/it/en/fr/es/de) starting with one of `given` (folded); `source` = `"sparql"`; at most 25.
  - `title_candidates(text: str) -> list[dict]` — `_search` in la/it/en without the human filter; `source` = `"title"`.

- [ ] **Step 1: Write the failing tests** — `relatives("Q2652595")` on a recorded entity whose P3373 is Q52161488 returns one dict with `wikidata == "Q52161488"`, `source == "companion:P3373"`; `saints_by_death_day(1, 1, ["Jean","Ioannes","John"])` builds a query containing `MONTH(?d) = 1` and `wd:Q2369287` and parses the recorded bindings; a fetch raising `WikidataError` propagates.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement; reuse `_get` caching, `PREFIXES`, `_entities` + `summarize_person`.
- [ ] **Step 4:** Run — PASS; full suite PASS (`build_person_items` still imports `SAINT_STATUSES`).
- [ ] **Step 5: Commit** `"wikidata: relatives, saints by death day, titles"`

### Task 5: Expanded candidates on the person cards

**Files:**
- Modify: `scripts/build_person_items.py`
- Test: `tests/test_person_items.py`

**Interfaces:**
- Consumes: Task 4 methods; Task 1 records (for given-name equivalents, death year, kind).
- Produces: `expand(review: dict, items: dict, records: dict[str, dict], client) -> list[tuple[str, str]]` (not processed) and CLI `expand <records.json> [repo_root]`. Each op of a record's eulogy gains new candidates (with `evidence`, `source`); existing candidates get `source: "search"` if missing; `MAX_CANDIDATES` raised to 15 for expanded ops. A companion contributes relatives only when its item is decided (`reviewed`/`auto`) and its candidate is human. `kind` celebration → `title_candidates(subject)` instead of persons, plus `CURATED_TITLES: dict[str, str]` (eulogy → QID, seeded `{"mr:0101-maria-dei-genetrix": "Q208542"}`, curator-confirmed only) added with `source: "curated"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sibling_found(self):     # Ioannes gains Q52161488 from Renatus Lego's decided Q2652595
    ...; self.assertIn(("Q52161488", "companion:P3373"), {(c["wikidata"], c["source"]) for c in op["candidates"]})
def test_unresolved_companion_adds_nothing(self): ...
def test_celebration_gets_titles(self):   # mr:0101-maria-dei-genetrix gains Q208542, source "title"
def test_decision_untouched(self): ...    # decision/edited stay as they were
```

- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement `expand` and the CLI. Records are read from outside the repo; the review file is the in-repo `data/person_items_review.json` (it quotes no text).
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"person items: candidates through companions, death day and titles"`

### Task 6: The monthly rename change-set

**Files:**
- Modify: `scripts/rename_candidates.py` (CLI)
- Test: `tests/test_rename_candidates.py`

**Interfaces:**
- Produces: `build_changeset(records: list[dict], ctx: Context, subjects_la: dict, old: dict|None) -> dict` and CLI `build <records.json> <out.json> [--old <bare-names changeset>...] [repo_root]` (out refused in a work tree).
  Op: `{"op": "rename", "id": mrid, "new_id": candidates[0].new_id, "uid": "subject:" + mrid, "class": candidates[0].category, "confidence": "high"|"medium"|"low", "candidates": [...Task 3 dicts], "reasoning": str, "subject_la": str, "decision": null}`. Only bare IDs (slug is one name token, as the bare-name pass defined) get a rename op. The old bare-name draft's `new_id`, if different, is appended as a candidate with `basis: "bare-name draft"`. `reasoning` lists the other candidates as `"also: <new_id> (<category>)"`. Confidence: low if `weak` or the genitive is not certain, medium if more than one candidate, else high.

- [ ] **Step 1: Write the failing tests** — Eugendus op has `new_id` `mr:0101-eugendus-abbas-condatiscensis`, `class` `role-place`, and the old draft `mr:0101-eugendus-condatisci` among `candidates`; a non-bare ID yields no op; schema `crmedr-changeset/v1`.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"rename candidates: monthly change-set"`

### Task 7: Jev requests and suggestions

**Files:**
- Create: `scripts/subject_jev.py`, `scripts/suggest_subjects.py`
- Test: `tests/test_subject_jev.py`, `tests/test_suggest_subjects.py`

**Interfaces:**
- Consumes: `mentions_jev.TypeSafe`, `api_key`, `MODEL`, `KeyRefused`, `TypeSafeError`; records; Task 5 and Task 6 change-sets.
- Produces:
  - `clause(la_text: str, record: dict) -> str` — the sentence of `la_text` holding the record's first cited form (split on `.`/`;`, max 400 chars).
  - `rename_request(op: dict, record: dict, la_clause: str, vernacular_clause: str) -> dict` — questions: `place_grammar` (choice over GRAMMAR, per cited place: `place_grammar_<i>`), `field_<roles|places>_<i>` (noul: "Does `clause` say that the subject was `record.roles[i].role`?" / "…that `record.places[i].nominative` is the subject's <kind>?"), `clarity_<k>` (score per candidate, 4 levels: "a reader could not tell which saint is meant"; "it narrows the saint down but other saints of the corpus could fit"; "it names this saint, but not in the way readers usually know them"; "the name readers would recognise, and no other saint of the corpus could be meant"), `pick` (choice among candidate ids `c0..cN`).
  - `person_request(op: dict, record: dict, la_clause: str, companions: list[dict]) -> dict` — `kind` (choice: person, celebration_or_title, anonymous_group, not_identifiable) and `item` (choice among `q0..qN` plus `none`).
  - `rename_suggestion(op, answers) -> dict|None` → `{"decision": "accept"|"edit", "new_id"?, "probability", "confidence", "model", "flags": [...]}`; a field noul < 0.5 adds `"flag": "record:<field>"` and no suggestion.
  - `person_suggestion(op, answers) -> dict|None` → `accept` (pick == preselected/first passing), `edit` with `wikidata` and `source`, `reject` (none or kind not_identifiable); None if the pick is not a request id.
  - `suggest_subjects.py suggest <renames.json> <records.json> /path/to/martyrology-texts [--persons] [--min-confidence X]` and `evaluate <decided.json>... --records <records.json> /path/to/martyrology-texts`; `DEFAULT_MIN_CONFIDENCE = 0.9` until the January evaluation; cache `.cache/typesafe/`.

- [ ] **Step 1: Write the failing tests**

```python
def test_rename_request_shape(self):
    body = sj.rename_request(OP, EUGENDUS, "…sancti Eugéndi, abbátis Condatiscénsis…", "")
    self.assertEqual(body["model"], mj.MODEL)
    self.assertEqual(body["questions"]["pick"]["type"], "choice")
    self.assertEqual(set(body["questions"]["pick"]["criteria"]), {"c0", "c1"})
    self.assertEqual(len(body["questions"]["clarity_c0"]["criteria"]), 4)
    self.assertNotIn("la_text", json.dumps(body))           # only the clause is sent
def test_edit_suggestion(self):
    s = sj.rename_suggestion(OP, {"pick": {"type": "choice", "choice": "c1", "probabilities": {"c1": 0.93}, "confidence": 0.9},
                                  "field_places_0": {"type": "noul", "noul": 0.97}})
    self.assertEqual((s["decision"], s["new_id"]), ("edit", OP["candidates"][1]["new_id"]))
def test_record_flag_blocks(self):
    s = sj.rename_suggestion(OP, {"pick": PICK_C0, "field_places_0": {"type": "noul", "noul": 0.2}})
    self.assertIsNone(s)
def test_unknown_pick_ignored(self):
    self.assertIsNone(sj.person_suggestion(POP, {"item": {"type": "choice", "choice": "q9", "probabilities": {"q9": 1}, "confidence": 1},
                                                  "kind": KIND_PERSON}))
def test_none_is_reject(self): ...
```

`test_suggest_subjects.py`: a fake client (as in `tests/test_suggest_mentions.py`) — suggestions below threshold removed, a `TypeSafeError` counted and the run continues, `KeyRefused` stops it, `decision` untouched; `evaluate` reports agreement per question family at each threshold.

- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement both modules, patterned on `mentions_jev.py` / `suggest_mentions.py`.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"Jev suggestions on subject renames and person cards"`

### Task 8: Run January (operational)

Work dir: `~/private-changesets/subject-identity/01/` (outside any work tree).

- [ ] **Step 1:** `python3 scripts/subject_records.py brief 01a <dir>/brief-01a.json ../martyrology-texts` and `01b`.
- [ ] **Step 2:** Dispatch research agents (one per ~4 days of the brief), each told: the record shape and enums of Task 1, R1/R2 from Global Constraints, cite only exact substrings, `cognomen.source` "text" unless taken from a twin ID or Wikidata. Output `<dir>/records-01-*.json`.
- [ ] **Step 3:** `python3 scripts/subject_records.py check <merged records> ../martyrology-texts` — 0 errors (fix records by re-dispatching the failing ones).
- [ ] **Step 4:** `python3 scripts/rename_candidates.py build <records> <dir>/crmedr-subjects-01-renames.json --old ~/private-changesets/bare-names/crmedr-bare-names-1-flagged.json --old ~/private-changesets/bare-names/crmedr-bare-names-2-routine.json`; check Eugendus → `-abbas-condatiscensis`, Basilius → `-magnus`.
- [ ] **Step 5:** `python3 scripts/build_person_items.py expand <records>`; check Ioannes has Q52161488 and Maria Dei Genetrix has Q208542 among candidates. Count how many January hand-typed QIDs (from the curator's export, when given) are now candidates.
- [ ] **Step 6:** `python3 scripts/suggest_subjects.py suggest …` for both change-sets; export the January person ops to `<dir>/crmedr-persons-01.json`.
- [ ] **Step 7:** Commit the code-side changes (`data/person_items_review.json` only if regenerated in-repo); push the branch and open the PR. Tell the curator which files to upload by hand to `CHANGESETS_DIR`; do not upload.

### Task 9: Evaluate on the curator's January decisions (after review)

- [ ] **Step 1:** `python3 scripts/suggest_subjects.py evaluate <decided renames> <decided persons> --records … ../martyrology-texts`.
- [ ] **Step 2:** Set per-family thresholds in `suggest_subjects.py` (lowest threshold with ≥95% agreement on ≥⅓ suggested, as for mentions); add the figures and the categories the curator chose, per situation, to the spec under "Evaluation result (January)"; note any rule exception the decisions show for the curator to rule on.
- [ ] **Step 3:** Commit, push, PR.
