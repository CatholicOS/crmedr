# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## What this repository is

CRMEDR (Common Roman Martyrology Eulogy Data Repository) is a **data repository**, not an application. It publishes canonical identifiers for the eulogies (elogia) of the Roman Martyrology (*Martyrologium Romanum*, editio typica altera 2004), plus factual placement metadata and per-language subject names. There is no build, no server, and no dependency manifest; a small stdlib `unittest` suite in `tests/` covers the scripts — the deliverable is the JSON/Markdown data itself.

**The copyrighted eulogy texts are deliberately absent.** Only the non-copyrightable structural registry (IDs + placement facts) lives here. Never add eulogy body texts. Citation-length incipits appear only in `docs/canonicalization-report.md`, to identify entries.

**One exception: place designations.** Place designations are factual and may be quoted verbatim in `places[].la` (Latin editio typica altera 2004) and `places[].it` (Italian CEI edition 2004) in `data/places.json`. No other text of either edition is stored. `scripts/extract_places.py` enforces part of this in code: every `la` / `it` must appear verbatim in its elogium, `la` at most 12 words (longer opening places need a commented `LONG_LEAD_OK` entry) and `it` at most 20, and an opening place is cut at a comma that starts a clause. It cannot tell every narrative phrase from a place, so `docs/places-report.md` lists each Latin opening place that still contains a comma for review.

**Names are facts too.** The saints and blessed a eulogy commemorates are stored in `data/persons.json` as Latin nominative names; the forms as printed (often genitive) are read to check them and never stored.

All IDs are **drafts pending committee review**. The `mr:` namespace prefix and the 2004 anchor-edition choice are placeholders; changing either is a mechanical rewrite.

## The identifier scheme

`mr:MMDD-slug` — `MMDD` anchors the eulogy's placement in the editio altera 2004; `slug` is the Latin nominative lemma of the eulogy's **first-named subject**, ASCII-folded, lowercase, honorific-free (no *sanctus*/*beatus*). Multi-subject eulogies: `-et-<second>` for a pair, `-et-socii` for three or more; only genuinely anonymous groups take a `[number-]class-<place in the genitive>` slug (`mr:0309-quadraginta-milites-sebastes`), or `martyres-` plus the name of a group known by one (`mr:0717-martyres-scillitani`). The full derivation rules, feast overrides, leap-day identity decisions and collision resolutions are in `docs/canonicalization-report.md`.

## Architecture: the generation pipeline

All generator scripts read **private source repositories** that hold the copyrighted texts, and emit only structural data. They cannot be run without those private sources.

1. **`scripts/extract_registry.py`** reads the private digitization workbook (`Roman Martyrology LA IT EN with IDs.xlsx`) and writes:
   - `data/martyrology_ids.json` — machine-readable registry (current + deprecated entries, with a header carrying `entry_count`/`current_count`/`deprecated_count`)
   - `registry/MM-<month>.md` — human-readable per-month tables
   - It also reads `data/deprecated_ids.json` as an *input* (deprecated IDs are produced by separate external alignment tooling, not by this script) and merges it into the output.
   - Run: `python3 scripts/extract_registry.py /path/to/"Roman Martyrology LA IT EN with IDs.xlsx"` (requires `openpyxl`)

2. **`scripts/extract_subjects.py`** reads `data/martyrology_ids.json` plus the private `CatholicOS/martyrology-texts` repo and writes `i18n/{la,it,en}.json` — the *subject* (the saint/blessed/celebration each eulogy is directed to) in nominative display form per language.
   - Run: `python3 scripts/extract_subjects.py /path/to/martyrology-texts` (stdlib only)

3. **`scripts/extract_typology.py`** reads `data/martyrology_ids.json` plus the private `CatholicOS/martyrology-texts` repo (Latin editio altera 2004) and writes `data/typology.json` (what each current eulogy's date marks) and `docs/typology-report.md`. `extract_registry.py` merges `data/typology.json` into the registry after `country`.
   - Run: `python3 scripts/extract_typology.py /path/to/martyrology-texts` (stdlib only)
4. **`scripts/extract_places.py`** reads `data/martyrology_ids.json`, `data/typology.json`, `data/places_curated.json` and the private `martyrology-texts` repo (Latin editio altera 2004), and writes `data/places.json` (the places each current eulogy states, with roles) and `docs/places-report.md` (including the curation candidates). `extract_registry.py` merges `data/places.json` after `typology`.
   - Run: `python3 scripts/extract_places.py /path/to/martyrology-texts` (stdlib only)
5. **`scripts/build_gazetteer.py`** resolves each distinct place designation in `data/places.json` to a Wikidata item, a label and the place's actual modern country, and writes `data/gazetteer.json`, the review change-set `data/gazetteer_review.json` (`crmedr-changeset/v1`, op `resolve_place`, reviewed in martyrology-frontend) and `docs/gazetteer-report.md`. Unlike the other generators it reads no private sources but **needs network access** (Wikidata, cached in `.cache/wikidata/`). A place is `auto` only when exactly one candidate passes the evidence bar; otherwise it waits in the change-set and has no key in `gazetteer.json`.
   - Run: `python3 scripts/build_gazetteer.py propose`; after review in martyrology-frontend, `python3 scripts/build_gazetteer.py apply <exported.json>`; `verify-suggestions` checks suggested QIDs; `check` validates offline (stdlib only)
6. **`scripts/extract_persons.py`** reads `data/martyrology_ids.json`, `i18n/la.json`, `data/persons_curated.json` and the private `martyrology-texts` repo (Latin editio altera 2004 texts and footnotes), and writes `data/persons.json` (the saints and blessed each current eulogy commemorates: the Latin nominative name and where it is printed, the text or the nth footnote) and `docs/persons-report.md`. Names are stored as facts; no text is. Hand decisions: `MARIAN_IDS`, `FEAST_PERSONS`, `GROUP_IDS` in `scripts/persons_text.py`, and `data/persons_curated.json`.
   - Run: `python3 scripts/extract_persons.py /path/to/martyrology-texts` (stdlib only)
7. **`scripts/build_person_items.py`** identifies each person with a Wikidata item and writes `data/person_items.json`, the review change-set `data/person_items_review.json` (`crmedr-changeset/v1`, op `resolve_person`, reviewed in martyrology-frontend) and `docs/person-items-report.md`. Like the gazetteer it needs network access (cached in `.cache/wikidata/`); a person is `auto` only when exactly one candidate passes the evidence bar.
   - Run: `python3 scripts/build_person_items.py propose`; after review, `python3 scripts/build_person_items.py apply <exported.json>`; `verify-suggestions` checks suggested QIDs; `check` validates offline

### Invariants the pipeline enforces (preserve these when editing)

- **Every `i18n/*.json` file carries the identical complete key set** (all IDs, current + deprecated). Untranslated subjects are empty strings, never missing keys. `la.json` is fully filled; `it.json`/`en.json` are mechanically extracted and hand-reviewed (#25, #31); a rerun of `extract_subjects.py` overwrites curated values, so diff its output rather than committing it.
- **IDs are unique** across current + deprecated (asserted at the end of `extract_registry.py`).
- **Deprecated IDs must not collide with current IDs** (asserted in `load_deprecated`); each has `deprecated: true` and an `attested_in` edition.
- **Subject and slug are edition-independent and tightly coupled**: the eulogy text may change between editions, but the subject and canonical ID do not. The day is part of the identity (`MMDD` is the day an edition prints the eulogy); entry number, asterisk marker and unnumbered status, the position within the day, are per-edition attributes, *not* part of identity. A eulogy an edition prints on another day has its own ID there, linked by `same_eulogy`.

### Where hand-corrections live

`extract_registry.py` holds the curated correction/override maps that encode the human canonicalization decisions on top of the raw workbook. When a slug, placement, or asterisk is wrong, the fix usually belongs in one of these constants (each with an explanatory comment), **not** in the generated output:
- `ID_CORRECTIONS` — slugs the workbook coined against the rules (place-name-lead bugs, over-latinized surnames, ł/diacritic folding bugs, byname disambiguation)
- `UNNUMBERED_LEADS` — `(month, day) → count` of drop-cap header eulogies (counted in numbering, printed without a number)
- `PLACEMENT_OVERRIDES` / `ENTRY_NOTES` / `LATIN_ASTERISKED` / `LATIN_PLAIN` — where the Latin editio altera print differs from the Italian (CEI) edition the workbook digitized; the registry follows the **Latin print** and each carries a `note`
- `PRINT_ONLY_ENTRIES` — entries in the Latin print but absent from the workbook
- `TYPOLOGY_OVERRIDES` / `FEAST_IDS` in `scripts/extract_typology.py` — hand typology decisions and the explicit list of celebrations (feasts of the Lord and of Mary, etc.)
- `data/places_curated.json` — hand-entered body places (birth, see, burial or death elsewhere); `NOT_A_PLACE` / `LONG_LEAD_OK` in `scripts/extract_places.py`
- `data/misprints.json` — verified misprints in the printed 2004 editions (Latin and Italian) and the unofficial English 2004 text, one word (or a phrase of up to three words) each; they also count as stop words in place extraction. `duplicated_entries` there records a whole eulogy an edition prints again on another day (the copy is not in the texts)
- `data/gazetteer.json` — `reviewed` and `unresolved` entries are human decisions; `propose` never changes an existing key. Fix a wrong place by editing its entry (keeping the validation rules), or delete the key and rerun `propose` to queue it again. A wrong `auto` place that no general rule can catch goes into `FORCE_REVIEW` in `scripts/build_gazetteer.py`, with a comment.
- `MARIAN_IDS` / `FEAST_PERSONS` / `GROUP_IDS` / `GROUP_HEADS` in `scripts/persons_text.py`, `data/persons_curated.json`, and `FORCE_REVIEW` / `NAME_EQUIVALENTS` in `scripts/build_person_items.py` — the persons' hand decisions

The diacritic-folding logic (`fold()` in `extract_subjects.py`, incl. `STROKE_LETTERS` for ł/ø/đ… which NFKD does not decompose) is the upstream fix; `ID_CORRECTIONS` patches slugs the old buggy fold already baked into the workbook.

## Editing the data

The JSON and Markdown files are **generated artifacts**. Prefer regenerating over hand-editing when you have the private sources. When you don't (the common case here), hand-edits to `data/*.json` and `registry/*.md` are acceptable but must keep the four invariants above intact and stay consistent with the correction maps in `extract_registry.py`. After any change touching IDs, verify the count header in `data/martyrology_ids.json` and the i18n key-set parity still hold. Run `python3 -m unittest discover -s tests` after changing any script.

The `docs/canonicalization-report.md` is the authoritative methodology record and print-verification log; update it when identity decisions or per-edition discrepancies change.
