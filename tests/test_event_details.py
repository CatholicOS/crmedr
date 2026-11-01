import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import event_details as ed  # noqa: E402


def time(t, precision=9):
    return {"mainsnak": {"datavalue": {"value": {"time": t, "precision": precision}}}, "rank": "normal"}


def item(qid):
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}, "rank": "normal"}


EPHESUS = {
    "labels": {"en": {"value": "First Council of Ephesus"}, "it": {"value": "Concilio di Efeso"},
               "la": {"value": "Concilium Ephesinum"}, "xx": {"value": "?"}},
    "descriptions": {"en": {"value": "ecumenical council in Ephesus in 431"}},
    "claims": {"P580": [time("+0431-06-22T00:00:00Z", 11)], "P582": [time("+0431-07-31T00:00:00Z", 11)],
               "P276": [item("Q47611")]},
    "sitelinks": {"enwiki": {"title": "Council of Ephesus"}, "itwiki": {"title": "Concilio di Efeso"}},
}


class EventDetailsTest(unittest.TestCase):
    def test_labels_description_dates_place_and_wikipedia(self):
        self.assertEqual(ed.summarize(EPHESUS), {
            "label": {"la": "Concilium Ephesinum", "en": "First Council of Ephesus", "it": "Concilio di Efeso"},
            "description": {"en": "ecumenical council in Ephesus in 431"},
            "start": {"year": 431, "precision": "year", "circa": False},
            "end": {"year": 431, "precision": "year", "circa": False},
            "place": "Q47611",
            "wikipedia": {"en": "Council of Ephesus", "it": "Concilio di Efeso"},
        })

    def test_a_point_in_time_is_its_start_and_end(self):
        raw = {"claims": {"P585": [time("+1095-11-18T00:00:00Z", 11)]}}
        out = ed.summarize(raw)
        self.assertEqual((out["start"]["year"], out["end"]["year"], out["place"]), (1095, 1095, None))

    def test_the_events_of_the_mentions_each_once_by_number(self):
        doc = {"editions": {"a": {"mr:x": [{"kind": "event", "qid": "Q184332"}, {"kind": "place", "qid": "Q47611"}]},
                            "b": {"mr:y": [{"kind": "event", "qid": "Q10951"}, {"kind": "event", "qid": "Q184332"}]}}}
        self.assertEqual(ed.event_qids(doc), ["Q10951", "Q184332"])

    def test_render_has_a_comment_and_sorts_by_number(self):
        doc = json.loads(ed.render_json({"Q184332": {"x": 1}, "Q10951": {"x": 2}}))
        self.assertEqual(list(doc), ["$comment", "Q10951", "Q184332"])


if __name__ == "__main__":
    unittest.main()
