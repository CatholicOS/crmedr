# Place extraction for eulogies (places, sub-project 1) — design

Issue: [#12](https://github.com/CatholicOS/crmedr/issues/12). Date: 2026-09-30.

## Goal

Give each current registry entry an optional `places` list: the places its elogium
states, each quoted **exactly as printed in the Latin editio altera 2004** and given
a **role** (what happened there). The main uses are role-aware filters ("saints
buried in …", "bishops of sees in …") and, later, geocoding. Roles must be reliable:
an untagged place is better than a guessed one.

`places` is built in three sub-projects, each with its own spec, plan and PR:

1. **Place extraction (this spec).** Latin place phrases with roles. No outside data.
2. **Gazetteer.** Each distinct Latin place is resolved once to a Wikidata QID, a
   modern label and a country, with a review decision per place.
3. **Merge and check.** `places[].modern` and `places[].country` come from the
   gazetteer, and `country` is cross-checked against the opening place.

## Scope

In scope:
- `places` for the current entries (4,639): the **opening place**, extracted
  automatically, and **body places** (birth, see, burial or death elsewhere), taken
  from a hand-curated file.
- A generator script, the curated file (empty at first), a review report with a
  curation candidate list, unit tests, docs, and the policy change on quoting.

Out of scope:
- Wikidata resolution, `modern`, and per-place `country` (sub-projects 2–3).
- Filling the curated file. That is ongoing curation work, not this PR.
- Deprecated entries (their texts come from other editions; see #11).
- A `places` column in `registry/*.md`, since the phrases are too long for a table.

## Policy: quoting place designations

The repository's rule is that elogium texts are never stored. This spec adds one
explicit exception, which goes into AGENTS.md and the README:

> Place designations are factual and may be quoted verbatim in `places[].la`.
> No other elogium text is stored.

The exception is enforced in code, not left to discipline (see "Checks").

## Data shape

Each current entry may have `places`, an ordered list (opening place first, then
curated places in their curated order):

```json
"places": [
  { "role": "death", "la": "Ad montem Iúram in pago Gálliæ Lugdunénsis", "source": "lead" },
  { "role": "birth", "la": "in Hibérnia", "source": "curated" }
]
```

- **`la`** is the place designation exactly as printed, including accents and
  ligatures (æ, œ). It is trimmed of surrounding spaces and trailing punctuation
  (`,` `;` `:`). A leading *Item* ("likewise") is dropped, since it isn't part of the
  place ("Item Romæ" → "Romæ"). *Ibidem* ("at the same place") is replaced by the
  `la` of the nearest preceding entry on the same day that has an opening place,
  and the item gets `"via": "<that entry's ID>"`.
- **`role`** comes from a closed set: `death`, `burial`, `translation`,
  `dedication`, `cult`, `birth`, `ministry`.
- **`source`** is `lead` (extracted automatically) or `curated` (hand-entered).
- **Entries with no place** get no `places` key, not an empty list.
- Sub-project 2 later adds `modern: {label, wikidata}` and `country` to each item.
  Nothing in this spec depends on them.

### Role of the opening place

The role is mapped from the entry's `typology` (`data/typology.json`):

| typology | role |
| --- | --- |
| `dies_natalis` | `death` |
| `depositio` | `burial` |
| `translatio` | `translation` |
| `dedicatio` | `dedication` |
| `ordinatio` | `ministry` |
| `celebratio`, `commemoratio` | `cult` (where the saint is venerated or commemorated) |
| `inventio` | `translation` (relics found there; no 2004 instances) |

`birth` and `ministry`, plus any extra `burial` or `death` places, come only from the
curated file.

## Extracting the opening place

Matching works on a copy of the printed text in which each character is mapped
**one to one**: an accented letter becomes its base letter (é → e), every other
character is kept, including the ligatures æ and œ, and **case is kept**. Offsets in
the copy are therefore offsets in the original, and the printed `la` is cut from the
original text at the match position. Stop words are listed in both spellings where
the print uses a ligature (*sanctae / sanctæ*, *beatae / beatæ*). A test pins the
offset alignment.

The opening place is the text before the first **stop word**:
- honorifics: *sanctus, sancta, sancti, sanctae/sanctæ, sanctorum, sanctarum, beatus,
  beata, beati, beatae/beatæ, beatorum, beatarum*;
- markers and celebration heads: *depositio, translatio, inventio, dedicatio,
  ordinatio, natalis, passio, transitus, commemoratio, memoria, festum,
  sollemnitas*, and the plural *commemorantur*.

A stop word counts only when it is **lowercase**, or when it is the **first word** of
the text in any case. The print capitalizes a saint inside a place name ("in
monasterio **S**ancti Cornelii", "ad **S**anctum Damianum"), while the subject's
honorific is lowercase ("**s**ancti Eugendi"). A drop-cap memorial or feast opens
with a capitalized stop word ("Sancti Fabiani…", "Sollemnitas…") and so has **no
opening place**.

Then:
- If the phrase is empty, or only *Item*, there is no opening place. (*Item* alone
  means "likewise, at the same place as before"; it is treated like *Ibidem*.)
- A leading *Item* is dropped from a non-empty phrase.
- *Ibidem*, or *Item* alone, resolves to the previous place (see Data shape). If the
  same day has no earlier entry with an opening place, there is no place, and the
  entry is listed in the report as unresolved.
- A trailing ", eodem die et anno" (on the same day and year) is stripped.
- The phrase is cut at a comma that starts a relative clause (*quod, quam, quo,
  qui, quae*), a reign (*sub …*) or a time phrase (*in eadem persecutione*,
  "… post annis"). *dormitio* and *sanctissimi / sanctissimae* are stop words too.
  The report lists every opening place that still contains a comma.
- A bare *Item* followed by *commemoratio / commemorantur* means "also, the
  commemoration of", not "at the same place": there is no opening place.
- `NOT_A_PLACE` lists openings that are not places (`mr:0101-maria-dei-genetrix`:
  "In octava Nativitatis Domini…", a time phrase), each with the reason.
- *Ibidem* followed by more words ("Ibidem in coemeterio …") keeps its printed
  phrase and records the antecedent in `via`.
- `via` always names the entry whose printed phrase supplies `la`, i.e. the root of
  a chain of back-references.

On the 2004 Latin, 4,260 entries get an opening place; 3 back-references stay
unresolved; 548 entries are curation candidates.

## Curated body places

`data/places_curated.json`: `{"<id>": [{"role": "<role>", "la": "<phrase>"}, …]}`,
starting as `{}`. Each item is validated:
- the ID is a current ID;
- the role is in the set;
- `la` appears **verbatim** in that entry's printed Latin text;
- `la` has at most 12 words;
- `la` is not identical to the entry's opening place.

## Pipeline

```
martyrology-texts (LA 2004) ─┐
data/martyrology_ids.json ───┤
data/typology.json ──────────┼─> scripts/extract_places.py ─> data/places.json
data/places_curated.json ────┘                                 docs/places-report.md
                                                                     │
workbook ─> scripts/extract_registry.py <── reads data/places.json ──┘
               └─> data/martyrology_ids.json (+ "places", after "typology")
```

- **`scripts/extract_places.py`** (standard library only). Run it with
  `python3 scripts/extract_places.py /path/to/martyrology-texts`. The extraction is
  a pure function of (text, typology, context), so it can be tested without the
  private texts. It reuses the text loader from `extract_typology.py`.
- **`data/places.json`**: `{"$comment": …, "roles": [7 roles], "places": {id:
  [items]}}`. Keys are sorted, and only IDs with at least one place are present.
- **`docs/places-report.md`**:
  - counts per role and per source;
  - entries with no place (IDs only);
  - unresolved *Ibidem / Item* back-references;
  - opening places over 12 words, with their `la` (these are allowed only through
    the allow-list, see Checks);
  - **curation candidates**: entries whose text holds a role cue outside the opening
    place, listed by ID and cue word only, and marked once curated. The cues are
    *natus, nata, ortus, orta, oriundus, oriunda* → `birth`; *episcopus/episcopi
    …ensis*, *sedem* → `ministry`; *sepultus, sepulta, tumulatus, tumulata* →
    `burial`; *obiit, obdormivit, defunctus, defuncta, occubuit* → `death`.
- **`scripts/extract_registry.py`** reads `data/places.json` (missing file: no
  places) and inserts `"places"` right after `"typology"` in each entry that has
  places. The private workbook isn't available here, so the field is applied to
  `data/martyrology_ids.json` with the same writer functions, as was done for
  typology.

## Checks

- `extract_places.py` asserts:
  - every key is a current ID, and no deprecated ID is present;
  - every role is in the set;
  - the role of every `lead` item matches the mapping from `typology`;
  - every `la` appears verbatim in its elogium;
  - no `lead` item has more than 12 words unless its ID is in `LONG_LEAD_OK`, a small
    allow-list where each entry has a comment saying why the long phrase is still a
    pure place designation;
  - every curated item passes the validation above.
- `extract_registry.py` asserts that the keys in `places.json` are a subset of the
  current IDs, failing with the same recovery message as for typology.

## Tests

`tests/test_places.py` (standard-library `unittest`, run with
`python3 -m unittest discover -s tests`), using made-up Latin phrases only. It
covers:
- a lowercase honorific ends the phrase;
- a capitalized saint inside a place name ("in monasterio Sancti Ficti") stays in
  the phrase;
- a capitalized stop word at the start means no opening place;
- *Item* dropped; *Ibidem* and bare *Item* resolved with `via`; unresolved when no
  antecedent exists;
- `la` keeps the printed accents and ligatures, and its offsets match the original;
- each typology → role mapping;
- curated validation: verbatim accepted; non-verbatim, overlong, duplicate-of-lead
  and unknown-role items rejected;
- the registry merge puts `places` after `typology`, handles a missing file, and
  fails on a non-current key.

The same 5-word overlap scan used for #10 must find no match between the tests and
the real texts.

## Review against the real data

Before committing the generated data, every opening place over 12 words and a
random sample of 100 opening places are read against the Latin. Each extraction
error becomes a rule fix or an allow-list entry.

## Documentation

- `AGENTS.md` and `README.md`: the quoting exception, `data/places.json`,
  `data/places_curated.json`, `extract_places.py`.
- `docs/canonicalization-report.md`: a new "Places" section with the data shape,
  roles, extraction rule and the curation workflow.
