import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_persons import with_mentioned  # noqa: E402


def mark(where="text", start=0, end=8, check="0123abcd"):
    return {"where": where, "start": start, "end": end, "check": check}


def person(name="Ambrosius", la=None, it=(), **kw):
    """A mentioned person as data/persons_mentioned.json holds it: marks, never the printed words."""
    return {"name": name, "where": "text", **kw,
            "marks": {"la": [mark()] if la is None else la, **({"it": list(it)} if it is not None else {})}}


class WithMentionedTest(unittest.TestCase):
    def test_mentioned_persons_are_added_with_their_role(self):
        persons = {"mr:0119-bassianus-laudis-pompeiae": [{"name": "Bassianus", "where": "text"}]}
        mentioned = {"mr:0119-bassianus-laudis-pompeiae": [person(it=[mark()])]}
        self.assertEqual(with_mentioned(persons, mentioned), [])
        self.assertEqual(persons["mr:0119-bassianus-laudis-pompeiae"][1],
                         {"name": "Ambrosius", "where": "text", "role": "mentioned"})

    def test_a_eulogy_without_persons_of_its_own_still_gets_its_mentioned_ones(self):
        persons = {}
        self.assertEqual(with_mentioned(persons, {"mr:x": [person()]}), [])
        self.assertEqual(persons, {"mr:x": [{"name": "Ambrosius", "where": "text", "role": "mentioned"}]})

    def test_a_mentioned_person_needs_a_new_name_or_n(self):
        persons = {"mr:x": [{"name": "Zeno", "where": "text"}]}
        errs = with_mentioned(persons, {"mr:x": [person("Zeno")]})
        self.assertIn("mr:x: 'Zeno' is already a person of the eulogy; give the mentioned one n", errs[0])
        self.assertEqual(with_mentioned({"mr:x": [{"name": "Zeno", "where": "text"}]}, {"mr:x": [person("Zeno", n=2)]}),
                         [])

    def test_a_mentioned_person_needs_a_latin_mark(self):
        errs = with_mentioned({}, {"mr:x": [person(la=[])]})
        self.assertEqual(errs, ["mr:x: 'Ambrosius' has no Latin mark (marks.la)"])

    def test_the_italian_marks_must_be_listed(self):
        # CodeRabbit #271: [] means the Italian does not name the person; no list is an error.
        errs = with_mentioned({}, {"mr:x": [person(it=None)]})
        self.assertEqual(errs, ["mr:x: 'Ambrosius' has no marks.it; list its Italian marks, or [] if the Italian "
                                "does not name them"])

    def test_a_text_and_a_footnote_mark_are_one_person(self):
        # A mark names its own where; the person's where stays the first printing.
        persons = {}
        mentioned = {"mr:x": [person(la=[mark(), mark({"footnote": 1}, 5, 14)])]}
        self.assertEqual(with_mentioned(persons, mentioned), [])
        self.assertEqual(persons, {"mr:x": [{"name": "Ambrosius", "where": "text", "role": "mentioned"}]})

    def test_printed_words_are_never_stored(self):
        # CodeRabbit #271 (AGENTS.md): a person's printed forms are read to check them, never stored.
        for bad in ({"la": ["Ambrósio"]}, {"it": ["Ambrogio"]}, {"marks": {"la": ["Ambrósio"], "it": []}},
                    {"marks": {"la": [mark() | {"form": "Ambrósio"}], "it": []}}):
            errs = with_mentioned({}, {"mr:x": [person() | bad]})
            self.assertTrue(errs and all(e.startswith("mr:x: 'Ambrosius' has ") for e in errs), (bad, errs))

    def test_malformed_wheres_and_marks_are_errors(self):
        for bad, message in (
                ({"where": "body"}, "mr:x: 'Ambrosius' has a malformed where 'body'"),
                ({"marks": {"la": [mark(start=3, end=3)], "it": []}},
                 "mr:x: 'Ambrosius' has a malformed la mark {'where': 'text', 'start': 3, 'end': 3, "
                 "'check': '0123abcd'}"),
                ({"marks": {"la": [mark()], "it": [mark({"footnote": 0})]}},
                 "mr:x: 'Ambrosius' has a malformed it mark {'where': {'footnote': 0}, 'start': 0, 'end': 8, "
                 "'check': '0123abcd'}"),
                ({"marks": {"la": [mark(check="Ambrósio")], "it": []}},
                 "mr:x: 'Ambrosius' has a malformed la mark {'where': 'text', 'start': 0, 'end': 8, "
                 "'check': 'Ambrósio'}"),
                ({"marks": "x"}, "mr:x: 'Ambrosius' has malformed marks 'x'")):
            persons = {}
            self.assertEqual(with_mentioned(persons, {"mr:x": [person() | bad]}), [message], bad)
            self.assertEqual(persons, {}, bad)


if __name__ == "__main__":
    unittest.main()
