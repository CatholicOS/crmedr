# Body places: the proposal pass and the add_place review card — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill `data/places_review.json` with checked `add_place` proposals for every place each current eulogy names outside its opening place, and give martyrology-frontend a review card to decide them.

**Architecture:** Two repositories, two PRs. In crmedr, `scripts/body_places.py` gains `brief` (a scratch file per half-month batch with what a subagent needs), structured failures, the eulogy's persons on each op, and `check --final` (failures kept under `unqueued` and listed in `docs/places-report.md`); then subagents run the pass and `check` queues what passes. In martyrology-frontend, an `AddPlaceCard` shows the Latin and Italian 2004 texts with the proposed printing highlighted, with role, person and printing selectors, and the review page gains a bulk accept by confidence; the change-set is bundled in `changesets/`.

**Tech Stack:** Python 3 stdlib + unittest (crmedr); Next.js, React, TypeScript, next-intl, Vitest + Testing Library (martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-14-body-places-design.md` (rollout steps 2 and 3; plan 1 `docs/superpowers/plans/2026-10-14-body-places-core.md` is merged as crmedr #129).

## Global Constraints

- No eulogy text is stored in either repository: only IDs, place designations (`la`, `it`), roles, person names and short English reasoning. Briefs and raw proposals (which quote the 2004 texts) live in the session scratchpad, never in a repository.
- `reasoning`: at most 300 characters (`MAX_REASONING`), no run of 4 words of the Latin or Italian text beyond the place's own words (`reasoning_errors`).
- Roles: the closed set `death, burial, translation, dedication, cult, birth, education, religious_life, ministry, foundation, exile, journey, mention` (`ROLES` in `scripts/extract_places.py`).
- `la` / `it`: the place designation only, verbatim, `MAX_WORDS` 12 / `MAX_WORDS_IT` 20; the cue word stays out; an adjectival see is quoted as the adjective.
- `occurrence` / `occurrence_it` (from 1) only when the form is printed more than once; `person` / `n` only when the eulogy has several persons and the role is one person's.
- The model never decides: no Wikidata guess, no write to `data/places_curated.json` in this plan.
- crmedr: never `git add` whole `data/` or `docs/`; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf`; PR footer `🤖 Generated with [Claude Code](https://claude.com/claude-code)` plus the session URL; merge commits.
- martyrology-frontend: every message key in all six locales (`messages/{en,it,fr,de,es,pt}.json`, `lib/__tests__/messages.test.ts`); no browser dialogs (`confirm`) — confirmations are inline.

## Review Focus

1. A proposal whose `la` is printed twice and comes without `occurrence` — `check` must reject it (validate_curated), and the card's edit must ask which printing; covered by Task 1 and Task 5 tests.
2. An edit that clears `it` or `person` — the card must send `null` (an empty string would fail `apply`'s validation); Task 5 test `clearing the Italian sends null`.
3. Bulk accept must touch only undecided `add_place` ops matching the filters, never ops on other pages' filters or decided ops; Task 6 test.
4. A `brief` written inside a repository would commit the 2004 texts — `brief` refuses a path under the repository root; Task 1 test.
5. Running `check --final` twice must not duplicate `unqueued` records; Task 1 test.

---

## Part A — crmedr (branch `feat/body-places-proposals` from `main`)

### Task 1: `body_places.py`: brief, structured failures, persons on ops, `check --final`

**Files:**
- Modify: `scripts/body_places.py`
- Test: `tests/test_body_places.py`

**Interfaces:**
- Consumes: `validate_curated`, `CURATED_KEYS`, `EDITION_IT`, `load_persons` (`extract_places.py`); `latin_texts`, `load_texts` (`extract_typology.py`).
- Produces:
  - `check(proposals, curated, review, texts, texts_it, leads, persons, final=False) -> (int, list[dict])`; each failure is `{"eulogy": str|None, "role": str|None, "la": str|None, "errors": [str]}`. With `final=True`, the failures replace `review["unqueued"]` records with the same (`eulogy`, `role`, `la`) and the list is sorted.
  - Each queued op gains `"persons": [{"name": str, "n"?: int}]` when the eulogy has two or more persons printed in its text.
  - `brief(first, last, texts, texts_it, leads, persons, curated) -> list[dict]` with `first`/`last` as `"MMDD"`; each record `{"id", "la_text", "it_text", "opening": {"la", "it"?, "role"}|None, "persons": [{"name","n"?}], "curated": [item]}`, in ID order.
  - `half_month(mm: str, half: str) -> (first, last)`: `("01","a") -> ("0101","0115")`, `("01","b") -> ("0116","0131")`.
  - CLI: `brief <MM><a|b> <out.json> /path/to/martyrology-texts [repo_root]`; `check [--final] <proposals.json> /path/to/martyrology-texts [repo_root]`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_body_places.py`, and adapt the two existing tests that read failures as strings)

In `CheckTest.test_bad_proposals_are_reported_good_ones_kept`, replace the five `assert…` lines after `self.assertEqual(n, 1)` with:

```python
        self.assertEqual(len(failures), 4)
        errors = [e for f in failures for e in f["errors"]]
        self.assertTrue(any("not verbatim" in e for e in errors))
        self.assertTrue(any("unknown role" in e for e in errors))
        self.assertTrue(any("not a current ID" in e for e in errors))
        self.assertTrue(any("confidence" in e for e in errors))
        self.assertEqual({(f["role"], f["la"]) for f in failures},
                         {("birth", "in Fictlandia"), ("nativity", "Romæ"), ("birth", "in Fictonia"), ("birth", "Romæ")})
```

Run `grep -n 'failures' tests/test_body_places.py` and change every other string use of a failure (`"…" in f`, `failures[0]`) to read `f["errors"]` the same way.

Then add:

```python
PERSONS2 = {"mr:0101-a": [{"name": "Fictitius", "where": "text"}, {"name": "Fictus", "where": "text"},
                          {"name": "Fictus", "n": 2, "where": "text"}, {"name": "Notus", "where": {"footnote": 1}}]}


class StructuredCheckTest(unittest.TestCase):
    def test_op_lists_the_persons_of_a_eulogy_with_several(self):
        review = bp.new_changeset()
        bp.check([prop()], {}, review, TEXTS, TEXTS_IT, LEADS, PERSONS2)
        self.assertEqual(review["operations"][0]["persons"],
                         [{"name": "Fictitius"}, {"name": "Fictus"}, {"name": "Fictus", "n": 2}])

    def test_op_has_no_persons_for_a_single_subject(self):
        _, _, review = run_check([prop()])
        self.assertNotIn("persons", review["operations"][0])

    def test_final_keeps_failures_once(self):
        review = bp.new_changeset()
        for _ in range(2):
            bp.check([prop(la="in Fictlandia")], {}, review, TEXTS, TEXTS_IT, LEADS, PERSONS, final=True)
        self.assertEqual(len(review["unqueued"]), 1)
        self.assertEqual({k: review["unqueued"][0][k] for k in ("eulogy", "role", "la")},
                         {"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictlandia"})

    def test_a_later_pass_that_queues_it_drops_the_failure(self):
        review = bp.new_changeset()
        # same eulogy, role and la; only the Italian is wrong
        bp.check([prop(it="in Fictlandia")], {}, review, TEXTS, TEXTS_IT, LEADS, PERSONS, final=True)
        self.assertEqual(len(review["unqueued"]), 1)
        bp.check([prop()], {}, review, TEXTS, TEXTS_IT, LEADS, PERSONS, final=True)
        self.assertEqual(review["unqueued"], [])
        self.assertEqual(len(review["operations"]), 1)

    def test_without_final_nothing_is_kept(self):
        _, _, review = run_check([prop(la="in Fictlandia")])
        self.assertEqual(review.get("unqueued", []), [])


class BriefTest(unittest.TestCase):
    TEXTS = {"mr:0101-a": "Fictopoli, sancti Fictitii.", "mr:0115-b": "Romæ, sancti B.",
             "mr:0116-c": "Parisiis, sancti C."}
    TEXTS_IT = {"mr:0101-a": "A Fictopoli, san Fictizio."}

    def test_half_month(self):
        self.assertEqual(bp.half_month("01", "a"), ("0101", "0115"))
        self.assertEqual(bp.half_month("02", "b"), ("0216", "0231"))

    def test_brief_holds_the_batch_in_order(self):
        out = bp.brief("0101", "0115", self.TEXTS, self.TEXTS_IT, LEADS, PERSONS,
                       {"mr:0101-a": [{"role": "birth", "la": "Romæ"}]})
        self.assertEqual([r["id"] for r in out], ["mr:0101-a", "mr:0115-b"])
        self.assertEqual(out[0], {"id": "mr:0101-a", "la_text": self.TEXTS["mr:0101-a"],
                                  "it_text": self.TEXTS_IT["mr:0101-a"],
                                  "opening": {"la": "Fictopoli", "role": "death"},
                                  "persons": [{"name": "Fictitius"}],
                                  "curated": [{"role": "birth", "la": "Romæ"}]})
        self.assertEqual((out[1]["it_text"], out[1]["opening"], out[1]["persons"]), ("", None, []))

    def test_brief_refuses_a_path_in_the_repository(self):
        repo = Path(__file__).resolve().parent.parent
        with self.assertRaises(SystemExit):
            bp.main(["brief", "01a", str(repo / "data" / "brief.json"), "/nonexistent"])
        self.assertFalse((repo / "data" / "brief.json").exists())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_body_places -v 2>&1 | tail -20`
Expected: FAIL/ERROR — `TypeError: string indices must be integers` in the adapted tests, `unexpected keyword argument 'final'`, `module 'body_places' has no attribute 'half_month'` / `'brief'`.

- [ ] **Step 3: Implement** in `scripts/body_places.py`

Update the module docstring's Usage:

```text
  python3 scripts/body_places.py brief <MMa|MMb> <out.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py check [--final] <proposals.json> /path/to/martyrology-texts [repo_root]
  python3 scripts/body_places.py apply <exported.json> /path/to/martyrology-texts [repo_root]

brief writes what a proposing subagent reads for a half-month (a: days 1-15,
b: 16-31): the Latin and Italian 2004 texts, the opening place, the persons
and the curated items of each eulogy. It quotes the 2004 edition, so it is
written outside the repository (brief refuses a path inside it).
check --final keeps the proposals that still fail under "unqueued" in
data/places_review.json, for docs/places-report.md.
```

Add after `op_id`:

```python
def _text_persons(persons, mrid):
    return [{"name": p["name"]} | ({"n": p["n"]} if p.get("n", 1) != 1 else {})
            for p in persons.get(mrid, []) if p.get("where") == "text"]


def _failure(p, errors):
    return {"eulogy": p.get("eulogy"), "role": p.get("role"), "la": p.get("la"), "errors": errors}


def _key(f):
    return (str(f["eulogy"]), str(f["role"]), str(f["la"]))
```

Replace `check` with:

```python
def check(proposals, curated, review, texts, texts_it, leads, persons, final=False):
    queued = {o["id"] for o in review["operations"]}
    rejected = set(review.get("rejected", []))
    done = {op_id(dict(it, eulogy=m)) for m, items in curated.items() for it in items}
    failures, added, passed = [], 0, set()
    for p in proposals:
        mrid = p.get("eulogy")
        if mrid not in texts:
            failures.append(_failure(p, [f"{mrid}: not a current ID with a Latin text"]))
            continue
        if p.get("confidence") not in CONFIDENCE:
            failures.append(_failure(p, [f"{mrid}: confidence must be one of {', '.join(CONFIDENCE)}"]))
            continue
        item = item_of(p)
        if not {"role", "la"} <= set(item):
            failures.append(_failure(p, [f"{mrid}: a proposal needs role and la"]))
            continue
        oid = op_id(dict(item, eulogy=mrid))
        if oid in queued or oid in rejected or oid in done:
            passed.add(_key(_failure(p, [])))
            continue
        errors = reasoning_errors(mrid, p, texts, texts_it) or _item_errors(
            mrid, item, curated, texts, texts_it, leads, persons)
        if errors:
            failures.append(_failure(p, errors))
            continue
        op = {"op": "add_place", "id": oid, "eulogy": mrid, **item,
              "confidence": p["confidence"], "reasoning": p.get("reasoning", "")}
        who = _text_persons(persons, mrid)
        if len(who) > 1:
            op["persons"] = who
        review["operations"].append(op | {"decision": None, "edited": None})
        queued.add(oid)
        passed.add(_key(_failure(p, [])))
        added += 1
    review["operations"].sort(key=lambda o: o["id"])
    if final:
        new = {_key(f): f for f in failures}
        kept = [f for f in review.get("unqueued", []) if _key(f) not in new and _key(f) not in passed]
        review["unqueued"] = sorted(kept + list(new.values()), key=_key)
    return added, failures
```

Add `brief` and `half_month` after `check`:

```python
def half_month(mm, half):
    return (f"{mm}01", f"{mm}15") if half == "a" else (f"{mm}16", f"{mm}31")


def brief(first, last, texts, texts_it, leads, persons, curated):
    out = []
    for mrid in sorted(m for m in texts if first <= m[3:7] <= last):
        lead = leads.get(mrid)
        out.append({"id": mrid, "la_text": texts[mrid], "it_text": texts_it.get(mrid, ""),
                    "opening": {k: lead[k] for k in ("la", "it", "role") if k in lead} if lead else None,
                    "persons": _text_persons(persons, mrid), "curated": curated.get(mrid, [])})
    return out
```

Replace `main` with:

```python
def main(argv):
    final = "--final" in argv
    argv = [a for a in argv if a != "--final"]
    cmds = {"brief": 4, "check": 3, "apply": 3}
    if not argv or argv[0] not in cmds or len(argv) < cmds[argv[0]]:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "brief":
        which, out, texts_repo = argv[1], Path(argv[2]), Path(argv[3])
        repo_root = Path(argv[4]) if len(argv) > 4 else Path(__file__).resolve().parent.parent
        if out.resolve().is_relative_to(repo_root.resolve()):
            sys.exit(f"{out}: a brief quotes the 2004 edition; write it outside the repository")
        if not re.fullmatch(r"(0[1-9]|1[0-2])[ab]", which):
            sys.exit(f"{which}: expected MMa or MMb (e.g. 01a)")
        curated, _, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
        records = brief(*half_month(which[:2], which[2]), texts, texts_it, leads, persons, curated)
        out.write_text(json.dumps({"batch": which, "eulogies": records}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"{len(records)} eulogies in {out}")
        return 0
    path, texts_repo = Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
    curated, review, texts, texts_it, leads, persons = _load(repo_root, texts_repo)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if cmd == "check":
        added, failures = check(doc["proposals"], curated, review, texts, texts_it, leads, persons, final=final)
        _write(repo_root, curated, review)
        for f in failures:
            print(f"{f['eulogy']} [{f['role']} {f['la']!r}]: " + "; ".join(f["errors"]))
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
```

Note: `brief` is checked for the repository path before anything is loaded, so the test's nonexistent texts path is never read.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_body_places -v 2>&1 | tail -5`
Expected: `OK`.

Then the whole suite: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/body_places.py tests/test_body_places.py
git commit -m "body_places: brief per half-month, structured failures, persons on ops, check --final (#12)"
```

### Task 2: the places report lists proposals that failed the check

**Files:**
- Modify: `scripts/extract_places.py` (`render_report`, `main`)
- Test: `tests/test_places.py` (`UnrecordedTest`)

**Interfaces:**
- Consumes: `review["unqueued"]` records from Task 1 (`{"eulogy","role","la","errors"}`).
- Produces: `result["unqueued"]` read by `render_report`; section `## Proposals that failed the check`.

- [ ] **Step 1: Write the failing test** (in `UnrecordedTest`)

```python
    def test_report_lists_proposals_that_failed_the_check(self):
        r = p.build(BuildTest.ORDER, BuildTest.TX, BuildTest.TY, {}, not_a_place={})
        self.assertIn("## Proposals that failed the check\n\nNone.", p.render_report(r))
        r["unqueued"] = [{"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictlandia",
                          "errors": ["mr:0101-a: la 'in Fictlandia' is not verbatim in the Latin text"]}]
        self.assertIn("- `mr:0101-a` birth *in Fictlandia*: mr:0101-a: la 'in Fictlandia' is not verbatim",
                      p.render_report(r))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_places.UnrecordedTest -v 2>&1 | tail -5`
Expected: FAIL — `'## Proposals that failed the check…' not found`.

- [ ] **Step 3: Implement**

In `render_report`, insert before `"## Entries with no place",`:

```python
        "## Proposals that failed the check",
        "",
        "Body-place proposals that still broke the rules after one correction "
        "(`scripts/body_places.py check --final`); they never reach review.",
        "",
        *([f"- `{f['eulogy']}` {f['role']} *{f['la']}*: {'; '.join(f['errors'])}"
           for f in result.get("unqueued", [])] or ["None."]),
        "",
```

In `main`, before the `places.json` write:

```python
    review_path = repo_root / "data" / "places_review.json"
    if review_path.exists():
        result["unqueued"] = json.loads(review_path.read_text(encoding="utf-8")).get("unqueued", [])
```

- [ ] **Step 4: Run tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`. Then `python3 scripts/extract_places.py ../martyrology-texts && git diff --stat` — Expected: only `docs/places-report.md` changes (the new section, `None.`).

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_places.py tests/test_places.py docs/places-report.md
git commit -m "places report: proposals that failed the check (#12)"
```

### Task 3: the proposal pass (operational)

**Files:**
- Modify: `data/places_review.json`, `docs/places-report.md`
- Scratch only (never committed): `$SCRATCH/body-places/brief-MMx.json`, `$SCRATCH/body-places/proposals-MMx.json`, where `$SCRATCH` is the session scratchpad directory.

No TDD: this task runs the tooling of Task 1 over the data. Its gate is `check` itself plus the committed-data checks.

- [ ] **Step 1: Write the 24 briefs**

```bash
S=$SCRATCH/body-places; mkdir -p "$S"
for m in 01 02 03 04 05 06 07 08 09 10 11 12; do for h in a b; do
  python3 scripts/body_places.py brief $m$h "$S/brief-$m$h.json" ../martyrology-texts; done; done
```

Expected: 24 lines `N eulogies in …`, N summing to the current eulogies with a Latin text (about 6,000).

- [ ] **Step 2: Dispatch the proposing subagents, four at a time** (Agent tool, `general-purpose`, one per batch; send four in one message, the next four when they finish). The prompt, with `MMx` and `$S` substituted:

```text
You are proposing body places for the Roman Martyrology (crmedr issue #12). Read
$S/brief-MMx.json: for each eulogy it gives the Latin 2004 text (la_text), the Italian
CEI text (it_text), the opening place already recorded (opening), the persons named
in the text (persons) and places already curated (curated).

For EVERY place the eulogy names OTHER than its opening place (and other than the
curated items), write one proposal. A place named twice with two roles is two
proposals. Fields:
- eulogy: the eulogy id.
- role: one of death, burial, translation, dedication, cult, birth, education,
  religious_life, ministry, foundation, exile, journey, mention.
  death = died or martyred elsewhere than the opening place; ministry = a see, parish,
  office or mission field (an adjectival see like "Morinensem" counts); foundation =
  something founded there; religious_life = a monastery or house entered, professed
  or lived in; journey = pilgrimage, travel, passing through; exile = exile,
  deportation, imprisonment; mention = any other place named (a council, another
  person's see, a battle).
- la: the place designation copied EXACTLY from la_text (same accents, case and
  punctuation inside it), place words only, at most 12 words; leave the cue word out
  ("Nursiæ in Umbria", not "Nursiæ in Umbria natus"); keep a preposition only when it
  belongs to the designation as printed ("in Polonia").
- it: the matching designation copied EXACTLY from it_text (at most 20 words), or omit
  it when the Italian has no counterpart.
- occurrence: only when la is printed more than once in la_text: which printing (1, 2,
  …). occurrence_it likewise for it in it_text.
- person (and n): only when persons lists several and the role is one person's: that
  person's name as given in persons (and its n when it has one).
- confidence: high, medium or low.
- reasoning: one short English sentence (at most 300 characters) saying why this role.
  Never copy four or more consecutive words of the Latin or Italian text other than the
  place designation itself.

Do not propose the opening place again, a place inside the opening place's words, a
person's name, a church dedication title that is not a place, or anything in a
footnote. Do not guess Wikidata items.

Write {"proposals": [...]} to $S/proposals-MMx.json and reply only with the number of
eulogies read and proposals written.
```

- [ ] **Step 3: Check each batch as it returns** (sequentially: `check` rewrites `data/places_review.json`)

Run: `python3 scripts/body_places.py check "$S/proposals-MMx.json" ../martyrology-texts`
Expected: `K queued; F failed; T awaiting review`, with the F failures printed one per line.

- [ ] **Step 4: One correction round per batch with failures**

Send the printed failures to the same subagent (SendMessage): "These proposals failed the check; fix each (or drop it if it is not a place) and write only the corrected ones to `$S/fix-MMx.json` as `{"proposals": [...]}`." Then:

Run: `python3 scripts/body_places.py check --final "$S/fix-MMx.json" ../martyrology-texts`
Expected: `K queued; F failed`; the F still failing are kept under `unqueued`.

For a batch whose first check had no failures, nothing more. A batch whose first check failed but whose fix file is empty: run `check --final` on the first file again so its failures are recorded.

- [ ] **Step 5: Verify the committed data**

```bash
python3 scripts/extract_places.py ../martyrology-texts
python3 -m unittest discover -s tests 2>&1 | tail -3
python3 scripts/registry_places.py --check && python3 scripts/build_gazetteer.py check
git status --short
```

Expected: tests `OK`; both checks exit 0; changed files are `data/places_review.json` and `docs/places-report.md` only (`data/places.json` unchanged: nothing is curated yet). Spot-check five ops from different months by reading their eulogies in `../martyrology-texts`, and grep the change-set for 4-word quotations: `check` already rejects them, so this is a read, not a gate.

- [ ] **Step 6: Commit, push, open the PR**

```bash
git add data/places_review.json docs/places-report.md
git commit -m "places: add_place proposals for every eulogy's body places, checked (#12)"
git push -u origin feat/body-places-proposals
gh pr create --title "Body places: the proposal pass (#12)" --body "…"
```

The PR body states the counts (queued, by role, by confidence, unqueued), that the model decided nothing, and that the review card is martyrology-frontend's PR. End it with the footer from Global Constraints.

---

## Part B — martyrology-frontend (branch `feat/add-place-card` from `main`)

### Task 4: the `add_place` op type and printing helpers

**Files:**
- Modify: `lib/changeset.ts`
- Create: `lib/body-places.ts`
- Test: `lib/__tests__/changeset.test.ts`, `lib/__tests__/body-places.test.ts`

**Interfaces:**
- Produces:
  - `PLACE_ROLES: readonly PlaceRole[]` (the 13 roles, in the spec's order) and `type PlaceRole`.
  - `printings(text: string, form: string): number[]` — start offsets of exact, non-overlapping printings (as crmedr's `occurrences`).
  - `printingSpan(text: string, form: string, n?: number | null): { start: number; end: number } | null` — the nth (from 1, default 1) printing.
  - `interface AddPlaceOp extends Base { op: "add_place"; id; eulogy; role: PlaceRole; la; it?; person?; n?; occurrence?; occurrence_it?; persons?: { name: string; n?: number }[] }`.
  - `EditedFields` gains `role?: PlaceRole; la?: string; it?: string | null; person?: string | null; n?: number | null; occurrence?: number | null; occurrence_it?: number | null`.
  - `isAdjudicable` is true for `add_place`.

- [ ] **Step 1: Write the failing tests**

`lib/__tests__/body-places.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { PLACE_ROLES, printings, printingSpan } from "@/lib/body-places";

describe("body places", () => {
  it("lists the thirteen roles", () => {
    expect(PLACE_ROLES).toHaveLength(13);
    expect(PLACE_ROLES[0]).toBe("death");
    expect(PLACE_ROLES).toContain("religious_life");
  });

  it("finds exact, non-overlapping printings", () => {
    expect(printings("Romæ natus, Romæ sepultus", "Romæ")).toEqual([0, 12]);
    expect(printings("aaaa", "aa")).toEqual([0, 2]);
    expect(printings("Romæ", "")).toEqual([]);
  });

  it("gives the nth printing's span", () => {
    expect(printingSpan("Romæ natus, Romæ sepultus", "Romæ", 2)).toEqual({ start: 12, end: 16 });
    expect(printingSpan("Romæ natus", "Romæ")).toEqual({ start: 0, end: 4 });
    expect(printingSpan("Romæ natus", "Romæ", 2)).toBeNull();
    expect(printingSpan("Romæ natus", "Parisiis")).toBeNull();
  });
});
```

In `lib/__tests__/changeset.test.ts`, add:

```ts
  it("an add_place op is adjudicable and keyed by its id", () => {
    const op = { op: "add_place", id: "mr:0711-benedictus#birth#Núrsiæ in Umbria", eulogy: "mr:0711-benedictus",
      role: "birth", la: "Núrsiæ in Umbria", decision: null } as const;
    expect(isAdjudicable(op as Op)).toBe(true);
    expect(opId(op as Op)).toBe("mr:0711-benedictus#birth#Núrsiæ in Umbria");
  });
```

(Import `isAdjudicable`, `opId`, `type Op` there if the file does not already.)

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run lib/__tests__/body-places.test.ts lib/__tests__/changeset.test.ts`
Expected: FAIL — cannot resolve `@/lib/body-places`; `isAdjudicable` returns false.

- [ ] **Step 3: Implement**

`lib/body-places.ts`:

```ts
/** The role a place plays in one eulogy (crmedr's ROLES in scripts/extract_places.py). */
export const PLACE_ROLES = [
  "death", "burial", "translation", "dedication", "cult", "birth", "education",
  "religious_life", "ministry", "foundation", "exile", "journey", "mention",
] as const;

export type PlaceRole = (typeof PLACE_ROLES)[number];

/** Start offsets of the exact, non-overlapping printings of form in text (crmedr's `occurrences`). */
export function printings(text: string, form: string): number[] {
  const out: number[] = [];
  if (!form) return out;
  for (let i = text.indexOf(form); i >= 0; i = text.indexOf(form, i + form.length)) out.push(i);
  return out;
}

/** The nth printing (from 1) of form in text, or null. */
export function printingSpan(text: string, form: string, n?: number | null): { start: number; end: number } | null {
  const start = printings(text, form)[(n ?? 1) - 1];
  return start === undefined ? null : { start, end: start + form.length };
}
```

In `lib/changeset.ts`: `import type { PlaceRole } from "@/lib/body-places";`; add to `EditedFields` (after the `resolve_place` fields):

```ts
  // add_place: the item's fields; null removes an optional one
  role?: PlaceRole;
  la?: string;
  it?: string | null;
  person?: string | null;
  n?: number | null;
  occurrence?: number | null;
  occurrence_it?: number | null;
```

Add after `ResolvePlaceOp`:

```ts
/**
 * A place a eulogy names outside its opening place, with its role (crmedr's
 * scripts/body_places.py). `la` / `it` are the place designation as printed in the
 * Latin and Italian 2004 texts; `occurrence` / `occurrence_it` pick the printing when
 * it is printed more than once; `person` / `n` say whose role it is. `persons` lists
 * the eulogy's persons when it has several. Keyed `<eulogy>#<role>#<la>[#occ][#person[#n]]`.
 */
export interface AddPlaceOp extends Base {
  op: "add_place";
  id: string;
  eulogy: string;
  role: PlaceRole;
  la: string;
  it?: string;
  person?: string;
  n?: number;
  occurrence?: number;
  occurrence_it?: number;
  persons?: { name: string; n?: number }[];
}
```

Add `| AddPlaceOp` to `Op` (after `ResolvePlaceOp`) and `op.op === "add_place" ||` to `isAdjudicable`.

- [ ] **Step 4: Run tests**

Run: `npx vitest run lib/__tests__/body-places.test.ts lib/__tests__/changeset.test.ts && npx tsc --noEmit`
Expected: PASS; no type errors.

- [ ] **Step 5: Commit**

```bash
git add lib/body-places.ts lib/changeset.ts lib/__tests__/body-places.test.ts lib/__tests__/changeset.test.ts
git commit -m "review: the add_place op (crmedr#12)"
```

### Task 5: `AddPlaceCard`

**Files:**
- Create: `components/AddPlaceCard.tsx`
- Modify: `components/OperationCard.tsx`, `messages/{en,it,fr,de,es,pt}.json`
- Test: `components/__tests__/AddPlaceCard.test.tsx`

**Interfaces:**
- Consumes: `AddPlaceOp`, `EditedFields`, `DecisionRecord` (Task 4); `PLACE_ROLES`, `printings`, `printingSpan` (Task 4); `getElogium` (`lib/api.ts`); `decisionClass`, `decisionLabel`.
- Produces: `default function AddPlaceCard({ op, decision, onDecide }: { op: AddPlaceOp; decision?: DecisionRecord; onDecide: (id: string, d: DecisionRecord) => void })`; `data-testid="op-card-<id>"`.

Behaviour:
- Fetches the eulogy once (`getElogium(op.eulogy)`) and shows the Latin (`martyrologium_romanum_2004`) and Italian (`martyrologium_romanum_2004_it_IT`) texts side by side, each as plain text with the chosen printing in a `<mark>` (`data-testid="la-mark"` / `"it-mark"`); a form not printed shows the warning `Review.addPlace.notPrinted`.
- Header: role label, `la` and `it`, the person when given, confidence and reasoning.
- Accept (unchanged) → `{decision: "accept"}`; Reject → `{decision: "reject"}`.
- Edit opens: role `<select>` (13 roles, labelled), `la` and `it` text inputs, a printing `<select>` for each when its form is printed more than once (1…count), a person `<select>` (`—` plus each of `op.persons`, shown only when `op.persons` has entries). Save sends `{decision: "edit", edited}` with only the changed fields; an emptied `it`, a cleared person, an occurrence back to the only printing → `null`. Save is disabled while `la` is not printed in the Latin text, or is printed more than once with no printing chosen.

- [ ] **Step 1: Write the failing tests** — `components/__tests__/AddPlaceCard.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@/test/intl";
import OperationCard from "@/components/OperationCard";
import AddPlaceCard from "@/components/AddPlaceCard";
import type { AddPlaceOp } from "@/lib/changeset";

const { getElogium } = vi.hoisted(() => ({ getElogium: vi.fn() }));
vi.mock("@/lib/api", () => ({
  getElogium,
  ApiError: class ApiError extends Error { status = 0; title = ""; },
}));

const LA = "Fictopoli, sanctorum Ficti et Fictitii, qui Romæ nati et Romæ sepulti sunt.";
const IT = "A Fictopoli, santi Fitto e Fittizio, nati a Roma e sepolti a Roma.";

function op(extra: Partial<AddPlaceOp> = {}): AddPlaceOp {
  return { op: "add_place", id: "mr:0101-ficti#burial#Romæ#2", eulogy: "mr:0101-ficti", role: "burial",
    la: "Romæ", it: "a Roma", occurrence: 2, occurrence_it: 2, confidence: "high",
    reasoning: "Buried there.", decision: null, persons: [{ name: "Fictus" }, { name: "Fictitius" }], ...extra };
}

beforeEach(() => {
  getElogium.mockReset();
  getElogium.mockResolvedValue({ id: "mr:0101-ficti", subject: {}, anchor_day: "01-01", deprecated: false,
    editions: { martyrologium_romanum_2004: { text: LA }, martyrologium_romanum_2004_it_IT: { text: IT } } });
});

describe("AddPlaceCard", () => {
  it("marks the chosen printing in both texts", async () => {
    render(<AddPlaceCard op={op()} onDecide={vi.fn()} />);
    const la = await screen.findByTestId("la-mark");
    expect(la.textContent).toBe("Romæ");
    expect(la.previousSibling?.textContent).toBe(LA.slice(0, LA.lastIndexOf("Romæ")));
    expect((await screen.findByTestId("it-mark")).previousSibling?.textContent).toBe(IT.slice(0, IT.lastIndexOf("a Roma")));
    expect(screen.getByText("burial")).toBeTruthy();
  });

  it("accepts and rejects", async () => {
    const onDecide = vi.fn();
    render(<AddPlaceCard op={op()} onDecide={onDecide} />);
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(onDecide).toHaveBeenLastCalledWith(op().id, { decision: "accept" });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onDecide).toHaveBeenLastCalledWith(op().id, { decision: "reject" });
  });

  it("an edit sends only the changed fields", async () => {
    const onDecide = vi.fn();
    render(<AddPlaceCard op={op()} onDecide={onDecide} />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "death" } });
    fireEvent.change(screen.getByLabelText("Person"), { target: { value: "Fictitius" } });
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    expect(onDecide).toHaveBeenLastCalledWith(op().id, { decision: "edit", edited: { role: "death", person: "Fictitius" } });
  });

  it("clearing the Italian sends null", async () => {
    const onDecide = vi.fn();
    render(<AddPlaceCard op={op()} onDecide={onDecide} />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Italian"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    expect(onDecide).toHaveBeenLastCalledWith(op().id, { decision: "edit", edited: { it: null, occurrence_it: null } });
  });

  it("asks which printing and blocks a Latin form not printed", async () => {
    render(<AddPlaceCard op={op({ id: "x", la: "Fictopoli", occurrence: undefined, it: undefined, occurrence_it: undefined })} onDecide={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Latin"), { target: { value: "Romæ" } });
    expect(screen.getByRole("button", { name: "Save edit" })).toHaveProperty("disabled", true);
    fireEvent.change(screen.getByLabelText("Latin printing"), { target: { value: "1" } });
    expect(screen.getByRole("button", { name: "Save edit" })).toHaveProperty("disabled", false);
    fireEvent.change(screen.getByLabelText("Latin"), { target: { value: "Parisiis" } });
    expect(screen.getByText("Not printed in this text.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save edit" })).toHaveProperty("disabled", true);
  });

  it("OperationCard routes add_place here", async () => {
    render(<OperationCard op={op()} onDecide={vi.fn()} locale="la" baseEdition="martyrologium_romanum_2004" />);
    expect(await screen.findByTestId("la-mark")).toBeTruthy();
  });
});
```

The role is shown by its label: the test expects the English label of `burial` to be `burial`; use labels as listed below.

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run components/__tests__/AddPlaceCard.test.tsx`
Expected: FAIL — cannot resolve `@/components/AddPlaceCard`.

- [ ] **Step 3: Implement**

`messages/en.json` → `Review.addPlace`:

```json
"addPlace": {
  "title": "Place named in the eulogy",
  "latin": "Latin",
  "italian": "Italian",
  "latinPrinting": "Latin printing",
  "italianPrinting": "Italian printing",
  "role": "Role",
  "person": "Person",
  "everyone": "—",
  "notPrinted": "Not printed in this text.",
  "choosePrinting": "Printed {count} times: choose which.",
  "whose": "whose: {person}",
  "confidence": "confidence: {value}",
  "loading": "Loading the texts…",
  "unavailable": "The texts could not be loaded.",
  "roles": {
    "death": "death", "burial": "burial", "translation": "translation", "dedication": "dedication",
    "cult": "cult", "birth": "birth", "education": "education", "religious_life": "religious life",
    "ministry": "ministry", "foundation": "foundation", "exile": "exile", "journey": "journey",
    "mention": "mention"
  }
}
```

The five other locales get the same keys translated (Italian: "Luogo nominato nell'elogio", "Latino", "Italiano", "Stampa latina", "Stampa italiana", "Ruolo", "Persona", "—", "Non stampato in questo testo.", "Stampato {count} volte: scegli quale.", "di chi: {person}", "affidabilità: {value}", "Caricamento dei testi…", "Impossibile caricare i testi.", roles "morte, sepoltura, traslazione, dedicazione, culto, nascita, formazione, vita religiosa, ministero, fondazione, esilio, viaggio, menzione"; French, German, Spanish, Portuguese likewise). `everyone` ("—") is the same in every locale: add `"Review.addPlace.everyone": ALL` to `SAME_AS_ENGLISH` in `lib/__tests__/messages.test.ts` if that test flags identical strings.

`components/AddPlaceCard.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { getElogium } from "@/lib/api";
import { PLACE_ROLES, printings, printingSpan, type PlaceRole } from "@/lib/body-places";
import { decisionClass, decisionLabel } from "@/components/decisionClass";
import type { AddPlaceOp, DecisionRecord, EditedFields } from "@/lib/changeset";

const LATIN = "martyrologium_romanum_2004";
const ITALIAN = "martyrologium_romanum_2004_it_IT";

interface Props {
  op: AddPlaceOp;
  decision?: DecisionRecord;
  onDecide: (id: string, d: DecisionRecord) => void;
}

/** One text with the nth printing of form marked; nothing marked when it is not printed. */
function Marked({ text, form, n, testId }: { text: string; form: string; n?: number | null; testId: string }) {
  const span = form ? printingSpan(text, form, n) : null;
  if (!span) return <span className="font-serif">{text}</span>;
  return (
    <span className="font-serif">
      <span>{text.slice(0, span.start)}</span>
      <mark data-testid={testId} className="rounded-sm bg-amber-200 px-0.5 dark:bg-amber-700/60">
        {text.slice(span.start, span.end)}
      </mark>
      <span>{text.slice(span.end)}</span>
    </span>
  );
}

/**
 * Review card for crmedr's `add_place` op: a place the eulogy names outside its opening
 * place, with its role. Both 2004 texts are shown with the proposed printing marked; an
 * edit may change the role, the words (as printed), which printing, and whose role it
 * is. crmedr's `body_places.py apply` validates the result again.
 */
export default function AddPlaceCard({ op, decision, onDecide }: Props) {
  const t = useTranslations("Review.addPlace");
  const tr = useTranslations("Review");
  const [texts, setTexts] = useState<{ la: string; it: string } | null>(null);
  const [failed, setFailed] = useState(false);
  const ed = decision?.decision === "edit" ? decision.edited : undefined;
  const [editing, setEditing] = useState(false);
  const [role, setRole] = useState<PlaceRole>(ed?.role ?? op.role);
  const [la, setLa] = useState(ed?.la ?? op.la);
  const [it, setIt] = useState(ed?.it === null ? "" : (ed?.it ?? op.it ?? ""));
  const [occ, setOcc] = useState<number | null>(ed?.occurrence !== undefined ? ed.occurrence : (op.occurrence ?? null));
  const [occIt, setOccIt] = useState<number | null>(
    ed?.occurrence_it !== undefined ? ed.occurrence_it : (op.occurrence_it ?? null));
  // A person is "Name", or "Name#n" for the nth person of a name (n from 2), as option values.
  const personKey = (name?: string | null, n?: number | null) => (name ? (n && n > 1 ? `${name}#${n}` : name) : "");
  const [person, setPerson] = useState(
    ed?.person !== undefined ? personKey(ed.person, ed.n) : personKey(op.person, op.n));

  useEffect(() => {
    let cancelled = false;
    getElogium(op.eulogy)
      .then((e) => {
        if (!cancelled) setTexts({ la: e.editions[LATIN]?.text ?? "", it: e.editions[ITALIAN]?.text ?? "" });
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [op.eulogy]);

  const laCount = texts ? printings(texts.la, la).length : 0;
  const itCount = texts && it ? printings(texts.it, it).length : 0;
  // A form printed once needs no printing; printed several times, one must be chosen.
  const laOcc = laCount > 1 ? occ : null;
  const itOcc = itCount > 1 ? occIt : null;
  const canSave = laCount === 1 || (laCount > 1 && laOcc !== null && laOcc <= laCount);

  const [pName, pNs] = person ? person.split("#") : [null, undefined];
  const pN = pNs ? Number(pNs) : null;
  const save = () => {
    const edited: EditedFields = {};
    if (role !== op.role) edited.role = role;
    if (la !== op.la) edited.la = la;
    if ((it || null) !== (op.it ?? null)) edited.it = it || null;
    if (laOcc !== (op.occurrence ?? null)) edited.occurrence = laOcc;
    if (itOcc !== (op.occurrence_it ?? null)) edited.occurrence_it = itOcc;
    if (pName !== (op.person ?? null)) edited.person = pName;
    if ((pN && pN > 1 ? pN : null) !== (op.n ?? null)) edited.n = pN && pN > 1 ? pN : null;
    onDecide(op.id, Object.keys(edited).length ? { decision: "edit", edited } : { decision: "accept" });
    setEditing(false);
  };

  const printingSelect = (label: string, count: number, value: number | null, set: (n: number | null) => void) =>
    count > 1 && (
      <label className="flex items-center gap-2 text-xs">
        {label}
        <select
          aria-label={label}
          className="rounded border border-slate-300 px-1 py-0.5 dark:border-slate-700 dark:bg-slate-900"
          value={value ?? ""}
          onChange={(e) => set(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">{t("choosePrinting", { count })}</option>
          {Array.from({ length: count }, (_, i) => (
            <option key={i + 1} value={i + 1}>{i + 1}</option>
          ))}
        </select>
      </label>
    );

  const input = "flex-1 rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900";
  return (
    <div className={`mb-3 rounded border p-3 text-sm ${decisionClass(decision)}`} data-testid={`op-card-${op.id}`}>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{op.op} · {op.eulogy}</span>
        {decision && (
          <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-medium dark:bg-slate-800">
            {decisionLabel(tr, decision)}
          </span>
        )}
      </div>
      <p className="mb-1">
        <span className="mr-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium dark:bg-amber-900/50">
          {t(`roles.${role}`)}
        </span>
        <span className="font-semibold">{la}</span>
        {it && <span className="text-slate-600 dark:text-slate-400"> · {it}</span>}
        {pName && <span className="text-xs text-slate-500 dark:text-slate-400"> · {t("whose", { person: pName })}</span>}
      </p>
      <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
        {op.confidence ? t("confidence", { value: op.confidence }) : ""}
        {op.reasoning ? ` · ${op.reasoning}` : ""}
      </p>

      {!texts && !failed && <p className="text-slate-500 dark:text-slate-400">{t("loading")}</p>}
      {failed && <p className="text-red-600 dark:text-red-400">{t("unavailable")}</p>}
      {texts && (
        <div className="mb-2 grid gap-3 rounded bg-slate-50 p-2 sm:grid-cols-2 dark:bg-slate-900">
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">{t("latin")}</p>
            <Marked text={texts.la} form={la} n={laOcc} testId="la-mark" />
            {laCount === 0 && <p className="text-xs text-amber-700 dark:text-amber-400">{t("notPrinted")}</p>}
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">{t("italian")}</p>
            <Marked text={texts.it} form={it} n={itOcc} testId="it-mark" />
            {it && itCount === 0 && <p className="text-xs text-amber-700 dark:text-amber-400">{t("notPrinted")}</p>}
          </div>
        </div>
      )}

      {!editing ? (
        <div className="flex gap-2">
          <button type="button" className="rounded bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700"
            onClick={() => onDecide(op.id, { decision: "accept" })}>{tr("actions.accept")}</button>
          <button type="button" className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
            onClick={() => onDecide(op.id, { decision: "reject" })}>{tr("actions.reject")}</button>
          <button type="button" className="rounded bg-slate-600 px-2 py-1 text-xs font-medium text-white hover:bg-slate-700"
            onClick={() => setEditing(true)}>{tr("actions.edit")}</button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-xs">
            {t("role")}
            <select aria-label={t("role")} className={input} value={role} onChange={(e) => setRole(e.target.value as PlaceRole)}>
              {PLACE_ROLES.map((r) => <option key={r} value={r}>{t(`roles.${r}`)}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs">
            {t("latin")}
            <input aria-label={t("latin")} className={input} value={la} onChange={(e) => setLa(e.target.value)} />
          </label>
          {printingSelect(t("latinPrinting"), laCount, laOcc, setOcc)}
          <label className="flex items-center gap-2 text-xs">
            {t("italian")}
            <input aria-label={t("italian")} className={input} value={it} onChange={(e) => setIt(e.target.value)} />
          </label>
          {printingSelect(t("italianPrinting"), itCount, itOcc, setOccIt)}
          {op.persons && op.persons.length > 0 && (
            <label className="flex items-center gap-2 text-xs">
              {t("person")}
              <select aria-label={t("person")} className={input} value={person} onChange={(e) => setPerson(e.target.value)}>
                <option value="">{t("everyone")}</option>
                {op.persons.map((p) => (
                  <option key={personKey(p.name, p.n)} value={personKey(p.name, p.n)}>
                    {p.name}{p.n ? ` (${p.n})` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="flex gap-2">
            <button type="button" disabled={!canSave}
              className="rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-40"
              onClick={save}>{tr("actions.saveEdit")}</button>
            <button type="button" className="rounded bg-slate-400 px-2 py-1 text-xs font-medium text-white hover:bg-slate-500"
              onClick={() => setEditing(false)}>{tr("actions.cancel")}</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

Ruling to record if the test disagrees: in `an edit sends only the changed fields`, the op's `it` "a Roma" is printed twice, so `occurrence_it` 2 stays unchanged and is not sent; in `clearing the Italian sends null`, `itCount` becomes 0, so `itOcc` is null and differs from the op's 2: `occurrence_it: null` is sent with `it: null`, which is what `apply` needs (an `occurrence_it` with no `it` would be stale).

In `components/OperationCard.tsx`: `import AddPlaceCard from "@/components/AddPlaceCard";`, `type AddPlaceOp` in the changeset import, and before the `resolve_person` branch:

```tsx
  // A place a eulogy names, with its role (crmedr body places): both 2004 texts, the printing marked.
  if (props.op.op === "add_place") {
    return <AddPlaceCard op={props.op as AddPlaceOp} decision={props.decision} onDecide={props.onDecide} />;
  }
```

- [ ] **Step 4: Run tests**

Run: `npx vitest run components/__tests__/AddPlaceCard.test.tsx lib/__tests__/messages.test.ts && npx tsc --noEmit && npx eslint components/AddPlaceCard.tsx components/OperationCard.tsx`
Expected: PASS; no type or lint errors.

- [ ] **Step 5: Commit**

```bash
git add components/AddPlaceCard.tsx components/OperationCard.tsx components/__tests__/AddPlaceCard.test.tsx messages/*.json lib/__tests__/messages.test.ts
git commit -m "review: the add_place card, both 2004 texts with the printing marked (crmedr#12)"
```

### Task 6: bulk accept by confidence

**Files:**
- Modify: `components/ReviewPage.tsx`, `messages/{en,it,fr,de,es,pt}.json`
- Test: `components/__tests__/ReviewPage.test.tsx`

**Interfaces:**
- Consumes: `filteredOps`, `decisions`, `onDecide`/`saveDecisions` in `ReviewPage`; `opId`.
- Produces: a button `Review.bulkAccept` ("Accept the {count} undecided shown") visible when the confidence filter is set and the op filter is `add_place`; one click asks inline (`Review.bulkConfirm`: "Accept {count}?" with Confirm / Cancel); confirming accepts every undecided `add_place` op in `filteredOps` (all pages, not only the rendered ones) in one `saveDecisions`.

- [ ] **Step 1: Write the failing test** — append to `components/__tests__/ReviewPage.test.tsx`, following how that file already loads a change-set (reuse its upload/fetch helper; read the top of the file first):

```tsx
  it("bulk-accepts the undecided add_place ops of one confidence", async () => {
    const ops = [
      { op: "add_place", id: "a#birth#Romæ", eulogy: "a", role: "birth", la: "Romæ", confidence: "high", decision: null },
      { op: "add_place", id: "b#birth#Romæ", eulogy: "b", role: "birth", la: "Romæ", confidence: "high", decision: null },
      { op: "add_place", id: "c#birth#Romæ", eulogy: "c", role: "birth", la: "Romæ", confidence: "low", decision: null },
    ];
    await loadChangeset({ schema: "crmedr-changeset/v1", generated_by: "t", base: { edition: "martyrologium_romanum_2004", registry: "r" }, operations: ops });
    expect(screen.queryByRole("button", { name: /Accept the \d+ undecided shown/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Op"), { target: { value: "add_place" } });
    fireEvent.change(screen.getByLabelText("Confidence"), { target: { value: "high" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept the 2 undecided shown" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(screen.getByText("2 accepted")).toBeTruthy();
    expect(screen.getByText("1 undecided")).toBeTruthy();
  });
```

`loadChangeset` stands for the file's existing way of loading a change-set object into the page; if the file has no helper, write one at the top that uploads a `File` with the JSON through the upload input, as its existing tests do. The labels `Op` / `Confidence` are the filter labels' English texts (`Review.filters.op`, `Review.filters.confidence`); if the selects are not labelled that way, query them as the file's existing filter tests do.

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run components/__tests__/ReviewPage.test.tsx`
Expected: FAIL — no button named "Accept the 2 undecided shown".

- [ ] **Step 3: Implement**

Messages (`en`): `"bulkAccept": "Accept the {count} undecided shown"`, `"bulkConfirm": "Accept {count}?"`, `"confirm": "Confirm"` under `Review` (skip `confirm` if `Review.actions` already has an equivalent and use that). Translate in the five other locales.

In `ReviewPage`:

```tsx
  const [bulkAsk, setBulkAsk] = useState(false);
  const bulkTargets = useMemo(
    () => (opFilter === "add_place" && confidenceFilter
      ? filteredOps.filter((op) => op.op === "add_place" && !decisions[opId(op)])
      : []),
    [filteredOps, opFilter, confidenceFilter, decisions],
  );
  const bulkAccept = () => {
    if (!cs) return;
    const next = { ...decisions };
    for (const op of bulkTargets) next[opId(op)] = { decision: "accept" };
    setDecisions(next);
    saveDecisions(decisionsKey(cs), next);
    setBulkAsk(false);
  };
```

Render it just above the cards list (`<div className="mt-4">` holding `filteredOps.slice…`):

```tsx
            {bulkTargets.length > 0 && (
              <div className="mb-2 flex items-center gap-2 text-sm">
                {!bulkAsk ? (
                  <button type="button" className="rounded bg-green-700 px-2 py-1 text-xs font-medium text-white hover:bg-green-800"
                    onClick={() => setBulkAsk(true)}>{t("bulkAccept", { count: bulkTargets.length })}</button>
                ) : (
                  <>
                    <span>{t("bulkConfirm", { count: bulkTargets.length })}</span>
                    <button type="button" className="rounded bg-green-700 px-2 py-1 text-xs font-medium text-white"
                      onClick={bulkAccept}>{t("confirm")}</button>
                    <button type="button" className="rounded bg-slate-400 px-2 py-1 text-xs font-medium text-white"
                      onClick={() => setBulkAsk(false)}>{t("actions.cancel")}</button>
                  </>
                )}
              </div>
            )}
```

- [ ] **Step 4: Run tests**

Run: `npm test 2>&1 | tail -5 && npx tsc --noEmit && npm run lint`
Expected: all tests pass; no type or lint errors.

- [ ] **Step 5: Commit**

```bash
git add components/ReviewPage.tsx components/__tests__/ReviewPage.test.tsx messages/*.json
git commit -m "review: accept the undecided add_place ops of one confidence at once (crmedr#12)"
```

### Task 7: bundle the change-set and open the PR

**Files:**
- Create: `changesets/places-review.json` (copy of crmedr's `data/places_review.json` from Task 3)
- Modify: `changesets/index.json`

- [ ] **Step 1: Copy and list it**

```bash
cp ../crmedr/data/places_review.json changesets/places-review.json
python3 - <<'EOF'
import json; p = "changesets/index.json"; d = json.load(open(p))
d["changesets"] = sorted(set(d["changesets"]) | {"places-review.json"}); open(p, "w").write(json.dumps(d, indent=1) + "\n")
EOF
```

- [ ] **Step 2: Verify**

Run: `npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5`
Expected: tests pass (the bundled change-sets test, if any, parses the new file); the build succeeds.

- [ ] **Step 3: Commit, push, open the PR**

```bash
git add changesets/places-review.json changesets/index.json
git commit -m "changesets: the body-places review queue (crmedr#12)"
git push -u origin feat/add-place-card
gh pr create --title "Review card for add_place: places a eulogy names, with their roles (crmedr#12)" --body "…"
```

The PR body describes the card, the bulk accept, the bundled queue (its op count) and links the crmedr PR from Task 3; footer as in Global Constraints. After both PRs merge and the frontend deploys, the user reviews at /review, exports, and `body_places.py apply` (spec rollout step 4) follows.
