# Every place a eulogy names, with its role (places, sub-project 4) — design

Issue: [#12](https://github.com/CatholicOS/crmedr/issues/12). Date: 2026-10-14. Builds on
`docs/superpowers/specs/2026-09-30-places-extraction-design.md` (sub-project 1),
`docs/superpowers/specs/2026-10-01-gazetteer-design.md` (sub-project 2) and
`docs/superpowers/specs/2026-10-14-registry-place-countries-design.md` (sub-project 3).

## Goal

Record **every place a eulogy names**, each with the role it plays in that eulogy, and
mark each one in the Latin and Italian 2004 texts. This is the purpose of #12: several
typed places per eulogy, not only the opening place. Today `places` holds the opening
place of each eulogy and four hand-curated body places, while the texts name many more:
*Núrsiæ in Umbria natus*, *Romæ educátus*, *Cluníaci mónachus*, *Zagábriæ sedem
episcopálem cóndidit*, *Obiit vero Trebnítii in Polónia*.

## Decisions

- **Scope: every place named**, not only biographical anchors. Each named place gets an
  item and a mark in the text.
- **A role belongs to one eulogy's place item**, never to the place. The gazetteer holds
  what a place is (item, label, country); `places[]` holds what it means in that eulogy.
  One town can be `foundation` in one eulogy, `death` in another and `ministry` in a
  third.
- **Fine-grained roles first**; merging roles later is a mechanical change.
- **A role names its person** when the eulogy commemorates several persons and the role is
  one person's (`person`, `n`), as `data/persons.json` identifies them; it is omitted
  when the role is the whole group's or the eulogy's only subject's.
- **Approach: proposed by the model, checked by a script, decided by a person.** Subagents
  read the texts and propose; a script rejects anything that breaks the quoting and
  identity rules; the user reviews the rest in martyrology-frontend. The model never
  decides.
- **The registry `country` stays tied to the opening place** (sub-project 3); body places
  never change it.

## Roles

A closed set; `ROLES` in `scripts/extract_places.py` and `roles` in `data/places.json`
become:

| Role | Covers |
|---|---|
| `death` | death or martyrdom (the opening place of a `dies_natalis`; a body place when it is elsewhere) |
| `burial` | burial |
| `translation` | where relics were moved |
| `dedication` | the church dedicated |
| `cult` | where venerated |
| `birth` | birth or origin |
| `education` | upbringing, studies |
| `religious_life` | a monastery or house entered, professed or lived in |
| `ministry` | a see, parish, office or mission field |
| `foundation` | something founded there |
| `exile` | exile, deportation |
| `captivity` | arrest, imprisonment, chains, captivity (a prison where the saint died is `death`) |
| `journey` | pilgrimage, travel, passing through |
| `mention` | a place named for another reason: an event, a council, another person's see or title (*a sancto Eusébio Vercellénsi*) |

Opening places keep their roles from typology, unchanged.

## Data

### `data/places_curated.json`

Body places are curated items, in the existing file:

```json
"mr:0711-benedictus": [
  { "role": "birth", "la": "Núrsiæ in Umbria", "it": "a Norcia in Umbria" },
  { "role": "education", "la": "Romæ", "it": "a Roma" }
],
"mr:0101-x-et-socii": [
  { "role": "birth", "la": "Smyrnæ", "it": "a Smirne", "person": "Pionius" }
]
```

- `role`, `la` required; `it`, `person`, `n`, `occurrence`, `occurrence_it` optional.
- `la` / `it`: the place designation only, verbatim, within the existing limits
  (`MAX_WORDS` 12, `MAX_WORDS_IT` 20); the cue word stays out (*Núrsiæ in Umbria*, not
  *…natus*). An adjectival see is quoted as the adjective (*Morinénsem*, Italian *di
  Thérouanne*). `it` is omitted when the Italian has no counterpart.
- `person` / `n`: a name (and number) of that eulogy in `data/persons.json`.
- `occurrence` (from 1): which printing of `la` in the Latin text, required only when `la`
  is printed more than once there; `occurrence_it` likewise for `it` in the Italian.
- One role per item; a place with two roles has two items (they may share a printing).
- No two items of one eulogy share (`la`, `occurrence`, `role`, `person`, `n`).
- No item's span overlaps the opening place's span.

`validate_curated` in `extract_places.py` enforces all of this; `extract_places.py`
copies the items into `data/places.json` with `source: "curated"`, keeping the new keys.

### Mentions: `roles` on place mentions

A place mention in `data/mentions.json` gains `roles`, from the place items that point at
its span:

```json
{"kind": "place", "where": "text", "start": 31, "end": 47, "check": "…", "qid": "Q…",
 "roles": [{"role": "birth"}, {"role": "burial"}]}
{"kind": "place", "where": "text", "start": 80, "end": 85, "check": "…", "qid": "Q…",
 "roles": [{"role": "ministry", "name": "Pionius"}]}
```

- One printed span, one mention; `roles` lists every item on it, in item order, each
  `{role}` plus `name` / `n` when the item has `person` / `n` (`name`, as person mentions
  call it).
- The opening place's mention carries its role too, so every place mark has `roles`.
- A body place is found as the opening place is today (as printed, then folded), using
  `occurrence` to pick the printing; one not found becomes an `add_mention` proposal,
  never a guess.

## The proposal pass (one-off, model)

- Subagents work in half-month batches (about 200 eulogies each), a few at a time. Each
  reads, locally, the eulogies' Latin and Italian 2004 texts, their opening places
  (`data/places.json`) and their persons (`data/persons.json`).
- For each place named outside the opening place, an `add_place` proposal: `id`, `la`,
  `it`, `role`, `person` / `n`, `occurrence` / `occurrence_it` where needed, `confidence`
  (`high` / `medium` / `low`) and `reasoning` (short English, quoting nothing beyond the
  place designation).
- No Wikidata guess: new places go through `build_gazetteer.py propose` and its review.
- The proposals are written outside the repository (scratch), then checked.

## `scripts/body_places.py`

Stdlib only; reads the private `martyrology-texts` repo for `check` (no network).

- `check <proposals.json> /path/to/martyrology-texts`: validates each proposal with the
  same rules as `validate_curated`, plus: the role is in `ROLES`; the item is not already
  in `places_curated.json`; it was not rejected before (see `rejected`). Writes the
  passing proposals as `add_place` ops into `data/places_review.json` (no existing op is
  changed) and prints the failures, which go back to a subagent once for correction;
  what still fails is listed in `docs/places-report.md` and never reaches review.
- `apply <exported.json>`: for each decided op: `accept` / `edit` adds the item (with the
  edits) to `data/places_curated.json`, validated; `reject` records the item under
  `rejected` in `data/places_review.json` so a later pass does not propose it again.
  Decided ops are removed; undecided ops stay. An invalid decision fails the whole apply,
  as in the gazetteer.
- **Recall check** (in `extract_places.py`'s report): every gazetteer place whose Latin
  form is printed in a eulogy's body, outside every item's span, is listed under
  "Places named but not recorded" in `docs/places-report.md`.

### `data/places_review.json`

`crmedr-changeset/v1`, op `add_place`, in the repository like the gazetteer's change-set
(it quotes only place designations):

```json
{"op": "add_place", "id": "mr:0711-benedictus#birth#Núrsiæ in Umbria", "eulogy": "mr:0711-benedictus",
 "la": "Núrsiæ in Umbria", "it": "a Norcia in Umbria", "role": "birth",
 "confidence": "high", "reasoning": "…", "decision": null, "edited": null}
```

`edited` may change `la`, `it`, `role`, `person`, `n`, `occurrence`, `occurrence_it`; the edited item is
validated on apply.

## martyrology-frontend

- **Review card** for `add_place`: the eulogy's Latin and Italian (from the API) with the
  proposed span highlighted; role and person selectors; accept / edit / reject; bulk
  accept by confidence; paging, as the `resolve_place` card has.
- **Display**: the place popup in the eulogy text shows the roles in the reader's
  language ("born here", "bishop here", "founded here") and, when given, whose; the index
  of places and the map list each eulogy under a place with its role, with a role filter.
  Role labels in all six locales.

## martyrology-api

`MentionBase` gains optional `roles: list[{role, name?, n?}]` on place mentions (`role` in
the closed set; `name` / `n` as for persons); served as given; the OpenAPI / Scalar
reference updates. Live at the crmedr pin bump.

## Rollout

1. crmedr: roles, curated validation, `body_places.py`, the change-set, `roles` on
   mentions, the recall check (no proposals yet).
2. The proposal pass and `check`; the change-set committed.
3. martyrology-frontend: the review card; the user reviews.
4. `body_places.py apply`, then `build_gazetteer.py propose` (suggestions and review for
   new places), then `extract_places.py`, `registry_places.py`, `extract_mentions.py`.
5. martyrology-api: `roles` on mentions, pin bump, release; martyrology-frontend: the
   display.

Three implementation plans: crmedr core (1, and the tooling for 2 and 4);
martyrology-frontend review card (3); martyrology-api and frontend display (5).

## Tests

- `validate_curated`: new keys, roles, `person` / `n` against persons, `occurrence`,
  duplicates, overlap with the opening place.
- `body_places.py`: `check` (each rejection reason; passing proposals become ops; existing
  ops untouched; rejected items not re-queued), `apply` (accept, edit, reject, undecided,
  invalid decision fails all).
- Mentions: `roles` on a lead and a body place; two items on one span give one mention
  with two roles; `occurrence` picks the second printing; an unfound body place becomes
  `add_mention`.
- The committed-data tests (`registry_places.py --check`, `build_gazetteer.py check`)
  hold at every step.

## Out of scope

- Places in footnotes (lists of martyrs' names).
- Deprecated entries.
- Merging roles (a later, mechanical change).
- Persons' places from Wikidata (e.g. P19 birthplace): only what the eulogy states.
