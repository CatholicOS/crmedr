# Event mentions: historical events

Status: requested by the curator (2026-11-06: "tag every historical event mentioned in the eulogies of the Latin and
Italian 2004 editions that can be associated with a Wikidata item"), who asked for the work without a question
round. The decisions below are the implementer's calls, made on the precedent of the councils
(`2026-11-01-event-mentions-design.md`), for the curator to review on the pull request.

## Why

The `event` mark kind was built general on purpose, but only councils and synods were tagged: 51 phrases per
edition. The eulogies name many other events, above all persecutions (*persecutióne Décii imperatóris*,
*persecuzione dei Boxer*), the French Revolution (*gállica perturbatióne*, *rivoluzione francese*), the wars of the
twentieth century, invasions and sieges. A reader should reach their items the same way.

## Decisions (implementer's calls)

1. **Any kind of event**, when a phrase names one identifiable historical happening that has a Wikidata item:
   persecutions, wars, revolutions, uprisings, invasions, sieges, schisms, epidemics, a plot, a suppression.
2. **Bare words count only when the eulogy makes the event certain**, as *Concílio in hac civitáte* did for
   Carthage: *persecutióne* in a Mexican martyr's eulogy of 1927 is the Cristero War; *nella medesima
   persecuzione* in a Spanish martyr's eulogy of 1936 is the persecution of 1936. The eulogy's year
   (`data/dates.json`) checks each such case: Pedro Maldonado (1937, after the Cristero War) is left unmarked, and
   David Galván's *persecutióne mexicána* (1915) is the Mexican Revolution.
3. **The persecution, not the war, where the eulogy names the persecution.** A Spanish martyr's *persecutióne
   erga fidem* links to the Red Terror (Q3120811), the anticlerical repression of 1936; *bello civíli* / *guerra
   civile* links to the Spanish Civil War (Q10859). The persecution of Maximian and Maximinus Daia, and Diocletian's
   edict, link to the Diocletianic Persecution (Q1265674), whose years (303–313) they fall in.
4. **The phrase is the words that name the event**, no leading preposition or article: *persecutióne Diocletiáni
   imperatóris*, *occupazione militare della Polonia*, *medesima persecuzione*. An edition that does not name the
   event has no phrase: the Latin's *eádem tempestáte* ("at the same time") for the Italian's *stessa persecuzione*
   is left unmarked, so an entry may carry only `la` or only `it`.
5. **Marks inside the phrase stay.** A person inside the phrase keeps its mark, inside the event's (*imperatore
   Diocleziano* in *persecuzione dell’imperatore Diocleziano*); so does a place, through `keep_places` on the
   entry (*Polonia* in *occupazione della Polonia*). The councils keep dropping theirs, as decided for them.
6. **A phrase naming two events is left unmarked** (*persecutióne Décii et Valeriáni imperatórum*, 28 July): a mark
   links one item.
7. **No items created.** An event without an item is reported below, not created, as for the councils.

## How the events were found

A word list in both languages (persecution, war, battle, siege, revolution, schism, plague, translation, invasion,
edict, occupation and their forms) picked 973 of 4,640 eulogies, texts and footnotes. Each was read in Latin and
Italian, and the phrases naming an event were copied exactly; every phrase was checked to be printed in its text.
The events were then unified and their items looked up in Wikidata and the Wikipedias. Not found this way: an
event named with none of the words (the exile of the 4,966 under Huneric on 12 October is told with *exsílium*).

## Result

505 phrases in 500 eulogies, linked to 40 items: 529 event marks in the Latin and 555 in the Italian, councils
included (51 each before). The most frequent: the Red Terror (176 phrases), the French Revolution (100), the
Diocletianic Persecution (55), the Boxer Rebellion (34), the Second World War (26), the German occupation of Poland
(22), the Cristero War (19), the Decian persecution (17).

## Events without an item (73 phrases, 33 events)

Left unmarked until the curator decides whether to create items:

- the Moorish persecution of Córdoba's Christians, 850–859: 17 phrases (*Maurórum persecutióne*); Wikidata has the
  martyrs (Q1582818), a group, not the persecution;
- the Vandal persecution of the Catholics: 15;
- the persecution of Catholics under Elizabeth I: 6;
- Shapur II's persecution: 4 (Q3850292 is the martyrs, a group);
- Mwanga's persecution in Buganda: 3 (Q1094107 is the martyrs, a group);
- the Saracen capture of Gaza (634–637): 2;
- one phrase each: the persecutions under Domitian, Trajan, Hadrian, Marcus Aurelius and Aurelian; the persecution
  under Antiochus IV; the Manchu persecution in Fujian (1648); the persecution in Thailand (1940); Julian's edicts;
  the Novatianist schism (Q1276913 is the church, not the schism); the Hunnic invasion of Gaul and the siege of
  Orléans (451); the fall of Nisibis (363); Theuderic I's invasion of the Auvergne; the war of Franks and Lombards
  (773–774); the Saracen raids on Mar Saba (614, 797) and Lérins; the fires of Constantinople (404) and of the
  palace at Nicomedia (303); Henry VIII's divorce; the translations of the relics of Augustine, John Chrysostom,
  the Magi and Radbod; the martyrs of Najran (a group).

## Order

crmedr (curated events, extractor, details, reports) → API pin + release (no API change: the `event` kind and its
details are served already) → frontend snapshot + deploy (no frontend change: event marks, nesting and popups exist).
