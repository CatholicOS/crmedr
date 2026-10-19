# Apply renames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/apply_renames.py` applies the decided `rename` ops of a review change-set: `texts` re-keys martyrology-texts' 2004 editions, `crmedr` renames the ID across crmedr, writes the new subject labels, rebuilds the registry and runs the tests.

**Architecture:** Pure functions for the rename table and its checks; a textual re-key (replace the quoted ID, `"old"` and `"old|`, in a file's text, then check it still parses as JSON / Python) so every file keeps its exact formatting and key order; two thin subcommands on top. Patterned on `build_person_items.py apply` (all-or-nothing) and `body_places.py` (CLI shape).

**Tech Stack:** Python 3 standard library; `unittest`; `git ls-files` via `subprocess`.

**Spec:** `docs/superpowers/specs/2026-10-19-apply-renames-design.md`

## Global Constraints

- Nothing is written unless every rename passes the checks; `--dry-run` writes nothing.
- A decision: `accept` → `op.new_id`; `edit` → `edited.new_id`; `reject` → skipped. Only `op == "rename"` ops with a decision count.
- Labels: from the candidate whose `new_id` is the applied ID (`labels.la/en/it`); `edited.subject_la` non-empty overrides the Latin; `""` and `null` mean "leave that language's subject unchanged".
- Re-key rule: a JSON string that is exactly `old` or starts with `old|` takes `new` (so `mr:0101-basilius-magnus` is never touched by renaming `mr:0101-basilius`). Implemented textually: `"old"` → `"new"` and `"old|` → `"new|`.
- crmedr files: only tracked files (`git ls-files data i18n`) plus `scripts/extract_registry.py`; never an untracked file.
- texts files: `data/editions/{martyrologium_romanum_2004, martyrologium_romanum_2004_it_IT, martyrologium_romanum_2004_en_unofficial}/*.json`.
- Idempotent: an old ID absent from the registry whose new ID is present is "already applied" and skipped (both subcommands, judged against crmedr's registry).
- New-ID checks: `^mr:\d{4}-[a-z]+(?:-[a-z]+)*$`, same MMDD as the old ID, no numeric token, not an existing current or deprecated ID, unique among the run's new IDs, not another rename's old ID.
- Standard library only; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` + Claude-Session line.

## Review Focus

- A rename whose old ID is a prefix of another ID (`mr:0101-basilius` vs `mr:0101-basilius-magnus-…`): the longer one must be untouched. → Task 2.
- A file where the old ID occurs inside a longer text (a note mentioning it in prose without quotes): left alone — only quoted IDs change. → Task 2.
- An edit with `subject_la: ""`: the Latin subject stays as it was. → Task 1.
- Running `crmedr` twice with the same file: the second run changes nothing and reports every rename as already applied. → Task 3.
- `extract_registry.py` or the test suite failing after the writes: exit non-zero, files left for `git diff`. → Task 3.

---

### Task 1: The rename table and its checks

**Files:**
- Create: `scripts/apply_renames.py`
- Test: `tests/test_apply_renames.py`

**Interfaces:**
- Produces:
  - `Rename = NamedTuple("Rename", old: str, new: str, labels: dict[str, str | None])` (keys `la`, `en`, `it`).
  - `renames(changeset: dict) -> list[Rename]` — from the decided rename ops (see Global Constraints), in file order.
  - `split_applied(rs: list[Rename], ids: set[str]) -> tuple[list[Rename], list[Rename]]` — (to apply, already applied); `ids` = every ID of `data/martyrology_ids.json`.
  - `check(rs: list[Rename], ids: set[str]) -> list[str]` — error strings (empty = all pass), e.g. `"mr:0101-x → mr:0102-x: the day changes"`, `"… : a numeric token"`, `"… : mr:0101-y already exists"`, `"… : no such ID"`, `"… : two renames give mr:0101-y"`, `"… : mr:0101-y is renamed too"`, `"… : not mr:MMDD-slug"`.

- [ ] **Step 1: Write the failing tests** — accept/edit/reject table (edit with `subject_la: "Sanctus Eugendus abbas Condatiscensis"` overrides la; `subject_la: ""` keeps the candidate's la; a candidate label `null` stays `None`; an edit to an ID not among candidates has labels all `None` except an explicit subject_la); each check error above; `split_applied` with an old ID gone and new present.
- [ ] **Step 2:** `python3 -m unittest tests.test_apply_renames -v` — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"apply renames: the rename table and its checks (#74)"`

### Task 2: Textual re-key

**Files:**
- Modify: `scripts/apply_renames.py`
- Test: `tests/test_apply_renames.py`

**Interfaces:**
- Produces:
  - `rekey_text(text: str, mapping: dict[str, str]) -> tuple[str, int]` — replaces `"old"` and `"old|` (one regex, longest IDs first is not needed since the match requires the closing `"` or `|`), returns (text, replacements).
  - `rekey_file(path: Path, mapping, kind: "json" | "python", dry: bool) -> int` — reads, re-keys, checks the result (`json.loads` for json; `compile(text, path, "exec")` for python), writes unless `dry` or unchanged; returns the count. Raises `ValueError` if the check fails (nothing written for that file).
  - `set_labels(path: Path, labels: dict[str, str], dry: bool) -> int` — in a flat i18n file, replaces the value of each `"<id>": "<value>"` line with `json.dumps(new, ensure_ascii=False)`; ids absent from the file are an error.

- [ ] **Step 1: Write the failing tests** — keys and values renamed; `"mr:0101-basilius|Basilius"` renamed; `"mr:0101-basilius-magnus"` untouched; prose `see mr:0101-basilius in …` (unquoted) untouched; exact formatting kept (compare a fixture with 1-space indent and one-line arrays byte for byte except the IDs); a Python notes file renamed and still compiles; `set_labels` writes `"Sant’Eugendo, abate di Condat"` with the curly apostrophe unescaped.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"apply renames: re-key a file's quoted IDs, keeping its format"`

### Task 3: The `texts` and `crmedr` subcommands

**Files:**
- Modify: `scripts/apply_renames.py` (docstring usage, `main`)
- Test: `tests/test_apply_renames.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces:
  - `apply_texts(changeset, texts_repo: Path, repo_root: Path, dry: bool) -> Report`
  - `apply_crmedr(changeset, repo_root: Path, dry: bool, run=subprocess.run) -> Report` — re-keys tracked `data/` + `i18n/` JSON and `scripts/extract_registry.py`, writes labels to `i18n/la.json`, `en.json`, `it.json`, then (unless dry) runs `python3 scripts/extract_registry.py` and `python3 -m unittest discover -s tests` through `run`; a non-zero return makes the report fail.
  - `Report` (NamedTuple): `applied: list[Rename]`, `skipped: list[Rename]`, `files: dict[str, int]` (path → replacements), `errors: list[str]`, `ok: bool`; `render(report) -> str` (per rename `old → new`, files, counts, and for `crmedr` the next steps: run `CRMEDR_PATH=<repo> python3 -m pytest tests/test_registry_keys.py` in martyrology-texts, merge texts then crmedr, then AGENTS.md steps 3-4).
  - CLI: `apply_renames.py texts <decided.json> /path/to/martyrology-texts [--dry-run] [repo_root]`; `apply_renames.py crmedr <decided.json> [--dry-run] [--regenerate /path/to/martyrology-texts] [repo_root]`; exit 1 on check errors or a failed run.

- [ ] **Step 1: Write the failing tests** on a temporary git repository built in the test (`git init`, a small registry with 3 entries incl. one deprecated, `i18n/{la,en,it}.json`, `data/typology.json`, an untracked `data/wip.json` that also names the old ID, a stub `scripts/extract_registry.py` with an ENTRY_NOTES dict): crmedr applies one accept and one edit (files counted, labels written, untracked file unchanged); a failing check writes nothing; `--dry-run` writes nothing; a second run reports both as already applied and changes nothing; a fake `run` returning 1 makes `ok` false and exit 1; texts re-keys the three edition dirs of a temporary texts tree.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — PASS; full suite PASS.
- [ ] **Step 5: Commit** `"apply renames: texts and crmedr subcommands"`

### Task 4: `--regenerate`, AGENTS.md and a real dry run

**Files:**
- Modify: `scripts/apply_renames.py`
- Modify: `AGENTS.md` ("Changing an ID…": the script does steps 1-2)
- Test: `tests/test_apply_renames.py`

**Interfaces:**
- Produces: with `--regenerate <texts>`, after the registry rebuild `apply_crmedr` runs (through `run`) `extract_typology.py`, `extract_places.py`, `registry_places.py`, `extract_persons.py`, `extract_mentions.py` with the texts path, and fails the report if `git diff --quiet -- data/typology.json data/places.json` shows changes beyond the re-key (compare the files' re-keyed content before regeneration with after).

- [ ] **Step 1: Write the failing test** — with a fake `run`, the regenerators are called in that order with the texts path; a regenerated typology differing from the re-keyed one fails the report.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement; update AGENTS.md's rename section: steps 1 and 2 are `apply_renames.py texts` then `apply_renames.py crmedr` on the decided change-set (one paragraph, keep the manual list as what the script does).
- [ ] **Step 4:** Run — PASS; full suite PASS. Then a real `--dry-run` on a decided sample: build `/tmp`-free sample in the scratchpad from `~/private-changesets/subject-identity/01/crmedr-subjects-01.json` with two rename ops marked accepted (mr:0101-eugendus, mr:0101-fulgentius), run `python3 scripts/apply_renames.py crmedr <sample> --dry-run` and `texts <sample> ../martyrology-texts --dry-run`; record the report in the task report (counts only; no text).
- [ ] **Step 5: Commit** `"apply renames: --regenerate; AGENTS.md"`
