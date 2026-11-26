import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_redirects as cr  # noqa: E402


class QidsInTest(unittest.TestCase):
    def test_values_and_keys_not_prose(self):
        data = {"Q1": ["mr:0101-x"], "mr:0605-x": {"Illidius": {"wikidata": "Q653804",
                "note": "Q653804 was merged into Q17393639"}}, "list": ["Q5", "Q12a", "q7", "Q0"]}
        self.assertEqual(cr.qids_in(data), {"Q1", "Q653804", "Q5"})


class ClassifyTest(unittest.TestCase):
    def test_redirect_missing_and_live(self):
        entities = {
            "Q653804": {"id": "Q17393639", "redirects": {"from": "Q653804", "to": "Q17393639"}},
            "Q99": {"id": "Q99", "missing": ""},
            "Q5": {"id": "Q5", "type": "item"},
        }
        self.assertEqual(cr.classify(["Q653804", "Q99", "Q5", "Q6"], entities), {
            "Q653804": {"status": "redirect", "to": "Q17393639"},
            "Q99": {"status": "missing"},
        })

    def test_entity_answered_under_its_target_id(self):
        self.assertEqual(cr.classify(["Q2"], {"Q2": {"id": "Q3"}}), {"Q2": {"status": "redirect", "to": "Q3"}})


class FetchTest(unittest.TestCase):
    def test_batches_of_fifty(self):
        asked = []

        def get(url):
            ids = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["ids"][0].split("|")
            asked.append(ids)
            return {"entities": {q: ({"id": q, "missing": ""} if q == "Q60" else {"id": q}) for q in ids}}

        stale = cr.fetch([f"Q{i}" for i in range(1, 121)], get=get)
        self.assertEqual([len(b) for b in asked], [50, 50, 20])
        self.assertEqual(stale, {"Q60": {"status": "missing"}})


class ScanTest(unittest.TestCase):
    def test_skips_review_changesets_and_reports_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            (root / "i18n").mkdir()
            (root / "data" / "person_items.json").write_text(json.dumps({"a": {"wikidata": "Q653804"}}))
            (root / "data" / "person_items_review.json").write_text(json.dumps({"c": "Q131237866"}))
            (root / "i18n" / "la.json").write_text(json.dumps({"Q653804": "Illidius"}))
            where = cr.scan(root)
        self.assertEqual(where, {"Q653804": ["data/person_items.json", "i18n/la.json"]})
        self.assertEqual(cr.report({"Q653804": {"status": "redirect", "to": "Q17393639"}}, where),
                         ["Q653804 redirects to Q17393639: data/person_items.json, i18n/la.json"])


if __name__ == "__main__":
    unittest.main()
