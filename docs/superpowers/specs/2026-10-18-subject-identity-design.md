# Subject identity: IDs, labels and Wikidata items from one record — design

Issues: [#74](https://github.com/CatholicOS/crmedr/issues/74) (bare-name discriminators) and the person
items review (`data/person_items_review.json`, `scripts/build_person_items.py`). Date: 2026-10-18.
Builds on the bare-name drafts (review change-sets `crmedr-bare-names-1-flagged.json` and
`-2-routine.json`, realigned 2026-10-13), the persons design
(`2026-10-08-persons-design.md`) and the Jev mention suggestions (`2026-10-15-jev-mention-suggestions-design.md`).

## Why

Two reviews are stuck on the same problem from opposite ends.

- **Person items.** `propose` searches Wikidata by the bare name, so a one-word name returns famous
  namesakes. In January, 227 of 383 cards are one-word names and 121 have no candidate at all. The right
  item is often one hop away but never reaches the card: *Ioannes* of `mr:0101-ioannes-et-renatus-lego` is
  Jean Légo (Q52161488), the sibling (P3373) of René Lego (Q2652595), whose candidate was right, with the
  same death date and the same "blessed" status. `mr:0101-maria-dei-genetrix` is the title Theotokos
  (Q208542), which a search for humans can never find.
- **Bare-name IDs.** The 3,050 drafted renames were written from the eulogy and the drafter's knowledge;
  230 are low confidence, mostly because a Latin genitive had to be coined for a place the 2004 text
  prints in another form. `mr:0101-eugendus` was drafted `-condatisci` ("genitive uncertain") although the
  2004 Latin calls him *abbátis Condatiscénsis*.

The circle (better labels need Wikidata, better Wikidata matches need labels) is broken by the
**eulogy text itself**: the editio altera 2004 Latin already prints most of what tells a saint apart (a
surname, a role, a see or a monastery, a cognomen, a death place, the relation to the companions). One
**identity record** per subject, read from the text, feeds three things: the ID's discriminator, the
subject labels, and a narrow Wikidata search. Wikidata then confirms the record instead of rescuing a
bare name.

## Goals

- One identity record per subject of a month's eulogies, each field tied to the printed words it comes from.
- From the record: two to four rule-built rename candidates per bare ID, each with its **category**; the
  matching subject labels (la, en, it); and a Wikidata candidate list that contains the right item when
  Wikidata has one.
- Jev, TypeSafe's System One model, checks the record against the text, ranks the rename candidates, and
  picks the Wikidata item (or none). Each card shows the suggestion with its probability; the curator
  decides every card.
- Month by month, January first. January is the evaluation set: Jev's thresholds come from the curator's
  January decisions before any other month gets suggestions.
- The evidence gathered here is also used to test the minting rules: where it shows a rule producing
  uncertain or unconventional IDs, the refinement is proposed to the curator (below), not applied silently.

## Non-goals

- No change to the four-repository rename workflow (texts → crmedr → API → frontend; see AGENTS.md).
  A decided month goes through it like #63 and #118.
- No new rules decided by the pipeline. Code applies the rules as they stand; proposed refinements wait
  for the curator.
- IDs that are not bare are not renamed here. Their subjects get a record and a Wikidata match only.
- No suggestion is applied by itself, and the exported change-sets keep their current shape.

## Anti-goals

- An ID minted from a form the 2004 Latin does not print, when the print offers a usable one (the
  `-condatisci` case).
- Wikidata deciding an ID. Wikidata may supply evidence (a conventional cognomen like *Magnus* for Basil,
  a twin's item), always marked as such, but the 2004 Latin is the prime reference for minting.
- Silent drift between twins: a saint's IDs on several days (`same_eulogy` or the same person item) must
  keep one discriminator (`mr:0101-basilius` → `-magnus` with `mr:0614-basilius-magnus` and
  `mr:0102-basilius-magnus-et-gregorius-nazianzenus`).

## The minting rules as they stand

From `docs/canonicalization-report.md` and the curator's rulings, in the order they apply to a bare slug:

1. **Surname**, where the saint is known by one; a surname makes a place unnecessary unless ambiguity
   remains. One name form per ID; secular name first unless the religious name is the famous one (#63, #116).
2. **Place**, the see (or the abbot's monastery), else the place of death, else the burial or cult place,
   in the Latin genitive (`-bononiae`, `-prusae`); one genitive per place across the corpus; existing
   adjective forms stay (`-portuensis`).
3. **Epithet**: a cognomen (rule 4: `petrus-chrysologus`), popes without an ordinal `-papa`, biblical
   figures with no place their title in the nominative (`abraham-patriarcha`), prophets `-propheta`,
   apostles `-apostolus`, the two evangelists `-evangelista`.
4. **Twins agree**: the same saint on several days takes one discriminator.
5. Never a number; papal ordinals are roman numerals.

## What the evidence says about the rules

Counted over the 3,050 bare-name drafts (classes and the drafters' "place as printed" notes):

- **The print often gives an adjective, and the drafts turned it into a genitive.** 497 drafts note a place
  printed as an adjective (*Condatiscensis*, *Pictaviensis*, *Corbionensis*, *in monasterio Bodacensi*);
  2,399 note a locative, ablative or genitive (*Ruspis*, *Metis*, *Tréviris*); 154 note none. Of the
  adjective cases, 71 are low confidence because of the coined genitive (`-pictavorum`, `-corbionis`,
  `-bodaci`), and only 8 drafts kept an adjective.
- **Role is what the drafters reached for when no place is printed**, and the result is often weak: 29
  drafts are flagged `weak-epithet` (`-martyr` 15, `-episcopus` 3, `-confessor` 2, `-virgo` 2, `-abbas` 1…).
  A class word like *martyr* tells little apart; most of the saints of the Martyrology are martyrs.
- **Roles in the drafts' reasoning**: bishop 802, martyr 313, abbot 133, abbess 40, virgin 31, hermit 29,
  priest 28. A role is a strong discriminator only where it is rare for the name.

### Refinements (decided by the curator, 2026-10-18)

- **R1. The printed adjective first.** When the 2004 Latin prints the place as an adjective of the
  subject or of the subject's role (*abbátis Condatiscénsis*, *epíscopi Pictaviénsis*), the slug takes that
  adjective in the nominative, agreeing with the subject (`-condatiscensis`, `-pictaviensis`; with R2 a
  cleric also takes the role: `mr:0101-eugendus-abbas-condatiscensis`). This is the print's own form and the conventional Latin name (*Hilarius
  Pictaviensis*, *Gregorius Turonensis*); nothing is coined. The genitive stays the rule when the print
  gives a locative or genitive (*Tréviris* → `-trevirorum`). Consistency becomes "one form per place and
  per kind": all *Pictaviensis* subjects take `-pictaviensis`, so `mr:0113-hilarius` and
  `mr:0114-hilarius` still agree.
  An adjective of a place noun, not of the person (*in monasterio Bodacensi*, *in pago Dumbensi*), is
  turned into the subject's adjective the same way (`mr:0127-marius-bodacensis`): decided.
- **R2. Role and place for clerics.** A cleric's slug carries the role, in the nominative, before the
  place: `mr:0101-eugendus-abbas-condatiscensis`, `mr:0114-hilarius-episcopus-pictaviensis`,
  `mr:0113-agricius-episcopus-trevirorum` (decided). *Clerics* here (the builder's reading, to be confirmed
  on the January cards): the ordained (*episcopus*, *archiepiscopus*, *presbyter*, *diaconus*,
  *subdiaconus*) and the superiors of a monastery (*abbas*, *abbatissa*, *prior*), whose place is their see
  or monastery. Others (*monachus*, *eremita*, *virgo*, lay people) take the place alone. The higher tiers
  still win: a surname (rule 1), a cognomen or a twin's discriminator (`mr:0101-basilius-magnus`), and
  `-papa` for popes, which already is a role. A cleric with no printed place takes the role alone
  (`-episcopus`), flagged weak like a class word (*martyr*, *virgo*, *confessor*), which is used only when
  nothing else is printed.
- **R3. Labels follow the ID.** The Latin subject takes the discriminator the slug takes ("Sanctus
  Eugendus abbas Condatiscensis"); the English and Italian
  subjects take the same discriminator in their language, read from their 2004 text where it prints one
  ("Saint Eugendus, abbot of Condat"; "Sant'Eugendo, abate di Condat"), as #61 did for 415 labels.

The rename candidates follow these rules; the current draft stays among them so its decision is not
lost, and the January decisions show where the rules need a further exception.

## The pipeline (per month)

### 1. Identity records (research)

For each subject of the month's eulogies (every bare ID, and every subject with a person card), a record:

| Field | Source |
|---|---|
| `name` (nominative, one name form), `surname` | the 2004 Latin, `data/persons.json` |
| `n` (only for a name repeated in the eulogy, as in `data/persons.json`) | `data/persons.json` |
| `roles` (as printed, with the printed words' offsets) | the 2004 Latin |
| `places` (each with its role: see, monastery, death, burial; its printed form and grammar: adjective of the person, adjective of a noun, locative, genitive) | the 2004 Latin, `data/places.json`, the gazetteer |
| `cognomen` / epithet | the 2004 Latin; else a twin's ID; else Wikidata (marked) |
| `companions` and their relation (brother, mother, disciple…) | the 2004 Latin, the person cards |
| `twins` (other days, by `same_eulogy` or by a shared person item) | the registry, `data/person_items.json` |
| `death` (year if printed; the day is the eulogy's) | the 2004 Latin |
| `kind`: person, celebration or title, anonymous group | typology, the text |

Research is done by Claude agents reading the private martyrology-texts locally, as the bare-name drafts
were (one agent per batch of days, structured JSON out, `consolidate.py`-style validation). Code checks that
every printed form a record quotes is found in the eulogy at the given offsets, so a record can only cite
words that exist. The English and Italian 2004 texts are second witnesses for roles and places.

### 2. Candidates (code)

- **Renames.** Code builds every candidate the rules allow from the record (surname; place in the
  genitive; printed adjective; role; role and place; cognomen; `-papa`; biblical title; twin alignment),
  drops those that break a hard rule (numbers, mixed name forms, a slug already taken that day, a twin
  disagreement), and keeps two to four. Each carries its **category**, one of: `surname`, `place-genitive`,
  `place-adjective`, `role`, `role-place`, `epithet`, `twin`, `papa`, `biblical-title`. The current draft
  is always among them, so its decision is not lost.
- **Labels.** For each rename candidate, the la, en and it subjects it implies (R3).
- **Wikidata candidates.** Besides the name search `propose` already does, three expansions:
  - *through companions*: the items a decided or passing companion links to (sibling P3373, relative
    P1038, spouse P26, child P40, mother P25, father P22), and the members of a group item it belongs to
    (P361);
  - *by the record*: a SPARQL query for humans with a saint or blessed status (`SAINT_STATUSES`), a death
    date on the eulogy's day (or year when printed), and a given name equivalent to the Latin
    (`NAME_EQUIVALENTS`), narrowed by the record's place or role when there are many;
  - *celebrations and titles*: for `kind` celebration or title, a search among non-human items (feasts,
    Marian titles); with four January cards, a curated map is the fallback.
  Each candidate records where it came from (`search`, `companion:P3373`, `sparql`, `curated`), so a card
  can say "found through the sibling".

### 3. Jev judgments

One request per card, the questions asked together (they cannot see one another's answers). State: the
eulogy's clause about the subject (see "Data sent"), the record, the day and typology, the companions with
their decided items, and the candidates. Model pinned to a versioned ID, as in the mention suggestions.

- **Record check** (Noul per cited field): "Does the clause say that `record.places[i].name` is the
  subject's see / monastery / place of death?", "…that the subject was `record.roles[j]`?" A field below
  threshold sends the card to the curator flagged, before its renames are trusted (TypeSafe's citation
  check pattern).
- **Place grammar** (Choice): is the printed place an attribute of the person (*abbátis Condatiscénsis*),
  of another noun (*in monasterio Bodacensi*), or a locative of the death or burial? Needed for R1.
- **Rename ranking** (one Score per candidate, plus a Choice among them): how clearly and conventionally
  the candidate names *this* saint, from "a reader could not tell which saint" to "the name a reader would
  recognise, and no other saint of the corpus could be meant". Code owns the rules; Jev judges only
  recognisability and clarity among candidates that already follow them.
- **Wikidata item** (Choice among the candidates plus "none of these"): the expanded list from step 2.
- **Kind** (Choice: person, celebration or title, anonymous group, not identifiable): routes the card.

### 4. Cards and decisions

Per eulogy, the change-set keeps today's operation types: one `rename` (now with `candidates`, each with
its category, labels and Jev score, and `suggested`) and one `resolve_person` per name (with the expanded
candidates and `suggested`). The frontend groups a eulogy's operations on one card and shows "Jev
suggests" with "Take the suggestion", as on the mention cards. The curator can also type an ID or a QID.

How each person card maps to an outcome:

| Jev | Card |
|---|---|
| agrees with the preselected candidate, above threshold | accept suggested |
| picks another existing candidate | edit suggested |
| picks a candidate from the expansions | edit suggested, badged with its source |
| "none" above threshold, or kind "not identifiable" | unresolved suggested |
| below threshold | no suggestion |

The person-card decisions the curator has already made for January are inputs (their items are evidence
for the companions) and are kept.

### 5. Evaluation (January)

The curator decides January in full (renames and person cards). Then:

- per question, agreement with the curator against Jev's probability, and a threshold per question chosen
  from it (as `suggest_mentions.py evaluate` does);
- for Wikidata, the **coverage** of the expansions: how many of the items the curator typed by hand are
  now among the candidates;
- for renames, which category the curator chose, per situation: this is the evidence for R1 and R2.

Other months get suggestions only after the curator has seen the January figures.

## Data sent to TypeSafe

The mention suggestions send only a card's own sentence or two of the CEI text (the curator's ruling,
2026-10-15). Here the state needs the clause of the 2004 Latin (and, as a second witness, the English or
Italian clause) about one subject: a sentence, never a whole eulogy or day. The curator extended the
earlier ruling to the Latin and English 2004 texts on these terms (2026-10-18).

## Components

- `scripts/subject_records.py`: briefs for the research agents per batch of days, validation of their
  output (offsets, grammar labels, categories), merge per month. The records and the change-sets built
  from them quote printed words, so neither is committed to any repository: they are kept in the private
  local work directory (`~/private-changesets/`) and the change-sets are uploaded by hand to the server's
  `CHANGESETS_DIR`, curator-only, like every change-set that quotes the 2004 texts (decided).
- `scripts/rename_candidates.py`: the rule-built rename and label candidates, with categories; reuses the
  PLACE map and `normalize.py` logic of the bare-name pass.
- `scripts/wikidata.py`: `relatives(qid)`, `group_members(qid)`, `saints_by_death_day(month, day, names)`
  (SPARQL, with the same retry and cache as today).
- `scripts/build_person_items.py propose`: merges the expanded candidates with their source.
- `scripts/subject_jev.py` and `scripts/suggest_subjects.py suggest|evaluate`: the requests, cache under
  `.cache/typesafe/`, `suggested` on the change-set, the evaluation report; patterned on
  `mentions_jev.py` and `suggest_mentions.py`.
- martyrology-frontend: rename candidates with category and score; a eulogy's operations grouped; the
  "Jev suggests" block on rename and person cards.

## Error handling

A failed Wikidata lookup leaves the card with today's candidates and a note; a failed TypeSafe request
leaves the card without a suggestion; neither blocks the change-set. A record whose cited words are not
found at their offsets is rejected and goes back to research.

## Testing

Unit tests on the candidate builder (each rule and category, twin agreement, hard-rule rejections,
the Eugendus, Basilius and Lego cases as fixtures), on the Wikidata expansions (recorded responses), and on
the Jev request builder and suggestion mapping (as in `tests/test_mentions_jev.py`). `check` keeps
validating the change-sets.

## Left to the builder

The exact Score levels, the SPARQL narrowing, the agents' batch size, the order of candidates on a card,
and file layout within the components above.

## Curator's decisions (2026-10-18)

1. R1: yes, the printed adjective first, also for an adjective of a place noun.
2. R2: role and place for clerics.
3. One clause of the 2004 Latin and English per card may be sent to TypeSafe.
4. The records and change-sets stay private: uploaded by hand to the server, never committed.
