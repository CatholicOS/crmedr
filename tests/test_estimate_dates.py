import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dates_jev as dj  # noqa: E402
import estimate_dates as ed  # noqa: E402
import mentions_jev as mj  # noqa: E402


def answer(pick, p):
    probs = {o: 0.0 for o in dj.OPTIONS}
    probs[pick] = p
    return {"answers": {"century": {"type": "choice", "choice": pick, "probabilities": probs,
                                    "confidence": p}}, "model": dj.MODEL}


class FakeClient:
    def __init__(self, picks, key="k", cached=True):
        self.picks, self.key, self._cached, self.asked = picks, key, cached, []

    def cached(self, body):
        return self._cached

    def ask(self, body):
        if not self.key and not self._cached:
            raise mj.TypeSafeError("no TypeSafe key")
        mid = body["state"]["latin_clause"]
        self.asked.append(mid)
        return answer(*self.picks[mid])


# One-sentence eulogies: the opening place is dropped, so the clause sent is the ID.
TEXTS = {"la": {m: f"Romae, {m}" for m in ("mr:0101-a", "mr:0101-b", "mr:0101-c")}, "en": {}}


class RowsTest(unittest.TestCase):
    def test_calibration_table(self):
        client = FakeClient({"mr:0101-a": ("c4", 0.95), "mr:0101-b": ("c5", 0.6), "mr:0101-c": ("c9", 0.92)})
        rows = ed.rows_for(sorted(TEXTS["la"]), TEXTS, {}, {}, client)
        truths = {"mr:0101-a": {"year": 304}, "mr:0101-b": {"year": 304}, "mr:0101-c": {"year": 304}}
        table = ed.calibration(rows, truths, [0.5, 0.9])
        self.assertIn("≥0.50: 3 estimated (100%), 1 right (33%), 2 within one century (67%)", table)
        self.assertIn("≥0.90: 2 estimated (67%), 1 right (50%), 1 within one century (50%)", table)
        self.assertIn("mr:0101-c c9 p=0.92 died 304", table)

    def test_estimate_scope(self):
        dates = {"mr:0101-a": {"year": 304, "source": "wikidata"}, "mr:0101-b": {"year": 431, "source": "curated"},
                 "mr:0101-c": {"to": 1630, "source": "edition"}}
        self.assertEqual(ed.estimate_ids({"mr:0101-a", "mr:0101-b", "mr:0101-c", "mr:0101-d"}, dates),
                         ["mr:0101-c", "mr:0101-d"])

    def test_failed_request_keeps_the_previous_estimate(self):
        previous = {"mr:0101-a": {"century": "c4", "probability": 0.9, "confidence": 0.9},
                    "mr:0101-b": {"century": "c5", "probability": 0.9, "confidence": 0.9}}
        rows = {"mr:0101-a": None, "mr:0101-b": None, "mr:0101-c": {"century": "c9", "probability": 0.8,
                                                                    "confidence": 0.8}}
        self.assertEqual(ed.merged_estimates(previous, rows, failed={"mr:0101-a"}),
                         {"mr:0101-a": previous["mr:0101-a"], "mr:0101-c": rows["mr:0101-c"]})

    def test_failures_are_collected(self):
        class Failing(FakeClient):
            def ask(self, body):
                raise mj.TypeSafeError("HTTP 503")
        failed = set()
        rows = ed.rows_for(["mr:0101-a"], TEXTS, {}, {}, Failing({}), failed)
        self.assertEqual((rows, failed), ({"mr:0101-a": None}, {"mr:0101-a"}))

    def test_no_key_stops(self):
        client = FakeClient({}, key=None, cached=False)
        with self.assertRaises(mj.TypeSafeError):
            ed.require_key(["mr:0101-a"], TEXTS, {}, {}, client)
        self.assertEqual(client.asked, [])


if __name__ == "__main__":
    unittest.main()
