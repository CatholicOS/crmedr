import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dates_jev as dj  # noqa: E402

LA = ("Romæ, via Appia, sancti Fictitii, epíscopi et mártyris, qui sub Diocletiáno imperatóre "
      "passus est. Eius corpus póstea translátum est.")
EN = "At Rome on the Appian Way, Saint Fictitius, bishop and martyr, who suffered under Diocletian."


def answer(pick, p=0.8):
    probs = {o: 0.0 for o in dj.OPTIONS}
    probs[pick] = p
    return {"type": "choice", "choice": pick, "probabilities": probs, "confidence": 0.7}


class CenturyTest(unittest.TestCase):
    def test_century_ranges(self):
        self.assertEqual(dj.century_range("c1"), {"from": 1, "to": 100})
        self.assertEqual(dj.century_range("c4"), {"from": 301, "to": 400})
        self.assertEqual(dj.century_range("c21"), {"from": 2001, "to": 2100})
        self.assertEqual(dj.century_range("bc"), {"to": -1})
        self.assertIsNone(dj.century_range("cannot_tell"))

    def test_agrees(self):
        self.assertEqual(dj.agrees("c4", {"year": 304}), (True, True))
        self.assertEqual(dj.agrees("c5", {"year": 304}), (False, True))
        self.assertEqual(dj.agrees("c7", {"year": 304}), (False, False))
        self.assertEqual(dj.agrees("bc", {"year": -50}), (True, True))
        self.assertEqual(dj.agrees("c4", {"from": 390, "to": 410}), (True, True))
        self.assertEqual(dj.agrees("cannot_tell", {"year": 304}), (False, False))


class RequestTest(unittest.TestCase):
    def test_request_shape(self):
        body = dj.request_for(LA, EN, "dies_natalis", 1630)
        self.assertEqual(body["model"], dj.MODEL)
        self.assertEqual(set(body["state"]), {"latin_clause", "english_clause", "typology", "printed_by"})
        self.assertEqual(body["state"]["latin_clause"],
                         "Romæ, via Appia, sancti Fictitii, epíscopi et mártyris, qui sub Diocletiáno "
                         "imperatóre passus est.")
        self.assertEqual(body["state"]["printed_by"], 1630)
        q = body["questions"]["century"]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(list(q["criteria"]), dj.OPTIONS)
        self.assertEqual(len(dj.OPTIONS), 23)

    def test_long_clause_is_cut(self):
        body = dj.request_for("Romæ " + "x" * 900 + ".", None, None, None)
        self.assertLessEqual(len(body["state"]["latin_clause"]), 400)

    def test_request_without_english(self):
        self.assertEqual(dj.request_for(LA, None, None, None)["state"]["english_clause"], "")

    def test_no_latin_no_request(self):
        self.assertIsNone(dj.request_for("", EN, None, None))


class EstimateTest(unittest.TestCase):
    def test_estimate_of(self):
        self.assertEqual(dj.estimate_of(answer("c4")), {"century": "c4", "probability": 0.8, "confidence": 0.7})

    def test_bad_answer(self):
        self.assertIsNone(dj.estimate_of({"type": "choice", "choice": "c99", "probabilities": {"c99": 1}}))
        self.assertIsNone(dj.estimate_of(None))
        self.assertIsNone(dj.estimate_of({"type": "noul", "probability": 0.9}))


if __name__ == "__main__":
    unittest.main()
