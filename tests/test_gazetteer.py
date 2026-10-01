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
