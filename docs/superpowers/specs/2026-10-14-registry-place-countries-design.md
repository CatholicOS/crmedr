# Gazetteer into the registry: place items and derived countries (places, sub-project 3) — design

Issue: [#12](https://github.com/CatholicOS/crmedr/issues/12). Date: 2026-10-14. Builds on
`docs/superpowers/specs/2026-10-01-gazetteer-design.md` (sub-project 2).

## Goal

Copy each place's gazetteer resolution onto the registry's `places[]` items, and make
each current entry's `country` follow the place the eulogy opens with, so the registry
agrees with the map and with the gazetteer reviews.

Today 80 current entries carry a `country` that differs from the gazetteer country of
their resolved opening place: old-border countries ("in Polónia" for places now in
Belarus or Ukraine, Gusen and Hartheim under Germany), homonym and garbling errors
(0125-teresia-grillo EG, 0712-nabor-et-felix DZ, 0529-iosephus-gerard IT for Roma in
Lesotho), and the Holy Land coded IL where the convention is PS.

## Decisions

- **The actual modern country wins** over the country the text names or the border of
  the time (convention #9). "In Polónia" for a place now in Belarus is BY.
- **The Holy Land is PS**, everywhere, including places inside Israel's pre-1967 lines
  (Acre, Caesarea Maritima). The registry names the territory as historically called and
  takes no part in current disputes; a map marker lands in the same region either way,
  and each place's Wikidata item carries its current status. This is the gazetteer's
  existing `COUNTRY_CONVENTIONS` (`IL → PS`), now applied to the registry too.
- **The workbook is not a source.** No value is taken from
  `Roman Martyrology LA IT EN with IDs.xlsx`; the new step runs without it. Removing the
  workbook from `extract_registry.py` altogether is #127.
- **Deprecated entries are out of scope**: they keep their `country` and have no
  `places`.

## Data

### `places[]` items in `data/martyrology_ids.json`

Flat fields are added to each item whose `la` has a resolved gazetteer entry (status
`auto` or `reviewed`, `wikidata` not null):

```json
"places": [
  {
    "role": "death",
    "la": "Thinísæ in Numídia",
    "it": "A La Calle in Numidia, nell’odierna Tunisia",
    "source": "lead",
    "wikidata": "Q3050005",
    "label": "El Kala",
    "country": "DZ",
    "text_says": [{ "country": "TN", "it": "A La Calle in Numidia, nell’odierna Tunisia" }]
  }
]
```

- `wikidata`, `label`, `country` are copied from the gazetteer entry.
- `text_says` holds only the gazetteer `text_says` items whose `it` equals this item's
  `it` (one Latin place may carry several Italian phrases); omitted when none.
- No `modern` field: a Wikidata item is often the historical place with today's
  coordinates, so `label` is its name, not a modern equivalent.
- An item whose place is still queued, or `unresolved`, gets none of these fields.

`data/places.json` is unchanged; the fields live only in the registry.

### `country` of each current entry

Derived, in this order:

1. The `country` of the entry's opening place (`source: "lead"`) when the gazetteer
   resolves it (4,224 of 4,640 current entries at the time of writing).
2. Otherwise the value in `data/countries_curated.json` (378 entries with no opening
   place, 38 whose place is still queued).
3. `COUNTRY_CONVENTIONS` applied last (`IL → PS`).

### `data/countries_curated.json` (new)

```json
{
  "$comment": "...",
  "countries": {
    "mr:0202-praesentatio-domini": "PS",
    "mr:0101-maria-dei-genetrix": null,
    "mr:0622-paulinus": { "country": "IT", "note": "no place-lead; Nola" }
  }
}
```

- Seeded once from the committed registry values of the entries that rule 1 does not
  cover (the values that went through the #8/#9 corrections), with `IL → PS` applied.
  The live `COUNTRY_CORRECTIONS` comments become `note`s.
- A value is an ISO 3166-1 alpha-2 code, `null` (no country, e.g. a feast), or an object
  `{country, note}`.
- From then on it is hand-curated.

### `COUNTRY_CORRECTIONS` is removed

Its entries are either covered by rule 1 or folded into `countries_curated.json`.
`extract_registry.py` no longer applies a country of its own; it calls the new step
(below) after merging `places.json`.

## Component: `scripts/registry_places.py`

Stdlib only, offline, no private sources.

- `apply(entries, places, gazetteer, curated) -> entries`: pure function; fills the
  place fields and derives `country` for each current entry.
- `python3 scripts/registry_places.py`: reads `data/martyrology_ids.json`,
  `data/places.json`, `data/gazetteer.json`, `data/countries_curated.json`; rewrites
  `data/martyrology_ids.json` (same formatting as `extract_registry.py`) and the
  `Country` column of `registry/MM-*.md` (nothing else in either).
- `--check`: writes nothing; exits non-zero and lists the differing IDs when the
  committed registry differs from what the script would write.
- Run after `build_gazetteer.py apply` (and after any edit of `gazetteer.json` or
  `countries_curated.json`).

Validation (errors stop the run):
- every current ID gets its country from exactly one of rule 1 or the curated file:
  an ID with a resolved opening place must not be in the curated file (it says to
  remove it, e.g. after a queued place is reviewed), and an ID with none must be in it;
- no ID in the curated file is unknown or deprecated;
- every code is in the embedded ISO set (the gazetteer's), or `null`;
- no current entry ends up `IL`.

## Report

`docs/gazetteer-report.md`: the "Preview for sub-project 3" section is replaced by
**Registry countries from opening places**: the entries whose derived country differs
from the country the registry carried before this change (ID, `la`, before, after), so
the one-time correction is auditable. After this change the section lists entries whose
curated value differs from the place (none expected) and is otherwise empty.

## Downstream

- **martyrology-api**: its registry model reads only `country`; the new place fields are
  ignored. The corrected countries go live at the next crmedr pin bump and API release.
- **martyrology-frontend**: no change; the map already places each eulogy by its
  gazetteer place.

## Tests

- `apply` on small fixtures: lead resolved → place country; lead queued → curated;
  no lead → curated; IL → PS on both paths; `text_says` filtered by `it`; queued and
  `unresolved` places get no fields; deprecated entries untouched.
- Validation errors: a resolved-lead ID in the curated file; a missing curated ID; an
  unknown code; an `IL` result.
- `registry_places.py --check` passes on the committed data.

## Docs

- `AGENTS.md`: pipeline step for `registry_places.py`; `data/countries_curated.json`
  under hand-corrections; `COUNTRY_CORRECTIONS` removed.
- `docs/canonicalization-report.md`: the country rule (opening place, curated fallback,
  Holy Land convention).
- The registry header `$comment` and the `registry/MM-*.md` intro describe `country` as
  the modern country of the opening place.

## Closing #12

The issue's open questions, as built: places cover current entries only; the role set
is `death`, `burial`, `translation`, `dedication`, `cult`, `birth`, `ministry` (opening
places take theirs from typology; `birth` and `ministry` are defined but used by no item
yet, the four hand-curated body places in `data/places_curated.json` being `death` and
`cult`); places below country level are recorded as Wikidata items. Body places (birth,
see, burial elsewhere) are not extracted beyond the curated ones; the closing comment
says so.
