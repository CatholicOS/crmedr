# Eulogy items: one Wikidata item for what a eulogy commemorates as a whole

Status: draft for the curator, 2026-10-31.

## Why

The registry links each person a eulogy names to a Wikidata item (`data/person_items.json`). Some eulogies, though, commemorate something that is not one person:

- **Groups:** "Liberatus and six companions", "Hermes and Caius", the many martyrs of Pontus. Wikidata often has an item for the group itself (Q85977003, the seven martyrs of Carthage under Huneric; Q97253965, Hermes and Gaius).
- **Feasts:** Joseph the Worker (Q105888686, the feast), the Visitation, the Presentation of Mary. Marian titles are a special case, below.
- **Dedications and translations:** the dedication of a basilica (the church's item), the translation of relics.

There is nowhere to record those items today. A person mention is the wrong place for them: Liberatus's mention is Liberatus, not the seven martyrs, and Joseph's mention on 1 May is Joseph, not the feast. Of the 4,640 current eulogies, 666 commemorate several persons, 58 none (feasts, dedications, anonymous groups), and 49 a single person under the typology `celebratio`, `dedicatio` or `translatio` (Joseph the Worker, the Marian titles). Those 773 are the candidates; the other 3,867 commemorate one person and get no item.

## Goals

- An optional Wikidata item per current eulogy, for what it commemorates as a whole.
- Recorded only when the eulogy's subject is not a single person. For a single saint it would repeat that saint's person item, so it is not recorded (curator, 2026-10-31).
- Shown with the eulogy on romanmartyrology.com, next to its date and places.
- Used as a check: the persons of a group eulogy should be members of its group item.

## Non-goals

- Replacing person links. Liberatus keeps his own item; the eulogy links to the group.
- Recording an item for every eulogy.
- Creating Wikidata items in bulk. Items are created one at a time, after research, as in the person audit.

## The data

- **`data/eulogy_items.json`**, curated, keyed by current eulogy ID: `{"mr:0702-liberatus-et-socii": {"wikidata": "Q85977003", "kind": "group", "status": "reviewed"}}`.
- **`kind`** is one of `group`, `feast` (a feast, solemnity or memorial), `dedication` or `translation`. It says why the eulogy has an item, and lets the frontend label the link.
- **`status`**, as for persons: `auto` (suggested by the rule below, not yet reviewed), `reviewed`, or `unresolved` (`wikidata: null` with a `note`: researched, and Wikidata has no fitting item). Like `data/person_items.json`, the file holds the `auto` suggestions and the decisions together; a curator review turns `auto` into `reviewed`.
- **Renames** re-key it, like the other registry files keyed by ID (`apply_renames.py`, `PROSE_SCRIPTS`).
- **`extract_registry.py`** copies `wikidata` and `kind` onto the registry entry as `item: {"wikidata", "kind"}`, as it copies `date`, for entries with an item only: `null` items and their notes stay in the file. martyrology-api and the frontend then read it from the registry they already consume.

## Single person or not

The rule decides, not the counts above. A person is **commemorated** in a eulogy unless `data/persons.json` gives it the role `mentioned`: the role is absent for the commemorated, its default. A word naming several persons (a shared mark) counts once per person.

- **Several commemorated persons, or none:** the eulogy may get an item.
- **One commemorated person, typology other than `celebratio`, `dedicatio` or `translatio`:** a single-person eulogy. It gets no item, and a test fails if it has one, unless the entry carries a curator `note` saying why.
- **One commemorated person under `celebratio`, `dedicatio` or `translatio` (49):** decided by hand, one by one, as part of the research below. Either the feast, church or event goes on the eulogy (Joseph the Worker), or nothing does, because the person mention already links the title item (the Marian titles). The second case is recorded as `{"wikidata": null, "status": "reviewed", "note": "the mention links the title"}`, so the report can tell decided from not yet looked at. A title cannot be told from a person by its Wikidata class: Joseph's item, Q128267, is a "human biblical figure", not Q5.

Only current eulogies get items. Deprecated IDs and their `same_eulogy` twins inherit nothing, as with dates.

## Suggestions

- **Groups:** read P361 (part of) and P463 (member of) from the items of the eulogy's commemorated persons. When two or more of them, and at least half, point at the same item, that item is suggested as `auto` with kind `group`. Jev then asks whether that item is the group the clause describes, as in the person audit, and a low probability leaves the eulogy for research instead. The suggester needs network access (Wikidata reads cached in `.cache/wikidata/`, Jev cached by request), like `build_person_items.py propose`; `check` validates offline.
- **Feasts, titles, dedications, translations:** no reliable rule. The 58 eulogies with no commemorated person and the 49 one-person feasts, dedications and translations are researched by hand and recorded as `reviewed` (or `unresolved`).
- Nothing is linked as `reviewed` without someone having looked at it.

## The membership check

For each eulogy with a group item, `docs/eulogy-items-report.md` lists the commemorated persons whose item is not a member of that group: neither P361 nor P463 to it, nor listed in its P527. Each listed person is a candidate wrong link, or a missing statement on Wikidata to add there. The report also counts eulogies by kind and status, and lists the group eulogies with no item yet.

## The Marian titles and Joseph the Worker (decided with this design)

- **Marian titles** (Dei Genetrix, Guadalupe, Lourdes, Fatima, Mount Carmel, Regina, Perdolens, Rosario, …): the person mention is the title as printed ("Beata Maria Virgo de Guadalupe"), and it links to the title or apparition item, never to Mary, Q345. This was the curator's decision for Dei Genetrix (Q208542), extended to every Marian title. The eulogy item would repeat that link, so, as for a single saint, none is recorded. Most of these mentions have no item yet: finding them is part of this work, recorded in `data/person_items.json` (or `data/mentions_curated.json` where the matcher does not mark the title).
- **Joseph the Worker:** Wikidata has no item for the title, only for the feast (Q105888686). `mr:0501-ioseph-sponsus-mariae` is renamed `mr:0501-ioseph-opifex`, the form of `maria-regina` and `maria-perdolens`. Its "Ioseph" mention stays on Joseph, Q128267, and the eulogy item is the feast, kind `feast`. The rename goes first, in the usual order (texts, crmedr, API, frontend), as its own PRs ahead of the data work. The other Marian title IDs need no rename. In general, a title links its mention when Wikidata has an item for the title; otherwise the feast goes on the eulogy.

## Display

- The API exposes `item` on the eulogy as the registry gives it, with no new endpoint.
- The frontend shows a Wikidata link on the eulogy, labelled by kind ("Group on Wikidata", "Feast on Wikidata", …), in the six interface languages.

## Left to the builder

- The exact thresholds of the group rule and of Jev, tuned on the eulogies where the answer is known: Liberatus, Hermes and Caius, the Martyrs of Cirta.
- The order of the work: crmedr data and checks first, then the API pin, then the frontend.
- The wording of the report and of the frontend labels.
