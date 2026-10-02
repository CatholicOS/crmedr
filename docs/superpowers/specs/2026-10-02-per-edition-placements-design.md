# Per-edition placements — design

**Status:** approved in brainstorming 2026-10-02; spec under review.
**Repos:** `crmedr` (format, data, extraction), `martyrology-texts` (two text
changes), `martyrology-api` (serving each edition's own placement; release),
`martyrology-frontend` (one gap-note change; snapshot refresh).

## Goal

Show every 2004-family edition numbered, asterisked and dated as **its own
print** reads. Today the registry holds one placement per eulogy and the API
serves it to every edition, so where the Latin editio altera 2004 and the
Italian (CEI) edition differ, at least one of them is shown wrongly: on
4 January the Latin reader prints two bare "\*" at the end of the day instead
of 2\* Abrunculus and 12\* Emmanuel González García; the CEI reader shows
Bl. Marcantonio Durando on 10 June, where only the Latin prints him, and its
10 December skips from 8 to 10.

## Decisions taken

| Question | Decision |
|---|---|
| Which edition the registry's main placement follows | The **Latin editio altera 2004 print** (the anchor edition). Other editions record only their differences. |
| A eulogy printed on different days in different editions | **Separate IDs**, one per day, since an ID names the day the eulogy is printed; the IDs are linked as the same eulogy. |
| The leap-day eulogies (printed on 28 and 29 February) | **Unchanged**: one ID each, anchored at 0229, with `also_on`. That is one edition reading a eulogy on a different day by year, not two editions disagreeing. |
| Latin texts of eulogies the Latin print lacks | **Deleted** from martyrology-texts. |
| Side-by-side view of a eulogy printed on another day in the other edition | A gap note naming that day and entry, with a link — never "not in". |

## The differences between the 2004 editions

All are recorded in `docs/canonicalization-report.md` and were re-checked on
the Latin print's text layer for this design.

**Numbering** (L = Latin print, C = CEI; registry today = C except where noted):

| Day | Latin print | CEI |
|---|---|---|
| 4 January | 1 Hermes & Caius, **2\* Abrunculus**, 3 Gregorius, 4\* Ferreolus, 5\* Rigomerus, 6 Rigobertus, 7\* Pharaildis, 8\* Angela, 9\* Christiana Menabuoi, 10\* Thomas Plumtree, 11 Elizabeth Ann Seton, **12\* Emmanuel González García** | Abrunculus absent; Gregorius 2 … Seton 10; **11\*** González García |
| 10 June | … 8\* Thomas Green, **9\* Marcantonio Durando**, **10\*** Eduardus Poppe | Durando absent; Poppe **9\*** |
| 25 August | Louis IX, Joseph Calasanz (unnumbered), Eusebius absent, **3** Genesius … **13\*** Aloysius Urbano Lanaspa | Louis IX, Joseph Calasanz, **3 Eusebius & companions**, **4** Genesius … **14\*** Urbano Lanaspa |
| 10 December | … 8 Ioannes Roberts, **9\*** Gundisalvus Viñes Masip, **10\*** Antonius Martín Hernández & Augustinus García Calvo | … 8 Roberts, **9\* Marcantonio Durando**, **10\*** Viñes Masip, **11\*** Martín Hernández & García Calvo |

Registry today has `entry: null` for Abrunculus, González García and the
10 June Durando, and C's numbers for everything else on these days.

**Presence:** Abrunculus is only in L. Proclus & Hilarion (12 July, C 1),
Eusebius & companions (25 August, C 3) and Bl. Marija Petković (9 July, C 11\*)
are only in C; L leaves a gap on 12 July and 9 July (no renumbering) and
renumbers on 25 August. Durando: L 10 June, C 10 December.

**Asterisks:** 29 eulogies carry an asterisk in one edition and not the other
(the registry follows L; `ASTERISK_OVERRIDES` in `scripts/extract_registry.py`
records the discrepancy only in a note).

**The unofficial English translation** follows the Latin print (it translates
the editio altera: it has Abrunculus and the 10 June Durando, and lacks the three
CEI-only eulogies). It needs no overrides.

## Format (`data/martyrology_ids.json`)

Each entry keeps its main placement — `month`, `day`, `entry`, `asterisk`,
`unnumbered` — which now follows the Latin print. Two optional fields are added.

### `editions`: differences within the day

A map from CLBDR edition ID to the fields in which that edition differs.
Allowed keys: `entry` (int or null), `asterisk` (bool), `unnumbered` (bool),
`absent` (true). No `month`/`day`: a different day is a different ID.

```json
{ "id": "mr:0104-gregorius", "month": 1, "day": 4, "entry": 3, "asterisk": false,
  "editions": { "martyrologium_romanum_2004_it_IT": { "entry": 2 } } }

{ "id": "mr:0104-abrunculus", "month": 1, "day": 4, "entry": 2, "asterisk": true,
  "editions": { "martyrologium_romanum_2004_it_IT": { "absent": true } } }

{ "id": "mr:0712-proclus-et-hilarion", "month": 7, "day": 12, "entry": 1, "asterisk": false,
  "editions": { "martyrologium_romanum_2004": { "absent": true },
                "martyrologium_romanum_2004_en_unofficial": { "absent": true } } }
```

An edition's placement of a eulogy is the main placement with that edition's
entry in `editions` applied; `absent: true` means the edition does not print it.
A eulogy printed only by some editions keeps an ordinary main placement on the
day it is printed (for a CEI-only eulogy, the CEI's), with `absent` for the
others — there is no separate "base is absent" flag.

### `same_eulogy`: one eulogy, different days

A list of the IDs under which another edition prints the same eulogy on another
day. The link is symmetric.

```json
{ "id": "mr:0610-marcus-antonius-durando", "month": 6, "day": 10, "entry": 9, "asterisk": true,
  "same_eulogy": ["mr:1210-marcus-antonius-durando"],
  "editions": { "martyrologium_romanum_2004_it_IT": { "absent": true } } }

{ "id": "mr:1210-marcus-antonius-durando", "month": 12, "day": 10, "entry": 9, "asterisk": true,
  "same_eulogy": ["mr:0610-marcus-antonius-durando"],
  "editions": { "martyrologium_romanum_2004": { "absent": true },
                "martyrologium_romanum_2004_en_unofficial": { "absent": true } } }
```

`mr:1210-marcus-antonius-durando` is today only the workbook's ID, renamed on
extraction (`ID_CORRECTIONS` in `extract_registry.py`); it was never published,
so nothing redirects from it. The workbook's 10 December row now keeps it, and
the 10 June placement becomes a print-only entry like Abrunculus.

### Placements after the change

| ID | Main (Latin) | CEI override |
|---|---|---|
| mr:0104-abrunculus | 2\* | absent |
| mr:0104-gregorius … mr:0104-elisabeth-anna-seton | 3 … 11 (asterisks as today) | entry 2 … 10 |
| mr:0104-emmanuel-gonzalez-garcia | 12\* | entry 11 |
| mr:0610-marcus-antonius-durando | 9\* | absent; same_eulogy mr:1210-… |
| mr:0610-eduardus-poppe | 10\* | entry 9 |
| mr:0825-eusebius-et-socii | 3 (CEI's) | — ; absent in L and EN |
| mr:0825-genesius … mr:0825-aloysius-urbano-lanaspa | 3 … 13 | entry 4 … 14 |
| mr:1210-marcus-antonius-durando | 9\* (CEI's) | — ; absent in L and EN; same_eulogy mr:0610-… |
| mr:1210-gundisalvus-vines-masip, mr:1210-antonius-martin-hernandez-… | 9\*, 10\* | entry 10, 11 |
| mr:0712-proclus-et-hilarion | 1 (CEI's) | — ; absent in L and EN |
| mr:0709-maria-a-iesu-crucifixo-petkovic | 11\* (CEI's) | — ; absent in L and EN |
| the 29 asterisk discrepancies | L's asterisk | `asterisk` = C's |

Note that the main entry of Eusebius (3) equals L's number for Genesius on the
same day: that is correct, since no single edition prints both at 3, and the
per-edition numbering check below is per edition.

### Extraction and checks (`scripts/extract_registry.py`)

The registry stays generated from the private workbook (C's numbering and
asterisks) plus small tables of the Latin print's differences, as
`ASTERISK_OVERRIDES` and `PRINT_ONLY_ENTRIES` are today:

- `PRINT_ONLY_ENTRIES` gains entry numbers (Abrunculus 2, González García 12,
  the 10 June Durando 9) and a CEI-absence override, and the 10 June Durando
  gains `same_eulogy`.
- A new `LATIN_RENUMBERING` table gives L's entry for each eulogy whose L number
  differs from C's (4 January, 10 June, 25 August, 10 December); extraction sets
  the main `entry` from it and writes C's number into the CEI override.
- A new `CEI_ONLY` table (Proclus & Hilarion, Eusebius & companions, Petković,
  the 10 December Durando) adds `absent` for the Latin and English editions.
- `ASTERISK_OVERRIDES` additionally writes C's asterisk into the CEI override.
- `ID_CORRECTIONS` drops the mr:1210-… → mr:0610-… rename, and
  `PLACEMENT_OVERRIDES` drops its Durando entry (which today moves the
  workbook's 10 December row to 10 June): the workbook row stays on
  10 December as mr:1210-…, and the 10 June placement comes from
  `PRINT_ONLY_ENTRIES`.

Validation, failing the extraction on any error:

- `editions` keys are known CLBDR 2004-family edition IDs; override keys are
  only `entry`, `asterisk`, `unnumbered`, `absent`; an override never repeats
  the main value.
- `same_eulogy` targets exist, are on another day, and link back.
- For each 2004-family edition and each day, the numbered entries the edition
  prints have distinct numbers.

The human-readable `registry/MM-*.md` tables gain a column listing per-edition
differences. `docs/canonicalization-report.md` records the new format and the
Durando split.

Other consumers of the registry in crmedr (`extract_places.py`'s
`PRINT_POSITION`, `print_order`) switch to the now-present main entries;
`PRINT_POSITION` is removed if nothing else needs it.

## martyrology-texts

- The CEI text of Durando moves from `it_IT/06.json` (key
  `mr:0610-marcus-antonius-durando`) to `it_IT/12.json` (key
  `mr:1210-marcus-antonius-durando`). The Latin and English texts stay under
  the 10 June ID.
- The Latin texts of mr:0712-proclus-et-hilarion, mr:0825-eusebius-et-socii and
  mr:0709-maria-a-iesu-crucifixo-petkovic are deleted.
- `scripts/extract_texts.py` applies the same rules, so a regeneration reproduces
  this; the README's coverage counts are updated.

## martyrology-api

- `Registry` loads `editions` and `same_eulogy` for each entry.
- The flat (aligned 2004) day builder in `store.py` takes the edition: it skips
  an entry whose override for that edition is `absent` (even if a text exists),
  and uses the edition's `entry`, `asterisk` and `unnumbered`. Ordering is
  unchanged (unnumbered first, then by entry), now per edition.
- `/elogium/{id}` placements follow from the per-edition days; the response adds
  `same_eulogy: string[]`.
- Editions not in the 2004 family (1749, 1914) are unaffected.
- Tests, against the fixture registry extended with these cases: 4 January in L
  (2\* Abrunculus, 3 Gregorius, 12\* González García) and C (2 Gregorius,
  11\* González García, no Abrunculus); Durando on 10 June in L only and on
  10 December in C only; a CEI-only eulogy absent from L even with a stray L
  text; a CEI asterisk override; `same_eulogy` on `/elogium`.
- Data pins bumped (crmedr, martyrology-texts), version 0.8.0, release, deploy.

## martyrology-frontend

- `EulogyOut` gains `same_eulogy?: string[]`.
- Parallel reader: for a one-sided eulogy, the placements lookup also fetches
  its `same_eulogy` IDs; if the other edition prints one of them, the gap note
  reads [*2004 Italian: 10 December, n. 9\** →], linking to that day in the
  same pairing (the existing "elsewhere" note), instead of [*not in 2004
  Italian*].
- `npm run snapshot-registry` refreshes `data/registry-snapshot.json`
  (main placement only; the curator tools are unaffected otherwise).
- Tests: the gap note for a eulogy whose `same_eulogy` the other edition prints
  on another day.

## Order of work

1. crmedr: format, extraction tables, validation, regenerated data, report.
2. martyrology-texts: Durando's CEI text moved, three Latin texts deleted.
3. martyrology-api: per-edition day building and `same_eulogy`; pins; release
   0.8.0; deploy.
4. martyrology-frontend: gap note via `same_eulogy`; snapshot refresh; deploy.

## Out of scope

- Per-edition placements for editions outside the 2004 family.
- Changing the leap-day eulogies.
- Re-verifying the 29 asterisk discrepancies (already verified on both scans).
