import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_persons import with_mentioned  # noqa: E402


class WithMentionedTest(unittest.TestCase):
    def test_mentioned_persons_are_added_with_their_role(self):
        persons = {"mr:0119-bassianus-laudis-pompeiae": [{"name": "Bassianus", "where": "text"}]}
        mentioned = {"mr:0119-bassianus-laudis-pompeiae": [
            {"name": "Ambrosius", "where": "text", "la": ["Ambrósio Mediolanénsi"], "it": ["Ambrogio di Milano"]}]}
        self.assertEqual(with_mentioned(persons, mentioned), [])
        self.assertEqual(persons["mr:0119-bassianus-laudis-pompeiae"][1],
                         {"name": "Ambrosius", "where": "text", "role": "mentioned"})

    def test_a_eulogy_without_persons_of_its_own_still_gets_its_mentioned_ones(self):
        persons = {}
        self.assertEqual(with_mentioned(persons, {"mr:x": [{"name": "Ambrosius", "where": "text", "la": ["A"]}]}), [])
        self.assertEqual(persons, {"mr:x": [{"name": "Ambrosius", "where": "text", "role": "mentioned"}]})

    def test_a_mentioned_person_needs_a_new_name_or_n(self):
        persons = {"mr:x": [{"name": "Zeno", "where": "text"}]}
        errs = with_mentioned(persons, {"mr:x": [{"name": "Zeno", "where": "text", "la": ["Zenónis"]}]})
        self.assertIn("mr:x: 'Zeno' is already a person of the eulogy; give the mentioned one n", errs[0])
        self.assertEqual(with_mentioned({"mr:x": [{"name": "Zeno", "where": "text"}]},
                                        {"mr:x": [{"name": "Zeno", "n": 2, "where": "text", "la": ["Zenónis"]}]}), [])

    def test_a_mentioned_person_needs_a_printed_phrase(self):
        errs = with_mentioned({}, {"mr:x": [{"name": "Ambrosius", "where": "text", "la": []}]})
        self.assertEqual(errs, ["mr:x: 'Ambrosius' has no printed phrase (la)"])

    def test_a_text_and_a_footnote_phrase_are_one_person(self):
        # Final review 2: a phrase object names its own where; the person's where stays the first printing.
        persons = {}
        mentioned = {"mr:x": [{"name": "Ambrosius", "where": "text",
                               "la": ["Ambrósio", {"phrase": "Ambrósium", "where": {"footnote": 1}}], "it": []}]}
        self.assertEqual(with_mentioned(persons, mentioned), [])
        self.assertEqual(persons, {"mr:x": [{"name": "Ambrosius", "where": "text", "role": "mentioned"}]})

    def test_malformed_wheres_and_phrases_are_errors(self):
        for bad, message in (
                ({"where": "body"}, "mr:x: 'Ambrosius' has a malformed where 'body'"),
                ({"la": [3]}, "mr:x: 'Ambrosius' has a malformed la phrase 3"),
                ({"it": [{"phrase": "Ambrogio", "where": {"footnote": 0}}]},
                 "mr:x: 'Ambrosius' has a malformed it phrase {'phrase': 'Ambrogio', 'where': {'footnote': 0}}")):
            persons = {}
            entry = {"name": "Ambrosius", "where": "text", "la": ["Ambrósio"], "it": []} | bad
            self.assertEqual(with_mentioned(persons, {"mr:x": [entry]}), [message], bad)
            self.assertEqual(persons, {}, bad)


if __name__ == "__main__":
    unittest.main()
