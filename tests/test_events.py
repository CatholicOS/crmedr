import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def read(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class EventsTest(unittest.TestCase):
    def setUp(self):
        self.events = {k: v for k, v in read("events_curated.json").items() if not k.startswith("$")}
        self.qids = {e["qid"] for items in self.events.values() for e in items}

    def test_no_eulogy_lists_a_council_among_its_places(self):
        # A council's phrase resolves to the city where it met: 1 January lists Ephesus, not the council.
        entries = {e["id"]: e for e in read("martyrology_ids.json")["entries"]}
        councils = {(mrid, p.get("wikidata")) for mrid, e in entries.items() for p in e.get("places", [])
                    if p.get("wikidata") in self.qids}
        self.assertEqual(councils, set())
        self.assertIn("Q47611", [p.get("wikidata") for p in entries["mr:0101-maria-dei-genetrix"]["places"]])

    def test_every_curated_event_is_marked_in_both_editions(self):
        mentions = read("mentions.json")["editions"]
        for edition, lang in (("martyrologium_romanum_2004", "la"), ("martyrologium_romanum_2004_it_IT", "it")):
            for mrid, items in self.events.items():
                marked = sorted(m["qid"] for m in mentions[edition].get(mrid, []) if m["kind"] == "event")
                self.assertEqual(marked, sorted(e["qid"] for e in items if e.get(lang)), f"{edition} {mrid}")

    def test_each_event_is_curated_with_both_phrases_and_an_item(self):
        for mrid, items in self.events.items():
            for e in items:
                self.assertTrue(e.get("la") and e.get("it") and e.get("qid", "").startswith("Q"), (mrid, e))


if __name__ == "__main__":
    unittest.main()
