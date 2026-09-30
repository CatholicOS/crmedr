# Typology metadata for eulogies — design

Issue: [#6](https://github.com/CatholicOS/crmedr/issues/6). Date: 2026-09-30.

## Goal

Add a `typology` field to every **current** registry entry. It answers one question:
**what does this date mark?** Consumers can use it to filter (e.g. all *depositio*
entries), for statistics across the year, and to show badges in apps. Every tag
must be checkable against the elogium's own text. Like the rest of the repository,
the tags are derived from the text, and no text is published.

## Scope

In scope:
- `typology` for the 4,639 current entries (editio altera 2004).
- A generator script, a hand-override map, a review report, unit tests, docs.

Out of scope (noted on #6 for later rounds):
- Typology for the 1,443 deprecated entries. Their texts come from other
  editions and need their own marker patterns.
- The `places` proposal (typed place roles, see the comment on #6). The schema
  leaves room for it.
- The JSON Schema file mentioned in the issue, since the repo has no validation
  setup to hang it on.
- The issue's `location.city/site` fields.
- Liturgical rank (*sollemnitas / festum / memoria*). Rank is a different axis
  from typology and belongs to the liturgical-calendar project.

## Values

One value per current entry, from this closed set:

| Value | Meaning |
| --- | --- |
| `dies_natalis` | The actual day of death or martyrdom (*natalis*, *passio*, *transitus*, or no marker) |
| `depositio` | Burial |
| `translatio` | Moving of relics |
| `inventio` | Finding of relics (no 2004 instances; kept for other editions) |
| `dedicatio` | Dedication of a church or altar |
| `ordinatio` | Episcopal ordination (no 2004 instances; kept for other editions) |
| `celebratio` | The date is fixed by a liturgical celebration, not by an event: feasts of the Lord and of Mary, Cathedra Petri, Exaltatio Crucis, the Angels, All Saints, and saints' memorials placed away from their death day |
| `commemoratio` | Commemoration with no event behind the date: Old Testament figures, *commemoratio sancti N.*, All Souls |

`dies_natalis` therefore always means the saint's actual death day. When the
calendar memorial falls on another day (for example, mr:1228-franciscus-de-sales is
`dies_natalis` and mr:0124-franciscus-de-sales is `celebratio`), a filter on
`dies_natalis` returns exactly one date per saint.

## Classification rules

The text is the Latin editio altera 2004 (`martyrology-texts`,
`data/editions/martyrologium_romanum_2004/*.json`). It is matched after
accent-folding and lowercasing with `fold()` from `extract_subjects.py`
(æ/œ→e, j→i, punctuation→space). Word lists are therefore written in folded
form (*sancte*, *beate*). The first rule that matches wins:

1. **Override.** `TYPOLOGY_OVERRIDES[id]`, one line per ID with a comment giving
   the reason.
2. **Off-day memorial.** Another 2004 elogium says *cuius / eius / quorum /
   earum memoria* followed by a date expression: *cras / crastina die /
   postridie* (+1), *perendie / biduo post* (+2), *pridie* (−1), *hodie* (0), or an
   ordinal day with a month genitive (*die vigesima quarta ianuarii*,
   *vicesimo septembris*). The target is the entry on that date with the same
   slug as the source. If there is none, it is the single entry on that date
   whose lead holds *memoria / festum / sollemnitas*. The target gets
   `celebratio`, unless the cross-reference names the event of that day
   (*die depositionis* → `depositio`, *die ordinationis* → `ordinatio`,
   *die translationis* → `translatio`). A cross-reference with no resolvable
   date, or with no single target, is listed in the report and tags nothing.
3. **Feast of a mystery or object → `celebratio`.** The entry is in `FEAST_IDS`,
   an explicit list of 27 IDs. Its object is a mystery of the Lord, a Marian feast
   or title, the angels, the Chair of Peter, the Conversion of Paul, the Holy
   Cross or All Saints: 0101-maria-dei-genetrix, 0103-nomen-iesu,
   0106-epiphania-domini, 0125-conversio-sancti-pauli, 0202-praesentatio-domini,
   0211-maria-de-lourdes, 0222-cathedra-sancti-petri, 0325-annuntiatio-domini, 0501-ioseph (Joseph the Worker, a title feast),
   0513-maria-de-fatima, 0531-visitatio-beatae-mariae-virginis,
   0716-maria-de-monte-carmelo, 0806-transfiguratio-domini,
   0815-assumptio-beatae-mariae-virginis, 0822-maria-regina,
   0908-nativitas-beatae-mariae-virginis, 0912-nomen-mariae,
   0914-exaltatio-sanctae-crucis, 0915-maria-perdolens, 0929-michael-et-socii,
   1002-angeli-custodes, 1007-maria-de-rosario, 1101-omnes-sancti,
   1121-praesentatio-beatae-mariae-virginis,
   1208-conceptio-immaculata-beatae-mariae-virginis, 1212-maria-de-guadalupe,
   1225-nativitas-domini. The dedications, translatio-trium-magorum,
   omnium-fidelium-defunctorum and avi-iesu-christi are deliberately left out:
   rule 4 gives them `dedicatio`, `translatio` and `commemoratio`.
4. **Marker in the lead.** The lead is the first 25 folded words, cut at the
   first relative pronoun (*qui, que, quod, quorum, quarum, cuius, quibus, quos,
   quas, quem, quam*) that follows an honorific, which starts the body. A relative
   pronoun before any honorific belongs to the place phrase ("via quae … dicitur"). The first marker word in the lead
   decides the value, unless it directly follows an honorific (*sancti, sancte,
   sanctorum, sanctarum, beati, beate, beatorum, beatarum, domini*). In that
   position it is a name, e.g. "beati natalis pinot". The marker words are
   *depositio(nis)*, *translatio(nis)*, *inventio(nis)*, *dedicatio(nis)*,
   *ordinatio(nis)* and *commemoratio*, each mapping to its own value, and
   *natalis*, *passio* and *transitus*, which map to `dies_natalis`. The
   genitive forms catch "festum dedicationis …" and "in die depositionis eius".
5. **Default → `dies_natalis`.** This is the unmarked 2004 convention
   ("Place, sancti N., title"), and about 84% of entries fall here.

A simulation of rule 4 alone on the 2004 Latin gives: default 4,023,
commemoratio 324, passio 88, transitus 86, depositio 73, natalis 34,
dedicatio 6, translatio 5. Entries that carry more than one marker word anywhere
in the text (48) all go into the report for hand review.

## Pipeline

```
martyrology-texts (LA 2004) ─┐
                             ├─> scripts/extract_typology.py ─> data/typology.json
data/martyrology_ids.json ───┘        (rules + TYPOLOGY_OVERRIDES)   docs/typology-report.md
                                                                        │
workbook ─> scripts/extract_registry.py  <── reads data/typology.json ──┘
               └─> data/martyrology_ids.json (+ "typology") , registry/MM-*.md (+ column)
```

- **`scripts/extract_typology.py`** (standard library only). Run it with
  `python3 scripts/extract_typology.py /path/to/martyrology-texts`. The
  classification is a pure function of (id, text, context), so it can be tested
  without the private texts.
- **`data/typology.json`**: `{"$comment": …, "values": [8 values], "typology":
  {id: value}}`. Keys are sorted, and there is exactly one key per current ID.
- **`docs/typology-report.md`**: counts per value; every tag that isn't
  `dies_natalis`, as ID → value → rule (`override`, `off-day`, `feast`,
  `marker:<word>`); the multi-marker entries; and any unresolved off-day
  cross-references. It holds IDs and marker words only, no elogium text.
- **`scripts/extract_registry.py`** reads `data/typology.json` (as it does
  `deprecated_ids.json`) and inserts `"typology"` after `"country"` in each
  current entry. Deprecated entries get no key. The registry Markdown tables get
  a `Typology` column between `Country` and `Notes`, and the header paragraph
  explains it.
- **Because the workbook isn't available here**, the same field and column are
  applied to `data/martyrology_ids.json` and `registry/*.md` by a one-off script.
  The result must match what `extract_registry.py` would generate.

## Invariants and tests

- `extract_typology.py` asserts: every current ID has exactly one value, and it is
  one of the 8; every `TYPOLOGY_OVERRIDES` key is a current ID; no deprecated ID
  is tagged.
- `extract_registry.py` asserts that the keys in `typology.json` are exactly the
  current IDs.
- `tests/test_typology.py` (standard-library `unittest`, run with
  `python3 -m unittest discover tests`) covers each rule and the precedence
  between them, using short made-up Latin phrases, never elogium text:
  - an unmarked phrase → `dies_natalis`
  - *depositio* in the opening clause → `depositio`
  - a later "cuius memoria" is ignored
  - an off-day memorial is detected from a cross-reference
  - `FEAST_IDS` → `celebratio`
  - an override beats a marker
- **Review against the real data.** Every tag that isn't `dies_natalis` and every
  multi-marker entry in the report is checked against the Latin. Each
  misclassification becomes an override (with a comment) or a rule fix.

## Documentation

- `docs/canonicalization-report.md`: a new "Typology" section with the value
  definitions and rule order.
- `README.md` (Repository contents) and `AGENTS.md` (pipeline, correction maps):
  mention the field, `data/typology.json`, `extract_typology.py`, and
  `TYPOLOGY_OVERRIDES`.
