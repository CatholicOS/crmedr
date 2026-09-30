# Italian place phrases (`places[].it`) — design

Issue: [#12](https://github.com/CatholicOS/crmedr/issues/12) (before the gazetteer
sub-project). Date: 2026-09-30. Builds on
`docs/superpowers/specs/2026-09-30-places-extraction-design.md`.

## Goal

Add the Italian place phrase from the Italian (CEI) edition of the 2004 Martyrology
to each place, next to the Latin one. The Italian often gives the **modern** name and
country where the Latin has a historical one (*Brixinae in pago Tridentino* → "A
Bressanone nell'Alto Adige"; *Ramusciae in Raetia* → "A Ramosch in Rezia, nel
territorio dell'odierna Svizzera"), which will help the gazetteer find the modern
place and its Wikidata item. Those modern notes are sometimes wrong (#8), so the
gazetteer treats them as hints.

## Policy

The quoting exception extends to the Italian edition: **place designations are
factual and may be quoted verbatim in `places[].la` (Latin editio typica) and
`places[].it` (Italian CEI edition); no other text of either edition is stored.**
AGENTS.md and the README name both editions.

## Data shape and alignment

```json
{ "role": "death", "la": "Ramúsciæ in Rǽtia",
  "it": "A Ramosch in Rezia, nel territorio dell’odierna Svizzera", "source": "lead" }
```

- `it` goes right after `la`. Key order: `role`, `la`, `it` (when present),
  `source`, `via` (when present).
- **The Latin decides whether an item exists.** `it` is only ever added to an item
  that has `la`. An item has no `it` when the Italian has no usable phrase.
- **A bare Latin back-reference** (it has `via` and its `la` is the root's) takes the
  **root's `it`**. `la` and `it` then describe the same printed place, and `it` is
  verbatim in the `via` entry's Italian text.
- **Every other lead item** takes the entry's own Italian opening phrase.
- **Curated items** may carry an optional `it`, entered by hand.

## Extracting the Italian opening phrase

Same machinery as the Latin (`base_copy`, one character to one, case kept):

- **Stop words.** A stop word counts when it is lowercase, or when it is the first
  word of the text:
  - honorifics: *san, sant, santo, santa, santi, sante, beato, beata, beati, beate,
    santissimo, santissima*;
  - markers: *memoria, commemorazione, commemorano, parimenti, deposizione,
    traslazione, natale, anniversario, martirio, passione, transito, dedicazione,
    festa, solennità, dormizione*. The list includes *anniversario*, since ",
    anniversario della morte di …" renders *natalis*, and *martirio* for *passio*.
    "Parimenti si commemorano" renders *Item commemorantur*.
  - `MISSPELLED_STOP_WORDS_IT`: *desposizione* and *comemorazione*, as found in the
    CEI text, each with its entry. They have **not** been verified against the CEI
    print, and the comment says so.
- **Comma segments.** The phrase is split at commas, and the first segment is always
  kept. Each later segment is kept, in order, until the first one that fails:
  - it is **cut** if it is a time or relative clause: it starts with *dove*, *da
    lui*, *che*, *chiamat…* or *sotto*, or it matches "… anni dopo", "… anni più
    tardi" or "(nello stesso) giorno e anno";
  - otherwise it is **kept** if its first word is a locative or modern-hint word:
    *in, nel, nella, nello, nell, nei, negli, nelle, presso, vicino, sul, sulla,
    sulle, sui, al, alla, ai, lungo, tra, fra, ora, oggi, attualmente, sempre,
    ancora*;
  - otherwise it is **cut**. This also removes stray words before the subject: ",
    trecentodieci", ", due", ", circa ottocento", ", il centurione".
- **Back-references.** A leading *Sempre* or *Ancora* ("also") is dropped ("Sempre a
  Parigi" → "a Parigi"). After that, "nello stesso luogo" or "nella stessa città" (in
  any case) is a **bare back-reference** and yields no phrase of its own. A bare
  Latin back-reference takes the root's `it` anyway, so the Italian side never needs
  its own `via`.
- **Length.** At most 20 words (`MAX_WORDS_IT`). Italian place designations are
  wordier than the Latin: 84 exceed 12 words, and none exceeds 20.

The Latin extraction and every existing `la` are unchanged.

## Report

`docs/places-report.md` gains two sections:

- **Latin places without an Italian phrase**: IDs only, currently 4.
  `mr:0104-abrunculus` is absent from the CEI edition, and three Italian texts lack
  a lowercase honorific.
- **Italian places without a Latin place**: ID and `it` phrase, currently about 10.
  They are curation candidates, and some are real Latin gaps. A Latin place name
  that starts with a capitalized saint ("Sancti Trudonis fani" = Sint-Truiden,
  "Sancti Iacobi" = Santiago) is read as "no place" by the Latin rule.

## Checks

`validate()` also asserts:

- every `it` appears verbatim in its Italian text: the entry's own, or the `via`
  entry's for a bare back-reference;
- every `it` is at most 20 words;
- a bare back-reference's `it` equals its root's `it`, or is absent when the root
  has none;
- curated `it` passes the same checks, in `validate_curated`.

## Tests

`tests/test_places.py`, with made-up Italian phrases only:

- lowercase honorific ends the phrase; capitalized saint in a place name stays;
  capitalized stop word at the start means no phrase;
- each marker (*anniversario*, *martirio*, *parimenti*) ends the phrase;
- the comma rule both ways: a modern hint is kept, and a relative clause, a time
  clause and a stray numeral are cut;
- *Sempre* / *Ancora* dropped; "Nello stesso luogo" is a bare back-reference;
- alignment: a lead item gets its own `it`; a bare Latin back-reference gets the
  root's `it`; no `it` when the Italian has no phrase;
- validation: a non-verbatim or overlong `it` is rejected, and so is a mismatched
  `it` on a bare back-reference;
- the report lists both mismatch sections.

The 5-word overlap scan covers the tests against both the Latin and the Italian
texts.

## Review against the real data

After generation, every `it` is scanned, not a sample:

- every `it` containing a comma segment, with the part after the comma listed;
- every `it` over 16 words;
- the two mismatch lists.

Each problem found becomes a rule fix with a test.

## Documentation

- AGENTS.md and README.md: the exception names both editions, and `places[].it` is
  described.
- `docs/canonicalization-report.md` (Places): the `it` key, its extraction rule, and
  the counts.
