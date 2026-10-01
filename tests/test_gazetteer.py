import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gazetteer_text as gt  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class FoldTest(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(gt.fold("  Fictópoli  Ǽquæ  Nell’ "), "fictopoli aequae nell'")

    def test_country_of(self):
        self.assertEqual(gt.country_of("Israele"), "PS")  # the registry's Holy Land convention
        self.assertEqual(gt.country_of("Francia"), "FR")
        self.assertEqual(gt.country_of("viet nam"), "VN")
        self.assertIsNone(gt.country_of("Fictia"))
        self.assertIn("DE", gt.ISO_CODES)


class IsoCodesTest(unittest.TestCase):
    def test_official_codes_only(self):
        self.assertIn("JE", gt.ISO_CODES)
        for withdrawn in ("AN", "CP", "CQ", "DD", "DG", "PC", "YU"):
            self.assertNotIn(withdrawn, gt.ISO_CODES)
        self.assertEqual(len(gt.ISO_CODES - {"XK"}), 249)


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
        for it in ("A Fictopoli in Fictia, ora in Francia", "A Fictopoli in Fictia, oggi in Francia",
                   "A Fictopoli nel territorio dell’attuale Francia", "A Fictopoli nell’attuale Francia",
                   "A Fictopoli in Fictia, nell’odierna Francia"):
            self.assertEqual(gt.parse_italian(it)["claims"], ["FR"], it)
        self.assertEqual(gt.parse_italian("Presso Fictopoli nel Fictiense, nell’odierno Belgio")["claims"], ["BE"])
        self.assertEqual(gt.parse_italian("A Fictopoli nel Fictiense, ora Viet Nam")["claims"], ["VN"])

    def test_a_bare_country_name_is_a_region_not_a_claim(self):
        # "in Siria" may name the ancient region; only explicit modern wording is a claim.
        for it in ("A Fictopoli sempre in Francia", "A Fictopoli ancora in Francia",
                   "A Fictopoli in Fictia, in Francia", "A Fictopoli in Francia"):
            p = gt.parse_italian(it)
            self.assertEqual(p["claims"], [], it)
            self.assertIn("Francia", p["regions"], it)
        p = gt.parse_italian("A Fictopoli nell’antica Armenia")
        self.assertEqual((p["claims"], p["regions"]), ([], ["Armenia"]))

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
        p = gt.parse_italian("In nave al largo di Fictopoli sulla costa fittizia")
        self.assertEqual(p["heads"], [])
        self.assertEqual(p["regions"], [])

    def test_antica_before_a_region(self):
        self.assertEqual(gt.parse_italian("A Fictopoli nell’antica Fictia")["regions"], ["Fictia"])
        self.assertEqual(gt.parse_italian("A Fictopoli nell’antico Fictiense")["regions"], ["Fictiense"])

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

    def test_only_the_head_words_before_a_connector(self):
        noms = gt.latin_nominatives("Fictópoli in Fíctia")
        self.assertIn("fictopolis", noms)
        self.assertNotIn("fictia", noms)
        self.assertNotIn("altropolis", gt.latin_nominatives("Ficti prope Altrópoli in Fíctia"))
        self.assertIn("fictum", gt.latin_nominatives("Ficti prope Altrópoli in Fíctia"))
        self.assertEqual(gt.latin_nominatives("Fictópoli apud Sanctum Fictum") & {"fictus", "sanctus"}, set())

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
        self.assertEqual(s["p9314_names"], ["fictopoli"])
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
        if "query" in q and "P297" in q["query"][0]:
            return {"results": {"bindings": [
                {"c": {"value": "http://www.wikidata.org/entity/" + i}, "iso": {"value": wd.summarize(raw)["iso_self"]}}
                for i, raw in self.entities.items() if wd.summarize(raw)["iso_self"]]}}
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

    def test_country_iso_from_one_cached_query(self):
        self.client.candidates("Fictopoli")
        self.client.candidates("Fictia")
        fetched = [u for u in self.fetch.calls if "wbgetentities" in u and "Q100" in u]
        self.assertEqual(fetched, [])
        self.assertEqual(sum(1 for u in self.fetch.calls if "P297" in u), 1)

    def test_netherlands_constituent_country_maps_to_nl(self):
        self.fetch.entities["Q8"] = raw_entity("Q8", it=("Fictadam",), p17=[snak("P17", "Q55")])
        self.fetch.searches["Fictadam"] = ["Q8"]
        self.assertEqual(self.client.candidates("Fictadam")[0]["country"], "NL")

    def test_cache_writes_are_atomic(self):
        cache = Path(self.tmp.name)
        with mock.patch("wikidata.os.replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.client.candidates("Fictopoli")
        self.assertEqual(list(cache.glob("*.json")), [])
        self.assertEqual(list(cache.glob("*.tmp")), [])
        self.client.candidates("Fictopoli")
        self.assertTrue(list(cache.glob("*.json")))
        self.assertEqual(list(cache.glob("*.tmp")), [])
        self.assertTrue(all(json.loads(f.read_text(encoding="utf-8")) is not None for f in cache.glob("*.json")))

    def test_region_coords_skip_a_country_name(self):
        self.fetch.entities["Q9"] = raw_entity("Q9", it=("Fictistan",), p17=[snak("P17", "Q100")], coords=(1.0, 2.0))
        self.fetch.searches["Fictistan"] = ["Q100", "Q9"]
        self.assertEqual(self.client.region_coords("Fictistan"), [])

    def test_a_territory_item_keeps_its_own_code(self):
        self.fetch.entities["Q7"] = raw_entity("Q7", it=("Fictaria",), p17=[snak("P17", "Q100")], p297="FY")
        self.fetch.searches["Fictaria"] = ["Q7"]
        self.assertEqual(self.client.candidates("Fictaria")[0]["country"], "FY")

    def test_holy_land_convention(self):
        self.fetch.entities["Q801"] = raw_entity("Q801", it=("Israele",), p297="IL", p31=("Q6256",))
        self.fetch.entities["Q8"] = raw_entity("Q8", it=("Fictaroth",), p17=[snak("P17", "Q801")])
        self.fetch.searches["Fictaroth"] = ["Q8"]
        c = self.client.candidates("Fictaroth")[0]
        self.assertEqual((c["country"], c["countries"]), ("PS", ["PS"]))

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

    def test_connection_reset_bad_json_and_date_retry_after_are_retried(self):
        import http.client
        ok = mock.MagicMock()
        ok.__enter__.return_value = io.BytesIO(json.dumps({"x": 1}).encode())
        html = mock.MagicMock()
        html.__enter__.return_value = io.BytesIO(b"<html>busy</html>")
        dated = urllib.error.HTTPError("u", 503, "down", {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None)
        sleeps = []
        with mock.patch("wikidata.urllib.request.urlopen",
                        side_effect=[http.client.RemoteDisconnected("bye"), ConnectionResetError(), html, dated, ok]):
            self.assertEqual(wd.http_get("https://example/u", sleep=sleeps.append), {"x": 1})
        self.assertEqual(len(sleeps), 4)

    def test_gives_up(self):
        err = urllib.error.HTTPError("u", 503, "down", {}, None)
        with mock.patch("wikidata.urllib.request.urlopen", side_effect=[err] * 3):
            with self.assertRaises(wd.WikidataError):
                wd.http_get("https://example/u", retries=3, sleep=lambda s: None)


import build_gazetteer as bg  # noqa: E402


def cand(qid, it=(), la=(), country="IT", countries=None, place=True, p9314=False, label=None):
    return {"wikidata": qid, "label": label or qid, "description": "", "names_it": sorted(gt.fold(x) for x in it),
            "la": list(la), "p9314": p9314, "p9314_names": [], "country_qids": [], "iso_self": None,
            "country": country, "countries": countries if countries is not None else ([country] if country else []),
            "coords": None, "types": ["Q486972"], "place_type": place}


def item(*its, occ=("mr:0101-fictus",)):
    return {"it": list(its), "occurrences": list(occ), "lead_countries": {}}


REGIONS = {"Fictia": {"IT"}, "Fictiense": {"IT"}, "Altrofictia": {"ES"}}


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

    def test_other_items_with_the_name_filtered_by_other_rules(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [
            cand("Q2", it=["Fictopoli"], place=False),                # a school
            cand("Q3", it=["Fictopoli"]),                             # a hamlet, no Latin name
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        self.assertEqual(r["candidates"][0]["wikidata"], "Q1")

    def test_homonyms_go_to_review(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="IT"),
            cand("Q2", it=["Fictopoli"], la=["Fictopolis"], country="IT")], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("2 candidates pass every rule", r["failed"])

    def test_region_separates_homonyms(self):
        r = bg.evaluate("Fictópoli in Altrofíctia", item("A Fictopoli in Altrofictia"), [
            cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="IT"),
            cand("Q2", it=["Fictopoli"], la=["Fictopolis"], country="ES")], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q2")

    def test_every_italian_variant_must_match(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli", "In nave al largo di Fictopoli"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("no item has the Italian name of every variant", r["failed"])

    def test_claim_against_country_goes_to_review_with_claims(self):
        it = "A Fictopoli in Fictia, nell’odierna Germania"
        r = bg.evaluate("Fictópoli", item(it), [cand("Q1", it=["Fictopoli"], la=["Fictopolis"])], regions)
        self.assertIsNone(r["auto"])
        self.assertEqual(r["claims"], [{"country": "DE", "it": it}])
        self.assertIn("country: the Italian says DE, the item is in IT", r["failed"])

    def test_bare_italian_implies_italy(self):
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="HR")], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("country: the Italian names no region or country (in the CEI edition: Italy); "
                      "the item is in HR", r["failed"])
        r = bg.evaluate("Fictópoli", item("A Fictopoli"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="IT")], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")

    def test_bare_italian_naming_a_country_item(self):
        country = dict(cand("Q1", it=["Fictistan"], la=["Fictistania"], country="FR"), iso_self="FR")
        r = bg.evaluate("In Fictistánia", item("In Fictistan"), [country], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")

    def test_p9314_alone_is_not_latin_evidence(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [cand("Q1", it=["Fictopoli"], p9314=True)], regions)
        self.assertIsNone(r["auto"])
        self.assertIn("p9314", r["candidates"][0]["evidence"])
        self.assertNotIn("la", r["candidates"][0]["evidence"])

    def test_p9314_slug_matching_the_latin_head_counts(self):
        c = dict(cand("Q1", it=["Fictopoli"]), p9314=True, p9314_names=["fictopoliuae"])
        r = bg.evaluate("Fictopolívæ", item("A Fictopoli"), [c], regions)
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        r = bg.evaluate("Altrópoli", item("A Fictopoli"), [c], regions)
        self.assertIsNone(r["auto"])

    def test_place_far_from_the_stated_region(self):
        far = dict(cand("Q1", it=["Fictopoli"], la=["Fictopolis"]), coords=[45.0, 8.0])
        near = dict(far, coords=[38.5, 16.0])
        coords = {"Fictia": [[38.1, 15.6]]}
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli in Fictia"), [far], regions, coords.get)
        self.assertIsNone(r["auto"])
        self.assertTrue(any(f.startswith("region: the item is") and "from 'Fictia'" in f for f in r["failed"]))
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli in Fictia"), [near], regions, coords.get)
        self.assertEqual(r["auto"]["wikidata"], "Q1")

    def test_region_without_coordinates_is_not_checked_but_candidate_without_is(self):
        c = dict(cand("Q1", it=["Fictopoli"], la=["Fictopolis"]), coords=None)
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli in Fictia"), [c], regions, lambda r: [])
        self.assertEqual(r["auto"]["wikidata"], "Q1")
        r = bg.evaluate("Fictópoli in Fíctia", item("A Fictopoli in Fictia"), [c], regions,
                        lambda r: [[38.1, 15.6]])
        self.assertIsNone(r["auto"])

    def test_country_must_be_an_iso_code(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli in Fictia"),
                        [cand("Q1", it=["Fictopoli"], la=["Fictopolis"], country="TA")], lambda t: {"TA"})
        self.assertIsNone(r["auto"])
        self.assertIn("country: TA is not an ISO 3166-1 alpha-2 code", r["failed"])

    def test_a_bare_country_name_is_checked_as_a_region(self):
        r = bg.evaluate("Fictiochíæ in Sýria", item("Ad Fictiochia in Siria"),
                        [cand("Q1", it=["Fictiochia"], la=["Fictiochia"], country="TR")], lambda t: {"SY"})
        self.assertIsNone(r["auto"])
        self.assertEqual(r["claims"], [])
        self.assertIn("country: region 'Siria' is not in TR", r["failed"])

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
        self.assertIn("country: region 'Nowhere' is not in IT", r["failed"])

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


class DeriveTextSaysTest(unittest.TestCase):
    def test_only_explicit_claims_that_disagree(self):
        its = ["Ad Fictiochia di Fictia, nell’odierna Turchia", "Ad Fictiochia di Fictia, oggi in Turchia",
               "Ad Fictiochia in Siria"]
        self.assertEqual(bg.derive_text_says(its, "TR"), [])
        self.assertEqual(bg.derive_text_says(its, "SY"), [
            {"country": "TR", "it": its[0]}, {"country": "TR", "it": its[1]}])


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
            # FR differs from the explicit "nell’odierna Germania": text_says is required
            ("Fictópoli", {"wikidata": "Q1", "label": "x", "country": "FR", "status": "reviewed"}, "text_says"),
        ]
        for la, entry, word in cases:
            errors = bg.validate({la: entry}, INDEX)
            self.assertTrue(errors and word in errors[0], (la, entry, errors))

    def test_text_says_absent_when_the_text_agrees(self):
        good = {"Fictópoli": {"wikidata": "Q1", "label": "x", "country": "DE", "status": "reviewed"}}
        self.assertEqual(bg.validate(good, INDEX), [])

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
        self.assertEqual(gaz, {"Fictopoli": {"wikidata": "Q1", "label": "Q1", "country": "IT", "status": "auto"}})
        [op] = review["operations"]
        self.assertEqual(op["op"], "resolve_place")
        self.assertEqual(op["id"], "Altropoli")
        self.assertEqual(op["la"], "Altropoli")
        self.assertEqual(op["it"], ["A Altropoli"])
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q2", "Q3"])
        self.assertIsNone(op["decision"])
        self.assertEqual(review["schema"], "crmedr-changeset/v1")
        self.assertEqual(review["base"], {"edition": "martyrologium_romanum_2004", "registry": "data/places.json"})

    def test_existing_keys_untouched(self):
        gaz = {"Fictopoli": {"wikidata": "Q42", "label": "Other", "country": "FY", "status": "reviewed"}}
        review = bg.new_changeset([])
        bg.propose(gaz, review, self.index, self.client)
        self.assertEqual(gaz["Fictopoli"]["wikidata"], "Q42")
        self.assertNotIn("Fictopoli", [op["id"] for op in review["operations"]])

    def test_suggestions_kept_on_rerun(self):
        review = bg.new_changeset([{"op": "resolve_place", "id": "Altropoli", "candidates": [],
                                    "suggested": {"wikidata": "Q3", "country": "IT"},
                                    "reasoning": "r", "confidence": "high"}])
        bg.propose({}, review, self.index, self.client)
        [op] = review["operations"]
        self.assertEqual(op["suggested"], {"wikidata": "Q3", "country": "IT"})
        self.assertEqual((op["reasoning"], op["confidence"]), ("r", "high"))
        self.assertEqual(len(op["candidates"]), 2)

    def test_a_kept_suggestion_loses_its_text_says(self):
        review = bg.new_changeset([{"op": "resolve_place", "id": "Altropoli", "candidates": [],
                                    "suggested": {"wikidata": "Q3", "country": "IT",
                                                  "text_says": [{"country": "SY", "it": "A Altropoli"}]}}])
        bg.propose({}, review, self.index, self.client)
        self.assertEqual(review["operations"][0]["suggested"], {"wikidata": "Q3", "country": "IT"})

    def test_disagreeing_suggestion_keeps_the_place_queued(self):
        review = bg.new_changeset([{"op": "resolve_place", "id": "Fictopoli", "candidates": [],
                                    "suggested": {"wikidata": "Q9", "country": "IT"},
                                    "reasoning": "r", "confidence": "high"}])
        gaz = {}
        bg.propose(gaz, review, self.index, self.client)
        self.assertNotIn("Fictopoli", gaz)
        op = next(o for o in review["operations"] if o["id"] == "Fictopoli")
        self.assertEqual(op["suggested"]["wikidata"], "Q9")
        self.assertIn("the suggestion (Q9) disagrees with the item that passes every rule (Q1)", op["failed"])

    def test_agreeing_suggestion_lets_the_place_become_auto(self):
        review = bg.new_changeset([{"op": "resolve_place", "id": "Fictopoli", "candidates": [],
                                    "suggested": {"wikidata": "Q1", "country": "IT"}}])
        gaz = {}
        bg.propose(gaz, review, self.index, self.client)
        self.assertEqual(gaz["Fictopoli"]["status"], "auto")

    def test_network_failure_leaves_place_unprocessed(self):
        client = FakeClient(self.client.by_text, fail_on={"Altropoli"})
        gaz, review = {}, bg.new_changeset([])
        failed = bg.propose(gaz, review, self.index, client)
        self.assertEqual(failed, [("Altropoli", "boom")])
        self.assertIn("Fictopoli", gaz)
        self.assertNotIn("Altropoli", gaz)
        self.assertEqual(review["operations"], [])

    def test_forced_review_is_never_auto(self):
        gaz, review = {}, bg.new_changeset([])
        bg.propose(gaz, review, self.index, self.client, force_review={"Fictopoli": "the Latin names another Fictopoli"})
        self.assertNotIn("Fictopoli", gaz)
        op = next(o for o in review["operations"] if o["id"] == "Fictopoli")
        self.assertIn("forced review: the Latin names another Fictopoli", op["failed"])
        self.assertEqual(op["candidates"][0]["wikidata"], "Q1")

    def test_force_review_keys_are_places(self):
        self.assertTrue(set(bg.FORCE_REVIEW) <= set(bg.load_state(REPO)[2]))

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
                                           suggested={"wikidata": "Q1", "country": "FR"}))
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

    def test_text_says_is_derived_not_taken_from_the_decision(self):
        _, gaz, _ = self.run_apply(op("Fictópoli", "edit", [self.c1, self.c2],
                                      suggested={"wikidata": "Q1", "country": "FR", "text_says": []},
                                      edited={"wikidata": "Q1", "country": "IT", "text_says": []}))
        self.assertEqual(gaz["Fictópoli"]["text_says"], self.says)

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
        for word in ("no such item", "not an ISO", "confidence"):
            self.assertIn(word, text)
        self.assertTrue(any("differs from the item's country FR" in w for w in warnings))




class CommittedGazetteerTest(unittest.TestCase):
    def test_committed_files_validate(self):
        if not (REPO / "data" / "gazetteer.json").exists():
            self.skipTest("no data/gazetteer.json yet")
        gazetteer, review, index = bg.load_state(REPO)
        self.assertEqual(bg.validate(gazetteer, index, review["operations"]), [])
        self.assertEqual(set(gazetteer) | {op["id"] for op in review["operations"]}, set(index))


class PruneNonPlacesTest(unittest.TestCase):
    """Candidates that are neither a place type nor located (films, songs,
    people, surnames, schools named after a city) are not offered for review."""

    def test_evaluate_does_not_publish_non_places_without_coordinates(self):
        film = cand("Q2", it=["Fictopoli"], place=False)
        university = dict(cand("Q3", it=["Fictopoli"], place=False), coords=[45.0, 9.0])
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [cand("Q1", it=["Fictopoli"]), film, university],
                        regions)
        self.assertEqual({c["wikidata"] for c in r["candidates"]}, {"Q1", "Q3"})

    def test_non_places_do_not_use_up_the_candidate_slots(self):
        junk = [cand(f"Q{i}", it=["Fictopoli"], place=False) for i in range(20)]
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), junk + [cand("Q99", it=["Altro"])], regions)
        self.assertEqual([c["wikidata"] for c in r["candidates"]], ["Q99"])

    def test_diagnosis_still_sees_pruned_candidates(self):
        r = bg.evaluate("Fictópoli", item("A Fictopoli"), [cand("Q2", it=["Fictopoli"], place=False)], regions)
        self.assertEqual(r["candidates"], [])
        self.assertIn("type: the item is not a place", r["failed"])

    def test_propose_keeps_the_suggested_candidate_even_if_not_a_place(self):
        province = cand("Q9", it=["Altropoli"], place=False)
        client = FakeClient({"Altropoli": [cand("Q2", it=["Altropoli"]), province]})
        index = index_of(Altropoli=["A Altropoli"])
        review = bg.new_changeset([dict(op("Altropoli", None, [province]),
                                        suggested={"wikidata": "Q9", "country": "IT"})])
        bg.propose({}, review, index, client)
        [o] = review["operations"]
        self.assertIn("Q9", [c["wikidata"] for c in o["candidates"]])

    def test_prune_queue_keeps_places_located_items_and_the_suggestion(self):
        place = bg.published(cand("Q1"), ["it", "type"])
        located = dict(bg.published(cand("Q3", place=False), ["it"]), coords=[45.0, 9.0])
        film = bg.published(cand("Q2", place=False), ["it"])
        province = bg.published(cand("Q9", place=False), [])
        review = bg.new_changeset([
            dict(op("Fictópoli", None), candidates=[place, film, located]),
            dict(op("Altrópoli", None), candidates=[province, film], suggested={"wikidata": "Q9", "country": "IT"}),
        ])
        self.assertEqual(bg.prune_queue(review), 2)
        self.assertEqual([[c["wikidata"] for c in o["candidates"]] for o in review["operations"]],
                         [["Q1", "Q3"], ["Q9"]])


class SuggestionEvidenceTest(unittest.TestCase):
    """verify-suggestions evaluates the suggested item instead of publishing it
    with no evidence, so the reviewer sees why it is (or is not) plausible."""

    def setUp(self):
        self.client = FakeClient({"x": [cand("Q7", it=["Fictopoli"], la=["Fictopolis"], country="DE")]})

    def suggested_op(self, candidates):
        o = op("Fictópoli", None, suggested={"wikidata": "Q7", "country": "DE"})
        o["candidates"], o["confidence"] = candidates, "high"
        return o

    def evidence(self, review):
        [c] = [c for c in review["operations"][0]["candidates"] if c["wikidata"] == "Q7"]
        return c["evidence"]

    def test_appended_suggestion_is_evaluated(self):
        review = bg.new_changeset([self.suggested_op([])])
        self.assertEqual(bg.verify_suggestions(review, INDEX, self.client), ([], []))
        self.assertEqual(self.evidence(review), ["it", "la", "country", "type"])

    def test_suggestion_with_empty_evidence_is_backfilled_in_place(self):
        other = bg.published(cand("Q1"), ["type"])
        stale = bg.published(cand("Q7", country="DE"), [])
        review = bg.new_changeset([self.suggested_op([other, stale])])
        bg.verify_suggestions(review, INDEX, self.client)
        self.assertEqual([c["wikidata"] for c in review["operations"][0]["candidates"]], ["Q1", "Q7"])
        self.assertEqual(self.evidence(review), ["it", "la", "country", "type"])

    def test_suggestion_with_evidence_is_left_alone(self):
        kept = bg.published(cand("Q7", country="DE"), ["type"])
        review = bg.new_changeset([self.suggested_op([kept])])
        bg.verify_suggestions(review, INDEX, self.client)
        self.assertEqual(self.evidence(review), ["type"])
