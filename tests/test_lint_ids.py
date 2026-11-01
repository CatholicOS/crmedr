import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lint_ids as l  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class GrammarTest(unittest.TestCase):
    def test_form_and_day(self):
        found = l.check_grammar(["mr:0101-felix", "mr:0230-felix", "mr:0101-Felix", "mr:0101-felix--x", "mr:101-x"])
        self.assertEqual([f[1][0] for f in found], ["mr:0230-felix", "mr:0101-Felix", "mr:0101-felix--x", "mr:101-x"])

    def test_only_ascii_digits_and_the_whole_id(self):
        # "١" is an Arabic-Indic digit, which \d accepts; "$" also matches before a trailing newline.
        found = l.check_grammar(["mr:0\u066101-felix", "mr:0101-felix\n"])
        self.assertEqual([f[1][0] for f in found], ["mr:0\u066101-felix", "mr:0101-felix\n"])

    def test_an_id_is_never_used_twice(self):
        entries = [{"id": "mr:0901-priscus-capuae"}, {"id": "mr:0901-priscus-capuae", "deprecated": True}]
        self.assertEqual(l.check_unique(entries), [("unique", ["mr:0901-priscus-capuae"], "used 2 times")])


class SameSubjectTest(unittest.TestCase):
    def test_one_saint_two_discriminators(self):
        found = l.check_same_subject({"mr:0526-augustinus-cantuariae": "Q32520",
                                      "mr:0527-augustinus-cantuariensis": "Q32520"})
        self.assertEqual([f[0] for f in found], ["same-subject"])

    def test_a_group_tail_or_a_joint_eulogy_agrees(self):
        self.assertEqual(l.check_same_subject({"mr:0806-xystus-ii": "Q127385",
                                               "mr:0807-xystus-ii-et-socii": "Q127385",
                                               "mr:0916-cornelius-et-xystus-ii": "Q127385"}), [])

    def test_a_deprecated_twin_with_another_slug_is_a_warning(self):
        entries = [{"id": "mr:0528-augustinus", "deprecated": True, "same_eulogy": ["mr:0527-augustinus-cantuariensis"]}]
        found = l.check_twins(entries, {"mr:0527-augustinus-cantuariensis": (5, 27)})
        self.assertEqual([f[0] for f in found], ["twin"])
        self.assertNotIn("twin", l.ERRORS)


class TextTest(unittest.TestCase):
    def test_the_printed_ae_is_kept(self):
        texts = {"mr:0903-sandalius-cordube": "Córdubæ in Hispánia Bǽtica, sancti Sandálii, mártyris.",
                 "mr:0903-sandalius-cordubae": "Córdubæ in Hispánia Bǽtica, sancti Sandálii, mártyris."}
        found = l.check_ae(texts, texts)
        self.assertEqual([f[1] for f in found], [["mr:0903-sandalius-cordube"]])

    def test_a_reference_names_the_same_saint_alike(self):
        current = {"mr:0526-augustinus-cantuariae": (5, 26), "mr:0527-augustinus-cantuariensis": (5, 27)}
        texts = {"mr:0526-augustinus-cantuariae": "Cantuariae, depositio sancti Augustini, cuius memoria cras agitur.",
                 "mr:0527-augustinus-cantuariensis": "Sancti Augustini, episcopi Cantuariensis."}
        found = l.check_cross_day(current, texts, {})
        self.assertEqual([(f[0], f[1]) for f in found],
                         [("cross-day", ["mr:0526-augustinus-cantuariae", "mr:0527-augustinus-cantuariensis"])])

    def test_a_reference_to_another_saints_feast_is_a_warning(self):
        current = {"mr:0920-laurentius-et-socii": (9, 20), "mr:0920-andreas-et-socii": (9, 20)}
        texts = {"mr:0920-laurentius-et-socii": "sanctorum Laurentii et sociorum, quorum memoria hodie agitur.",
                 "mr:0920-andreas-et-socii": "Memoria sanctorum Andreae et sociorum."}
        found = l.check_cross_day(current, texts, {})
        self.assertEqual([f[0] for f in found], ["cross-day-other"])


class StaleExceptionTest(unittest.TestCase):
    def test_an_exception_no_error_matches_is_an_error_of_its_own(self):
        excepted = [{"check": "same-subject", "ids": ["mr:0101-a-x", "mr:0201-a-y"], "note": "n"},
                    {"check": "same-subject", "ids": ["mr:0101-b-x", "mr:0201-b-y"], "note": "n"}]
        found = [("same-subject", ["mr:0201-b-y", "mr:0101-b-x"], "why")]
        self.assertEqual(l.stale_exceptions(excepted, found, {"same-subject"}),
                         [("stale-exception", ["mr:0101-a-x", "mr:0201-a-y"],
                           "same-subject: no longer an error: remove the exception")])
        self.assertIn("stale-exception", l.ERRORS)

    def test_an_exception_of_a_check_that_did_not_run_is_not_stale(self):
        excepted = [{"check": "cross-day", "ids": ["mr:0101-a", "mr:0102-a-x"], "note": "n"}]
        self.assertEqual(l.stale_exceptions(excepted, [], {"same-subject"}), [])


class RegistryTest(unittest.TestCase):
    def test_the_registry_has_no_errors_beyond_the_known_exceptions(self):
        errors, _ = l.lint(ROOT)
        self.assertEqual(errors, [], "fix the IDs, or record a curator decision in data/id_lint_exceptions.json")


if __name__ == "__main__":
    unittest.main()
