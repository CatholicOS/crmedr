# A person known by more than one name — design

Date: 2026-10-10. Amends `docs/superpowers/specs/2026-10-08-persons-design.md` and
`docs/superpowers/specs/2026-10-10-repeated-person-names-design.md`, and martyrology-frontend's
index of names (`docs/superpowers/specs/2026-10-09-names-index-design.md` there). Places are out of
scope: CatholicOS/crmedr#86.

## Goal

The 2004 Latin often gives a saint's second name in the same breath: *sancti Mamántis seu
Mamétis*, *Kingæ seu Cunegúndis*, *Ioánnis Sordi seu Cacciafronte*, *Dativus qui et Sanator*.
These are one person, but today:
- the index of names knows only the first name, so a reader looking for "Mames" or "Cunegundis"
  finds nothing;
- *Dativus, qui et Sanator* in the Abitinian list (`mr:0212-martyres-abitinenses`, footnote 1) is
  extracted as two persons;
- the second name is lost: *Maximianus seu Maximus* keeps only Maximianus;
- some of these persons are left unmarked in the text. Mamas is one: the extractor can't get from
  "Mamas" to *Mamántis*.

After this change, each such person stays one person under one main name, with their other names
recorded. The index of names gives each other name a cross-reference to the main heading:
**"Mames → see Mamas"**.

About 35 phrases in the texts and footnotes give a person's second name: *seu* (most), *vel*,
*sive*, and *qui et* / *quæ et*. The other *seu* phrases join two places (*Oświęcim seu
Auschwitz*, 16 eulogies; #86), or name someone who is not commemorated (*Dhu Nuwās seu Dun*).

## The data

A person in `data/persons.json` gains an optional **`also`**: the person's other names, as Latin
nominatives, in printed order.

```json
{ "name": "Mamas", "also": ["Mames"], "where": "text" }
{ "name": "Ioannes Sordi", "also": ["Ioannes Cacciafronte"], "where": "text" }
{ "name": "Dativus", "also": ["Sanator"], "where": { "footnote": 1 } }
```

- **The main name doesn't change.** It is the subject in `i18n/la.json`, or the first form printed
  for a companion. Keys, numbering (`n`) and decisions still go by the main name.
- **A variant is a full name.** When only part of the name changes (a surname, an epithet), the
  variant repeats the rest: "Ioannes Cacciafronte", "Ioannes Messor", "Hugo Cook". The index files
  names by their first word, so the cross-reference sits next to its heading.
- **`also` is written only when non-empty.** A variant is never the person's own name, and never
  appears twice.
- As with names, only the nominative is stored, never the printed form.

## Extraction: `scripts/persons_text.py`, `scripts/extract_persons.py`

- **After a person's printed form,** a variant is introduced by *seu*, *vel* or *sive*, or by
  *qui et* / *quæ et*. That person's variant is the name that follows, never a new person.
  - In a footnote list: "Maximianus seu Maximus" gives Maximianus, also Maximus. "Dativus, qui
    et Sanator" gives Dativus, also Sanator. The segment opening with *qui et* / *quæ et* belongs to
    the name before it, instead of being split at "et".
  - In the text: the person's printed form is found as `extract_mentions.py` finds it
    (`mentions_text.find_person`). The words right after it are then read: "Mamántis seu Mamétis".
    Companions read by `text_companions` are handled in the same way.
- **Nominatives.** A printed variant is converted with the lexicon, as names are now (the
  genitive endings, a known nominative). If the conversion isn't sure, as with *Mamétis*, the
  variant isn't guessed: `docs/persons-report.md` lists "eulogy: person, variant not read", for a
  curator. A variant already in the nominative, as in the footnote lists, is taken as it is.
- **Only persons are followed up.** *seu* after a place, or after a name that isn't one of the
  eulogy's persons, adds nothing.

### Curated variants: `data/persons_variants_curated.json`

```json
{ "$comment": "…",
  "mr:0817-mamas": { "Mamas": ["Mames"] } }
```

- **Keyed by eulogy, then by person key** (`name` or `name#n`).
- **Added to the extracted variants, in order, without repeats.** Unlike `persons_curated.json`,
  it never replaces a eulogy's persons, so correcting one variant doesn't freeze the other names of
  a long list.
- **The check (the script fails on it):** the eulogy and the person exist; each variant is a
  non-empty name, not the person's own name, and contains no `#`.

## Marks: `scripts/extract_mentions.py`

- **A person printed with a variant is marked over the whole phrase,** "Mamántis seu Mamétis", as
  one mention of one person. That phrase is one span, from the main form to the end of the
  variant.
- **Matching tries each name in turn:** the main name first, then each variant, so a person
  printed only under a variant is still found. A match is a mention of the person, with their main
  name and `n`.
- **Irregular stems stay with the curator.** Variants don't help when no name's stem matches the
  print. *Mamántis seu Mamétis* matches neither "Mamas" nor "Mames", so Mamas is still proposed as
  an unmatched `add_mention`, and the curator marks the phrase in `/review`.
- **Leftover matches** (`add_mention`, "matched again") count matches of any of the person's names.

## Identification: `scripts/build_person_items.py`

- **The Wikidata candidate search also tries each variant,** after the main name: Kinga is also
  sought as Cunegundis, Marina as Margarita.
- **`name_matches` accepts a candidate whose names match the main name or any variant.** The
  evidence bar for `auto` is unchanged.
- **A `resolve_person` op carries `also`,** so the review card can show it.

## The frontend (martyrology-frontend, separate PR)

- **Persons snapshot:** `buildPersons` copies `also`. `PersonMention` gains `also?: string[]`.
- **Index of names (`lib/names-index.ts`):**
  - **"See" entries:** each variant of a person gives an entry
    `{ name: "Mames", see: <heading key>, target: "Mamas" }`. It is filed under the variant's own
    letter, and sorted among the headings by name.
  - **No duplicates:** one entry per variant and heading, however many eulogies print it.
  - **No redundant entries:** an entry is dropped when its name is already the heading's.
  - **Same-name saints:** a variant that is also another saint's name (Margarita) sits next to
    that saint's headings.
  - A letter may hold "see" entries only. The counts of printed eulogies and of eulogies naming
    someone don't change.
- **Rendering (`components/NamesIndex.tsx`):**
  - Each heading gets a stable `id` made from its key, with characters an id can't hold replaced.
  - A "see" entry renders as "*Mames* → see **Mamas**", linking to the heading. The names are
    tagged `lang="la"`, and "see" is translated: see / vedi / siehe / véase / voir / ver.
- **Review cards:** the person card shows `also` under the name ("Also: Mames").
- **Out of scope:** the variant in the reader's popup. The API's mentions don't carry it.

## Rollout

1. **crmedr PR:** the scripts, their tests, `data/persons_variants_curated.json` (starting with
   Mames for Mamas), then the regenerated persons, items (`propose`) and mentions.
2. **martyrology-frontend PR:** the snapshot, the index of names, the card, their tests, then the
   snapshot refresh.
3. **martyrology-api:** the vendor refresh at crmedr's next release. No code change.

## Tests

crmedr:
- reading variants:
  - *seu / vel / sive / qui et* after a name, in a footnote list and in the text;
  - Dativus/Sanator and Maximianus/Maximus are one person each;
  - an unsure genitive is reported, not guessed;
  - *seu* after a place adds nothing;
- curated variants are added without repeats, and the check refuses bad entries;
- marks:
  - a mark spans "Mamántis seu Mamétis";
  - a person printed only under a variant is marked;
  - leftovers count every name;
- identification: the search tries each variant, `name_matches` accepts a variant, and the op
  carries `also`.

martyrology-frontend:
- `buildPersons` copies `also`;
- the "see" entries: filing, de-duplication, dropping redundant entries, sorting, and same-name
  saints;
- the heading ids and the links;
- the card shows `also`.
