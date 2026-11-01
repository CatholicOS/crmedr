# Event mentions: councils and synods

Status: approved by the curator (2026-11-01); crmedr implemented on this branch.

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
an event when the eulogy makes the council certain; otherwise no mark. The curator decides each such case: *Concílio in hac civitáte*
(Successus and companions, 18 January, at Carthage) is the Council of Carthage of 256 (Q141808067). *Sýnodo Romæ celebráta* (Geruntius, 9 May), from which he is said (*tráditur*) to have been returning when
he was killed, is identified by its date: most historians put his death in 501, the year the Palmary Synod
(Synodus Palmaris, 501–502) met in Rome over Pope Symmachus. Wikidata had no item for it; Q141966070 was created
(2026-11-01, sourced to Cathopedia's *Concilio di Roma (501)*).

## Data (crmedr)

- `data/events_curated.json`: by eulogy, the printed phrase in each language and the event's QID:
  `{"mr:0101-maria-dei-genetrix": [{"la": "Concílio Ephesíno", "it": "Concilio di Efeso", "qid": "Q184332"}]}`.
  Phrases are stored as printed, so the extractor finds their offsets; like the other curated files the repository
  stores no text beyond the phrase itself. The first version is drafted from the survey with candidate QIDs and
  reviewed by the curator.
- `scripts/extract_mentions.py`: `KINDS` gains `event`. An event mark carries `kind`, `where`, `start`, `end`,
  `check` and `qid`, no `name` and no `roles`. A place or person mark inside an event's span is dropped. A curated
  phrase not found in the text is an error, as for persons.
- `data/event_details.json`, written by `scripts/event_details.py` from Wikidata (network, cached like
  `person_details.json`): for each event QID its labels (la and the interface languages en, it, fr, de, es, pt),
  descriptions, `start` and `end` (P580/P582, else the point in time P585, as year, precision and circa), the
  place it was held (P276, a QID; the venue where Wikidata gives one, as Lyon Cathedral for Lyon II) and the
  Wikipedia titles.
- The gazetteer resolves each council phrase (26 keys, *Ephesíno*, *Concílio Nicǽno*, *Sýnodum
  Chalcedonénsem*…) to the city where the council met, no longer to the council: Ephesus (Q47611), Nicaea
  (Q739037), Chalcedon (Q337381), Lyon (Q456), Trento (Q3376), Vatican City (Q237) for Vatican I and II, Albon
  (Q389248) for Epaone, and so on. The council's item is in `events_curated.json`, reviewed there: the eight
  keys Jev had suggested included, and Carthage decided per eulogy (256, Q141808067, for Libosus on 29 December;
  484, Q141810272, for Vindemialis and Longinus on 2 May).
- Eulogy places: the curated body place behind the old mark (role "mention") stays and now resolves to the
  city; `tests/test_events.py` pins that no eulogy lists a council among its places and that 1 January lists
  Ephesus (Q47611).
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
- Creating Wikidata items, except with the curator's leave: a missing one is reported first (the Palmary Synod, Q141966070, was created so).

## Order

crmedr (curated events, extractor, details, reports) → API (kind, details) + release → frontend (tint, popup) +
snapshot + deploy.
