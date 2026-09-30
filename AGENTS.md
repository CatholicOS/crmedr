# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## What this repository is

CRMEDR (Common Roman Martyrology Eulogy Data Repository) is a **data repository**, not an application. It publishes canonical identifiers for the eulogies (elogia) of the Roman Martyrology (*Martyrologium Romanum*, editio typica altera 2004), plus factual placement metadata and per-language subject names. There is no build, no server, and no dependency manifest; a small stdlib `unittest` suite in `tests/` covers the scripts — the deliverable is the JSON/Markdown data itself.

**The copyrighted eulogy texts are deliberately absent.** Only the non-copyrightable structural registry (IDs + placement facts) lives here. Never add eulogy body texts. Citation-length incipits appear only in `docs/canonicalization-report.md`, to identify entries.

**One exception: place designations.** Place designations are factual and may be quoted verbatim in `places[].la` (Latin editio typica altera 2004) and `places[].it` (Italian CEI edition 2004) in `data/places.json`. No other text of either edition is stored. `scripts/extract_places.py` enforces part of this in code: every `la` / `it` must appear verbatim in its elogium, `la` at most 12 words (longer opening places need a commented `LONG_LEAD_OK` entry) and `it` at most 20, and an opening place is cut at a comma that starts a clause. It cannot tell every narrative phrase from a place, so `docs/places-report.md` lists each Latin opening place that still contains a comma for review.

All IDs are **drafts pending committee review**. The `mr:` namespace prefix and the 2004 anchor-edition choice are placeholders; changing either is a mechanical rewrite.

## The identifier scheme

`mr:MMDD-slug` — `MMDD` anchors the eulogy's placement in the editio altera 2004; `slug` is the Latin nominative lemma of the eulogy's **first-named subject**, ASCII-folded, lowercase, honorific-free (no *sanctus*/*beatus*). Multi-subject eulogies: `-et-<second>` for a pair, `-et-socii` for three or more; only genuinely anonymous groups take a `martyres-<place>` slug. The full derivation rules, feast overrides, leap-day identity decisions and collision resolutions are in `docs/canonicalization-report.md`.

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

### Invariants the pipeline enforces (preserve these when editing)

- **Every `i18n/*.json` file carries the identical complete key set** (all IDs, current + deprecated). Untranslated subjects are empty strings, never missing keys. `la.json` is fully filled; `it.json`/`en.json` are partial and mechanically extracted, awaiting translators.
- **IDs are unique** across current + deprecated (asserted at the end of `extract_registry.py`).
- **Deprecated IDs must not collide with current IDs** (asserted in `load_deprecated`); each has `deprecated: true` and an `attested_in` edition.
- **Subject and slug are edition-independent and tightly coupled**: the eulogy text may change between editions, but the subject and canonical ID do not. Entry number, asterisk marker, and calendar placement are per-edition attributes, *not* part of identity.

### Where hand-corrections live

`extract_registry.py` holds the curated correction/override maps that encode the human canonicalization decisions on top of the raw workbook. When a slug, placement, or asterisk is wrong, the fix usually belongs in one of these constants (each with an explanatory comment), **not** in the generated output:
- `ID_CORRECTIONS` — slugs the workbook coined against the rules (place-name-lead bugs, over-latinized surnames, ł/diacritic folding bugs, byname disambiguation)
- `UNNUMBERED_LEADS` — `(month, day) → count` of drop-cap header eulogies (counted in numbering, printed without a number)
- `PLACEMENT_OVERRIDES` / `ENTRY_NOTES` / `LATIN_ASTERISKED` / `LATIN_PLAIN` — where the Latin editio altera print differs from the Italian (CEI) edition the workbook digitized; the registry follows the **Latin print** and each carries a `note`
- `PRINT_ONLY_ENTRIES` — entries in the Latin print but absent from the workbook
- `TYPOLOGY_OVERRIDES` / `FEAST_IDS` in `scripts/extract_typology.py` — hand typology decisions and the explicit list of celebrations (feasts of the Lord and of Mary, etc.)
- `data/places_curated.json` — hand-entered body places (birth, see, burial or death elsewhere); `NOT_A_PLACE` / `LONG_LEAD_OK` in `scripts/extract_places.py`
- `data/misprints.json` — verified misprints in the printed 2004 editions (Latin and Italian), one word (or a phrase of up to three words) each; they also count as stop words in place extraction

The diacritic-folding logic (`fold()` in `extract_subjects.py`, incl. `STROKE_LETTERS` for ł/ø/đ… which NFKD does not decompose) is the upstream fix; `ID_CORRECTIONS` patches slugs the old buggy fold already baked into the workbook.

## Editing the data

The JSON and Markdown files are **generated artifacts**. Prefer regenerating over hand-editing when you have the private sources. When you don't (the common case here), hand-edits to `data/*.json` and `registry/*.md` are acceptable but must keep the four invariants above intact and stay consistent with the correction maps in `extract_registry.py`. After any change touching IDs, verify the count header in `data/martyrology_ids.json` and the i18n key-set parity still hold. Run `python3 -m unittest discover -s tests` after changing any script.

The `docs/canonicalization-report.md` is the authoritative methodology record and print-verification log; update it when identity decisions or per-edition discrepancies change.
