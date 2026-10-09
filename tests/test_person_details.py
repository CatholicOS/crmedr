import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import wikidata as wd  # noqa: E402
import person_details as pd  # noqa: E402


def claim(time, precision=9, rank="normal", circa=False):
    c = {"rank": rank, "mainsnak": {"datavalue": {"value": {"time": time, "precision": precision}}}}
    if circa:
        c["qualifiers"] = {"P1480": [{"datavalue": {"value": {"id": "Q5727902"}}}]}
    return c


def life(time, precision=9, circa=False):
    return wd.life_date({"P569": [claim(time, precision, circa=circa)]}, "P569")


class LifeDateTest(unittest.TestCase):
    def test_a_day_or_a_year_is_a_year(self):
        self.assertEqual(life("+1597-02-05T00:00:00Z", 11), {"year": 1597, "precision": "year", "circa": False})
        self.assertEqual(life("+0329-00-00T00:00:00Z"), {"year": 329, "precision": "year", "circa": False})

    def test_decade_and_century(self):
        self.assertEqual(life("+0330-00-00T00:00:00Z", 8)["precision"], "decade")
        self.assertEqual(life("+0400-00-00T00:00:00Z", 7), {"year": 400, "precision": "century", "circa": False})

    def test_coarser_than_a_century_is_unknown(self):
        self.assertIsNone(life("+1000-00-00T00:00:00Z", 6))

    def test_circa(self):
        self.assertTrue(life("+0329-00-00T00:00:00Z", circa=True)["circa"])

    def test_bce_is_negative(self):
        self.assertEqual(life("-0100-00-00T00:00:00Z")["year"], -100)

    def test_preferred_first_deprecated_never(self):
        claims = {"P570": [claim("+0400-00-00T00:00:00Z", rank="deprecated"), claim("+0379-00-00T00:00:00Z"),
                           claim("+0378-00-00T00:00:00Z", rank="preferred")]}
        self.assertEqual(wd.life_date(claims, "P570")["year"], 378)

    def test_the_old_date_helper_is_unchanged(self):
        self.assertEqual(wd._date({"P569": [claim("+0329-00-00T00:00:00Z")]}, "P569"), "0329")

    def test_undated(self):
        self.assertIsNone(wd.life_date({}, "P569"))
        self.assertIsNone(wd.life_date({"P569": [{"mainsnak": {"snaktype": "somevalue"}}]}, "P569"))


class DetailsClientTest(unittest.TestCase):
    def test_entities_and_commons(self):
        urls = []

        def fetch(url):
            urls.append(url)
            if url.startswith(wd.COMMONS_API):
                return {"query": {"normalized": [{"from": "File:Basil_of_Caesarea.jpg",
                                                  "to": "File:Basil of Caesarea.jpg"}],
                                  "pages": {"1": {"title": "File:Basil of Caesarea.jpg", "imageinfo": [
                                      {"extmetadata": {"LicenseShortName": {"value": "Public domain"}}}]},
                                            "-1": {"title": "File:Gone.jpg", "missing": ""}}}}
            return {"entities": {"Q19546": {"id": "Q19546", "descriptions": {}, "claims": {}, "sitelinks": {}},
                                 "Q404": {"id": "Q404", "missing": ""}}}

        with tempfile.TemporaryDirectory() as d:
            client = wd.Wikidata(Path(d), fetch=fetch)
            self.assertEqual(list(client.details_entities(["Q19546", "Q404"])), ["Q19546"])
            self.assertIn("sitefilter=enwiki%7Citwiki%7Cfrwiki%7Cdewiki%7Ceswiki%7Cptwiki", urls[0])
            self.assertIn("props=descriptions%7Cclaims%7Csitelinks", urls[0])
            self.assertEqual(client.commons_files(["Basil_of_Caesarea.jpg", "Gone.jpg"]),
                             {"Basil_of_Caesarea.jpg": {"LicenseShortName": {"value": "Public domain"}}})

    def test_a_renamed_file_is_mapped_back_to_the_name_as_given(self):
        urls = []

        def fetch(url):
            urls.append(url)
            return {"query": {"redirects": [{"from": "Old.jpg", "to": "New.jpg"}],
                              "pages": {"7": {"title": "File:New.jpg", "imageinfo": [
                                  {"extmetadata": {"LicenseShortName": {"value": "CC0"}}}]}}}}

        with tempfile.TemporaryDirectory() as d:
            client = wd.Wikidata(Path(d), fetch=fetch)
            self.assertEqual(client.commons_files(["Old.jpg"]), {"Old.jpg": {"LicenseShortName": {"value": "CC0"}}})
            self.assertIn("redirects=1", urls[0])


RAW = {
    "id": "Q19546",
    "descriptions": {"en": {"value": "Greek bishop"}, "la": {"value": "episcopus"}},
    "claims": {"P569": [claim("+0329-00-00T00:00:00Z", circa=True)],
               "P570": [claim("+0379-01-01T00:00:00Z", 11)],
               "P18": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "Basil.jpg"}}}]},
    "sitelinks": {"enwiki": {"title": "Basil of Caesarea"}, "lawiki": {"title": "Basilius Magnus"}},
}
CREDIT = {"Artist": {"value": "<a href='https://x'>Unknown</a> painter"},
          "LicenseShortName": {"value": "Public domain"}}


class SummarizeTest(unittest.TestCase):
    def test_details_in_the_interface_languages_only(self):
        self.assertEqual(pd.summarize_details(RAW, {"Basil.jpg": CREDIT}), {
            "description": {"en": "Greek bishop"},
            "born": {"year": 329, "precision": "year", "circa": True},
            "died": {"year": 379, "precision": "year", "circa": False},
            "image": {"file": "Basil.jpg", "author": "Unknown painter", "license": "Public domain",
                      "license_url": None},
            "wikipedia": {"en": "Basil of Caesarea"},
        })

    def test_no_license_no_image(self):
        self.assertIsNone(pd.summarize_details(RAW, {"Basil.jpg": {"Artist": {"value": "X"}}})["image"])
        self.assertIsNone(pd.summarize_details(RAW, {})["image"])

    def test_a_bare_item(self):
        self.assertEqual(pd.summarize_details({"id": "Q1"}, {}),
                         {"description": {}, "born": None, "died": None, "image": None, "wikipedia": {}})


class BuildTest(unittest.TestCase):
    def test_person_qids(self):
        doc = {"editions": {"ed": {"mr:x": [{"kind": "person", "qid": "Q19546"}, {"kind": "person", "qid": None},
                                            {"kind": "place", "qid": "Q220"}, {"kind": "person", "qid": "Q9"}]}}}
        self.assertEqual(pd.person_qids(doc), ["Q9", "Q19546"])

    def test_build_skips_missing_items_and_asks_commons_once(self):
        class Client:
            files = None

            def details_entities(self, qids):
                return {"Q19546": RAW}

            def commons_files(self, files):
                self.files = files
                return {"Basil.jpg": CREDIT}

        client = Client()
        out = pd.build(client, ["Q19546", "Q404"])
        self.assertEqual(list(out), ["Q19546"])
        self.assertEqual(client.files, ["Basil.jpg"])
        self.assertEqual(out["Q19546"]["image"]["license"], "Public domain")

    def test_render_json(self):
        doc = json.loads(pd.render_json({"Q20": {}, "Q3": {}}))
        self.assertEqual(list(doc), ["$comment", "Q3", "Q20"])


if __name__ == "__main__":
    unittest.main()
