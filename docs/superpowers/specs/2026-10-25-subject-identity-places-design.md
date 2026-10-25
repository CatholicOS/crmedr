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
4. **The subject rename beside the ID rename** (`relabel`): the eulogy's Latin, English and Italian
   subjects follow its decided ID, with their wording adjustable, and a decided single person's Wikidata
   labels as a hint.
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

## The ID and its subject, decided together (revised 2026-10-25)

A bare-name eulogy's card carries the ID rename and the subject rename, and one Wikidata decision per
person. The ID and the subject are two steps, but they go hand in hand: **the eulogy's subject follows its
ID** (curator, 2026-10-25). "Subject" here is the eulogy's own subject in the three `i18n` files ("Sanctus
Almachius Romae" / "Saint Almachius of Rome" / "Sant'Almachio di Roma"), not the labels of the persons it
commemorates (those come from their items).

1. **The ID rename** (`rename`): the new ID among the candidates, with Jev's suggestion, as now.
2. **The subject rename** (`relabel`): the eulogy's subject in Latin, English and Italian. It follows the
   ID:
   - Its proposal is the subject the **decided** ID implies: the labels of the rename candidate whose ID the
     curator accepted or picked (R3). Picking another ID changes the proposal. While the rename is
     undecided, the card shows the subject of the rename's proposed ID, marked as following an undecided ID.
   - **Follow the ID** (`accept`) writes exactly those labels. It is possible only when the decided ID is
     one of the candidates (a typed ID has no implied subject: edit instead).
   - **Edit the wording** (`edit`, three fields, prefilled with the followed subject) adjusts the wording
     for the same ID; **Keep the current subject** (`reject`) writes nothing.
   - An undecided subject card with a decided rename writes the followed subject (today's behaviour), so
     the ID and the subject can never be written apart.
   - No independent Jev pick and no prefill for the subject card: Jev's rename pick already chooses the
     pairing, and the card shows the subject of the ID Jev picked.
   - **The Wikidata hint.** When the eulogy has exactly one commemorated person and that person's item is
     decided, the card shows the item's English and Italian labels (and the QID, linked) as a reference
     for the wording. It is a hint, not a candidate: the subject keeps the martyrology's own form
     (honorific, name, discriminator).
   - The subject card is built only beside a rename (bare-name IDs). `apply_renames.py` writes an accepted
     or edited `relabel` under the new ID; accepting with no decided rename among the candidates is an
     error, reported before anything is written.
3. **The Wikidata item** (`resolve_person`, one per person): as now, with the place agreement.

Jev's answers are shown on the rename and person cards (`--min-confidence 0`), in February too (curator,
2026-10-25). The evaluation (Task 9) is therefore of agreement with suggestions the curator saw, and is read
as such. Prefilled decisions (`op.prefilled`), as January had them (rule-prefilled renames, Jev persons at
p ≥ 0.9), are written by `suggest_subjects.py prefill` and stay undoable on the card.

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

- The `relabel` card: the current subject and the subject the decided (or proposed) ID implies; follow the ID /
  edit the wording (three fields) / keep current; the Wikidata hint when there is one. It reads its
  eulogy's rename decision on the same grouped card, where it sits between the rename and the persons.

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
- `relabel`: candidates from the renames and the current labels, and the hint for a single decided person;
  `apply_renames.py` writes an accepted one as the decided ID's subject (an error when that ID is not a
  candidate), an edited one as edited, under the new ID; no Jev request and no prefill for it.
- `prefill`: the rule and Jev prefills as January's, marked `op.prefilled`; a decided op is never touched.
- Frontend: chips and their translations; the `place` source badge; the `relabel` card follows the rename
  decision (picking another ID changes its proposal), edit, keep, and the hint.

## Left to the builder

- The exact SPARQL for the place route, and the list of places too large for it.
- How a record place finds its `data/places.json` item when the printed form is not contained in it (an
  adjective printed apart from the place phrase): leave it unlinked, today's behaviour.
- Chip styling.

## Curator's decisions (2026-10-25)

1. Place agreement is shown on the cards and to Jev; it does not count toward auto.
2. January keeps every decision (the 2026-10-19 export is complete); only undecided cards are rebuilt.
3. Jev's suggestions are shown on the rename and person cards, February included, as in the gazetteer review.
4. Genitives from the IDs: certain with two or more agreeing IDs and none disagreeing; one ID, uncertain;
   two genitives for one item, reported and uncertain until the curator picks.
5. A month's `persons-review-MM` bundle leaves `/review` once its `crmedr-subjects-MM` file is uploaded.
6. The ID and the subject go hand in hand: the subject card follows the decided ID (follow, edit the wording,
   or keep the current), with no independent Jev pick; a single decided person's item labels are shown as a hint.
