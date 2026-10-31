import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_eulogy_items as b  # noqa: E402


def P(name, **kw):
    return {"name": name, "where": "text", **kw}


class ClassTest(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(b.eulogy_class([P("Felix")], "dies_natalis"), "single")
        self.assertEqual(b.eulogy_class([P("Felix"), P("Willibrordus", role="mentioned")], "dies_natalis"), "single")
        self.assertEqual(b.eulogy_class([P("Ioseph")], "celebratio"), "hand")
        self.assertEqual(b.eulogy_class([], "dedicatio"), "hand")
        self.assertEqual(b.eulogy_class([P("Felix"), P("Felix", n=2)], "dies_natalis"), "several")


class CheckTest(unittest.TestCase):
    IDS = {"mr:0101-a", "mr:0101-b", "mr:0101-c"}
    CLASSES = {"mr:0101-a": "single", "mr:0101-b": "several", "mr:0101-c": "hand"}
    OK = {"wikidata": "Q1", "kind": "group", "status": "reviewed"}

    def test_check(self):
        self.assertEqual(b.check({"mr:0101-b": self.OK}, self.IDS, self.CLASSES), [])
        for items, needle in [({"mr:0101-a": self.OK}, "mr:0101-a"),                      # single without a note
                              ({"mr:0101-gone": self.OK}, "mr:0101-gone"),                 # not current
                              ({"mr:0101-b": {**self.OK, "kind": "title"}}, "kind"),
                              ({"mr:0101-b": {**self.OK, "wikidata": "X1"}}, "wikidata"),
                              ({"mr:0101-b": {**self.OK, "status": "maybe"}}, "status"),
                              ({"mr:0101-c": {"wikidata": None, "status": "unresolved"}}, "note"),
                              ({"mr:0101-b": {"wikidata": None, "kind": "group", "status": "auto"}}, "auto")]:
            with self.subTest(items=items):
                self.assertTrue(any(needle in e for e in b.check(items, self.IDS, self.CLASSES)))

    def test_a_single_person_eulogy_with_a_curator_note_passes(self):
        noted = {"mr:0101-a": {**self.OK, "note": "curator: why"}}
        self.assertEqual(b.check(noted, self.IDS, self.CLASSES), [])

    def test_the_title_decision_passes(self):
        title = {"mr:0101-c": {"wikidata": None, "kind": None, "status": "reviewed",
                               "note": "the mention links the title"}}
        self.assertEqual(b.check(title, self.IDS, self.CLASSES), [])

    def test_committed_items_are_valid(self):
        self.assertEqual(b.main(["check", str(ROOT)]), 0)


if __name__ == "__main__":
    unittest.main()
