# Gazetteer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve each distinct place designation in `data/places.json` once to a Wikidata item, a modern label and a modern country (`data/gazetteer.json`), auto-accepting only on strong evidence and sending the rest to a `crmedr-changeset/v1` review queue (`data/gazetteer_review.json`) for martyrology-frontend.

**Architecture:** Three new modules under `scripts/`:
- `gazetteer_text.py`: pure parsing of the Italian and Latin phrases (head toponyms, regions, modern-country claims, Latin nominatives), backed by a generated `countries_it.py` table.
- `wikidata.py`: a cached, retrying Wikidata client that turns search hits into summarized candidates (Italian names, Latin names, P9314, current countries as ISO codes, place type).
- `build_gazetteer.py`: the evidence bar, `propose`, `verify-suggestions`, `apply`, `check`, the report and validation.

The evidence bar and every decision path are pure functions tested against a fake client, so no test touches the network.

**Tech Stack:** Python 3 standard library only (`urllib`, `json`, `hashlib`, `unittest`, `unittest.mock`).

**Spec:** `docs/superpowers/specs/2026-10-01-gazetteer-design.md` (builds on `docs/superpowers/specs/2026-09-30-places-extraction-design.md` and `docs/superpowers/specs/2026-09-30-places-italian-design.md`).

## Global Constraints

- Gazetteer key: the exact printed `la`. Entry key order: `wikidata`, `label`, `country`, `status`, `text_says`, `note`. Keys sorted. Statuses: `auto`, `reviewed`, `unresolved`.
- `wikidata` matches `^Q[1-9]\d*$`, or is `null` exactly when `status` is `unresolved`; `unresolved` has a `note` and no `label`/`country`.
- `country` is an ISO 3166-1 alpha-2 code from the generated table. No workbook conventions (no `PS`-for-Holy-Land) in the gazetteer.
- Places awaiting review have **no key** in `gazetteer.json`; `propose` never modifies or removes an existing key.
- `text_says` is a list of `{"country", "it"}`; each `it` is verbatim one of that place's Italian phrases, and its `country` differs from the entry's `country`.
- Change-set: `{"schema": "crmedr-changeset/v1", "generated_by", "generated_at", "base": {"edition": "2004", "registry": "data/places.json"}, "operations": [...]}`; ops have `"op": "resolve_place"` and `"id"` equal to `la`.
- Network: User-Agent `crmedr-gazetteer/1.0 (https://github.com/CatholicOS/crmedr)`, `maxlag=5` on API calls, retry 429/5xx/maxlag with backoff, cache under `.cache/wikidata/` (git-ignored).
- No elogium text beyond place designations in any committed file. Tests use made-up place names (*Fictopoli*, *Fictia*…); the 5-word overlap scan must find no match against the real texts.
- Standard library only. Test command (repo root): `python3 -m unittest discover -s tests -v`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A place whose Italian variants disagree** (one variant is a narrative fragment such as "All’ancora in mare davanti a Fictopoli"). Expected: it goes to review with "no item has the Italian name of every variant", and is never auto. Pinned in Task 3.
2. **A Wikidata item with ended and preferred P17 statements** (London has 7 ended countries and one preferred). Expected: only the preferred, unended statement counts, giving a single country. Pinned in Task 2.
3. **The network fails halfway through `propose`.** Expected: the places processed so far are written, the failed place is reported as not processed, and nothing is written as `auto` or `unresolved` for it. Pinned in Task 4.
4. **An exported change-set with one bad decision among good ones** (reject without a reason, or accept with no country). Expected: `apply` writes nothing and lists every error. Pinned in Task 5.
5. **A reviewer edits the QID to a different item while a suggestion with `text_says` exists.** Expected: the suggestion's `country` and `text_says` do not carry over to the other item. Pinned in Task 5.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/countries_it.py` (create, generated) | `COUNTRY_IT`: Italian country name → ISO code |
| `scripts/gazetteer_text.py` (create) | `fold`, `parse_italian`, `latin_nominatives`, `ISO_CODES` |
| `scripts/wikidata.py` (create) | `http_get`, `current_country_qids`, `summarize`, `Wikidata` client |
| `scripts/build_gazetteer.py` (create) | Index, evidence bar, validation, JSON/report rendering, `propose`, `verify-suggestions`, `apply`, `check`, CLI |
| `tests/test_gazetteer.py` (create) | All tests for the above |
| `.gitignore` (modify) | `.cache/` |
| `data/gazetteer.json`, `data/gazetteer_review.json`, `docs/gazetteer-report.md` (generated) | Output |
| `AGENTS.md`, `README.md`, `docs/canonicalization-report.md` (modify) | Docs |

Not in this plan (follow-ups named in the spec's Rollout): writing the suggestions (Claude, in batches, then `verify-suggestions`), the martyrology-frontend `resolve_place` card (other repo), and the review rounds (`apply`).

---

### Task 1: Phrase parsing (`gazetteer_text.py`) and the country table

**Files:**
- Create: `scripts/countries_it.py` (generated by the snippet in Step 1), `scripts/gazetteer_text.py`
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Produces:
  - `countries_it.COUNTRY_IT: dict[str, str]` — Italian country label (as written) → ISO alpha-2.
  - `gazetteer_text.fold(s: str) -> str` — lowercase, accents stripped, æ→ae, œ→oe, ’→', whitespace collapsed.
  - `gazetteer_text.ISO_CODES: frozenset[str]`
  - `gazetteer_text.country_of(name: str) -> str | None` — ISO code of an Italian country name.
  - `gazetteer_text.parse_italian(it: str) -> dict` with keys `heads: list[str]`, `regions: list[str]`, `claims: list[str]` (ISO codes), each de-duplicated in order.
  - `gazetteer_text.latin_nominatives(la: str) -> set[str]` — folded candidate nominatives of the capitalized words.

- [ ] **Step 1: Generate the country table**

Run this once from the repo root (it needs the network). It writes `scripts/countries_it.py`.

```bash
python3 - <<'EOF'
import json, urllib.parse, urllib.request
q = 'SELECT ?iso ?it WHERE { ?c wdt:P297 ?iso . ?c rdfs:label ?it FILTER(lang(?it)="it") }'
url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
req = urllib.request.Request(url, headers={"User-Agent": "crmedr-gazetteer/1.0 (https://github.com/CatholicOS/crmedr)"})
rows = json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]
table = {r["it"]["value"]: r["iso"]["value"] for r in rows if len(r["iso"]["value"]) == 2}
# Forms the CEI edition uses that are not the Wikidata label.
table.update({"Viet Nam": "VN", "Stati Uniti d’America": "US", "Repubblica Ceca": "CZ",
              "Città del Vaticano": "VA", "Paesi Bassi": "NL", "Olanda": "NL",
              "Russia": "RU", "Bielorussia": "BY", "Gran Bretagna": "GB", "Regno Unito": "GB"})
lines = ['"""Italian country names -> ISO 3166-1 alpha-2. Generated from Wikidata',
         "(items with P297 and their Italian label), plus the forms the CEI edition",
         'uses; see docs/superpowers/plans/2026-10-01-gazetteer.md, Task 1."""', "",
         "COUNTRY_IT = {"]
lines += [f"    {json.dumps(k, ensure_ascii=False)}: {json.dumps(v)}," for k, v in sorted(table.items())]
lines += ["}", ""]
open("scripts/countries_it.py", "w", encoding="utf-8").write("\n".join(lines))
print(len(table), "names")
EOF
```

Expected: about 260 names. Check that `"Francia": "FR"`, `"Germania": "DE"`, `"Svizzera": "CH"` and `"Spagna": "ES"` are present, and that `"Inghilterra"` is **absent** (it is a region of GB and must be treated as one). Remove it if the query returned it.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_gazetteer.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gazetteer_text as gt  # noqa: E402


class FoldTest(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(gt.fold("  Fictópoli  Ǽquæ  Nell’ "), "fictopoli aequae nell'")

    def test_country_of(self):
        self.assertEqual(gt.country_of("Francia"), "FR")
        self.assertEqual(gt.country_of("viet nam"), "VN")
        self.assertIsNone(gt.country_of("Fictia"))
        self.assertIn("DE", gt.ISO_CODES)


class ParseItalianTest(unittest.TestCase):
    def test_plain_place_and_region(self):
        p = gt.parse_italian("A Fictopoli in Fictia")
        self.assertEqual(p, {"heads": ["Fictopoli"], "regions": ["Fictia"], "claims": []})

    def test_elided_lead_and_modern_claim(self):
        p = gt.parse_italian("Presso Fictopoli nel Fictiense, nell’odierna Germania")
        self.assertEqual(p["heads"], ["Fictopoli"])
        self.assertEqual(p["regions"], ["Fictiense"])
        self.assertEqual(p["claims"], ["DE"])

    def test_claim_forms(self):
        for it in ("A Fictopoli in Fictia, ora in Francia", "A Fictopoli sempre in Francia",
                   "A Fictopoli ancora in Francia", "A Fictopoli nel territorio dell’odierna Francia",
                   "A Fictopoli in Fictia, in Francia", "A Fictopoli nell’attuale Francia"):
            self.assertEqual(gt.parse_italian(it)["claims"], ["FR"], it)
        self.assertEqual(gt.parse_italian("Presso Fictopoli nel Fictiense, nell’odierno Belgio")["claims"], ["BE"])
        self.assertEqual(gt.parse_italian("A Fictopoli nel Fictiense, ora Viet Nam")["claims"], ["VN"])

    def test_site_heads(self):
        self.assertEqual(gt.parse_italian("Nel monastero di Fictiaco in Fictia")["heads"],
                         ["monastero di Fictiaco", "Fictiaco"])
        self.assertEqual(gt.parse_italian("Nell’isola di Fictosa nel Mare Fictum")["heads"],
                         ["isola di Fictosa", "Fictosa"])
        self.assertEqual(gt.parse_italian("In località Fictana in Fictia")["heads"],
                         ["località Fictana", "Fictana"])
        self.assertEqual(
            gt.parse_italian("Nel monastero delle monache fittizie di Fictiaco in Fictia")["heads"],
            ["monastero delle monache fittizie di Fictiaco", "Fictiaco"])

    def test_multiword_head_kept(self):
        self.assertEqual(gt.parse_italian("A Fictopoli di Fictaria in Fictia")["heads"],
                         ["Fictopoli di Fictaria"])

    def test_lowercase_head_dropped_and_lowercase_region_ignored(self):
        p = gt.parse_italian("All’ancora in mare davanti a Fictopoli sulla costa fittizia")
        self.assertEqual(p["heads"], [])
        self.assertEqual(p["regions"], [])

    def test_vicino_a_is_a_connector_and_a_lead(self):
        p = gt.parse_italian("Vicino a Fictopoli presso Fictaria in Fictia")
        self.assertEqual(p["heads"], ["Fictopoli"])
        self.assertEqual(p["regions"], ["Fictaria", "Fictia"])


class LatinNominativesTest(unittest.TestCase):
    def test_endings(self):
        self.assertIn("fictinium", gt.latin_nominatives("Fictínii in Fíctia"))
        self.assertIn("fictopolis", gt.latin_nominatives("Fictópoli"))
        self.assertIn("ficta", gt.latin_nominatives("Fictæ in Fíctia"))
        self.assertIn("fictanum", gt.latin_nominatives("Fictáni"))
        self.assertIn("fictago", gt.latin_nominatives("Fictágine"))
        self.assertIn("fictii", gt.latin_nominatives("Fictiis"))

    def test_skips_lowercase_and_lead_words(self):
        noms = gt.latin_nominatives("In monastério Fictiacénsi")
        self.assertNotIn("in", noms)
        self.assertNotIn("monasterium", noms)
        self.assertIn("fictiacensis", noms)
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'gazetteer_text'`

- [ ] **Step 4: Implement `scripts/gazetteer_text.py`**

```python
"""Parse the place phrases of data/places.json for the gazetteer.

Pure functions, standard library only: the Italian head toponyms, regions and
modern-country claims of an Italian (CEI) place phrase, and the candidate
nominatives of a Latin one. See docs/superpowers/specs/2026-10-01-gazetteer-design.md.
"""

import re
import unicodedata

from countries_it import COUNTRY_IT


def fold(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    return " ".join(s.lower().split())


_COUNTRY = {fold(k): v for k, v in COUNTRY_IT.items()}
ISO_CODES = frozenset(COUNTRY_IT.values())


def country_of(name):
    return _COUNTRY.get(fold(name))


# The preposition that opens an Italian place phrase ("A", "Presso", "Nell’").
LEAD_IT = re.compile(
    r"^(?:(?:nei pressi di|vicino al|vicino alla|vicino a|presso|nella|nelle|nello|negli|nel|nei"
    r"|sulla|sulle|sul|sui|alla|al|ad|a|in|da)\s+|(?:nei pressi d|vicino all|nell|sull|all)')",
    re.IGNORECASE)
# Where the head toponym ends and a region or modern-country note begins.
CONNECTOR_IT = re.compile(
    r",|\s(?:in|nel|nella|nelle|nello|nei|negli|presso|vicino a|vicino al|vicino alla|sul|sulla|sulle"
    r"|sui|sempre|ancora|ora|oggi|lungo|tra|fra|nei pressi di)(?=\s)|\s(?:nell|sull|all)'")
# A site noun before the proper name ("monastero di X", "località X").
SITE_IT = re.compile(
    r"^(?:localit[àa]\s+|(?:citt[àa]|cittadina|territorio|isola|monastero|eremo|abbazia|villaggio"
    r"|fortezza|regione|diocesi|castello|borgo|villa|contrada|frazione)\b[^,]*?\s"
    r"(?:di\s+|del\s+|della\s+|dell'|d'))(?=[A-ZÀ-ÖØ-Þ])")
# Words before the name in a region or modern-country segment.
SEGMENT_PREFIX_IT = re.compile(
    r"^(?:(?:il|lo|la|i|gli|le)\s+|l')?(?:(?:territorio|regione)\s+(?:di\s+|del\s+|della\s+|dell'|d'))?"
    r"(?:(?:odiern[oa]|attuale)\s+)?")


def _dedupe(xs):
    return list(dict.fromkeys(x for x in xs if x))


def parse_italian(it):
    s = it.replace("’", "'").strip()
    m = LEAD_IT.match(s)
    if m:
        s = s[m.end():]
    cuts = list(CONNECTOR_IT.finditer(s))
    head = (s[:cuts[0].start()] if cuts else s).strip(" ,")
    heads = []
    if head:
        site_text = head[0].lower() + head[1:]
        site = SITE_IT.match(site_text)
        if site:
            heads = [site_text, site_text[site.end():].strip()]
        elif head[0].isupper():
            heads = [head]
    regions, claims = [], []
    for i, cut in enumerate(cuts):
        end = cuts[i + 1].start() if i + 1 < len(cuts) else len(s)
        seg = s[cut.end():end].strip(" ,")
        seg = seg[SEGMENT_PREFIX_IT.match(seg).end():].strip()
        if not seg:
            continue
        iso = country_of(seg)
        if iso:
            claims.append(iso)
        elif seg[0].isupper():
            regions.append(seg)
    return {"heads": _dedupe(h.replace("'", "’") for h in heads),
            "regions": _dedupe(r.replace("'", "’") for r in regions),
            "claims": _dedupe(claims)}


LEAD_LA = {"in", "ad", "apud", "prope", "iuxta", "item", "ibidem", "inter", "sub", "super", "circa"}
WORD_LA = re.compile(r"[^\W\d_]+")
# Ending of a locative or ablative -> endings of the nominatives it may come from.
# This only adds evidence, so a missing form sends the place to review.
LATIN_ENDINGS = [
    ("ibus", ("es", "a")), ("ine", ("o",)), ("one", ("o",)), ("ae", ("a", "ae")),
    ("ii", ("ium", "ius", "ii")), ("is", ("a", "ae", "i", "is", "um", "us")),
    ("i", ("um", "us", "ium", "i", "is", "a")), ("o", ("um", "us", "o", "a")),
    ("e", ("is", "e", "es")), ("a", ("a",)),
]


def latin_nominatives(la):
    out = set()
    for word in WORD_LA.findall(la):
        if not word[0].isupper():
            continue
        w = fold(word)
        if w in LEAD_LA:
            continue
        out.add(w)
        for ending, noms in LATIN_ENDINGS:
            if w.endswith(ending) and len(w) > len(ending) + 1:
                stem = w[: -len(ending)]
                out.update(stem + n for n in noms)
    return out
```

Note on `test_skips_lowercase_and_lead_words`: "monastério" is lowercase, so it is skipped; "Fictiacénsi" folds to `fictiacensi`, and the `i` ending gives `fictiacensis`.

- [ ] **Step 5: Run the tests to check they pass**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: all PASS. If `test_claim_forms` fails for "sempre in Francia", check that `CONNECTOR_IT` matches `\ssempre` (lookahead space) and then `\sin`, leaving the segment "Francia".

- [ ] **Step 6: Commit**

```bash
git add scripts/countries_it.py scripts/gazetteer_text.py tests/test_gazetteer.py
git commit -m "feat: parse Italian and Latin place phrases for the gazetteer (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Wikidata client (`wikidata.py`)

**Files:**
- Create: `scripts/wikidata.py`
- Modify: `.gitignore` (add `.cache/`)
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Consumes: `gazetteer_text.fold`.
- Produces:
  - `wikidata.WikidataError(Exception)`
  - `wikidata.http_get(url: str, retries: int = 6, sleep=time.sleep) -> dict`
  - `wikidata.current_country_qids(claims: dict) -> list[str]`
  - `wikidata.summarize(raw: dict) -> dict` with keys `wikidata, label, description, names_it (sorted folded), la (sorted, as printed in Wikidata), p9314 (bool), country_qids, iso_self (str|None), coords ([lat, lon]|None), types (P31 QIDs)`.
  - `wikidata.Wikidata(cache_dir: Path, fetch=http_get)` with:
    - `candidates(text: str) -> list[dict]`: the search hits for `text` in Italian, summarized and **enriched**: adds `countries: list[str]` (ISO codes, or the country QID when it has no P297), `country: str|None` (the single ISO code, else `None`) and `place_type: bool`.
    - `candidate(qid: str) -> dict | None`: one enriched candidate, or `None` if the item does not exist.
    - `region_countries(text: str) -> set[str]`: ISO codes of the items named exactly `text` in Italian (the item's own P297 if it is a country, plus its current countries).
  - `wikidata.PLACE_ROOTS: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gazetteer.py`:

```python
import io  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402
import urllib.error  # noqa: E402
from unittest import mock  # noqa: E402

import wikidata as wd  # noqa: E402


def snak(pid, value, rank="normal", qualifiers=None):
    if isinstance(value, str) and value.startswith("Q"):
        value = {"entity-type": "item", "id": value}
    return {"mainsnak": {"property": pid, "datavalue": {"value": value}}, "rank": rank,
            "qualifiers": qualifiers or {}}


def raw_entity(qid, it=(), la=(), en=None, p17=(), p31=("Q486972",), p297=None, p9314=None, coords=None):
    claims = {"P17": list(p17), "P31": [snak("P31", c) for c in p31]}
    if p297:
        claims["P297"] = [snak("P297", p297)]
    if p9314:
        claims["P9314"] = [snak("P9314", p9314)]
    if coords:
        claims["P625"] = [snak("P625", {"latitude": coords[0], "longitude": coords[1]})]
    labels, aliases = {}, {}
    for lang, names in (("it", it), ("la", la)):
        if names:
            labels[lang] = {"value": names[0]}
            aliases[lang] = [{"value": n} for n in names[1:]]
    if en:
        labels["en"] = {"value": en}
    return {"id": qid, "labels": labels, "aliases": aliases, "descriptions": {}, "claims": claims}


class CurrentCountryTest(unittest.TestCase):
    def test_ended_and_deprecated_excluded_preferred_wins(self):
        claims = {"P17": [
            snak("P17", "Q10", qualifiers={"P582": [{}]}),
            snak("P17", "Q11", rank="deprecated"),
            snak("P17", "Q12"),
            snak("P17", "Q13", rank="preferred", qualifiers={"P580": [{}]}),
        ]}
        self.assertEqual(wd.current_country_qids(claims), ["Q13"])

    def test_several_normal_kept(self):
        claims = {"P17": [snak("P17", "Q12"), snak("P17", "Q14")]}
        self.assertEqual(wd.current_country_qids(claims), ["Q12", "Q14"])

    def test_no_p17(self):
        self.assertEqual(wd.current_country_qids({}), [])


class SummarizeTest(unittest.TestCase):
    def test_summarize(self):
        raw = raw_entity("Q1", it=("Fictopoli", "Fictòpoli"), la=("Fictopolis",), en="Fictopolis",
                         p17=[snak("P17", "Q100")], p9314="f/fictopoli", coords=(1.5, 2.5))
        s = wd.summarize(raw)
        self.assertEqual(s["wikidata"], "Q1")
        self.assertEqual(s["label"], "Fictopolis")
        self.assertEqual(s["names_it"], ["fictopoli"])
        self.assertEqual(s["la"], ["Fictopolis"])
        self.assertTrue(s["p9314"])
        self.assertEqual(s["country_qids"], ["Q100"])
        self.assertIsNone(s["iso_self"])
        self.assertEqual(s["coords"], [1.5, 2.5])
        self.assertEqual(s["types"], ["Q486972"])

    def test_label_falls_back_to_italian(self):
        self.assertEqual(wd.summarize(raw_entity("Q2", it=("Fictaria",)))["label"], "Fictaria")


class FakeFetch:
    """Answers wbsearchentities, wbgetentities and the SPARQL place-type query."""

    def __init__(self, entities, searches, place_classes=("Q486972",)):
        self.entities, self.searches, self.place_classes = entities, searches, set(place_classes)
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(url).query)
        if "query" in q:
            found = [c for c in self.place_classes if f"wd:{c} " in q["query"][0]]
            return {"results": {"bindings": [{"c": {"value": "http://www.wikidata.org/entity/" + c}}
                                              for c in found]}}
        if q["action"] == ["wbsearchentities"]:
            return {"search": [{"id": i} for i in self.searches.get(q["search"][0], [])]}
        ids = q["ids"][0].split("|")
        return {"entities": {i: self.entities.get(i, {"id": i, "missing": ""}) for i in ids}}


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        entities = {
            "Q1": raw_entity("Q1", it=("Fictopoli",), p17=[snak("P17", "Q100")]),
            "Q2": raw_entity("Q2", it=("Fictopoli",), p17=[snak("P17", "Q100")], p31=("Q3914",)),
            "Q3": raw_entity("Q3", it=("Fictia",), p17=[snak("P17", "Q100")], p31=("Q82794",)),
            "Q100": raw_entity("Q100", it=("Fictistan",), p297="FX", p31=("Q6256",)),
        }
        self.fetch = FakeFetch(entities, {"Fictopoli": ["Q1", "Q2"], "Fictia": ["Q3"], "Fictistan": ["Q100"]},
                               place_classes=("Q486972", "Q82794", "Q6256"))
        self.client = wd.Wikidata(Path(self.tmp.name), fetch=self.fetch)

    def test_candidates_enriched(self):
        cands = self.client.candidates("Fictopoli")
        self.assertEqual([c["wikidata"] for c in cands], ["Q1", "Q2"])
        self.assertEqual(cands[0]["country"], "FX")
        self.assertEqual(cands[0]["countries"], ["FX"])
        self.assertTrue(cands[0]["place_type"])
        self.assertFalse(cands[1]["place_type"])

    def test_cache_avoids_refetch(self):
        self.client.candidates("Fictopoli")
        n = len(self.fetch.calls)
        again = wd.Wikidata(Path(self.tmp.name), fetch=self.fetch)
        again.candidates("Fictopoli")
        self.assertEqual(len(self.fetch.calls), n)

    def test_region_countries(self):
        self.assertEqual(self.client.region_countries("Fictia"), {"FX"})
        self.assertEqual(self.client.region_countries("Fictistan"), {"FX"})
        self.assertEqual(self.client.region_countries("Nowhere"), set())

    def test_candidate_missing(self):
        self.assertIsNone(self.client.candidate("Q999"))
        self.assertEqual(self.client.candidate("Q1")["country"], "FX")


class HttpGetTest(unittest.TestCase):
    def test_retries_429_then_succeeds(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value = io.BytesIO(json.dumps({"x": 1}).encode())
        err = urllib.error.HTTPError("u", 429, "slow down", {"Retry-After": "1"}, None)
        sleeps = []
        with mock.patch("wikidata.urllib.request.urlopen", side_effect=[err, ok]):
            self.assertEqual(wd.http_get("https://example/u", sleep=sleeps.append), {"x": 1})
        self.assertEqual(sleeps, [1])

    def test_maxlag_retried_and_other_errors_raise(self):
        lag = mock.MagicMock()
        lag.__enter__.return_value = io.BytesIO(json.dumps({"error": {"code": "maxlag"}}).encode())
        bad = mock.MagicMock()
        bad.__enter__.return_value = io.BytesIO(json.dumps({"error": {"code": "badvalue"}}).encode())
        with mock.patch("wikidata.urllib.request.urlopen", side_effect=[lag, bad]):
            with self.assertRaises(wd.WikidataError):
                wd.http_get("https://example/u", sleep=lambda s: None)

    def test_gives_up(self):
        err = urllib.error.HTTPError("u", 503, "down", {}, None)
        with mock.patch("wikidata.urllib.request.urlopen", side_effect=[err] * 3):
            with self.assertRaises(wd.WikidataError):
                wd.http_get("https://example/u", retries=3, sleep=lambda s: None)
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'wikidata'`

- [ ] **Step 3: Implement `scripts/wikidata.py`**

```python
"""A small cached Wikidata client for the gazetteer (standard library only).

Search hits are summarized into candidates: Italian names (folded), Latin
labels and aliases, P9314 (Latin Place Names ID), current countries as ISO
codes, coordinates, and whether the item is a place (P31 through P279* to one
of PLACE_ROOTS). Responses are cached on disk, one file per request URL.
See docs/superpowers/specs/2026-10-01-gazetteer-design.md.
"""

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from gazetteer_text import fold

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "crmedr-gazetteer/1.0 (https://github.com/CatholicOS/crmedr)"
# human settlement, administrative territorial entity, monastery, church building,
# archaeological site, island, mountain, region, historical region, historical
# country, cave, castle, country
PLACE_ROOTS = ("Q486972", "Q56061", "Q44613", "Q16970", "Q839954", "Q23442", "Q8502",
               "Q82794", "Q1620908", "Q3024240", "Q35509", "Q23413", "Q6256")
RETRY_CODES = {429, 500, 502, 503, 504}


class WikidataError(Exception):
    pass


def http_get(url, retries=6, sleep=time.sleep):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES:
                raise WikidataError(f"HTTP {e.code} for {url}") from e
            sleep(int((e.headers or {}).get("Retry-After") or 2 ** attempt))
            continue
        except (urllib.error.URLError, TimeoutError):
            sleep(2 ** attempt)
            continue
        if isinstance(data, dict) and "error" in data:
            if data["error"].get("code") == "maxlag":
                sleep(5)
                continue
            raise WikidataError(f"{data['error'].get('code')} for {url}")
        return data
    raise WikidataError(f"gave up after {retries} attempts: {url}")


def _value(claim):
    return claim.get("mainsnak", {}).get("datavalue", {}).get("value")


def current_country_qids(claims):
    current = [c for c in claims.get("P17", [])
               if c.get("rank") != "deprecated" and "P582" not in c.get("qualifiers", {})
               and isinstance(_value(c), dict)]
    preferred = [c for c in current if c.get("rank") == "preferred"]
    return list(dict.fromkeys(_value(c)["id"] for c in (preferred or current)))


def _names(raw, lang):
    out = []
    if lang in raw.get("labels", {}):
        out.append(raw["labels"][lang]["value"])
    out += [a["value"] for a in raw.get("aliases", {}).get(lang, [])]
    return out


def summarize(raw):
    claims = raw.get("claims", {})
    labels = raw.get("labels", {})
    label = next((labels[lang]["value"] for lang in ("en", "it", "la") if lang in labels), raw["id"])
    descs = raw.get("descriptions", {})
    p297 = [_value(c) for c in claims.get("P297", []) if c.get("rank") != "deprecated"]
    coords = next((_value(c) for c in claims.get("P625", []) if isinstance(_value(c), dict)), None)
    return {
        "wikidata": raw["id"],
        "label": label,
        "description": next((descs[lang]["value"] for lang in ("it", "en") if lang in descs), ""),
        "names_it": sorted({fold(n) for n in _names(raw, "it")}),
        "la": sorted(set(_names(raw, "la"))),
        "p9314": bool(claims.get("P9314")),
        "country_qids": current_country_qids(claims),
        "iso_self": p297[0] if p297 else None,
        "coords": [coords["latitude"], coords["longitude"]] if coords else None,
        "types": list(dict.fromkeys(_value(c)["id"] for c in claims.get("P31", [])
                                    if isinstance(_value(c), dict))),
    }


class Wikidata:
    def __init__(self, cache_dir, fetch=http_get):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._types_path = cache_dir / "place_types.json"
        self._types = (json.loads(self._types_path.read_text(encoding="utf-8"))
                       if self._types_path.exists() else {})

    def _get(self, url):
        path = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.fetch(url)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def _api(self, **params):
        params.update(format="json", maxlag="5")
        return self._get(API + "?" + urllib.parse.urlencode(params))

    def _search(self, text, limit=10):
        data = self._api(action="wbsearchentities", search=text, language="it", uselang="it",
                         type="item", limit=str(limit))
        return [x["id"] for x in data.get("search", [])]

    def _entities(self, qids):
        out = {}
        for i in range(0, len(qids), 50):
            data = self._api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                             props="labels|aliases|descriptions|claims", languages="it|la|en")
            for qid, raw in data.get("entities", {}).items():
                if "missing" not in raw:
                    out[qid] = raw
        return out

    def _place_types(self, classes):
        unknown = sorted(set(classes) - set(self._types))
        if unknown:
            roots = " ".join("wd:" + r for r in PLACE_ROOTS)
            values = " ".join("wd:" + c + " " for c in unknown)
            query = (f"SELECT DISTINCT ?c WHERE {{ VALUES ?c {{ {values}}} "
                     f"?c wdt:P279* ?r . VALUES ?r {{ {roots} }} }}")
            data = self._get(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
            found = {b["c"]["value"].rsplit("/", 1)[1] for b in data["results"]["bindings"]}
            self._types.update({c: c in found for c in unknown})
            self._types_path.write_text(json.dumps(self._types, sort_keys=True), encoding="utf-8")
        return {c for c in classes if self._types[c]}

    def _enrich(self, summaries):
        qids = sorted({q for s in summaries for q in s["country_qids"]})
        countries = {q: summarize(raw)["iso_self"] for q, raw in self._entities(qids).items()}
        places = self._place_types([t for s in summaries for t in s["types"]])
        for s in summaries:
            s["countries"] = [countries.get(q) or q for q in s["country_qids"]]
            s["country"] = s["countries"][0] if len(s["countries"]) == 1 and countries.get(
                s["country_qids"][0]) else None
            s["place_type"] = any(t in places for t in s["types"])
        return summaries

    def candidates(self, text):
        qids = self._search(text)
        raws = self._entities(qids)
        return self._enrich([summarize(raws[q]) for q in qids if q in raws])

    def candidate(self, qid):
        raw = self._entities([qid]).get(qid)
        return self._enrich([summarize(raw)])[0] if raw else None

    def region_countries(self, text):
        name = fold(text)
        out = set()
        for c in self.candidates(text):
            if name in c["names_it"]:
                if c["iso_self"]:
                    out.add(c["iso_self"])
                out.update(x for x in c["countries"] if len(x) == 2)
        return out
```

Note: `FakeFetch` answers the SPARQL query by checking `f"wd:{c} "` in the query, which is why `values` puts a space after each class.

- [ ] **Step 4: Add `.cache/` to `.gitignore`**

```bash
printf '.cache/\n' >> .gitignore
```

- [ ] **Step 5: Run the tests to check they pass**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/wikidata.py tests/test_gazetteer.py .gitignore
git commit -m "feat: cached Wikidata client for the gazetteer (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Place index, evidence bar, validation and rendering

**Files:**
- Create: `scripts/build_gazetteer.py`
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Consumes: `gazetteer_text.fold`, `parse_italian`, `latin_nominatives`, `ISO_CODES`; enriched candidate dicts as produced by `Wikidata.candidates` (Task 2).
- Produces:
  - `STATUSES`, `ENTRY_KEYS`, `QID`, `SCHEMA = "crmedr-changeset/v1"`, `MAX_CANDIDATES = 10`
  - `place_index(places: dict, entries: list) -> dict[str, dict]` — `la` → `{"it": [sorted distinct], "occurrences": [sorted IDs], "lead_countries": {id: registry country}}`; `places` is the `"places"` object of `data/places.json`, `entries` the registry entries.
  - `evaluate(la: str, item: dict, candidates: list[dict], region_countries) -> dict` — `{"auto": candidate|None, "candidates": [published candidates], "failed": [str], "claims": [{"country", "it"}]}`; `region_countries` is a `str -> set[str]` callable.
  - `published(candidate: dict, evidence: list[str]) -> dict` — the op's candidate shape.
  - `auto_entry(candidate: dict) -> dict`
  - `validate(gazetteer: dict, index: dict, review_ops: list = ()) -> list[str]` — error messages.
  - `render_json(gazetteer: dict) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gazetteer.py`:

```python
import build_gazetteer as bg  # noqa: E402


def cand(qid, it=(), la=(), country="FX", countries=None, place=True, p9314=False, label=None):
    return {"wikidata": qid, "label": label or qid, "description": "", "names_it": sorted(gt.fold(x) for x in it),
            "la": list(la), "p9314": p9314, "country_qids": [], "iso_self": None,
            "country": country, "countries": countries if countries is not None else ([country] if country else []),
            "coords": None, "types": ["Q486972"], "place_type": place}


def item(*its, occ=("mr:0101-fictus",)):
    return {"it": list(its), "occurrences": list(occ), "lead_countries": {}}


REGIONS = {"Fictia": {"FX"}, "Fictiense": {"FX"}, "Altrofictia": {"FY"}}


def regions(text):
    return REGIONS.get(text, set())


class PlaceIndexTest(unittest.TestCase):
    def test_index(self):
        places = {
            "mr:0102-b": [{"role": "death", "la": "Fictópoli", "it": "A Fictopoli", "source": "lead"}],
            "mr:0101-a": [{"role": "death", "la": "Fictópoli", "it": "A Fictopoli in Fictia", "source": "lead"},
                          {"role": "birth", "la": "in Fíctia", "source": "curated"}],
        }
        entries = [{"id": "mr:0101-a", "country": "FX"}, {"id": "mr:0102-b", "country": "FY"}]
        idx = bg.place_index(places, entries)
        self.assertEqual(idx["Fictópoli"], {"it": ["A Fictopoli", "A Fictopoli in Fictia"],
                                           "occurrences": ["mr:0101-a", "mr:0102-b"],
                                           "lead_countries": {"mr:0101-a": "FX", "mr:0102-b": "FY"}})
        self.assertEqual(idx["in Fíctia"], {"it": [], "occurrences": ["mr:0101-a"], "lead_countries": {}})


class EvaluateTest(unittest.TestCase):
    def test_single_candidate_passing_all_is_auto(self):
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli in Fictia"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        self.assertEqual(r["failed"], [])
        self.assertEqual(r["candidates"][0]["evidence"], ["it", "la", "country", "type"])

    def test_p9314_satisfies_latin(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [cand("Q1", it=["Fictopoli"], p9314=True)], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        self.assertIn("p9314", r["candidates"][0]["evidence"])

    def test_other_items_with_the_name_filtered_by_other_rules(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [
            cand("Q2", it=["Fictopoli"], place=False),                # a school
            cand("Q3", it=["Fictopoli"]),                             # a hamlet, no Latin name
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        self.assertEqual(r["candidates"][0]["wikidata"], "Q1")

    def test_homonyms_go_to_review(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="FX"),
            cand("Q2", it=["Fictopoli"], la=["Fictopolis"], country="FY")], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("2 candidates pass every rule", r["failed"])

    def test_region_separates_homonyms(self):
        r = bg.evaluate("Fictópoli in Altrofíctia", item("A Fictopoli in Altrofictia"), [
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="FX"),
            cand("Q2", it=["Fictopoli"], la=["Fictopolis"], country="FY")], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q2")

    def test_every_italian_variant_must_match(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli", "All’ancora in mare davanti a Fictopoli"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("no item has the Italian name of every variant", r["failed"])

    def test_claim_against_country_goes_to_review_with_claims(self):
        it = "A Fictopoli in Fictia, nell’odierna Germania"
        r = bg.evaluate("Fictópoli", item(it), [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertIsNone(r["auto"])
        self.assertEqual(r["claims"], [{"country": "DE", "it": it}])
        self.assertIn("country: the Italian says DE, the item is in FX", r["failed"])

    def test_no_single_country(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country=None, countries=["FX", "FY"])],
                        regions)
        self.assertIsNone(r["auto"])
        self.assertIn("country: the item has no single current country (FX, FY)", r["failed"])

    def test_unresolvable_region(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli in Nowhere"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("country: region 'Nowhere' is not in FX", r["failed"])

    def test_no_italian_and_no_candidates(self):
        self.assertEqual(bg.evaluate("Fictópoli", item(), [], regions)["failed"],
                         ["no Italian phrase", "no candidates found"])

    def test_candidates_capped_and_ranked(self):
        cands = [cand(f"Q{i}", it=["Altro"]) for i in range(20)] + [cand("Q99", it=["Fictopoli"])]
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), cands, regions)
        self.assertEqual(len(r["candidates"]), bg.MAX_CANDIDATES)
        self.assertEqual(r["candidates"][0]["wikidata"], "Q99")
        self.assertEqual(set(r["candidates"][0]),
                         {"wikidata", "label", "description", "country", "countries", "la", "p9314",
                          "coords", "types", "evidence"})


INDEX = {"Fictópoli": {"it": ["A Fictopoli, nell’odierna Germania"], "occurrences": ["mr:0101-a"],
                       "lead_countries": {"mr:0101-a": "FR"}},
         "Altrópoli": {"it": [], "occurrences": ["mr:0102-b"], "lead_countries": {}}}


class ValidateTest(unittest.TestCase):
    def good(self):
        return {"Fictópoli": {"wikidata": "Q1", "label": "Fictopolis", "country": "FR", "status": "reviewed",
                              "text_says": [{"country": "DE", "it": "A Fictopoli, nell’odierna Germania"}]},
                "Altrópoli": {"wikidata": None, "status": "unresolved", "note": "no item"}}

    def test_good(self):
        self.assertEqual(bg.validate(self.good(), INDEX), [])

    def test_errors(self):
        cases = [
            ("Ignota", {"wikidata": "Q1", "label": "x", "country": "FR", "status": "auto"}, "not a place"),
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "FR", "status": "maybe"}, "status"),
            ("Fictópoli", {"wikidata": "1", "label": "x", "country": "FR", "status": "auto"}, "QID"),
            ("Fictópoli", {"wikidata": None, "label": "x", "country": "FR", "status": "auto"}, "QID"),
            ("Fictópoli", {"wikidata": "Q1", "country": "FR", "status": "auto"}, "label"),
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "XX", "status": "auto"}, "country"),
            ("Altrópoli", {"wikidata": None, "status": "unresolved"}, "note"),
            ("Altrópoli", {"wikidata": "Q1", "status": "unresolved", "note": "n"}, "null"),
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "FR", "status": "auto",
                           "text_says": [{"country": "DE", "it": "not a variant"}]}, "text_says"),
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "DE", "status": "auto",
                           "text_says": [{"country": "DE", "it": "A Fictopoli, nell’odierna Germania"}]},
             "text_says"),
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "FR", "status": "auto", "extra": 1},
             "keys"),
        ]
        for la, entry, word in cases:
            errors = bg.validate({la: entry}, INDEX)
            self.assertTrue(errors and word in errors[0], (la, entry, errors))

    def test_key_both_decided_and_queued(self):
        errors = bg.validate(self.good(), INDEX, [{"op": "resolve_place", "id": "Fictópoli"}])
        self.assertTrue(any("also queued" in e for e in errors))


class RenderJsonTest(unittest.TestCase):
    def test_key_order_and_sorting(self):
        out = json.loads(bg.render_json({"Zeta": {"status": "auto", "country": "FR", "label": "Z", "wikidata": "Q2"},
                                         "Alpha": {"note": "n", "status": "unresolved", "wikidata": None}}))
        self.assertEqual(list(out["places"]), ["Alpha", "Zeta"])
        self.assertEqual(list(out["places"]["Zeta"]), ["wikidata", "label", "country", "status"])
        self.assertEqual(out["statuses"], bg.STATUSES)
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'build_gazetteer'`

- [ ] **Step 3: Implement the first part of `scripts/build_gazetteer.py`**

```python
#!/usr/bin/env python3
"""Resolve each place designation in data/places.json to a Wikidata item.

Each distinct `la` is resolved once to a Wikidata QID, a modern label and the
place's actual modern country. A place is `auto` only when exactly one
candidate passes every rule of the evidence bar; every other place goes to the
review change-set (crmedr-changeset/v1, op `resolve_place`) for
martyrology-frontend, and comes back through `apply` as `reviewed` or
`unresolved`. Places awaiting review have no key in data/gazetteer.json.
See docs/superpowers/specs/2026-10-01-gazetteer-design.md.

  data/gazetteer.json          {la: {wikidata, label, country, status, ...}}
  data/gazetteer_review.json   the review change-set
  docs/gazetteer-report.md     progress, text_says, country preview

Usage:
  python3 build_gazetteer.py propose [repo_root]              (network)
  python3 build_gazetteer.py verify-suggestions [repo_root]   (network)
  python3 build_gazetteer.py apply <exported.json> [repo_root]
  python3 build_gazetteer.py check [repo_root]

Standard library only. Reads no private sources.
"""

import datetime
import json
import re
import sys
from pathlib import Path

from gazetteer_text import ISO_CODES, fold, latin_nominatives, parse_italian

STATUSES = ["auto", "reviewed", "unresolved"]
ENTRY_KEYS = ["wikidata", "label", "country", "status", "text_says", "note"]
QID = re.compile(r"^Q[1-9]\d*$")
SCHEMA = "crmedr-changeset/v1"
MAX_CANDIDATES = 10
CONFIDENCES = {"high", "medium", "low"}
PUBLISHED_KEYS = ["wikidata", "label", "description", "country", "countries", "la", "p9314", "coords", "types"]


def place_index(places, entries):
    country = {e["id"]: e.get("country") for e in entries}
    index = {}
    for mr_id, items in places.items():
        for it in items:
            slot = index.setdefault(it["la"], {"it": set(), "occurrences": set(), "lead_countries": {}})
            if "it" in it:
                slot["it"].add(it["it"])
            slot["occurrences"].add(mr_id)
            if it["source"] == "lead":
                slot["lead_countries"][mr_id] = country.get(mr_id)
    return {la: {"it": sorted(v["it"]), "occurrences": sorted(v["occurrences"]),
                 "lead_countries": dict(sorted(v["lead_countries"].items()))}
            for la, v in index.items()}


def published(candidate, evidence):
    out = {k: candidate[k] for k in PUBLISHED_KEYS}
    out["evidence"] = evidence
    return out


def auto_entry(candidate):
    return {"wikidata": candidate["wikidata"], "label": candidate["label"],
            "country": candidate["country"], "status": "auto"}


def _checks(c, parsed, noms, claims, region_sets):
    it_ok = bool(parsed) and all(any(fold(h) in c["names_it"] for h in p["heads"]) for p in parsed)
    la_ok = c["p9314"] or any(fold(x) in noms for x in c["la"])
    country_problems = []
    if c["country"] is None:
        country_problems.append("the item has no single current country (" + ", ".join(c["countries"]) + ")")
    else:
        for claim in sorted(claims):
            if claim != c["country"]:
                country_problems.append(f"the Italian says {claim}, the item is in {c['country']}")
        for region, isos in region_sets.items():
            if c["country"] not in isos:
                country_problems.append(f"region '{region}' is not in {c['country']}")
    return {"it": it_ok, "la": la_ok, "country": not country_problems, "type": c["place_type"]}, country_problems


def evaluate(la, item, candidates, region_countries):
    parsed = [parse_italian(it) for it in item["it"]]
    claims = [{"country": iso, "it": it} for it, p in zip(item["it"], parsed) for iso in p["claims"]]
    regions = list(dict.fromkeys(r for p in parsed for r in p["regions"]))
    region_sets = {r: region_countries(r) for r in regions} if candidates else {}
    noms = latin_nominatives(la)
    scored = []
    for rank, c in enumerate(candidates):
        ok, problems = _checks(c, parsed, noms, {x["country"] for x in claims}, region_sets)
        evidence = [k for k in ("it", "la", "country", "type") if ok[k]] + (["p9314"] if c["p9314"] else [])
        scored.append((c, ok, problems, evidence, rank))
    scored.sort(key=lambda s: (-sum(s[1].values()), s[4]))
    passing = [s for s in scored if all(s[1].values())]
    failed = []
    if not parsed:
        failed.append("no Italian phrase")
    if not candidates:
        failed.append("no candidates found")
    if len(passing) > 1:
        failed.append(f"{len(passing)} candidates pass every rule")
    elif not passing and scored:
        named = [s for s in scored if s[1]["it"]]
        if parsed and not named:
            failed.append("no item has the Italian name of every variant")
        else:
            best = named[0] if named else scored[0]
            if not best[1]["la"]:
                failed.append("latin: no Latin label, alias or P9314 matches")
            failed += ["country: " + p for p in best[2]]
            if not best[1]["type"]:
                failed.append("type: the item is not a place")
    return {"auto": passing[0][0] if len(passing) == 1 else None,
            "candidates": [published(s[0], s[3]) for s in scored[:MAX_CANDIDATES]],
            "failed": failed, "claims": claims}


def validate(gazetteer, index, review_ops=()):
    errors = []
    for la, e in gazetteer.items():
        where = f"gazetteer {la!r}"
        if la not in index:
            errors.append(f"{where}: not a place in data/places.json (remove or re-key it)")
            continue
        if set(e) - set(ENTRY_KEYS):
            errors.append(f"{where}: unknown keys {sorted(set(e) - set(ENTRY_KEYS))}")
        status = e.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: status {status!r} not in {STATUSES}")
            continue
        if status == "unresolved":
            if e.get("wikidata") is not None:
                errors.append(f"{where}: unresolved needs wikidata null")
            if not e.get("note"):
                errors.append(f"{where}: unresolved needs a note")
            if "label" in e or "country" in e or "text_says" in e:
                errors.append(f"{where}: unresolved has no label, country or text_says")
            continue
        if not isinstance(e.get("wikidata"), str) or not QID.match(e["wikidata"]):
            errors.append(f"{where}: wikidata {e.get('wikidata')!r} is not a QID")
        if not e.get("label"):
            errors.append(f"{where}: missing label")
        if e.get("country") not in ISO_CODES:
            errors.append(f"{where}: country {e.get('country')!r} is not an ISO 3166-1 alpha-2 code")
        for ts in e.get("text_says", []):
            if set(ts) != {"country", "it"} or ts["it"] not in index[la]["it"] \
                    or ts["country"] not in ISO_CODES or ts["country"] == e.get("country"):
                errors.append(f"{where}: bad text_says {ts!r} (it must be one of the place's Italian "
                              f"phrases, country an ISO code other than the entry's)")
    for op in review_ops:
        if op.get("id") in gazetteer:
            errors.append(f"gazetteer {op['id']!r}: decided but also queued in data/gazetteer_review.json")
    return errors


def render_json(gazetteer):
    out = {
        "$comment": "Each place designation of data/places.json (key: the Latin as printed) resolved "
                    "to a Wikidata item, its label and the place's actual modern country (ISO 3166-1 "
                    "alpha-2). status: auto (passed the evidence bar), reviewed (decided by a person), "
                    "unresolved (no suitable item). text_says: the modern country a printed Italian "
                    "phrase names wrongly. Places awaiting review are absent. Generated by "
                    "scripts/build_gazetteer.py; see docs/canonicalization-report.md (Gazetteer). "
                    "Draft pending committee review.",
        "statuses": STATUSES,
        "places": {la: {k: e[k] for k in ENTRY_KEYS if k in e} for la, e in sorted(gazetteer.items())},
    }
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_gazetteer.py tests/test_gazetteer.py
git commit -m "feat: gazetteer evidence bar, validation and JSON output (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `propose`, the change-set, the report and the CLI

**Files:**
- Modify: `scripts/build_gazetteer.py`
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Consumes: Task 3 functions; a client with `candidates(text)`, `candidate(qid)`, `region_countries(text)` (Task 2's `Wikidata`, or the test fake); `wikidata.WikidataError`.
- Produces:
  - `gather_candidates(item: dict, client) -> list[dict]` — candidates of every head of every Italian variant, de-duplicated by QID in first-seen order.
  - `make_op(la: str, item: dict, result: dict, old: dict | None) -> dict`
  - `new_changeset(operations: list) -> dict`
  - `propose(gazetteer: dict, review: dict, index: dict, client) -> list[tuple[str, str]]` — mutates `gazetteer` and `review` in place; returns the `(la, error)` pairs not processed.
  - `render_report(gazetteer: dict, index: dict, review_ops: list, not_processed=()) -> str`
  - `load_state(repo_root: Path) -> tuple[dict, dict, dict]` — `(gazetteer, review, index)`
  - `write_state(repo_root: Path, gazetteer: dict, review: dict, index: dict, not_processed=())`
  - `main(argv: list[str]) -> int`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gazetteer.py`:

```python
class FakeClient:
    def __init__(self, by_text, regions=None, fail_on=()):
        self.by_text, self.regions, self.fail_on = by_text, regions or {}, set(fail_on)

    def candidates(self, text):
        if text in self.fail_on:
            raise wd.WikidataError("boom")
        return [dict(c) for c in self.by_text.get(text, [])]

    def candidate(self, qid):
        for cs in self.by_text.values():
            for c in cs:
                if c["wikidata"] == qid:
                    return dict(c)
        return None

    def region_countries(self, text):
        return self.regions.get(text, set())


def index_of(**places):
    return {la: {"it": list(its), "occurrences": [f"mr:01{n:02d}-x"], "lead_countries": {}}
            for n, (la, its) in enumerate(places.items(), 1)}


class ProposeTest(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient({
            "Fictopoli": [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])],
            "Altropoli": [cand("Q2", it=["Altropoli"]), cand("Q3", it=["Altropoli"])],
        })
        self.index = index_of(Fictopoli=["A Fictopoli"], Altropoli=["A Altropoli"])

    def test_auto_and_queue(self):
        gaz, review = {}, bg.new_changeset([])
        self.assertEqual(bg.propose(gaz, review, self.index, self.client), [])
        self.assertEqual(gaz, {"Fictopoli": {"wikidata": "Q1", "label": "Q1", "country": "FX", "status": "auto"}})
        [op] = review["operations"]
        self.assertEqual(op["op"], "resolve_place")
        self.assertEqual(op["id"], "Altropoli")
        self.assertEqual(op["la"], "Altropoli")
        self.assertEqual(op["it"], ["A Altropoli"])
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q2", "Q3"])
        self.assertIsNone(op["decision"])
        self.assertEqual(review["schema"], "crmedr-changeset/v1")
        self.assertEqual(review["base"], {"edition": "2004", "registry": "data/places.json"})

    def test_existing_keys_untouched(self):
        gaz = {"Fictopoli": {"wikidata": "Q42", "label": "Other", "country": "FY", "status": "reviewed"}}
        review = bg.new_changeset([])
        bg.propose(gaz, review, self.index, self.client)
        self.assertEqual(gaz["Fictopoli"]["wikidata"], "Q42")
        self.assertNotIn("Fictopoli", [op["id"] for op in review["operations"]])

    def test_suggestions_kept_on_rerun(self):
        review = bg.new_changeset([{"op": "resolve_place", "id": "Altropoli", "candidates": [],
                                    "suggested": {"wikidata": "Q3", "country": "FX"},
                                    "reasoning": "r", "confidence": "high"}])
        bg.propose({}, review, self.index, self.client)
        [op] = review["operations"]
        self.assertEqual(op["suggested"], {"wikidata": "Q3", "country": "FX"})
        self.assertEqual((op["reasoning"], op["confidence"]), ("r", "high"))
        self.assertEqual(len(op["candidates"]), 2)

    def test_network_failure_leaves_place_unprocessed(self):
        client = FakeClient(self.client.by_text, fail_on={"Altropoli"})
        gaz, review = {}, bg.new_changeset([])
        failed = bg.propose(gaz, review, self.index, client)
        self.assertEqual(failed, [("Altropoli", "boom")])
        self.assertIn("Fictopoli", gaz)
        self.assertNotIn("Altropoli", gaz)
        self.assertEqual(review["operations"], [])

    def test_ops_sorted_by_occurrences_then_la(self):
        index = index_of(Beta=["A Beta"], Alfa=["A Alfa"])
        index["Beta"]["occurrences"] = ["mr:0101-a", "mr:0102-b"]
        review = bg.new_changeset([])
        bg.propose({}, review, index, FakeClient({}))
        self.assertEqual([op["id"] for op in review["operations"]], ["Beta", "Alfa"])

    def test_gather_candidates_dedupes_across_variants(self):
        client = FakeClient({"Fictopoli": [cand("Q1")], "monastero di Fictiaco": [cand("Q5")],
                             "Fictiaco": [cand("Q5"), cand("Q1")]})
        got = bg.gather_candidates({"it": ["A Fictopoli", "Nel monastero di Fictiaco"]}, client)
        self.assertEqual([c["wikidata"] for c in got], ["Q1", "Q5"])


class ReportTest(unittest.TestCase):
    def test_report_sections(self):
        index = {"Fictópoli": {"it": ["A Fictopoli, nell’odierna Germania"], "occurrences": ["mr:0101-a"],
                               "lead_countries": {"mr:0101-a": "DE"}},
                 "Altrópoli": {"it": ["A Altropoli"], "occurrences": ["mr:0102-b"], "lead_countries": {}}}
        gaz = {"Fictópoli": {"wikidata": "Q1", "label": "Fictopolis", "country": "FR", "status": "reviewed",
                             "text_says": [{"country": "DE", "it": "A Fictopoli, nell’odierna Germania"}]}}
        ops = [{"op": "resolve_place", "id": "Altrópoli", "occurrences": ["mr:0102-b"], "failed": ["no candidates found"]}]
        md = bg.render_report(gaz, index, ops, not_processed=[("Gamma", "boom")])
        self.assertIn("| reviewed | 1 |", md)
        self.assertIn("1 awaiting review", md)
        self.assertIn("| Altrópoli | 1 | no candidates found |", md)
        self.assertIn("| Fictópoli | FR | DE |", md)
        self.assertIn("| `mr:0101-a` | Fictópoli | DE | FR |", md)
        self.assertIn("Gamma", md)
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: FAIL/ERROR, `AttributeError: module 'build_gazetteer' has no attribute 'new_changeset'` (and the others).

- [ ] **Step 3: Implement**

Add `from wikidata import Wikidata, WikidataError` to the imports of `scripts/build_gazetteer.py`, and append:

```python
def gather_candidates(item, client):
    seen = {}
    for it in item["it"]:
        for head in parse_italian(it)["heads"]:
            for c in client.candidates(head):
                seen.setdefault(c["wikidata"], c)
    return list(seen.values())


def make_op(la, item, result, old):
    op = {"op": "resolve_place", "id": la, "la": la, "it": item["it"],
          "occurrences": item["occurrences"], "claims": result["claims"],
          "failed": result["failed"], "candidates": result["candidates"]}
    for key in ("suggested", "reasoning", "confidence"):
        if old and key in old:
            op[key] = old[key]
    op["decision"] = None
    op["edited"] = None
    return op


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/build_gazetteer.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": "2004", "registry": "data/places.json"},
            "operations": operations}


def _sort_ops(ops):
    return sorted(ops, key=lambda op: (-len(op.get("occurrences", [])), op["id"]))


def propose(gazetteer, review, index, client):
    ops = {op["id"]: op for op in review["operations"]}
    not_processed = []
    for la in sorted(index):
        if la in gazetteer:
            continue
        try:
            result = evaluate(la, index[la], gather_candidates(index[la], client), client.region_countries)
        except WikidataError as e:
            not_processed.append((la, str(e)))
            continue
        if result["auto"]:
            gazetteer[la] = auto_entry(result["auto"])
            ops.pop(la, None)
        else:
            ops[la] = make_op(la, index[la], result, ops.get(la))
    review["operations"] = _sort_ops(ops.values())
    review["generated_at"] = datetime.date.today().isoformat()
    return not_processed


def _cell(s):
    return str(s).replace("|", "\\|")


def render_report(gazetteer, index, review_ops, not_processed=()):
    counts = {s: sum(1 for e in gazetteer.values() if e["status"] == s) for s in STATUSES}
    text_says = [(la, e["country"], ts["country"]) for la, e in sorted(gazetteer.items())
                 for ts in e.get("text_says", [])]
    preview = [(mr_id, la, reg, gazetteer[la]["country"]) for la in sorted(index) if la in gazetteer
               and gazetteer[la].get("country") for mr_id, reg in index[la]["lead_countries"].items()
               if reg and reg != gazetteer[la]["country"]]
    lines = [
        "# Gazetteer report",
        "",
        "Generated by `scripts/build_gazetteer.py`. It holds place designations, IDs and "
        "Wikidata QIDs only.",
        "",
        "## Progress",
        "",
        f"{len(index)} distinct places; {len(gazetteer)} decided; {len(review_ops)} awaiting review"
        + (f"; {len(not_processed)} not processed (network)" if not_processed else "") + ".",
        "",
        "| Status | Places |",
        "| --- | --- |",
        *[f"| {s} | {counts[s]} |" for s in STATUSES],
        "",
        "## Awaiting review",
        "",
        "In `data/gazetteer_review.json`, most frequent first.",
        "",
        "| Place | Occurrences | Why not auto |",
        "| --- | --- | --- |",
        *[f"| {_cell(op['id'])} | {len(op.get('occurrences', []))} | {_cell('; '.join(op.get('failed', [])))} |"
          for op in review_ops],
        "",
        "## The text names another country (text_says)",
        "",
        "| Place | Country | The text says |",
        "| --- | --- | --- |",
        *([f"| {_cell(la)} | {c} | {t} |" for la, c, t in text_says] or ["| | | |"]),
        "",
        "## Preview: registry country differs from the opening place",
        "",
        "For the cross-check of sub-project 3. Registry conventions (e.g. `PS` for the Holy "
        "Land) show up here too.",
        "",
        "| ID | Place | Registry | Gazetteer |",
        "| --- | --- | --- | --- |",
        *([f"| `{m}` | {_cell(la)} | {r} | {g} |" for m, la, r, g in preview] or ["| | | | |"]),
    ]
    if not_processed:
        lines += ["", "## Not processed (network)", "",
                  *[f"- {_cell(la)}: {_cell(err)}" for la, err in not_processed]]
    return "\n".join(lines) + "\n"


def _read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_state(repo_root):
    data = repo_root / "data"
    places = json.loads((data / "places.json").read_text(encoding="utf-8"))["places"]
    entries = json.loads((data / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    gazetteer = _read_json(data / "gazetteer.json", {"places": {}})["places"]
    review = _read_json(data / "gazetteer_review.json", new_changeset([]))
    return gazetteer, review, place_index(places, entries)


def write_state(repo_root, gazetteer, review, index, not_processed=()):
    errors = validate(gazetteer, index, review["operations"])
    if errors:
        sys.exit("invalid gazetteer:\n" + "\n".join(errors))
    data = repo_root / "data"
    (data / "gazetteer.json").write_text(render_json(gazetteer), encoding="utf-8")
    (data / "gazetteer_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (repo_root / "docs" / "gazetteer-report.md").write_text(
        render_report(gazetteer, index, review["operations"], not_processed), encoding="utf-8")


def main(argv):
    if not argv or argv[0] not in {"propose", "verify-suggestions", "apply", "check"}:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    exported = None
    if cmd == "apply":
        if not rest:
            sys.exit(__doc__)
        exported, rest = Path(rest[0]), rest[1:]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    gazetteer, review, index = load_state(repo_root)
    client = Wikidata(repo_root / ".cache" / "wikidata")
    if cmd == "check":
        errors = validate(gazetteer, index, review["operations"])
        print("\n".join(errors) or f"ok: {len(gazetteer)} places decided, {len(review['operations'])} queued")
        return 1 if errors else 0
    if cmd == "propose":
        not_processed = propose(gazetteer, review, index, client)
        write_state(repo_root, gazetteer, review, index, not_processed)
        auto = sum(1 for e in gazetteer.values() if e["status"] == "auto")
        print(f"{len(index)} places; {auto} auto; {len(review['operations'])} awaiting review; "
              f"{len(not_processed)} not processed")
        return 1 if not_processed else 0
    raise NotImplementedError(cmd)  # verify-suggestions and apply: Task 5


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_gazetteer.py tests/test_gazetteer.py
git commit -m "feat: gazetteer propose, review change-set and report (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `apply` and `verify-suggestions`

**Files:**
- Modify: `scripts/build_gazetteer.py`
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Consumes: Task 3 and Task 4 functions, the client interface.
- Produces:
  - `apply_decisions(gazetteer: dict, review: dict, exported: dict, index: dict, client) -> int` — the number of decisions applied. It raises `ValueError` listing **every** error, without changing `gazetteer` or `review`.
  - `verify_suggestions(review: dict, index: dict, client) -> tuple[list[str], list[str]]` — `(errors, warnings)`; adds a missing suggested item to the op's candidates.
  - `main` handles `apply` and `verify-suggestions`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gazetteer.py`:

```python
def op(la, decision, candidates=(), suggested=None, edited=None):
    o = {"op": "resolve_place", "id": la, "la": la, "it": INDEX.get(la, {}).get("it", []),
         "candidates": [bg.published(c, []) for c in candidates], "decision": decision, "edited": edited}
    if suggested:
        o["suggested"] = suggested
    return o


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.c1 = cand("Q1", label="Fictopolis", country="FR")
        self.c2 = cand("Q2", label="Fictopolis Nova", country="DE")
        self.client = FakeClient({"x": [self.c1, self.c2, cand("Q7", label="Septima", country="IT")]})
        self.says = [{"country": "DE", "it": "A Fictopoli, nell’odierna Germania"}]

    def run_apply(self, *ops, gaz=None):
        gaz = {} if gaz is None else gaz
        review = bg.new_changeset([dict(o, decision=None, edited=None) for o in ops])
        n = bg.apply_decisions(gaz, review, bg.new_changeset(list(ops)), INDEX, self.client)
        return n, gaz, review

    def test_accept_uses_suggestion(self):
        n, gaz, review = self.run_apply(op("Fictópoli", "accept", [self.c2, self.c1],
                                           suggested={"wikidata": "Q1", "country": "FR", "text_says": self.says}))
        self.assertEqual(n, 1)
        self.assertEqual(gaz["Fictópoli"], {"wikidata": "Q1", "label": "Fictopolis", "country": "FR",
                                            "status": "reviewed", "text_says": self.says})
        self.assertEqual(review["operations"], [])

    def test_accept_without_suggestion_takes_top_candidate(self):
        _, gaz, _ = self.run_apply(op("Fictópoli", "accept", [self.c1, self.c2]))
        self.assertEqual(gaz["Fictópoli"]["wikidata"], "Q1")

    def test_edit_to_other_item_does_not_inherit_suggestion(self):
        _, gaz, _ = self.run_apply(op("Fictópoli", "edit", [self.c1, self.c2],
                                      suggested={"wikidata": "Q1", "country": "FR", "text_says": self.says},
                                      edited={"wikidata": "Q2"}))
        self.assertEqual(gaz["Fictópoli"], {"wikidata": "Q2", "label": "Fictopolis Nova", "country": "DE",
                                            "status": "reviewed"})

    def test_edit_to_item_not_in_candidates_is_fetched(self):
        _, gaz, _ = self.run_apply(op("Fictópoli", "edit", [self.c1], edited={"wikidata": "Q7", "country": "IT"}))
        self.assertEqual(gaz["Fictópoli"]["label"], "Septima")

    def test_reject_is_unresolved(self):
        _, gaz, _ = self.run_apply(op("Altrópoli", "reject", edited={"reason": "no item for the hill"}))
        self.assertEqual(gaz["Altrópoli"], {"wikidata": None, "status": "unresolved", "note": "no item for the hill"})

    def test_undecided_ops_stay(self):
        n, gaz, review = self.run_apply(op("Fictópoli", None, [self.c1]))
        self.assertEqual((n, gaz), (0, {}))
        self.assertEqual([o["id"] for o in review["operations"]], ["Fictópoli"])

    def test_all_errors_reported_and_nothing_written(self):
        gaz = {}
        ops = [op("Fictópoli", "accept", [cand("Q9", country=None, countries=["FR", "IT"])]),
               op("Altrópoli", "reject", edited={})]
        review = bg.new_changeset([dict(o, decision=None) for o in ops])
        with self.assertRaises(ValueError) as cm:
            bg.apply_decisions(gaz, review, bg.new_changeset(ops), INDEX, self.client)
        self.assertIn("needs a country", str(cm.exception))
        self.assertIn("needs a reason", str(cm.exception))
        self.assertEqual(gaz, {})
        self.assertEqual(len(review["operations"]), 2)

    def test_already_decided_and_unknown_place(self):
        gaz = {"Fictópoli": {"wikidata": "Q1", "label": "x", "country": "FR", "status": "auto"}}
        with self.assertRaises(ValueError) as cm:
            self.run_apply(op("Fictópoli", "accept", [self.c1]), op("Ignota", "accept", [self.c1]), gaz=gaz)
        self.assertIn("already decided", str(cm.exception))
        self.assertIn("not a place", str(cm.exception))

    def test_unknown_qid(self):
        with self.assertRaises(ValueError) as cm:
            self.run_apply(op("Fictópoli", "edit", [self.c1], edited={"wikidata": "Q404"}))
        self.assertIn("no such item", str(cm.exception))


class VerifySuggestionsTest(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient({"x": [cand("Q1", it=["Fictopoli"], country="FR"),
                                        cand("Q7", label="Septima", country="IT")]})

    def test_missing_suggested_item_added_to_candidates(self):
        review = bg.new_changeset([op("Fictópoli", None, [cand("Q1", country="FR")],
                                      suggested={"wikidata": "Q7", "country": "IT"})])
        review["operations"][0]["confidence"] = "medium"
        errors, warnings = bg.verify_suggestions(review, INDEX, self.client)
        self.assertEqual((errors, warnings), ([], []))
        self.assertEqual([c["wikidata"] for c in review["operations"][0]["candidates"]], ["Q1", "Q7"])

    def test_errors_and_warnings(self):
        review = bg.new_changeset([
            op("Fictópoli", None, suggested={"wikidata": "Q404", "country": "FR"}),
            op("Altrópoli", None, suggested={"wikidata": "Q1", "country": "XX"}),
        ])
        review["operations"].append(op("Fictópoli", None, suggested={
            "wikidata": "Q1", "country": "DE", "text_says": [{"country": "DE", "it": "nope"}]}))
        for o in review["operations"]:
            o["confidence"] = "sure"
        errors, warnings = bg.verify_suggestions(review, INDEX, self.client)
        text = "\n".join(errors)
        for word in ("no such item", "not an ISO", "text_says", "confidence"):
            self.assertIn(word, text)
        self.assertTrue(any("differs from the item's country FR" in w for w in warnings))
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `python3 -m unittest tests.test_gazetteer -v`
Expected: ERROR, `AttributeError: module 'build_gazetteer' has no attribute 'apply_decisions'`

- [ ] **Step 3: Implement**

Insert these functions before `main` in `scripts/build_gazetteer.py`:

```python
def _resolve(op, client):
    """The entry for one decided op, or an error message."""
    la, decision = op["id"], op["decision"]
    suggested, edited = op.get("suggested") or {}, op.get("edited") or {}
    if decision == "reject":
        reason = (edited.get("reason") or "").strip()
        if not reason:
            return None, f"{la!r}: reject needs a reason (edited.reason)"
        return {"wikidata": None, "status": "unresolved", "note": reason}, None
    if decision not in ("accept", "edit"):
        return None, f"{la!r}: unknown decision {decision!r}"
    candidates = op.get("candidates", [])
    qid = (edited.get("wikidata") if decision == "edit" else None) or suggested.get("wikidata") \
        or (candidates[0]["wikidata"] if candidates else None)
    if not qid or not QID.match(qid):
        return None, f"{la!r}: no item chosen"
    chosen = next((c for c in candidates if c["wikidata"] == qid), None) or client.candidate(qid)
    if chosen is None:
        return None, f"{la!r}: no such item {qid}"
    from_suggestion = suggested.get("wikidata") == qid
    edit = edited if decision == "edit" else {}
    country = edit.get("country") or (suggested.get("country") if from_suggestion else None) \
        or chosen.get("country")
    if not country:
        return None, f"{la!r}: {qid} needs a country (no single current P17; use edit)"
    text_says = edit["text_says"] if "text_says" in edit else \
        (suggested.get("text_says") if from_suggestion else None)
    entry = {"wikidata": qid, "label": chosen["label"], "country": country, "status": "reviewed"}
    if text_says:
        entry["text_says"] = text_says
    if edit.get("reason"):
        entry["note"] = edit["reason"]
    return entry, None


def apply_decisions(gazetteer, review, exported, index, client):
    if exported.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    decided, errors = {}, []
    for op in exported.get("operations", []):
        if op.get("op") != "resolve_place" or op.get("decision") is None:
            continue
        la = op["id"]
        if la not in index:
            errors.append(f"{la!r}: not a place in data/places.json")
            continue
        if la in gazetteer:
            errors.append(f"{la!r}: already decided in data/gazetteer.json")
            continue
        entry, error = _resolve(op, client)
        if error:
            errors.append(error)
        else:
            decided[la] = entry
    if not errors:
        trial = dict(gazetteer, **decided)
        errors = validate({la: trial[la] for la in decided}, index)
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    gazetteer.update(decided)
    review["operations"] = [op for op in review["operations"] if op["id"] not in decided]
    return len(decided)


def verify_suggestions(review, index, client):
    errors, warnings = [], []
    for op in review["operations"]:
        s = op.get("suggested")
        if not s:
            continue
        la = op["id"]
        if op.get("confidence") not in CONFIDENCES:
            errors.append(f"{la!r}: confidence {op.get('confidence')!r} not in {sorted(CONFIDENCES)}")
        qid = s.get("wikidata")
        item = None
        if not isinstance(qid, str) or not QID.match(qid):
            errors.append(f"{la!r}: suggested wikidata {qid!r} is not a QID")
        else:
            item = next((c for c in op.get("candidates", []) if c["wikidata"] == qid), None)
            if item is None:
                item = client.candidate(qid)
                if item is None:
                    errors.append(f"{la!r}: no such item {qid}")
                else:
                    item = published(item, [])
                    op.setdefault("candidates", []).append(item)
        if s.get("country") not in ISO_CODES:
            errors.append(f"{la!r}: suggested country {s.get('country')!r} is not an ISO code")
        elif item and item.get("country") and item["country"] != s["country"]:
            warnings.append(f"{la!r}: suggested country {s['country']} differs from the item's country "
                            f"{item['country']}; check the reasoning")
        its = index.get(la, {}).get("it", [])
        for ts in s.get("text_says", []):
            if set(ts) != {"country", "it"} or ts["it"] not in its or ts["country"] == s.get("country"):
                errors.append(f"{la!r}: bad text_says {ts!r}")
    return errors, warnings
```

Then replace the last line of `main` (`raise NotImplementedError(cmd)  # …`) with:

```python
    if cmd == "verify-suggestions":
        errors, warnings = verify_suggestions(review, index, client)
        write_state(repo_root, gazetteer, review, index)
        print("\n".join(["ERROR " + e for e in errors] + ["CHECK " + w for w in warnings]) or "ok")
        return 1 if errors else 0
    try:
        n = apply_decisions(gazetteer, review, json.loads(exported.read_text(encoding="utf-8")), index, client)
    except ValueError as e:
        sys.exit(str(e))
    write_state(repo_root, gazetteer, review, index)
    print(f"{n} decisions applied; {len(review['operations'])} awaiting review")
    return 0
```

- [ ] **Step 4: Run the tests to check they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS (the gazetteer tests and the existing places, registry and typology tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/build_gazetteer.py tests/test_gazetteer.py
git commit -m "feat: gazetteer apply and verify-suggestions (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: First `propose` run against Wikidata, with a hand check

**Files:**
- Create (generated): `data/gazetteer.json`, `data/gazetteer_review.json`, `docs/gazetteer-report.md`
- Modify (only if the hand check finds rule errors): `scripts/gazetteer_text.py`, `scripts/build_gazetteer.py`, `tests/test_gazetteer.py`
- Test: `tests/test_gazetteer.py` (committed-file check)

**Interfaces:**
- Consumes: the `propose` and `check` CLI.

- [ ] **Step 1: Add the committed-file test**

Append to `tests/test_gazetteer.py`:

```python
REPO = Path(__file__).resolve().parent.parent


class CommittedGazetteerTest(unittest.TestCase):
    def test_committed_files_validate(self):
        if not (REPO / "data" / "gazetteer.json").exists():
            self.skipTest("no data/gazetteer.json yet")
        gazetteer, review, index = bg.load_state(REPO)
        self.assertEqual(bg.validate(gazetteer, index, review["operations"]), [])
        self.assertEqual(set(gazetteer) | {op["id"] for op in review["operations"]}, set(index))
```

The second assertion holds only after a complete run with no unprocessed places. That is the state this task commits.

- [ ] **Step 2: Run `propose` in the background**

Run (as a background command, since it makes several thousand requests; the cache makes reruns cheap):

```bash
python3 scripts/build_gazetteer.py propose
```

Expected final line: `2517 places; N auto; M awaiting review; 0 not processed`. If any places are not processed, run it again; the cached requests are not repeated.

- [ ] **Step 3: Hand-check 50 `auto` entries**

```bash
python3 - <<'EOF'
import json, random
g = json.load(open("data/gazetteer.json"))["places"]
auto = sorted(la for la, e in g.items() if e["status"] == "auto")
random.seed(12)
for la in random.sample(auto, 50):
    e = g[la]; print(f"{la} | {e['wikidata']} {e['label']} {e['country']}")
EOF
```

For each line, check that the item is the place the Latin names (open `https://www.wikidata.org/wiki/<QID>` when unsure), and that the country is right. Every wrong one is a rule error. Find the rule that let it through, fix it in `gazetteer_text.py` or `evaluate`, add a test with made-up names that reproduces it, delete `data/gazetteer.json` and `data/gazetteer_review.json`, and rerun Step 2. Record the sample result (n correct of 50) for the PR description.

- [ ] **Step 4: Check the run's shape**

```bash
python3 scripts/build_gazetteer.py check
python3 - <<'EOF'
import json, collections
r = json.load(open("data/gazetteer_review.json"))["operations"]
print(collections.Counter(f.split(":")[0] for op in r for f in op["failed"]).most_common())
EOF
```

Expected: `check` prints `ok: …`. The failure counts show what sends places to review. If one reason dominates in a way that looks like a parsing bug (for example "no item has the Italian name of every variant" for phrases whose head is plainly a city), inspect 10 of those ops, and fix and test as in Step 3.

- [ ] **Step 5: Run all tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS, including `CommittedGazetteerTest`.

- [ ] **Step 6: Run the 5-word overlap scan**

Use the same scan as for #10, run against `tests/test_gazetteer.py` and the Latin and Italian texts in `../martyrology-texts`. It must find no 5-word sequence shared with a real elogium. If the private texts are not checked out next to the repo, note in the PR that the scan was not run.

- [ ] **Step 7: Commit**

```bash
git add data/gazetteer.json data/gazetteer_review.json docs/gazetteer-report.md tests/test_gazetteer.py
git commit -m "data: first gazetteer run (auto entries and review queue) (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

If Steps 3–4 changed any script, commit those changes first, in their own `fix:` commit with their tests.

---

### Task 7: Documentation

**Files:**
- Modify: `AGENTS.md`, `README.md`, `docs/canonicalization-report.md`

- [ ] **Step 1: AGENTS.md**

After item 4 of "Architecture: the generation pipeline" (the `extract_places.py` item), add:

```markdown
5. **`scripts/build_gazetteer.py`** resolves each distinct place designation in `data/places.json` to a Wikidata item, a label and the place's actual modern country, and writes `data/gazetteer.json`, the review change-set `data/gazetteer_review.json` (`crmedr-changeset/v1`, op `resolve_place`, reviewed in martyrology-frontend) and `docs/gazetteer-report.md`. Unlike the other generators it reads no private sources but **needs network access** (Wikidata, cached in `.cache/wikidata/`). A place is `auto` only when exactly one candidate passes the evidence bar; otherwise it waits in the change-set and has no key in `gazetteer.json`.
   - Run: `python3 scripts/build_gazetteer.py propose`; after review in martyrology-frontend, `python3 scripts/build_gazetteer.py apply <exported.json>`; `verify-suggestions` checks suggested QIDs; `check` validates offline (stdlib only)
```

Under "Where hand-corrections live", add:

```markdown
- `data/gazetteer.json` — `reviewed` and `unresolved` entries are human decisions; `propose` never changes an existing key. Fix a wrong place by editing its entry (keeping the validation rules), or delete the key and rerun `propose` to queue it again.
```

- [ ] **Step 2: README.md**

After the `data/places.json` bullet (line 48), add:

```markdown
- [`data/gazetteer.json`](data/gazetteer.json) — each place designation of `data/places.json` resolved to a Wikidata item, its label and the place's actual modern country (ISO 3166-1 alpha-2), with a status (`auto`, `reviewed`, `unresolved`) and, where a printed Italian phrase names the wrong modern country, `text_says`. Places still awaiting review are in [`data/gazetteer_review.json`](data/gazetteer_review.json); progress in [`docs/gazetteer-report.md`](docs/gazetteer-report.md)
```

- [ ] **Step 3: docs/canonicalization-report.md**

Read the "Places (September 2026)" section, then add at its end (before "## Post-2004 official variations") a subsection:

```markdown
### Gazetteer (October 2026)

Each distinct place designation (the `la` of `data/places.json`) is resolved once
in `data/gazetteer.json` to the most specific place that has a stable Wikidata
item, usually the settlement or territory: *Romæ apud sanctum Petrum* resolves to
Rome; a monastery resolves to its own item when Wikidata has one. Each entry has
the QID, the item's label and the place's **actual** modern country (ISO 3166-1
alpha-2), with no registry conventions applied. Reconciling it with each entry's
`country` is a later step.

A place is `auto` only when exactly one Wikidata candidate passes every rule:
its Italian label or alias is the head toponym of every Italian phrase of the
place; a Latin label or alias matches a nominative of the Latin, or it has a Latin
Place Names ID (P9314); it has one current country (P17), which agrees with every
modern country the Italian names and every region it states; and it is a place
(P31 through P279* to settlement, administrative entity, monastery, church,
archaeological site, island, mountain, region, cave, castle or country). Every other place
goes to the review change-set `data/gazetteer_review.json` and is decided in
martyrology-frontend (`reviewed`, or `unresolved` with a note). Places awaiting
review have no key.

Where the printed Italian names the wrong modern country, the actual location
wins and the entry records the printed claim in `text_says`, with the Italian
phrase it comes from (e.g. Lorch/Enns, "nell'odierna Germania", is in Austria).
```

- [ ] **Step 4: Run all tests and check**

Run: `python3 -m unittest discover -s tests -v && python3 scripts/build_gazetteer.py check`
Expected: all PASS; `ok: …`.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md README.md docs/canonicalization-report.md
git commit -m "docs: gazetteer (#12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
