# Subject identity: the places as evidence — design addendum

Addendum to `2026-10-18-subject-identity-design.md`. Date: 2026-10-25. The gazetteer is complete
(4,031 printed place phrases decided, `data/gazetteer.json`; issue #12 closed), so every place a eulogy
prints now has a Wikidata item. The subject pipeline was paused until then: the places can tell a saint
from a namesake, and give the rename's place a stable identity.

## Why

The pipeline ignores the places today:

- **Matching.** `build_person_items.py` judges a candidate on `human`, `status`, `name` and, for a
  *dies natalis*, `death` (the death date on the eulogy's day). It never compares the candidate's places
  with the eulogy's, so a namesake who died elsewhere looks as good as the saint, and a saint whose item
  lacks an exact death date but records where he died is not told apart.
- **Search.** The extra routes (`expand`) go through the companions' kin, the saints of the death day
  and the titles. A saint with no exact P570 is missed even when Wikidata records his place of death.
- **Renames.** `PLACE_GENITIVES` (`scripts/rename_candidates.py`) knows 8 places; every other genitive is
  coined from the record and marked uncertain, which is why about 230 January renames were low
  confidence. The record's places are keyed by their printed form, not by what they are.

## Goals

1. **Place agreement, shown.** For each person candidate, say which of the eulogy's places its item
   records, and in what role: on the card and to Jev.
2. **A place route.** Candidates whose place of death or burial is the eulogy's place, with a matching
   given name, are added like the death-day route's.
3. **One genitive per place item.** The rename's place genitive is chosen by the place's Wikidata item,
   from the genitives the corpus's IDs already use, so one place has one genitive everywhere.
4. **The subject rename on its own** (`relabel`): the eulogy's Latin, English and Italian subjects are
   decided apart from its ID, each of the three decisions (ID, subject, item) with Jev's suggestion.
5. **Regenerate**: January's undecided cards first (every decision kept), then February to December, one
   month at a time.

## Non-goals and anti-goals

- **The auto bar is unchanged** (curator, 2026-10-25): a person resolves by itself only with `human`,
  `status`, `name` and, for a *dies natalis*, `death`. Place agreement never makes a card automatic and
  never blocks one. It is evidence for the curator and for Jev.
- **The candidate order is unchanged** (*builder's call, for the curator to confirm*): an accept with no
  suggestion takes `candidates[0]`, so the order is part of the decision. Place agreement is not counted
  in the sort; a card may show it, Jev may weigh it, the order stays what the evidence bar gives.
- No new card type, no change to the decided January cards, no place data written to Wikidata.
- **Anti-goal:** place agreement read as identity. Two saints can die in one city (Rome); agreement is a
  hint, never proof, and a disagreement never removes a candidate.

## The eulogy's places

`eulogy_places(mrid)`: the eulogy's places from `data/places.json` (the opening place and the curated
ones, each with its role: death, burial, birth, ministry, religious life, translation, mention…), each
resolved through `gazetteer_text.lookup(gazetteer, la, mrid)` to `{role, qid, label}`. Unresolved phrases
(no item) and the `sites` of a disputed place are left out. A place's possible sites are not its item.

## Place agreement

The person summary (`wikidata.summarize_person`) gains the current, non-deprecated values of four
properties, as `current_qids` reads them: `birth_place` (P19), `death_place` (P20), `burial_place`
(P119), `work_places` (P937). The raw entity is cached already, so no lookup is repeated.

A candidate **agrees** with a eulogy place when one of its place QIDs is the place's item, or the two
are one step apart in P131 (located in the administrative entity), either way: a hermitage in a town,
a town in a diocese's city. The P131 steps come from the place summaries (`Wikidata.items`), fetched once
per run for the QIDs involved and cached as now.

Roles pair as follows. A pairing outside the table is not agreement.

| Eulogy role | Candidate's properties |
|---|---|
| death (and a *dies natalis*'s opening place) | P20, then P119 |
| burial, translation | P119, then P20 |
| birth | P19 |
| ministry, religious life, foundation | P937, then P20 |

The candidate gets the evidence string `place` when anything agrees, and a `places` list,
`[{role, qid, label, via}]` with `via` the property (`P20`…), for the card and for Jev. `place` is not in
`_required` and not in the sort key.

## The place route

In `expand`, for a person whose eulogy has a death or burial place: a SPARQL query for humans with a
saint or blessed status (`SAINT_STATUSES`) whose P20 or P119 is the place's item, and whose label or alias
matches a given name equivalent to the Latin (`NAME_EQUIVALENTS`), as the death-day route matches. Capped
like it (`MAX_SPARQL`); source `place`. Rome (Q220) and the other places with very many saints are left
to the other routes when the query would pass the cap; the cap is a guard, not a filter.

## Jev

The person request's state gains the eulogy's places (`[{role, label}]`), and each candidate its places
(`death_place`, `burial_place`, `birth_place`, `work_places` as labels) and its `places` agreement. The
questions do not change: Jev still chooses the item among the candidates or "none".

## One genitive per place item

- Each record place is linked to its item: the place in `data/places.json` whose Latin contains the
  record's printed form (or the opening place for the record's see or place of death), resolved through
  the gazetteer. A place with no link keeps today's behaviour.
- **The corpus map** `place_genitives(repo)`: `{place QID: genitive slug}`, mined from every current ID.
  A current ID whose last slug token(s) are a genitive of one of its eulogy's place items gives that item's
  genitive.
- **When it is certain** (curator, 2026-10-25): a mined genitive is certain only when **two or more** IDs
  give it and none gives another. A genitive one ID gives is offered, uncertain. An item with two
  genitives is listed in the report (`docs/rename-genitives-report.md`), both offered as uncertain, until
  the curator picks one in `PLACE_GENITIVES`; the report never blocks a build. The hand-written
  `PLACE_GENITIVES` stays the override, and is certain.
- `genitive_slug` takes a certain map genitive for the record place's item as **certain**; the record's own
  genitive and the locative stay uncertain fallbacks.
- The English and Italian subjects keep the record's `en` and `it` place names. A label from the
  gazetteer is the fallback when the record has none.

## Three decisions per eulogy, each with Jev's suggestion

A eulogy's card carries up to three kinds of operation, each decided on its own, and each shows Jev's
suggestion the way the gazetteer review did ("Jev suggests", its percentage, "Take the suggestion"):

1. **The ID rename** (`rename`): the new ID among the candidates, as now.
2. **The subject rename** (`relabel`, new): the eulogy's subject in Latin, English and Italian
   (`i18n/la.json`, `en.json`, `it.json`). Its candidates are the label sets the rename candidates imply
   (R3) and the current labels; the curator takes one, edits one, or keeps the current. It is decided
   apart from the ID, so a kept ID can get better labels and a new ID can keep its labels. Today the labels
   ride on the rename candidate; with `relabel` they no longer do. Jev ranks the label sets with the same
   Score as the renames ("how clearly and conventionally it names this saint"). `apply_renames.py` writes
   an accepted `relabel` to the three `i18n` files (for the new ID when the eulogy is also renamed).
3. **The Wikidata item** (`resolve_person`, one per person): as now, with the place agreement.

Jev's answers are shown on every card (`--min-confidence 0`), in February too (curator, 2026-10-25). The
evaluation (Task 9) is therefore of agreement with suggestions the curator saw, and is read as such.
*Builder's call:* prefilled decisions (`op.prefilled`), as January had them (rule-prefilled renames, Jev
persons at p ≥ 0.9), are written by a script step from now on (`suggest_subjects.py prefill`), not by hand,
and stay undoable on the card.

## Regeneration

- **January.** The curator has decided nothing since the 2026-10-19 export, so
  `~/private-changesets/subject-identity/01/crmedr-subjects-01.json` (identical to the copy in
  `CHANGESETS_DIR`) is the record of the decisions. Rebuild only its undecided operations: every op with a
  curator's decision, or a prefilled one (`op.prefilled` "rule" or "jev"), is kept byte for byte. The rebuilt ops get
  the new evidence, candidates and Jev answers (`--min-confidence 0`); the merged file is checked to hold
  the same op IDs as before, plus any new person, and uploaded to `CHANGESETS_DIR` in place of the old one.
- **February to December.** As the January pipeline: briefs, records by research agents (now with the
  place items in the brief), `check`, rename candidates, `build_person_items.py expand`, Jev with
  `--min-confidence 0`, one combined file per month, `crmedr-subjects-MM.json`, uploaded to
  `CHANGESETS_DIR`. February first; Task 9 (`suggest_subjects.py evaluate`, thresholds on unseen
  decisions) after the curator decides it, then March to December.
- **The persons bundles.** When a month's `crmedr-subjects-MM.json` is uploaded, its
  `persons-review-MM.json` bundle leaves `/review` (`npm run import-changeset … --by-month` skips the
  months listed in `--except-months`), so a person is never on two cards.

## Frontend

- The `relabel` card: the three subjects of each candidate, the current ones marked, Jev's pick, accept /
  edit (three fields) / keep current. On a eulogy's grouped card it sits between the rename and the persons.

`PersonCard` shows each candidate's evidence as labelled chips, translated in the six languages,
including `place` with its agreements ("died in Bologna", "buried in Rome"), and the source `place`.

## Testing

- `summarize_person` reads the four properties, skipping deprecated and ended values.
- Agreement: the same item; one P131 step either way; a role pairing outside the table is no agreement;
  `place` changes neither `auto` nor the order (an existing auto case stays auto; a non-auto case stays
  non-auto with place agreement).
- The place route: a SPARQL fake returns a saint whose P20 is the place, matched by name; the cap.
- The genitive map: mined from IDs; two genitives for one item reported; `genitive_slug` certain from
  the map.
- January rebuild: decided and prefilled ops unchanged; undecided ops rebuilt; same op IDs.
- `relabel`: candidates from the renames and the current labels; Jev's Score; `apply_renames.py` writes
  an accepted one to the three `i18n` files, under the new ID when the eulogy is renamed in the same file.
- `prefill`: the rule and Jev prefills as January's, marked `op.prefilled`; a decided op is never touched.
- Frontend: chips and their translations; the `place` source badge; the `relabel` card's accept, edit and
  keep.

## Left to the builder

- The exact SPARQL for the place route, and the list of places too large for it.
- How a record place finds its `data/places.json` item when the printed form is not contained in it (an
  adjective printed apart from the place phrase): leave it unlinked, today's behaviour.
- Chip styling.

## Curator's decisions (2026-10-25)

1. Place agreement is shown on the cards and to Jev; it does not count toward auto.
2. January keeps every decision (the 2026-10-19 export is complete); only undecided cards are rebuilt.
3. Jev's suggestions are shown on every card, February included, as in the gazetteer review; the eulogy
   ID rename, the subject rename and the Wikidata item are each adjudicated with a suggestion.
4. Genitives from the IDs: certain with two or more agreeing IDs and none disagreeing; one ID, uncertain;
   two genitives for one item, reported and uncertain until the curator picks.
5. A month's `persons-review-MM` bundle leaves `/review` once its `crmedr-subjects-MM` file is uploaded.
