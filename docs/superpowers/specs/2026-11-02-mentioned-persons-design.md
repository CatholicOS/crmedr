# Mentions beyond the commemorated: persons, movements and heresies, religious congregations

Status: designed with the curator (2026-11-02), awaiting approval. Tracks crmedr #230.

## Why

The persons index and the person marks hold the saints each eulogy **commemorates**: its own subjects and those
who suffered or died with them ([persons pass, 2026-10-28]). The eulogies also **name** other people: the emperor
who persecuted, the saint's parents, a teacher or founder, a Church Father they quote, the pope or bishop who
ordained, the saint who appears in another day's eulogy (Willibrord in the two Ewalds', 3 October; Ambrose of Milan
in Bassianus's, 19 January). Today these are plain text, or worse: in Bassianus's eulogy the reader marks only
*Mediolanénsis* inside "Ambrose of Milan", as a place, so the map puts the eulogy at Milan, where it has nothing to
do. The eulogies also name heretical movements (*Donatístæ*, *Ariáni*) and religious orders and congregations,
which have Wikidata items of their own but no mark.

A reader should see every person, movement and congregation a eulogy names, tell at a glance whether that person is
commemorated in the Martyrology, and reach their own eulogy or their item; and the site should list the persons,
movements and congregations the Martyrology names without commemorating.

## Decisions (curator, 2026-11-02)

### What is marked

1. **Every named human person** a eulogy names, whatever their part: persecutors and emperors, parents and kin,
   teachers and founders, Church Fathers and authors quoted, popes and bishops, other saints.
2. **Not marked as persons:** Christ, the Persons of the Trinity, and the Virgin Mary. They too often stand inside
   another name (a church, a feast, a title, *sanctæ Maríæ* in a dedication), and marking them adds nothing.
   Unnamed persons (*mater eius*, *præses*, *imperátor* with no name) are not marked. A saint inside the name of an
   order, church or monastery is never a person mark (unchanged rule); an order's name is a congregation mark (5).
3. **No place mark inside a mentioned person's name.** The name runs to the end of the epithets **and** the office
   attached to it (curator, 2026-11-02): *Ambrósius Mediolanénsis*, *Ambrósius, epíscopus Mediolanénsis*, *Cyríllus
   Alexandrínus*, *Gregórius papa*, *Iuliánus Apóstata* are each one person mark. A place word inside that span is
   not a place mark, and that place is not one of the eulogy's places. A eulogy that mentions Ambrose has
   nothing to do with Milan. Existing place marks and eulogy places that come only from inside such a name are
   removed (Q490 Milan, role "mention", in `mr:0119-bassianus-laudis-pompeiae`). Inside a **commemorated** person's
   name nothing changes.
4. **Movements and heresies**: heresies, schisms and heretical sects only (*Donatístæ*, *Ariáni*, *Manichǽi*,
   *hǽresis Albigénsis*, *Nestoriáni*, *Novatiáni*, Iconoclasts…). Peoples (*Vándali*, *Gothi*, *Saracéni*) and
   religions (*Iudǽi*, *pagáni*, *Mahometáni*) stay plain text (curator, 2026-11-02); in *Gothi Ariáni* only
   *Ariáni* is marked: a mark kind
   of their own, `movement`, linked to the movement's item (Donatism, Arianism, Manichaeism, Catharism…, not a
   "group of persons" item). A movement mark may sit one level inside a place mark (*regiónibus hǽresi Albigénsi
   perturbátis*, a place, Languedoc), as the reader already allows.
5. **Religious congregations** (orders, congregations, institutes, societies of apostolic life, military orders:
   *Ordo Prædicatórum*, *Societátis Iesu*, *Ordinis de Calatrava*, *Congregatiónis Sorórum…*): a mark kind of their
   own, `congregation`, linked to the institute's item. A saint's or place's name inside it is not marked.
6. Movements and congregations are **kept apart** (two kinds, two tints, two indexes), so that they can be shown
   together later without losing the distinction.

### Three kinds of person mark

The data model stays the curator's ruling of 2026-10-30 (#230): one persons record per eulogy, with a per-eulogy
`role`: commemorated (no key) or `"role": "mentioned"`. Which kind of mentioned person it is comes from the
Wikidata item, never from a second field:

1. **Commemorated here**: as today.
2. **Mentioned here, commemorated elsewhere**: another eulogy commemorates the same item (Willibrord, Q160714 →
   `mr:1107-willibrordus`). Same person tint as today. The popup says "Commemorated on 7 November", linked to that
   eulogy (all of them, if several).
3. **Mentioned here, commemorated nowhere**: no eulogy commemorates the item, or the person has no item. A
   **new highlight accent**, distinct from commemorated persons, places, events, movements and congregations, in
   light and dark. The popup says "Not commemorated in the Martyrology" and, through the shared item, "Also
   mentioned in" every other eulogy that mentions the same item.

**What "commemorated" means** (builder's call): a person is commemorated when a current eulogy of the 2004
Martyrology lists them without `role: "mentioned"`, in any of its editions (Latin, Italian), including a person who is
one of a shared mark's `others`. The 1914, 1749 and 1630 editions do not count. One function in crmedr computes it
and writes the result where the API and the frontend read it (below), so the three never derive it apart.

### Indexes

- **Persons index** (`/read/[edition]/names`): a person commemorated somewhere keeps their entry, which now
  distinguishes the eulogies that **commemorate** them from the eulogies that **mention** them (two groups under
  the name). This revises the 2026-10-30 note that the index stays limited to commemorated persons: it stays
  limited to commemorated **persons**, but lists every eulogy that names them.
- **Persons not commemorated**: a new index of kind-3 persons, with the eulogies that mention each.
- **Movements and heresies mentioned** and **Religious congregations mentioned**: two new indexes, one entry per
  item, with the eulogies that name it.

### Process: automated; the curator sees only what research cannot settle

The established pipeline, run end to end without uploading review cards:

1. **Extraction**: propose, for every eulogy of the Latin and Italian 2004 texts and footnotes, the named persons
   not yet in its persons list, the movements and the congregations, as cards (person: name, n, printed span,
   Latin and Italian; movement/congregation: printed phrase per language).
2. **Candidates**: for each person, Wikidata candidates; first, the item of any eulogy that commemorates the same
   name (the commemorated-elsewhere route), then name search. For movements and congregations, label search.
3. **Jev** scores the candidates (TypeSafe; the threshold used so far, 0.90). A candidate Jev picks with high
   confidence is accepted.
4. **Research** where Jev's confidence is low or it judges no candidate right: the same research done for places,
   from the eulogy, the hagiographical and historical literature and Wikidata.
5. **Wikidata**: when the right item exists but lacks the signals the matching relies on (dates, description,
   P1343 Roman Martyrology 2004 where it names them), add them, sourced. When no item exists, **create** one only
   when the literature gives at least one fact beyond the eulogy (a date, an office, a source that names the
   person); otherwise the person is marked with no item, `unresolved`, and listed by name in the non-commemorated
   index (curator, 2026-11-02). The curator gives leave for these edits and creations in this pass. maxlag 5 with
   retry, as always.
6. **Apply**: `persons_mentioned.json` (`role: "mentioned"`), `mentions_curated.json`, and the new curated files for
   movements and congregations; regenerate; tests.
7. **Human review, only for what research cannot settle** (curator, 2026-11-02): a case still in serious doubt
   after scholarly research (two candidates the literature cannot tell apart, an identity the sources dispute, a
   name that may or may not be a person) becomes a review card, and only those cards are uploaded to the server
   (`CHANGESETS_DIR`) for a final human pass. Until the curator decides, its mark is left out. Everything else is
   applied without review.

The decided cards and every decision (Jev's score, the research note, the item created or edited) are kept as an
audit trail in `~/private-changesets/` (they quote the 2004 texts), not uploaded and never in git. The curator can
spot-check them; the reports in `docs/` count what was decided and how (Jev, research, created, left for review).

## Data (crmedr), outline

- **A new additive file**, `data/persons_mentioned.json` (builder's call): by eulogy, `[{name, n?, where}]` of
  mentioned persons, **added** to the eulogy's persons by `extract_persons.py` with `role: "mentioned"`, validated
  like the rest. `persons_curated.json` replaces a eulogy's extraction, so putting mentioned persons there would
  freeze most of the persons index; the seven mentioned persons already there (Willibrord, Henry, Cunegund, Symeon,
  Eusebius, Nestabius, Zeno) move to the new file where their eulogy's curated list exists only for them. Audit the
  current persons for ones a eulogy only mentions (John I in `mr:0727-ecclesius`).
- `data/person_items.json`: statuses gain how a mentioned person was decided: `jev` (accepted at ≥ 0.90),
  `researched`, `created` (item made in this pass), and `unresolved` as an accepted final state. A person with no
  item keys the indexes by the existing `name:<name>#<n>@<eulogy>` fallback.
- `data/persons_commemorated.json` (generated): the QIDs commemorated somewhere, each with its eulogies, the one
  answer to "commemorated elsewhere" for the API and the frontend.
- `data/person_items.json`: their items; the evidence bar's "died on the eulogy's day" does not apply to a mentioned
  person; the decision comes from steps 2–5.
- `data/mentions.json`: person marks of mentioned persons carry `"role": "mentioned"`, so the reader needs no second
  lookup; whether commemorated elsewhere stays derived (the item against the commemorated persons).
- `data/movements_curated.json`, `data/congregations_curated.json`: by eulogy, the printed phrase per language and
  the QID, as `events_curated.json`. Their items get P1343 Q125252554 only when they lack it and the
  Martyrology names them (builder's call). Their marks carry `kind`, `where`, `start`, `end`, `check`, `qid`, no `name`
  and no `roles`. Details (labels, dates, Wikipedia) like `event_details.json`.
- `extract_dates.py` already ignores mentioned persons (Willibrord must not date the Ewalds).
- `tests/`: no eulogy place comes only from inside a mentioned person's name; Bassianus no longer lists Milan.

## API (martyrology-api)

- Person marks may carry `role: "mentioned"`.
- `MentionIn.kind` gains `movement` and `congregation`, served like events (qid, no name, no roles).

## Frontend (martyrology-frontend)

- The kind-3 accent, and the movement and congregation tints; popups as above.
- The persons index split, and the three new indexes.

## Order

As for events, the reader learns a new kind before the API sends it:

1. **Persons** (no new kind): crmedr (extraction, items, Wikidata, curated) → API (role on person marks) + release →
   frontend (accent, popup, index split, non-commemorated index) + snapshot + deploy.
2. **Movements and heresies**: crmedr → frontend (kind, tint, popup, index) deployed → API (kind) + release →
   snapshot + deploy.
3. **Religious congregations**: the same route as movements.

## Non-goals

- The 1914 English, 1749 and 1630 editions.
- Christ, the Trinity, the Virgin Mary; unnamed persons.
- Places inside mentioned persons' names.
- One shared index of movements and congregations (possible later, since the kinds stay apart).

## Left to the builder

- Exact colors of the new accent and tints (distinct from the existing ones in both themes, accessible contrast).
- The extraction method (lexical candidates plus Jev, as the persons and events passes did) and batching by month.
- The research and item-creation conventions follow those already used (P31, labels in la/en/it, description,
  P1343 Q125252554, sourced statements; dates with circa or presumed qualifiers).
