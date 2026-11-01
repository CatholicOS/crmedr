# Event mentions: councils and synods

Status: draft for curator review (2026-11-01).

## Why

The 2004 eulogies name church councils (*quam Patres in Concílio Ephesíno Theotókon acclamavérunt*, 1 January).
Today the reader marks only the adjective, and as a place: *Ephesíno* is a place mark, role "mention", and in the
Italian *Efeso* inside *Concilio di Efeso*. Its item, Q184332, is in fact the First Council of Ephesus, not the city:
the gazetteer resolves 15 council phrases to council items (`data/gazetteer.json`: *Concílii Ephesíni*, *Concílio
Nicǽno*, *Nicǽna Sýnodus*, *Sýnodo Arelaténsi* reviewed; *Concílio Chalcedonénsi*, *Concílio Sardicénsi*,
*Concílium Œcuménicum Tridentínum*, *Concílium Œcuménicum Vaticánum Primum* and seven more at Jev's suggestion), so
those councils sit among the eulogies' places, with a council where a city should be. Other council phrases have no
mark at all. A reader should see the council as the thing named and reach its item.

## Decisions (curator, 2026-11-01)

1. **A third mark kind, `event`**, beside `person` and `place`, linked to the event's Wikidata item. Councils and
   synods are the first events. The kind is general on purpose: later passes may add other events (translations of
   relics, dedications held on a date), but this work covers councils and synods only.
2. **One mark per phrase.** The whole phrase is the event mark: *Concílio Ephesíno*, *Concilio di Efeso*,
   *Concílium Œcuménicum Vaticánum Primum*, *Sýnodo Lateranénsi*. Any place mark inside it is dropped. The eulogy
   keeps the place in its places (role "mention") through the event item's location (P276): Ephesus (Q47611), where
   the council item stands today.
3. **Scope: texts and footnotes, councils and synods, Latin and Italian 2004.** A survey (2026-11-01) found the
   named councils and synods only in the eulogy texts: about 40 Latin phrases and their Italian counterparts, naming
   about 30 distinct events. The footnotes name none, but the extraction reads them too.

## What is an event mention

A phrase that names one council or synod, by its place adjective or genitive, its ordinal, or *Œcuménicum*:
*Concílio Nicǽno Primo*, *Concílii Toletáni Décimi*, *Sardicénse Concílium*, *Sýnodum Chalcedonénsem*,
*Concilio di Calcedonia*, *Concilio Costantinopolitano III*.

Not events:
- the verb *conciliare* and its forms (*conciliávit*, *concílians*);
- councils named by no place or number (*plúribus concíliis*, *concíliis hispánis*, *in sýnodis*);
- *Concílium Sanctórum* (25 October), a name for a church, not a council.

A council named only by its city's demonstrative (*qui Concílio in hac civitáte*, *tria concília hac in civitáte*) is
an event when the eulogy makes the council certain; otherwise no mark. The curator decides each such case.

## Data (crmedr)

- `data/events_curated.json`: by eulogy, the printed phrase in each language and the event's QID:
  `{"mr:0101-maria-dei-genetrix": [{"la": "Concílio Ephesíno", "it": "Concilio di Efeso", "qid": "Q184332"}]}`.
  Phrases are stored as printed, so the extractor finds their offsets; like the other curated files the repository
  stores no text beyond the phrase itself. The first version is drafted from the survey with candidate QIDs and
  reviewed by the curator.
- `scripts/extract_mentions.py`: `KINDS` gains `event`. An event mark carries `kind`, `where`, `start`, `end`,
  `check` and `qid`, no `name` and no `roles`. A place or person mark inside an event's span is dropped. A curated
  phrase not found in the text is an error, as for persons.
- `data/event_details.json`, written from Wikidata (network, cached like `person_details.json`): for each event QID
  its labels (la, it, en, fr, de, es, pt), date (P585, or P580/P582), location (P276) and the Wikipedia links.
- The gazetteer's 15 council keys move to `events_curated.json`, their QIDs reviewed there (the eight at Jev's
  suggestion included; *Concílio Carthaginénsi* is one key for two councils, Carthage 256 (Q141808067) and 484
  (Q141810272), and is decided per eulogy). The gazetteer no longer resolves a council phrase.
- Eulogy places: an event's P276 joins the eulogy's places with role "mention" in place of the council item; a test
  pins that the 1 January eulogy lists Ephesus (Q47611) and no council among its places. An event with no P276
  (Vatican I and II, Agde, Seleucia-Ctesiphon, Aquileia) adds no place unless the curator gives one.
- Reports: `docs/mentions-report.md` counts event marks; the persons and places reports are unchanged.

## API (martyrology-api)

- `MentionIn.kind` becomes `Literal["person", "place", "event"]`. An event, like a place, is served with no `name`
  and no `others`; it has no `roles`.
- Event details are served with the other entities, from `event_details.json` of the pinned crmedr.

## Frontend (martyrology-frontend)

- `MentionKind` gains `"event"`. Event marks get their own tint, distinct from persons and places, in light and dark.
- Hover or tap opens an event popup: the label in the reader's language (falling back to Latin, then English), the
  date, the place, and links to Wikidata and Wikipedia.
- Events take part in hover highlighting like places: every mark of the same QID in the eulogy lights together.
- No events index page in this work.

## Non-goals

- Events other than councils and synods.
- The 1914 English and 1749/1630 editions.
- Creating Wikidata items: every council named has an item; a missing one is reported to the curator first.

## Order

crmedr (curated events, extractor, details, reports) → API (kind, details) + release → frontend (tint, popup) +
snapshot + deploy.
