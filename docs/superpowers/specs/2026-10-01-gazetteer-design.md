# Gazetteer for place designations (places, sub-project 2) — design

Issue: [#12](https://github.com/CatholicOS/crmedr/issues/12). Date: 2026-10-01. Builds on
`docs/superpowers/specs/2026-09-30-places-extraction-design.md` (sub-project 1) and
`docs/superpowers/specs/2026-09-30-places-italian-design.md` (`places[].it`).

## Goal

Resolve each distinct place designation in `data/places.json` **once** to a Wikidata
item, a modern label and a modern country, with a review decision for each place.
Sub-project 3 (out of scope here) will copy the result into `places[].modern` and
`places[].country` and cross-check each entry's `country`.

The principle of sub-project 1 holds: **an unresolved place is better than a guessed
one.** A place is resolved only by strong, consistent evidence (`auto`) or by a
person (`reviewed`).

## Scope

In scope:
- Every distinct `la` in `data/places.json` (lead and curated items; current entries
  only).
- `data/gazetteer.json`, `scripts/build_gazetteer.py`, the review change-set
  `data/gazetteer_review.json`, `docs/gazetteer-report.md`, unit tests, docs.
- The `resolve_place` op of `crmedr-changeset/v1`, defined here so both repositories
  share it.

Out of scope:
- Writing `modern` / `country` into `places` items or the registry (sub-project 3).
- Deprecated entries.
- The review UI itself: a separate PR in `CatholicOS/martyrology-frontend`, built to
  the op format below.
- Sites below the resolved place as separate data (see Granularity).
- Coordinates in the published data. The QID is the key to them; candidates carry
  P625 only for the review UI.

## Granularity

Each place resolves to **the most specific place that has a stable Wikidata item**:
usually the settlement or territory. *Romæ apud sanctum Petrum* → Rome; *In
monastério Chozíbæ in Palæstína* → the Choziba monastery if Wikidata has an item for
it, otherwise the nearest settlement. Basilicas, catacombs and minor churches named
inside a city phrase are not resolved separately; they remain visible in `la`.

## Data shape: `data/gazetteer.json`

```json
{
  "$comment": "…",
  "statuses": ["auto", "reviewed", "unresolved"],
  "places": {
    "Londínii in Anglia": {
      "wikidata": "Q84", "label": "London", "country": "GB", "status": "auto"
    },
    "Lauríaci in Nórico Ripénsi": {
      "wikidata": "Q…", "label": "Enns", "country": "AT", "status": "reviewed",
      "text_says": [
        { "country": "DE", "it": "A Lorch nel Norico ripense, nell’odierna Germania" }
      ]
    },
    "Ad montem Fictum": {
      "wikidata": null, "status": "unresolved", "note": "no Wikidata item for the hill"
    }
  }
}
```

- **Key**: the exact printed `la`, so it joins `places[].la` directly. Phrases that
  differ only in accents remain separate keys (5 cases).
- **`wikidata`**: a QID (`Q\d+`), or `null` only when `status` is `unresolved`.
- **`label`**: the item's English label (Italian if it has none) when it was
  resolved. A readability snapshot; the QID is authoritative. Absent when unresolved.
- **`country`**: ISO 3166-1 alpha-2 of the place's **actual** modern country. From
  the item's single current P17, or set by a reviewer when P17 is missing, has
  several current values (Jerusalem) or the place is a historical region (*Bithynia*
  → `TR`). No workbook conventions are applied here (e.g. `PS` for the whole Holy
  Land); reconciling them is sub-project 3's cross-check. Absent when unresolved.
- **`status`**: `auto` (passed the evidence bar), `reviewed` (a person accepted or
  edited it), `unresolved` (a person decided there is no suitable item).
- **`text_says`** (optional): a list of `{country, it}`, one per Italian wording of
  this place that names a modern country other than `country`. `it` is the Italian
  phrase verbatim, so sub-project 3 can attach the note to exactly the items whose
  `it` matches. Only wrong **countries** go here.
- **`note`** (optional): free text; required for `unresolved`. Wrong regions or
  misnamed cities in the text are recorded here.
- **Places awaiting review have no key.** Every key in the file is a decision.
  Candidates, scores and suggestions live only in the review change-set.
- Keys are sorted; key order within an entry is `wikidata`, `label`, `country`,
  `status`, `text_says`, `note`.

## Pipeline

```
data/places.json ─┐                       ┌─> data/gazetteer.json (auto entries)
                  ├─> build_gazetteer.py ─┤
Wikidata API ─────┘      propose          └─> data/gazetteer_review.json (resolve_place ops)
                                                       │
                       Claude suggestions ─────────────┤ (suggested, reasoning, confidence)
                                                       ▼
                                       martyrology-frontend /review
                                                       │ exported decisions
                                                       ▼
                         build_gazetteer.py apply ─> data/gazetteer.json (reviewed/unresolved)
                                                  └─> docs/gazetteer-report.md
```

`scripts/build_gazetteer.py` uses only the standard library (`urllib`). It reads no
private sources, since its input is already public, but `propose` needs network
access. Subcommands:

### `propose` (network)

1. Collect each distinct `la` in `places.json` with **no key** in `gazetteer.json`,
   together with its Italian variants (the distinct `it` of its items) and the IDs it
   occurs in.
2. For each place, find candidates (see Candidate search), score them against the
   evidence bar, and:
   - with exactly one candidate passing, write an `auto` entry to `gazetteer.json`;
   - otherwise write a `resolve_place` op to `data/gazetteer_review.json`, with the
     ranked candidates and the rules that failed.
3. Never modify or remove an existing key in `gazetteer.json`. Existing ops in the
   change-set keep their `suggested`, `reasoning` and `confidence`; only their
   candidate lists are refreshed.
4. Regenerate the report.

Wikidata responses are cached under `.cache/wikidata/` (added to `.gitignore`), keyed by
request, so a rerun is fast and reproducible. Requests send a User-Agent naming the
project and its repository URL, follow the API's `maxlag` etiquette, and retry
HTTP 429/5xx with backoff. A place whose lookups fail is listed in the run's output
as not processed and left for the next run; it is never written as `auto` or
`unresolved`.

### `verify-suggestions` (network)

Claude (approach 3) works through the change-set in batches and writes into each op
`suggested: {wikidata, country, text_says?}`, `reasoning` and `confidence`
(`high | medium | low`). This subcommand then checks every suggestion: the QID
exists; if it is not among the candidates, it is fetched and added (so the UI shows
its evidence); and a suggested `country` that differs from the item's single current
P17 must be explained in `reasoning` (the subcommand lists those for a re-read). A
suggestion never makes a place `auto`.

### `apply <exported change-set>` (offline)

Reads the decisions exported from martyrology-frontend:
- `accept` → `reviewed`, from `suggested` (or the top candidate when there is none);
- `edit` → `reviewed`, from `edited.wikidata`, `edited.country`,
  `edited.text_says` (fields not given fall back to `suggested`, then to the
  chosen item's own label and P17);
- `reject` → `unresolved`, with `edited.reason` as `note` (required).

`label` comes from the candidate data in the op, or is fetched if the reviewer
entered a QID that is not among the candidates (this is the one case where `apply`
uses the network). Decided ops are removed from `gazetteer_review.json`; undecided
ops stay. An op whose `la` is already a key is an error (no silent overwrite). The
report is regenerated.

## Candidate search

- **Italian head toponym.** From each Italian variant: drop the leading preposition
  (*A, Ad, In, Nel, Nella, Nello, Nei, Negli, Presso, Nei pressi di, Vicino a…*),
  then take the place name up to the first region connector (*in, nel, nella,
  nell’, nelle, nei, presso, vicino a*) or comma. A site head ("Nel monastero di
  Coziba") yields both the full phrase ("monastero di Coziba") and the bare name
  ("Coziba").
- **Region.** The rest of each phrase after the connector: Latin *in Anglia*, *in
  pago …*; Italian "in Inghilterra", "nelle Fiandre".
- **Modern-country claim.** Italian "nell’odierna X", "nell’attuale X", "ora in X",
  "oggi in X", "in territorio dell’odierna X", and a trailing ", in X" where X is a
  country name. Country names map to ISO codes through an embedded Italian-name
  table.
- **Latin nominatives.** From the Latin head word, after folding accents and
  ligatures: locative and ablative endings mapped to candidate nominatives
  (*-æ/-ae → -a*; *-i → -um, -us, -ium*; *-is → -a, -ae, -i*; *-o → -um, -us*;
  *-e → -is* and similar). This only adds evidence, so a missing form sends the
  place to review and never causes a wrong `auto`.
- **Search.** `wbsearchentities` in Italian on each head toponym (top 10), then
  `wbgetentities` for the candidates' `it`/`la`/`en` labels and aliases, P17 (with
  qualifiers, so ended statements are excluded), P31, P9314 and P625. Regions are
  searched the same way.
- **Current P17.** A P17 statement is current when its rank is not `deprecated` and
  it has no end time (P582); if any current statement has `preferred` rank, only
  the preferred ones count. Country items map to ISO codes through their P297 (one cached SPARQL query), plus
  `EXTRA_COUNTRY_ISO` for countries that P17 names without a P297 (Q55, the
  Netherlands → NL).

## The evidence bar for `auto`

A place is `auto` only if exactly one candidate meets **all** of:

1. **Italian name**: its Italian label or an Italian alias equals the head toponym
   of **every** Italian variant of the place (accents and case ignored). Several
   items often share a name (a town, a school, a hamlet: all "Bressanone"); the
   other rules separate them, and if more than one candidate passes **all** rules
   the place goes to review (homonyms: Guadalajara, Córdoba).
2. **Latin name**: a `la` label or alias equals one of the Latin nominatives, or the
   item has a P9314 (Latin Place Names ID) value.
3. **Country**: the item has exactly one current P17 (no end time), and
   - every modern-country claim in the Italian names that country, and
   - every region stated in the Italian resolves, by the same search, to at least
     one item with that exact Italian name whose current P17 is that country, or
     that is that country. (Latin regions are not checked: places without Italian
     never pass rule 1, and the Italian region renders the Latin one.)
   With no region and no claim in any Italian variant, the country must be `IT`
   (the CEI edition names no region for Italian places) unless the item is itself a
   country (it has P297). *antico/antica* before a region name is skipped.
4. **Type**: one of its P31 values is, through `P279*` (subclass of), one of the
   root classes listed in the script: human settlement (Q486972), administrative
   territorial entity (Q56061), monastery (Q44613), church building (Q16970),
   archaeological site (Q839954), island (Q23442), mountain (Q8502), region
   (Q82794), historical region (Q1620908), historical country (Q3024240), cave
   (Q35509), castle (Q23413), country (Q6256). Each class is checked once with a SPARQL `ASK` and
   cached. This keeps out a person, a school, a film or a ship named like the
   place.
5. **Not forced to review**: `FORCE_REVIEW` (in the script, each with a comment)
   lists places that pass but are known to be wrong because the Italian and
   Wikidata agree on another place than the Latin names.
6. **No disagreement**: no `text_says` would be needed. Any disagreement between the
   text and the item's country is decided by a person.

Places with no Italian variant (the 4 items without `it`) cannot meet rule 1 and
always go to review.

## Review change-set: the `resolve_place` op

`data/gazetteer_review.json` is a `crmedr-changeset/v1` document
(`base: {edition: "2004", registry: "data/places.json"}`) whose operations are:

```json
{
  "op": "resolve_place",
  "id": "Lauríaci in Nórico Ripénsi",
  "la": "Lauríaci in Nórico Ripénsi",
  "it": ["A Lorch nel Norico ripense, nell’odierna Germania"],
  "occurrences": ["mr:0504-florianus"],
  "claims": [{ "country": "DE", "it": "A Lorch nel Norico ripense, nell’odierna Germania" }],
  "failed": ["country: the Italian says DE, the item is in AT"],
  "candidates": [
    { "wikidata": "Q…", "label": "Enns", "description": "…", "country": "AT",
      "countries": ["AT"], "la": ["Lauriacum"], "p9314": false,
      "coords": [48.21, 14.47], "types": ["Q3957"], "evidence": ["it", "la", "type"] }
  ],
  "suggested": { "wikidata": "Q…", "country": "AT",
                 "text_says": [{ "country": "DE", "it": "A Lorch nel Norico ripense, nell’odierna Germania" }] },
  "reasoning": "Lauriacum is Enns/Lorch in Upper Austria …",
  "confidence": "high",
  "decision": null,
  "edited": null
}
```

- `id` is the `la` (the frontend's `opId` uses `id`).
- `candidates` are ranked by evidence count, then by search rank. `country` is the
  single current P17 or `null`; `countries` lists all current P17 values (ISO codes);
  `types` are the P31 QIDs.
- The frontend extends `EditedFields` with `wikidata`, `country`, `text_says`
  (`reason` already exists) and treats `resolve_place` as adjudicable.
- The phrases quoted are place designations only, within the quoting exception.

## Report: `docs/gazetteer-report.md`

- Counts by status, and the number of places awaiting review.
- Places awaiting review: `la`, number of occurrences, failed rules.
- Every `text_says`: place, actual country, the countries the text says.
- Preview for sub-project 3: lead places whose gazetteer `country` differs from the
  entry's registry `country` (ID, `la`, both codes).

## Checks

`build_gazetteer.py` validates `gazetteer.json` after every write, and a test runs
the same validation on the committed file:
- every key occurs as a `la` in `places.json` (a stale key fails, telling the user
  to remove or re-key it);
- `status` is in the enum; `wikidata` is a QID, or `null` exactly when `unresolved`;
- `label` and `country` are present unless `unresolved`; `country` is in the
  embedded ISO 3166-1 alpha-2 set;
- `unresolved` has a `note`;
- every `text_says[].it` is an `it` of an item with that `la`, and its `country`
  differs from the gazetteer entry's own `country`;
- no key is both in `gazetteer.json` and an op in `gazetteer_review.json`.

## Tests

`tests/test_gazetteer.py` (standard-library `unittest`), with made-up phrases and
fake Wikidata JSON; no network:
- Italian head toponym, site head and region extraction;
- modern-country claim parsing;
- Latin nominative generation;
- each rule of the evidence bar, including homonyms (two candidates pass rule 1),
  an Italian-variant disagreement, a country claim against P17, ended P17
  statements, and a disallowed type;
- `propose` never modifies existing keys and keeps existing suggestions;
- `apply` for accept, edit and reject, a reject without a reason, and an op whose
  key already exists;
- each validation rule;
- the committed `gazetteer.json` passes validation against `places.json`.

The 5-word overlap scan used for the earlier sub-projects must find no match between
the tests and the real texts.

## Rollout

1. Script, tests, docs; a first `propose` run commits the `auto` entries, the
   change-set and the report. Before committing, a random sample of 50 `auto`
   entries is checked by hand; any wrong one becomes a rule fix.
2. Suggestions written in batches and verified.
3. The martyrology-frontend PR (the `resolve_place` card).
4. Review rounds: export → `apply` → commit, repeated until the queue is empty.
   These can be separate PRs.

## Documentation

- `AGENTS.md` and `README.md`: `data/gazetteer.json`, `data/gazetteer_review.json`,
  `scripts/build_gazetteer.py` (needs network, no private sources) and the review
  loop.
- `docs/canonicalization-report.md`: a "Gazetteer" subsection under Places with the
  data shape, the evidence bar and `text_says`.
