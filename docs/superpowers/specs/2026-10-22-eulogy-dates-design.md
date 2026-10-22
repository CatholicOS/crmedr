# Eulogy dates and era-sensitive places: design

Date: 2026-10-22. Issue #12 (places). Builds on the gazetteer design (`2026-10-01-gazetteer-design.md`),
its per-eulogy keys (`data/gazetteer_scoped.json`) and the registry place countries
(`2026-10-14-registry-place-countries-design.md`).

## Why

A printed place name can mean different Wikidata items in different centuries: *Anglia* in a 10th- to
18th-century eulogy is the Kingdom of England (Q179876), in a 20th-century one England (Q21). The
gazetteer has so far chosen by global rules (prefer the ancient place, or the modern one). The curator's
rule (2026-10-22) is instead: **a place links to the entity the eulogy itself refers to, in its
historical context.** That needs to know when a eulogy is set, and the 2004 texts print no year at all.
Dates come from the subject (who died when), which depends on person links, which in turn use places:
a circle of dependencies.

A measurement on 2026-10-22 (scratch scripts, not committed) showed the circle is narrow:

- Only **514 of 4,640** current eulogies link a region or polity (533 links, 237 items). The other links
  are cities, monasteries, churches, islands and mountains, which mean the same place in every century.
- Era evidence for all current eulogies: a subject's death year (Wikidata, through `person_items.json`
  and `person_details.json`) for **904**; presence in the 1630 or 1749 edition (an upper bound) for
  **1,530** more; only a dating cue in the Latin (an emperor, a persecution, a modern religious order)
  for **563**; nothing for **1,643**.
- "Not in an earlier edition" says nothing: of 492 eulogies first printed in 2004 that have a death
  year, 156 died before 1500 (the 2001 revision added many old local saints). Presence in 1630 is a
  strong bound: 7 of 306 dated eulogies already in 1630 died after 1500, and those may be wrong person
  links.
- Real anachronisms exist: Ireland Q27 (the state, 1937) on 31 eulogies, at least 10 ancient or early
  medieval; Egypt Q79 (1922) on 17, 14 of them in 1630; Italy Q38 (the Republic, 1946) on 14; Spain,
  Germany, Syria, Armenia, Greece, Ethiopia, Cyprus, India, Bavaria (the Free State, 1919); *In Anglia*
  as England Q21 on 2 eulogies whose subjects died before 927; and the reverse, *In Pérside* as the
  Achaemenid region Q3746183 (−600 to −330) on 13 eulogies of Sasanian-era martyrs.

## Goals

1. **Every current eulogy may carry a date**: the main year it is associated with, or a range when one
   year is too precise, with what the year is (its basis) and where it comes from. Optional: no
   eulogy needs one, and a date is a further signal, never a requirement of any other field.
2. **Filled mechanically where the data already says it**: death years of the linked subjects, the
   upper bound of the older editions, curated dates for feasts and special cases.
3. **An era estimate for the rest**, from the text, marked as an estimate and calibrated against the
   eulogies whose death year is known.
4. **The era-sensitive places are reviewed with the dates in view**, preferring an item that does not
   depend on the era wherever the eulogy means the land rather than a state.
5. **Dates check person links**: a subject who died after an edition that already prints the eulogy is
   reported.

## Non-goals

- Showing dates in the API or on the public site. The registry carries them; display is a later
  decision. (The API must tolerate the new registry key; see Constraints.)
- Re-deciding settlements. Cities, monasteries and churches keep their items.
- Changing the country rule: a place's `country` stays where it lies today, whatever its QID.
- Dating deprecated entries.

## The date of a eulogy

One optional `date` object per current eulogy, in a new generated file `data/dates.json` keyed by
eulogy ID, copied onto the registry entry by `extract_registry.py` (after `places`, like `typology`):

| Key | Meaning |
|---|---|
| `year` | The year, negative before Christ. Present only when one year is known. |
| `from`, `to` | A range (inclusive), when one year is not known: several subjects who died in different years, a Wikidata precision of a decade or a century, an era estimate. Either may be absent for an open bound (`to` alone: "before"). Never together with `year`. |
| `circa` | `true` when the source says circa. |
| `basis` | What the year is: `death`, `deposition`, `translation`, `dedication`, `event`. Optional: absent when nothing says what the date marks. |
| `source` | Where it comes from: `wikidata` (the subjects' death dates), `edition` (an upper bound from the oldest edition that prints the eulogy), `curated`, `estimate`. |
| `note` | Optional, for a curated date ("Council of Ephesus" for Mary Mother of God, 431). |

**Basis** follows the eulogy's typology (`data/typology.json`, seven values) whatever the source, an
estimate or an edition bound included: `dies_natalis` → `death`, `depositio` → `deposition`,
`translatio` → `translation`, `dedicatio` → `dedication`. `celebratio` (60), `commemoratio` (323) and
`ordinatio` (2) have no default basis: their dates are written without one unless curated. A curated entry may set any basis (a
`dies_natalis` eulogy whose year is really a translation's, say).

**Precedence**, first that applies: `data/dates_curated.json` (hand-made, same shape, keyed by ID);
the subjects' death dates; an accepted estimate; the edition bound. A curated `null` removes a date.

**Ranges by precision.** There is no year 0: a decade is its ten years (the 1930s: 1930–1939), a
century AD n is `100(n−1)+1` to `100n` (the 4th: 301–400), a century BC n is `−100n` to `−100(n−1)−1`
(the 1st BC: −100 to −1). A circa date keeps its year and sets `circa`.

**From the subjects' death dates.** The persons of the eulogy (`data/persons.json`) with a decided
item in `data/person_items.json` and a death date in `data/person_details.json`. One person, a year
precision: `year`. A decade or century precision: the range it covers. Several persons: `from` the
earliest, `to` the latest. A eulogy with some persons dated and others not takes the dated ones. These
dates refresh on every run, so dates follow the subject identity work as it links more persons.

**From the editions.** The oldest of the 1630 and 1914 editions (martyrology-api's
`data/editions/martyrologium_romanum_{1630,1914_en_unofficial}`) whose keys include the eulogy's ID or
one of its `same_eulogy` IDs gives `to` = that edition's year. The English edition (Baltimore, 1916)
translates the Roman copy of 1914. The folder `martyrologium_romanum_1749` bounds nothing: its copy is
a 1913 Mechelen printing with later additions (John Bosco, canonized 1934), found by the first run of
the checks below. An ID in a `same_eulogy` link counts even when it is
a deprecated cross-day ID (#49): the link says it is the same eulogy. The script that reads those files takes the
martyrology-api path as an argument, as other generators take martyrology-texts.

**Checks** (in the report, not errors): a death-year date later than its edition bound (a likely
wrong person link); a range wider than 300 years from death dates (likely a wrong person among
several). A wide range is still written; a death later than the bound is not (the bound is
written instead), since only a wrong person link produces it.

**Curated dates.** Step 1 ships `data/dates_curated.json` with Mary Mother of God (431, `event`,
"Council of Ephesus") and the report lists the undated `celebratio` and `commemoratio` eulogies as
candidates for the curator; it does not guess their dates.

## The era estimate

For eulogies with no death date, a model reads the eulogy's opening clause and picks the
**century** the eulogy is set in, or "cannot tell". The state sent follows the curator's ruling of
2026-10-18 for every TypeSafe request: one clause of the 2004 Latin and one of the English (the first
sentence, at most 400 characters), never a whole eulogy; with them the typology and the oldest
edition before 2004 that prints the eulogy, if any. My call: Jev, one Choice of 23 options (before
Christ, the 1st to the 21st century, cannot tell; a Score holds at most 10 levels), because the dated
eulogies give a ready calibration set: run Jev on them, report agreement (the right century, and
within one) by probability, and let the curator pick a threshold, as for the gazetteer suggestions.
Jev's answers are stored without text in `data/date_estimates.json`; a pick at or above the
threshold is written as `{from, to, source: "estimate"}` spanning that century (before Christ: `to:
-1` alone), cut at the edition bound when there is one, and dropped when the century begins after
the bound. Below the threshold, or "cannot tell", nothing is written. Precedence: curated, death
dates, estimate, edition bound.

A century is coarse, but the era-sensitive choices this serves
are centuries apart (ancient or medieval Ireland against the state of 1937, Achaemenid against
Sasanian Persia); a place card never takes an estimate alone as decisive. Estimates are not reviewed one by one: they are a signal for the place cards and for the subject
work. The curator can correct any one in `data/dates_curated.json`.

## The era-sensitive places

1. **Which places.** The phrases whose item (in `data/gazetteer.json`, and in the body place
   mentions) is a region or polity: Wikidata P31 reaching a region, country, historical country,
   historical region or Roman province, and not a settlement, municipality or building. The list is
   regenerated from Wikidata, not hand-kept.
2. **Prefer an era-free item.** Where a geographic item exists that covers the land in every century
   (the island of Ireland, Egypt as a region, the Italian peninsula, the Persia region), it is the
   default for a phrase that names the land. A polity of an era (the Kingdom of England, the Sasanian
   Empire, the Republic of Ireland) is linked only where the eulogy means the state itself, or where
   no era-free item exists.
3. **Scope by eulogy where the meaning really changes.** A phrase whose right item differs between
   its eulogies goes into `data/gazetteer_scoped.json` with a reason, and each eulogy's key is
   resolved on its own card.
4. **Cards.** One `resolve_place` card per phrase (or per eulogy, once scoped), in the existing
   gazetteer change-set, for the phrases where the date can matter: the item fails the check below
   for some eulogy, or an era-free item exists beside the linked polity. A phrase already decided is
   re-queued then; its live decision stays until the curator decides the new card. Era-free
   candidates come from a Wikidata search on the phrase's name (geographic region, island,
   peninsula) and, where that finds none, from Claude research agents as in the gazetteer Jev design. Each card shows its eulogies' dates
   (year or range, basis, source) next to the occurrences, and the candidates' inception and
   dissolution years. Suggestions (Jev or research agents, as in the gazetteer Jev design) may
   propose the era-free item or the polity that existed at the eulogy's date.
5. **Check.** `build_gazetteer.py` reports, for every decided place, the eulogies whose date falls
   outside the item's existence (inception P571 to dissolution P576, with 25 years' grace), so a later
   change of date or item surfaces again. A date counts by its bounds: a `to` alone (an edition bound)
   fails only an item founded more than 25 years after it; a `from` alone only an item dissolved more
   than 25 years before it. Settlements are not checked: their inception is often a modern municipal
   date (Nagasaki 1889), which would flood the report.

## Order of work

1. `data/dates.json` from death dates, editions and `data/dates_curated.json` (with Mary Mother of God
   and the other feasts the curator dates); registry key; report and checks.
2. The era estimate, calibration report, threshold, estimates written.
3. The era-sensitive place list, the cards with dates, and the gazetteer check.

Each step is its own pull request in crmedr; the card changes are a martyrology-frontend pull request
with step 3.

## Constraints

- Standard library only, offline except the Wikidata and Jev calls, as the other generators.
- `extract_registry.py --check` and `registry_places.py --check` stay the guard of the committed
  registry; `data/dates.json` gets the same `--check`.
- The API reads `data/martyrology_ids.json` key by key (`registry.py` `Registry.load` picks the keys
  it uses), so a new `date` key does not break a pin release; exposing it is a later decision.
- Years are integers, negative before Christ, matching `person_details.json`.

## Left to the builder

File and function names beyond those above; the report's layout; the exact Jev wording and how the
calibration report is tabulated; how the card lays out the dates.
