import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_subjects as s  # noqa: E402


class VernacularSubjectTest(unittest.TestCase):
    def test_saint_of_the_place_is_skipped_for_the_subject(self):
        it = "A Fictopoli presso San Paolo sulla via Fittizia, beato Fictitio, sacerdote."
        self.assertEqual(s.vern_subject("mr:0101-fictitius", it, s.IT_M), "Beato Fictitio")

    def test_no_name_match_and_no_latin_gives_nothing(self):
        it = "A Fictopoli presso San Paolo sulla via Fittizia, la memoria dei fedeli."
        self.assertIsNone(s.vern_subject("mr:0101-fictitius", it, s.IT_M))

    def test_aligned_with_the_latin_subject(self):
        la = "In monastério Sancti Fictii, beáti Altrónis, mónachi."
        it = "Nel monastero di San Fittio, beato Altrone, monaco."
        self.assertEqual(s.vern_subject("mr:0101-ignotus", it, s.IT_M, la), "Beato Altrone")

    def test_english_lowercase_honorific(self):
        en = "At Fictopolis, at Saint Paul’s on the Fictive Way, blessed Fictitius, priest."
        self.assertEqual(s.vern_subject("mr:0101-fictitius", en, s.EN_M), "Blessed Fictitius")

    def test_order_named_after_a_saint(self):
        en = "At Fictopolis, blessed Altro, priest of the Order of Saint Augustine."
        la = "Fictópoli, beáti Altrónis, presbýteri ex Ordine Sancti Augustíni."
        self.assertEqual(s.vern_subject("mr:0101-altro", en, s.EN_M, la), "Blessed Altro")

    def test_elided_italian_honorific(self):
        it = "A Fictopoli, al tempo di san Gregorio Magno, sant’Eufittio, vescovo."
        la = "Fictópoli, témpore sancti Gregórii Magni, sancti Eufittii, epíscopi."
        self.assertEqual(s.vern_subject("mr:0101-eufittius", it, s.IT_M, la), "Sant’Eufittio")
        self.assertEqual(s.vern_subject("mr:0101-ignotus", "Sant’Altrone, monaco.", s.IT_M), "Sant’Altrone")

    def test_italian_name_must_be_capitalized(self):
        it = "A Fictopoli, beato Fictitio, che condusse una santa vita."
        self.assertEqual([m.group(2) for m in s.IT_M.finditer(it)], ["Fictitio"])

    def test_drop_cap_heading(self):
        self.assertEqual(s.vern_subject("mr:0101-fictitius", "San Fittizio, vescovo.", s.IT_M), "San Fittizio")


if __name__ == "__main__":
    unittest.main()
