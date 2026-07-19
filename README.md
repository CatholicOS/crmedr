# CRMEDR

The home of the **Common Roman Martyrology Eulogy Data Repository**, curated by the **Catholic Engineering Task Force** of the [Catholic Digital Commons Foundation](https://github.com/CatholicOS).

## What is CRMEDR?

The Common Roman Martyrology Eulogy Data Repository (CRMEDR) provides a canonicalized list of identifiers for the eulogies (elogia) of the [Roman Martyrology](https://en.wikipedia.org/wiki/Roman_Martyrology) (*Martyrologium Romanum*), the official martyrology of the Roman Rite — and thereby for the saints, blesseds and celebrations to which the eulogies are directed.

The [Editio Typica](https://en.wikipedia.org/wiki/Editio_typica) of the Roman Martyrology is the official source for its eulogies, and all language editions of the Roman Martyrology are based off of the Latin Editio Typica published by the [Dicastery for Divine Worship and the Discipline of the Sacraments](https://www.cultodivino.va/en.html). The current reference edition is the **editio typica altera (2004)**, which anchors the identifiers in this repository.

The Roman Martyrology is a living source: eulogies are added with new canonizations and beatifications, and existing eulogies can be revised or repositioned from one edition to the next. The CRMEDR will therefore need to be revised with each new edition (and with Decrees of the Dicastery that touch the Martyrology). The only official variation issued since the editio altera — the decree *Postquam Summus Pontifex* (Variationes, 21 October 2021, Prot. N. 394/21, in Notitiae 57 (2021), 222) — touches only the Praenotanda (nn. 38 and 41, on the *Propria Martyrologii* and on Bishops' Conference editions) and affects no eulogy and therefore no canonical ID. Each edition's actual entry number, asterisk marker, and calendar placement are per-edition attributes, not part of the identity: an eulogy keeps its canonical ID across editions. The editions of the Roman Martyrology themselves are tracked in the [Common Liturgical Books Data Repository](https://github.com/CatholicOS/clbdr) (`martyrologium_romanum_1584` … `martyrologium_romanum_2004`); liturgical celebrations that correspond to martyrology eulogies can be cross-referenced with the [Common Liturgical Events Data Repository](https://github.com/CatholicOS/cledr).

## The identifier scheme

Identifiers take the form:

```
mr:MMDD-slug
```

- **`mr:`** — namespace prefix for the Roman Martyrology (placeholder pending committee decision);
- **`MMDD`** — the month and day that anchor the eulogy's placement in the editio typica altera 2004;
- **`slug`** — the Latin nominative lemma of the first-named subject of the eulogy, ASCII-folded, lowercase, without honorifics (no *sanctus*/*beatus*).

Examples: simple names (`mr:0101-basilius`), religious-name titles (`mr:0731-ignatius-de-loyola`, `mr:0128-thomas-de-aquino`), *cognomento* epithets (`mr:0730-petrus-chrysologus`), joined pairs (`mr:0926-cosmas-et-damianus`), companion groups (`mr:0206-paulus-miki-et-socii`), Marian invocations (`mr:0211-maria-de-lourdes`), and manual overrides for Christological and liturgical feasts (`mr:0806-transfiguratio-domini`).

### Owner segments for proper eulogies (proposal)

The Praenotanda of the Martyrologium Romanum (n. 38, as amended by the decree *Postquam Summus Pontifex*, 2021) foresee *Propria Martyrologii* of nations, dioceses and religious families. Eulogies **absent from the universal Martyrology** would receive IDs with an owner segment naming the registry that defines the owner:

```
mr:MMDD-slug                              universal (editio typica) — as above
mr:it:MMDD-slug                           national proprium (bare ISO 3166-1 alpha-2)
mr:cecdr/<circumscription>:MMDD-slug      diocesan/eparchial proprium
mr:ciclsaldr/<institute>:MMDD-slug        religious-family proprium
```

The circumscription and institute keys are the canonical IDs of the [Common Ecclesiastical Circumscription Data Repository](https://github.com/CatholicOS/cecdr) and of the [Common Institutes of Consecrated Life and Societies of Apostolic Life Data Repository](https://github.com/CatholicOS/ciclsaldr), without their own prefixes — e.g. `mr:cecdr/us-boston:0705-…`, `mr:ciclsaldr/ofm:0824-…`. A proprium that merely amplifies, moves or re-grades the eulogy of a saint already in the universal Martyrology does **not** create a new identity: those variations are per-proprium attributes of the existing `mr:` ID, just as entry number and asterisk are per-edition attributes. `MMDD` anchors to the proprium's own Dicastery-confirmed text.

The full derivation rules, the manual feast overrides, the leap-day (February 29) identity decisions, the anonymous-group slugs, the same-day collision resolutions, and the cross-edition verification work are documented in [docs/canonicalization-report.md](docs/canonicalization-report.md).

> **Note:** all IDs in this repository are **drafts pending committee review**. The namespace prefix and the anchor-edition choice are placeholders; changing either is a mechanical rewrite.

## Repository contents

- [`data/martyrology_ids.json`](data/martyrology_ids.json) — the machine-readable registry: 4,639 current canonical IDs with their calendar placement (month, day, entry position within the day), asterisk marker, the ISO 3166-1 alpha-2 code of the modern country corresponding to the place of the eulogy, and — where applicable — an `unnumbered` flag marking header eulogies (the drop-cap paragraphs that open a day for celebrations with liturgical rank: they are counted in the day's numbering but printed without a number); plus 1,147 **deprecated** IDs (`deprecated: true`, from [`data/deprecated_ids.json`](data/deprecated_ids.json)) coined for eulogies attested in historical editions with no counterpart in the editio altera 2004 — anchored to their placement in the edition named by `attested_in`.
- [`registry/`](registry/) — human-readable per-month tables of the same data; unnumbered header eulogies show their entry number in parentheses.
- [`i18n/`](i18n/) — the **subjects** of the eulogies: the saint, blessed or celebration each eulogy is directed to, in nominative display form per language. All locale files carry the identical complete key set (all 5,875 IDs); untranslated subjects are empty strings. `la.json` is fully filled — "Sancta Maria Dei Genetrix", "Sanctus Basilius" — including the deprecated IDs; `it.json` (4,047 filled) and `en.json` (2,943 filled) were extracted mechanically from the 2004 edition texts and await translator completion. Subject and slug are tightly coupled and edition-independent: the eulogy text may change between editions while subject and canonical ID remain the same.
- [`docs/canonicalization-report.md`](docs/canonicalization-report.md) — the canonicalization methodology, the special identity decisions, and the print-verification record.
- [`scripts/extract_registry.py`](scripts/extract_registry.py) — the script that generates the registry from the (private) digitization workbook.

## Copyright and the absence of texts

The texts of the eulogies of the Roman Martyrology — in Latin and in the various language editions — are copyrighted (© Dicastery for Divine Worship and the Discipline of the Sacraments / national episcopal conferences for the vernacular editions) and are **not** included in this repository. What is included here is only the non-copyrightable structural registry: the canonical identifiers and factual metadata about placement. Citation-length incipits appear in the methodology report solely to identify entries, following standard scholarly practice.

## Work in Progress

The goal is to establish a unified, canonical identifier system for the eulogies of the Roman Martyrology that can serve as a reference for interoperability between different liturgical applications — martyrology readers, liturgical calendar APIs such as the [Liturgical Calendar API](https://github.com/Liturgical-Calendar/LiturgicalCalendarAPI), and digital editions — in the same way that the [CLEDR](https://github.com/CatholicOS/cledr) does for liturgical celebrations of the Roman Missal.
