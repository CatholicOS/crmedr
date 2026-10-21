# Jev on the gazetteer review: design

Date: 2026-10-21. Issue #12 (places). Builds on the gazetteer design
(`2026-10-01-gazetteer-design.md`) and on the Jev suggestions already used on mention
cards (`suggest_mentions.py`) and subject cards (`suggest_subjects.py`).

## Why

The subject review (crmedr #74) mints place discriminators such as `-tuderti` and `-cenomani`. The
curator found the same place minted in different forms on different IDs (Todi: `mr:0813-cassianus-tuderti`
and a January pre-fill `-tudertis`; Le Mans: `mr:0127-iulianus-cenomanum` and `-cenomani`). The cure is one
decided form per place, keyed by the place's Wikidata item: that needs every place resolved first. The
curator decided (2026-10-21) to finish the gazetteer review before going on with the subjects.

The queue is large: `data/gazetteer_review.json` holds **1,406** `resolve_place` cards, none decided and
none with a suggestion (the round-1 suggestions covered only the earlier queue).

| Cards | State | Why queued (the evidence bar's `failed` reasons) |
|---|---|---|
| 1,003 | Wikidata candidates (510 have five or more) | mostly no Latin label matching the print (824), or a country the Italian does not confirm (680) |
| 403 | no candidate | nationalities (*polónus*, *anglus*), phrases (*límina Apostolórum*), places the search missed (*castra detentiónis Dacháni*, *Béthlehem Iudæ*), places that depend on their eulogy (*Cartúsia huius civitátis*) |

## Goals

1. **Jev picks among the candidates.** On every card with candidates, Jev chooses one candidate or "none
   of these". The pick, its probability and Jev's reading of the place's kind go on the card; a "Take the
   suggestion" button records it, as on person cards.
2. **Calibrated before it is shown.** Jev is first run on places the curator has already decided, and
   agreement is reported at each threshold. The curator picks the threshold from that report.
3. **Pre-filled at the threshold.** Picks at or above the chosen threshold are written into the
   change-set as decisions marked `"prefilled": "jev"`, as the January subject file was (the review page
   loads decisions carried in the file, under the curator's own saved ones). The curator reviews them
   and changes any.
4. **The cards with no candidate are sorted.** Jev reads each one's kind: a place to identify, a
   nationality or people, a reference that depends on the eulogy, or not a place. The places get a second
   Wikidata search; what that still misses goes to Claude research agents, as the 37 cards of
   2026-10-14 did. The others get a Jev suggestion of "no item" with the kind as the reason.

## Non-goals

- The automatic evidence bar does not change. Jev never makes a place `auto`; every place goes through a
  curator decision and `build_gazetteer.py apply`, and lands as `reviewed` or `unresolved`.
- No change to `propose`'s rules, to body places (`add_place`, sub-project 4), or to the registry's
  `places[]` (sub-project 3). Those consume the gazetteer as they do now.
- The place-form record for slugs (one ID form per place) is the next design, not this one.

## Anti-goals

- A Jev pick in `data/gazetteer.json` that the curator did not see. Pre-fills are decisions in the
  review file, never entries in the gazetteer.
- 2004 text in a public file. The gazetteer queue is bundled in martyrology-frontend's public
  `changesets/`; `jev` carries no quoted text, and research reasoning keeps the existing rule (at most
  300 characters, no quotation of four or more words of the 2004 text).
- Guessing. "An unresolved place is better than a guessed one" (curator, 2026-10-01) still holds: a
  "none of these" from Jev, and a "no item" decision, are good outcomes.

## Decided by the curator (2026-10-21)

- Jev assists with the gazetteer review, and the review is finished before the subject review goes on.
- **Sent to TypeSafe** per card: the printed Latin phrase, its Italian forms, and one Latin and one English
  clause of one eulogy that names the place, with the candidates' public Wikidata fields. (The same
  allowance as on subject cards.)
- **The cards with no candidate** that Jev reads as places get the extra search and, when that fails,
  Claude research.
- **Calibration on round 1 is enough**: the threshold is picked from the round-1 report and pre-fills
  follow at once, with no labelled sample of the current queue first. (Round 1 was easier: every card had a
  researched suggestion, and its "none" cases are synthetic. The curator accepted that.)
- **New Wikidata items** are created only after the curator approves each batch: research lists the
  proposed items (name, place, sources), and nothing is written to Wikidata before a yes.

## How it works

### 1. The Jev request (one card)

State: the place phrase (`la`), its Italian forms (`it`), the clause pair, and the candidates, each with
`label`, `description`, `country`, a readable form of `types`, and whether a Latin label matched (`la`,
`p9314`). Coordinates are not sent: the country and description carry the same meaning in words. (My call.)

Questions, asked together:
- **pick** (Choice): which candidate is the place the phrase names in this eulogy, or none of them. The
  options are the candidates plus `none`.
- **kind** (Choice): what the phrase names: `place` (a settlement, site, building, region or country),
  `people` (a nationality, a people, a tribe used as such: *anglus*, *Sáxonum orientálium* is a region
  and so a `place`), `relative` (a reference resolved only by the eulogy: *huius civitátis*), `not_place`.

The texts come from the martyrology-texts repository, loaded as `suggest_subjects.py` does (2004 Latin and
English editions). Requests and answers are cached in `.cache/typesafe/`, which is git-ignored; nothing
from the cache reaches the public `changesets/` bundle.

The clause: from the card's first occurrence whose 2004 Latin prints the phrase, the Latin sentence
holding it (at most 400 characters, as `subject_jev.MAX_CLAUSE`) and the English sentence of the same
eulogy that names the place (by a candidate's label or an Italian form), else the English text's first
sentence. (Selection details are the builder's.)

A card with many occurrences (Tyburn: 46) is asked once, from its first occurrence: the place is one
place in all of them (that is how the queue groups them).

### 2. What goes on the card (`op["jev"]`)

As on person cards, never over `suggested` (which stays the research agents' field):

```
{"decision": "accept" | "edit" | "reject", "wikidata": "Q…" (accept, edit),
 "reason": "…" (reject), "kind": "place" | "people" | "relative" | "not_place",
 "probability": 0.0–1.0, "confidence": 0.0–1.0, "model": "jev-…"}
```

`accept` means Jev picked the card's default (`suggested`, else the first candidate, as `apply` reads an
accept); `edit` another candidate; `reject` none, with the reason "Jev: none of the candidates is this
place" or, for a non-place kind, a reason naming the kind ("a nationality, not a place"). Every answer is
written, whatever its probability (the curator sees the percentage; the threshold governs pre-fills only).

### 3. Calibration

Ground truth: the places already decided. The round-1 queue (`data/gazetteer-review.decided.json`, local
and untracked: 1,901 cards with their candidate lists) gives each card's candidates; `data/gazetteer.json`
gives the item the curator settled on (1,898 `reviewed`).

- **Positives:** the round-1 cards whose settled item is among their candidates. Jev should pick it.
- **Negatives:** the same cards with the settled item removed from the candidates. Jev should say none.
  Without these, the evaluation could not see Jev choosing a wrong namesake.
- The report gives, at each threshold (0.5 to 0.99), how many picks Jev makes and how many agree, for
  positives and negatives separately, with the disagreements listed. Answers are cached in
  `.cache/typesafe/`, so the evaluation and the live run share them where requests are identical.

The curator picks the pre-fill threshold from the report. My suggestion to bring along: the lowest
threshold at which agreement on the negatives is at least 99% and on the positives at least 98%.

Round-1 suggestions were researched and then accepted by the curator, so agreement measures Jev against
reviewed answers, not against Jev's own earlier output.

### 4. The cards with no candidate

1. Jev answers `kind` only (there is nothing to pick).
2. `place`, and also a candidate card where Jev picks none but reads the kind as `place` (the right item
   may be missing from the candidates; my call): a second search, on the Italian forms with qualifiers stripped ("di Giuda", "in Francia"),
   then on the Latin nominatives without qualifiers, through the same candidate gathering and evidence
   checks as `propose`. Cards that gain candidates get the full Jev request (section 1).
3. Still no candidate: Claude research agents, in batches, write `suggested` + `reasoning` +
   `confidence` as in round 1, then `build_gazetteer.py verify-suggestions` checks them. Wikidata items
   may be created when a place has none and the evidence is solid, but only after the curator approves
   the batch's list of proposed items (name, place, sources).
4. `people`, `relative`, `not_place`: a Jev `reject` suggestion with the kind as the reason. The curator
   decides; an accepted reject lands as `unresolved` with that note, as `apply` already does.

Whether a nationality (*polónus*) should instead resolve to its country is the curator's call on the
cards; this design only labels them.

### 5. Pre-fill

After the curator picks the threshold: every card whose **pick** probability reaches it and whose pick is
an item `apply` would accept (a candidate with a country) gets `decision`/`edited` and
`"prefilled": "jev"`. Calibration measures the pick only, so (my calls):
- a `none` pick is never pre-filled: it goes to the second search (section 4), and stays open for the
  curator;
- a `kind` answer is never pre-filled: `people`, `relative` and `not_place` are shown as suggestions with
  their reason, for the curator to take;
- research suggestions are not pre-filled.

`prefilled` is a new optional field on an op. `apply` reads only the keys it knows and ignores it; the
frontend's change-set types gain it as optional. (My call.)

### 6. Frontend (martyrology-frontend)

- `PlaceCard` shows Jev as `PersonCard` does: the hint and kind under the candidates, "Take the
  suggestion" first in the button row; a "prefilled by Jev" chip on pre-filled cards.
- The review page's existing filters already page through the queue; a filter on pre-filled cards helps
  the curator check them. (My call; small.)
- The queue in `changesets/gazetteer-review.json` is refreshed from crmedr as now.

## Pieces (for the plan)

- `scripts/gazetteer_jev.py`: request and suggestion for a place card (pattern of `subject_jev.py`).
- `scripts/suggest_places.py`: `suggest`, `evaluate` (with negatives), `prefill`, caching and key handling
  as in `suggest_subjects.py`.
- `build_gazetteer.py`: the second search for no-candidate place cards (a subcommand), reusing
  `gather_candidates` and `evaluate`.
- Frontend: the `PlaceCard` changes and types.
- The research batches use the existing `suggested` path and `verify-suggestions`.

## Left to the builder

Question wording and criteria; the exact candidate fields and their order; clause selection details;
the report's format; batch sizes for research; how the second search strips qualifiers.

## Order of work

1. crmedr: `gazetteer_jev.py` + `suggest_places.py evaluate`; run on round 1; report to the curator.
2. Curator picks the threshold.
3. crmedr: `suggest` on the queue, the second search, research on what remains, `prefill`.
4. Frontend: `PlaceCard`; refresh the bundled queue; deploy.
5. Curator reviews; `apply`; the usual regeneration (`extract_places`, `registry_places`,
   `extract_mentions`), API pin and frontend snapshot.
