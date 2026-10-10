# Persons who share a name in one eulogy — design

Date: 2026-10-10. Amends `docs/superpowers/specs/2026-10-08-persons-design.md` (persons and
their Wikidata items) and martyrology-frontend's
`docs/superpowers/specs/2026-10-09-eulogy-markup-design.md` (mentions and their review).

## Goal

A eulogy's footnote may list two or more martyrs of the same name. The Abitinian martyrs
(`mr:0212-martyres-abitinenses`, footnote 1) count three called Rogatianus and two each called
Felix, Rogatus, Secunda, Matrona and Ianuaria. Some repeats are marked (*alius Felix*, *Iulia
altera*); most are not. Today crmedr keeps one person per name and eulogy:
- `extract_persons.py` drops every repeat;
- `person_items.json` keys a decision by eulogy and name, so a second Felix could have no item
  of his own;
- `extract_mentions.py` marks the first "Felix" and asks, with a `remove_mention`, whether that
  first match is right. The other Felix stays unmarked, and accepting the op removes the one
  correct mark.

After this change, each martyr of a repeated name is a person of their own, with their own
Wikidata decision, their own mark in the text, and their own place in the index of names.
Nothing changes for a person whose name doesn't repeat in their eulogy.

Seven eulogies repeat a name in their footnote lists today (about 25 repeats):
`mr:0212-martyres-abitinenses`, `mr:0602-pothinus-et-socii`,
`mr:0908-antonius-a-sancto-bonaventura-et-socii`, `mr:0910-sebastianus-kimura-et-socii`,
`mr:0920-andreas-kim-tae-gon-et-socii`, `mr:1124-andreas-dung-lac-et-socii`,
`mr:1217-quinquaginta-milites-eleutheropolis`.

## Scope

In scope:
- crmedr: `extract_persons.py`, `extract_mentions.py`, `build_person_items.py`, their tests, and
  the regenerated `persons.json`, `mentions.json` and `person_items.json`.
- martyrology-frontend (a separate PR): the persons snapshot (`scripts/snapshot-registry.mjs`),
  the index of names (`lib/names-index.ts`), the `resolve_person` review card, and the
  `ResolvePersonOp` and mention-op types.

Out of scope:
- Names printed in the ablative after a preposition ("Felice", "Hilarione"), and the missing
  Saturninus iunior: CatholicOS/crmedr#81.
- martyrology-api: its `MentionBase` ignores unknown fields, and the popups find a person by
  QID, so the new field is dropped on load. It needs only its usual vendor refresh.

## Identity: the ordinal `n`

A person is still known by eulogy and name. When a name repeats in one eulogy, the persons of
that name are numbered in printed order: `n` is 1 for the first, 2 for the next, and so on.
`n` is written only when it is 2 or more; a person without `n` has `n = 1`.

The printed name stays the plain name ("Felix") everywhere it is shown. The ordinal tells
persons apart; it is never part of the name.

Across eulogies, identity is unchanged: the Wikidata QID when a person is identified (Basil the
Great is one person in every eulogy that names him), and otherwise the name.

### The person key

Where a person is a key, the key is `<name>` when `n = 1` and `<name>#<n>` otherwise:
- in `person_items.json`, within a eulogy: `"Felix"`, `"Felix#2"`;
- in a `resolve_person` op's id: `mr:0212-martyres-abitinenses|Felix#2`.

Every existing key, decision and pending review op keeps its id. `#` never occurs in a Latin
name, and `extract_persons.py` checks that it doesn't.

## Extraction: `scripts/extract_persons.py`

- **Within one footnote's list, every occurrence of a name is a person.** A repeat gets the
  next `n` for that name in the eulogy, whether or not it is marked *alius*, *alia*, *alter* or
  *altera*.
- **Across the text and the footnotes, a repeat is the same person, as now.** A name already
  found among the subjects, the companions in the text, or an earlier footnote is not listed
  again the first time a footnote list names it (the subject named once more in a footnote).
  A further occurrence in that same list (*Felix, Victor, alius Felix*) is another person.
- **A name printed twice in a row in a footnote list, with no *alius*, counts once.** It is
  probably a misprint ("Emmanuel Lê Văn Phụng, Emmanuel Lê Văn Phụng" in
  `mr:1124-andreas-dung-lac-et-socii`, which the book's index lists once). `docs/persons-report.md`
  lists each such name, "noted" when the eulogy has a 2004 Latin note in `EDITION_NOTES`
  (`scripts/extract_registry.py`), else "needs a curator note".
- **In the text, a repeat marked as another person is another person:** *alter, altera, alius* or
  the genitive *alterius* after a name ("Theodóri, Theodóri alteríus" in
  `mr:1106-callinicus-et-socii`) ends that name and numbers the next `n`. Unmarked, a repeat in the
  text is still the same person.
- When a corrected list drops a person, `build_person_items.py propose` drops that person's queued
  (undecided) review op.
- As now, names are compared by `name_key`, and `_same_person` folds a fuller or shorter form of
  a subject into the subject.
- `persons_curated.json` entries may carry `n`, to merge two entries into one person or to split
  one into two by hand.
- **Check (the script fails on it):** within a eulogy, each name's persons are numbered 1, 2, 3…
  with no gap and no duplicate, `n` is absent or an integer of 2 or more, and no name contains
  `#`.
- While implementing, find why the third Rogatianus (*adhuc Rogatianus alius*) isn't read today,
  and read it as Rogatianus 3.

```json
"mr:0212-martyres-abitinenses": [
  { "name": "Felix", "where": { "footnote": 1 } },
  { "name": "Felix", "n": 2, "where": { "footnote": 1 } }
]
```

## Marks: `scripts/extract_mentions.py`

- **Placing persons.** Persons of one name and place are placed in `n` order, each on the first
  span not already taken: Felix 1 on the first "Felix", Felix 2 on the next. The sort key becomes
  (longer names first, a decided item first, then `n`).
- **No more "matched more than once" `remove_mention`.** When the last person of a name and place
  has been placed and further matches are still free, each of them becomes an `add_mention`
  proposing that span as that last person (its `name` and `n`). The reasoning says the name
  matched again. The curator accepts it when the same person is named twice, and rejects it when
  the match is a stem match on another word.
- **A mention carries `n`** when it is 2 or more, beside `name`. Its `qid` comes from
  `person_items.json` under the person key.
- **Change-set ops:** an `add_mention` for a person carries `n` when it is 2 or more, and `apply`
  copies it onto the mention it writes into `mentions_curated.json`. A `set_span` moves a mark
  and keeps its `name` and `n`. `curated_mention` looks the QID up by the person key.
- The `remove_mention` a place phrase gets when a person is named inside it is unchanged.

## Identification: `scripts/build_person_items.py`

- The person index, the decisions in `person_items.json`, `_decided` and `apply_decisions` use
  the person key (`name` or `name#n`).
- The Wikidata search uses the printed name. Each person of a repeated name gets their own
  candidates and their own decision.
- **Two persons of one eulogy never share an item.**
  - In `propose`, an automatic match whose item is already decided, or automatically matched,
    for another person of the same eulogy is not automatic. It goes to review, with the reasoning
    "the same item ({qid}) is matched for another person of this eulogy". This sits beside the
    one-word-namesake rule (`_shared_items`).
  - In `apply`, a decision giving a person an item that another person of the same eulogy
    holds, or is given in the same change-set, is an error, and no decision is applied.
  - `check` reports the same conflict in `person_items.json`.
- A `resolve_person` op carries `n` when it is 2 or more.

## The frontend (martyrology-frontend, separate PR)

- **Persons snapshot** (`scripts/snapshot-registry.mjs`, `buildPersons`): looks each person's
  decision up under the person key and copies `n` into the snapshot. `PersonMention` gains an
  optional `n`.
- **Index of names** (`lib/names-index.ts`): a heading's key is
  - the QID, for an identified person (as now);
  - `name:<name>`, for an unidentified person with `n = 1`, so unidentified namesakes in
    different eulogies still share a heading (as now);
  - `name:<name>#<n>@<eulogy>`, for an unidentified person with `n ≥ 2`, a heading of their own.

  So two unidentified Felixes of one footnote are two headings, and each gets their line. The
  headings sort by name, then by key; `name:Felix` is a prefix of `name:Felix#2@…`, so the first
  Felix comes first.
- **Review card** (`resolve_person`): `ResolvePersonOp` gains an optional `n`. The card shows the
  ordinal beside the name ("Felix — the 2nd of this name in this eulogy"), in all six locales.
- **Mention ops**: `AddMentionOp` gains an optional `n`. The mention card shows the same ordinal
  beside the name.

## Rollout

1. **crmedr PR:** the three scripts and their tests. Then regenerate `persons.json` and
   `mentions.json`, and run `build_person_items.py propose`, so the new persons are matched
   automatically or added to the persons review.
2. **martyrology-frontend PR:** the snapshot, the index of names, the review cards and their
   tests. Then refresh the persons snapshot from the new crmedr data.
3. **martyrology-api:** the vendor refresh at crmedr's next release. No code change.

The decided `mentions-review-01` and `mentions-review-02` change-sets can be applied before or
after step 1: none of their accepted ops touches a repeated name, and their six Abitinian ops
are all rejected.

## Tests

crmedr:
- `extract_persons`: a repeat in one footnote's list, marked (*alius Felix*) or not (Secunda
  … Secunda), gets `n = 2`, and a third gets `n = 3`; a subject named again in a footnote is still
  one person; a curated `n` is taken as given; the check fails on a gap, a duplicate, `n: 1`, or a
  `#` in a name.
- `extract_mentions`: Felix 1 and Felix 2 land on the first and second "Felix"; a further free
  match gives an `add_mention` for the last person, with no `remove_mention`; a mention carries
  `n` and the QID decided under `Felix#2`; `apply` copies `n` and looks the QID up by key.
- `build_person_items`: decisions and op ids use `Felix#2`; an automatic match already held by
  another person of the eulogy goes to review; `apply` refuses a second person given the same
  item, within the file or within one change-set; `check` reports it; keys without `#` are
  unchanged.

martyrology-frontend:
- `buildPersons` reads `Felix#2`'s decision and copies `n`.
- `namesIndex`: two unidentified Felixes of one footnote make two headings; an unidentified
  Felix with `n = 1` still shares a heading with another eulogy's; identified persons group by
  QID.
- The review cards show the ordinal for `n ≥ 2`, and nothing for `n = 1`.
