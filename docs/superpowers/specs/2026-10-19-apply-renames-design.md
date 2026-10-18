# Applying decided renames — design

Issue: [#74](https://github.com/CatholicOS/crmedr/issues/74). Date: 2026-10-19. Builds on the subject-identity
pipeline (`2026-10-18-subject-identity-design.md`, PR #147): its monthly change-set carries `rename` ops the curator
decides in martyrology-frontend's review page and exports as `<name>.decided.json`.

## Why

AGENTS.md ("Changing an ID, a placement or an asterisk") describes a rename as a checklist over four repositories.
It was done by hand for #52, #63, #118 (dozens of IDs at a time). The subject-identity pipeline produces up to two
hundred renames a month; by hand, keys get missed and the repositories drift apart.

## Goals

- One script, `scripts/apply_renames.py`, that reads a decided change-set and applies its decided renames:
  - `texts <decided.json> /path/to/martyrology-texts`: step 1, re-key the 2004 edition files in martyrology-texts
    (the curator's decision, 2026-10-19: the script does this too, as its own first step, since texts merges first);
  - `crmedr <decided.json>`: step 2, rename the ID everywhere in crmedr, write the new subject labels, rebuild the
    registry and check the result.
- Nothing is applied unless every rename passes the checks (the rule `build_person_items.py apply` follows).
- The same decided file can be applied twice without harm: a rename whose old ID is already gone and whose new ID
  is present is reported as already applied and skipped.

## Non-goals

- martyrology-api and martyrology-frontend (steps 3 and 4: re-align, pin bumps, release; `snapshot-registry`,
  deploy) stay manual, as AGENTS.md describes them.
- No commit, push or PR is made by the script.
- The `docs/canonicalization-report.md` log entry stays a human-written paragraph.

## The renames

From each `rename` op of the decided file with a decision:

| decision | old ID | new ID | labels |
|---|---|---|---|
| `accept` | `op.id` | `op.new_id` | the candidate whose `new_id` is `op.new_id` |
| `edit` | `op.id` | `edited.new_id` | that candidate's, else none; `edited.subject_la` (non-empty) overrides the Latin |
| `reject` | — | — | — (nothing applied) |

Other op types in the file (`resolve_person`) are ignored here; `build_person_items.py apply` applies them.
`subject_la: ""` counts as absent. A label that is `null` leaves that language's subject as it is.

## Checks (all before writing anything)

- The old ID exists in `data/martyrology_ids.json` (or the rename is already applied, see Goals).
- The new ID is `mr:MMDD-slug` with the old ID's MMDD (the day is part of the identity).
- The slug is lowercase ASCII words joined by `-`, with no numeric token (the existing test's rule).
- The new ID is not another current or deprecated ID, and no two renames share a new ID.
- No new ID is also another rename's old ID (no chains in one run).

## Step 1: `texts`

In `martyrology-texts/data/editions/<edition>/`, for the three 2004 editions (`martyrologium_romanum_2004`,
`..._it_IT`, `..._en_unofficial`): re-key each monthly `MM.json` and `footnotes.json` / `footnotes-overrides.json`
wherever a key or value is exactly an old ID. Key order is kept (the renamed key takes the old one's place). Files
are written with the same JSON formatting they had (indentation, `ensure_ascii=False`, trailing newline), so the diff
shows only the renamed keys. The script then runs that repository's `tests/test_registry_keys.py` only after step 2
(it checks the texts against crmedr's registry, `CRMEDR_PATH` or `../crmedr`), so step 1 prints the command to run.

## Step 2: `crmedr`

1. Re-key every tracked JSON file under `data/` and `i18n/` (from `git ls-files`): any dict key or string value that
   is exactly an old ID, or that starts with `<old ID>|` (person keys such as `mr:0101-basilius|Basilius`), takes the
   new ID. Key order and formatting are kept as in step 1. Untracked files are never touched (the curator keeps work
   in progress there).
2. Re-key the notes in `scripts/extract_registry.py` (`ENTRY_NOTES`, `EDITION_NOTES`, `REVIEW_EDITION_NOTES`): an
   exact quoted old ID becomes the new one.
3. Write the subject labels: `i18n/la.json`, `en.json`, `it.json` take the chosen candidate's labels (R3 of the
   subject-identity design); a `null` label leaves that file's subject unchanged.
4. Run `python3 scripts/extract_registry.py`, then `python3 -m unittest discover -s tests`. Their failure is reported
   and the script exits non-zero; the files stay written, for the curator to inspect with `git diff`.
5. Print the remaining steps: run the texts test, merge texts then crmedr, then AGENTS.md steps 3 and 4.

The generated files that read the texts (`extract_typology.py`, `extract_places.py`, `extract_persons.py`,
`extract_mentions.py`) are not re-run: re-keying them is what a re-run would produce for a rename that does not
change the texts, and a re-run needs the private texts. `--regenerate /path/to/martyrology-texts` runs them and
checks that typology and places come out identical (AGENTS.md's condition).

## Output

A report on stdout: per rename `old → new` and the files touched, the renames skipped as already applied, and a
count. `--dry-run` prints the report and writes nothing.

## Testing

Unit tests on a temporary copy of a small repository tree: the rename table from accept/edit/reject ops; every check
(day, numeric token, collision, duplicate, chain, missing old ID); re-keying keys, values and `old|name` prefixes
without touching `old-longer` IDs; key order and formatting kept; labels written and `null` left alone; idempotence;
untracked files left alone; `--dry-run` writes nothing.
