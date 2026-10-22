# Gazetteer review, round 2: page-1 conventions, peoples, Jev decisions: design

Date: 2026-10-22. Issue #12 (places). Builds on the gazetteer Jev design
(`2026-10-21-gazetteer-jev-design.md`) and comes before step 3 of the eulogy-dates design
(`2026-10-22-eulogy-dates-design.md`), the era pass, which the curator wants run after the review.

## Why

The curator decided page 1 of the queue (50 cards) on 2026-10-22, exported to
`martyrology-frontend/changesets/gazetteer-review.decided.json`. 1,359 cards remain: 960 undecided and
399 Jev pre-fills not yet confirmed. On page 1, Jev's item pick matched the curator's item 30 of
32 times at probability ≥ 0.90 and 26 of 27 at ≥ 0.95. The curator chose (2026-10-22) to let Jev
decide every pick at ≥ 0.95 outright, and to pre-fill the rest for review.

Page 1 also set conventions Jev did not follow:

| Phrase | Jev | Curator | Convention |
|---|---|---|---|
| *polónus*, *anglus*, *hibérnus* | "a people, no item" | Polans, Angles, Irish people | a nationality or people takes the people's item |
| *Merciórum* | a people, no item | Kingdom of Mercia | the same |
| *Cluniacénsis* | Cluny (town) | Cluny Abbey | an adjective of a monastery names the monastery |
| *ínsula Lirinénsi* | Lérins Islands | Abbaye Saint-Honorat de Lérins | the island's monastery, when the eulogy is monastic |
| *Gálliæ*, *Itáliam* | Gaul, Roman Italy | France, Italy | regions: left to the era pass |

A people's country is its homeland today, one country or several (*anglus* GB, *hibérnus* IE,
*polónus* PL, DE, CZ, SK, LT; the curator's ruling, 2026-10-22).

## Goals

1. **The curator's page-1 decisions are applied** to `data/gazetteer.json` (status `reviewed`), so
   those cards leave the queue.
2. **Peoples get items.** The 89 undecided cards Jev read as a people go to Claude research agents,
   which propose the people's (or kingdom's) Wikidata item and its homeland countries today, as the 236
   research suggestions of 2026-10-21 were made; `verify-suggestions` adds each item to its card's
   candidates.
3. **Jev is asked again** on every remaining card (undecided or pre-filled, not decided by the
   curator) with the page-1 conventions in its instructions: the people convention replaces "a people,
   not a place"; the monastery convention is added. Regions keep today's instructions.
4. **Calibration before deciding.** The re-asked Jev is evaluated on the round-1 decisions and the
   page-1 decisions together (`suggest_places.py evaluate`). If agreement on positives at 0.95 is below
   97%, nothing is decided and the report goes to the curator.
5. **Jev decides at ≥ 0.95.** A pick at or above 0.95 that is one of the card's candidates, with a
   country (or countries), is written to `data/gazetteer.json` with a new status **`jev`**, and its
   card leaves the queue. Picks from 0.90 to 0.95 are pre-filled (`"prefilled": "jev"`), as before.
   Everything else waits for the curator.
6. **Status `jev` is distinct**: not `reviewed` (a person decided it) and not `auto` (the evidence
   bar). It counts as identified wherever `auto` and `reviewed` do (the registry, the frontend's
   snapshot), and is never used as calibration truth.

## Non-goals

- Era-specific items (the era pass, after the review).
- Deciding regions differently from today: a region pick at ≥ 0.95 is decided like any other; the era
  pass re-queues regions and polities whatever their status.
- Showing the status on the public site.

## Reversibility

A `jev` entry is changed as any entry is: edited in `data/gazetteer.json`, or re-queued. The era pass
re-queues region and polity entries of every status; a `requeue` of all `jev` entries is a one-line
filter if the curator wants a full second look.

## Constraints

- What is sent to TypeSafe stays as in the gazetteer Jev design (one Latin and one English clause per
  card); a one-sentence eulogy is sent without its opening place, as `dates_jev` does (CodeRabbit on
  #159).
- The frontend's copy of the queue (`changesets/gazetteer-review.json`, indent 1) is replaced in the
  same round, and the curator's saved decisions carry over by op id.
- The snapshot (`scripts/snapshot-registry.mjs`) counts `jev` as identified.

## Order of work

1. crmedr: status `jev` (validation, report, calibration exclusion); apply the page-1 decisions.
2. Research the people cards; `verify-suggestions`.
3. Jev instructions; re-ask; evaluate; the curator's go/no-go if agreement is short of 97%.
4. Decide at ≥ 0.95, pre-fill 0.90–0.95; `registry_places.py`, `extract_mentions.py`.
5. Frontend: `jev` in the snapshot's identified statuses; the new queue; deploy after the curator's
   go-ahead.

## Left to the builder

The exact instruction wording; how the research brief is batched; report layout.
