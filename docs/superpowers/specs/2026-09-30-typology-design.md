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
accent-folding and lowercasing (æ→ae, œ→oe), using the same folding as
`extract_subjects.py`. The first rule that matches wins:

1. **Override.** `TYPOLOGY_OVERRIDES[id]`, one line per ID with a comment giving
   the reason.
2. **Off-day memorial → `celebratio`.** The elogium opens with
   *memoria / festum / sollemnitas*, and another 2004 elogium of the same subject
   says *cuius / eius / quorum / earum memoria* with a date expression (*cras*,
   *postridie*, *pridie*, *die N mensis*) that resolves to this entry's date.
   Subjects are matched on `i18n/la.json`. If the date expression can't be
   resolved, the entry is listed in the report and not auto-tagged by this rule.
3. **Feast of a mystery or object → `celebratio`.** The entry is in `FEAST_IDS`:
   entries whose object is a mystery of the Lord, a Marian feast or title, the
   angels, or another celebration that isn't a person's life event. The list is
   explicit, one ID per line, and is built during implementation by reviewing
   (a) the 99 elogia that open with *memoria / festum / sollemnitas* and
   (b) the Marian-title and angel entries that don't open that way. Known members
   include the celebrations among the manual feast overrides in
   `docs/canonicalization-report.md` (e.g. epiphania-domini,
   cathedra-sancti-petri, transfiguratio-domini,
   assumptio-beatae-mariae-virginis, exaltatio-sanctae-crucis, angeli-custodes,
   omnes-sancti, nativitas-domini) and entries such as 0211-maria-de-lourdes,
   0513-maria-de-fatima, 0716-maria-de-monte-carmelo, 1007-maria-de-rosario and
   0929-michael-et-socii (the archangels). It excludes persons, the dedications
   (rule 4 → `dedicatio`), translatio-trium-magorum (rule 4 → `translatio`),
   omnium-fidelium-defunctorum and avi-iesu-christi (→ `commemoratio`).
4. **Marker in the opening clause.** The opening clause is the text before the
   subject's name: the text before the first *sancti / sanctae / sanctorum /
   beati / beatae / beatorum / domini / beatae mariae*, or the first sentence
   when there is no such word. A marker there
   decides the value: *depositio*, *translatio*, *inventio*, *dedicatio*,
   *ordinatio* and *commemoratio* map to their own values, and *natalis*,
   *passio* and *transitus* → `dies_natalis`. Markers later in the text (e.g.
   "cuius memoria … agitur") never count.
5. **Default → `dies_natalis`.** This is the unmarked 2004 convention
   ("Place, sancti N., title"), and about 84% of entries fall here.

A survey of the 2004 Latin gives the expected marker counts: commemoratio 325,
memoria 116, transitus 90, passio 90, depositio 78, natalis 40, festum 25,
sollemnitas 9, translatio 5, dedicatio 4. 48 entries carry more than one marker,
and all of them go into the report for hand review.

## Pipeline

```
martyrology-texts (LA 2004) ─┐
i18n/la.json ────────────────┼─> scripts/extract_typology.py ─> data/typology.json
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
