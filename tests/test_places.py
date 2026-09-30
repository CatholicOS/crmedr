import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_places as p  # noqa: E402


class OpeningPhraseTest(unittest.TestCase):
    def test_base_copy_keeps_length_case_and_ligatures(self):
        self.assertEqual(p.base_copy("Fictópoli Sanctórum sanctæ"), "Fictopoli Sanctorum sanctæ")
        self.assertEqual(len(p.base_copy("Fictópoli ǽ")), len("Fictópoli ǽ"))

    def test_lowercase_honorific_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli in Fictia, sancti Fictitii, episcopi."),
                         "Fictopoli in Fictia")

    def test_capitalized_saint_in_a_place_name_stays(self):
        self.assertEqual(
            p.opening_phrase("In monasterio Sancti Ficti ad Fictum flumen, depositio beati Fictitii."),
            "In monasterio Sancti Ficti ad Fictum flumen")

    def test_capitalized_stop_word_at_start_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Sancti Fictitii, episcopi."))
        self.assertIsNone(p.opening_phrase("Memória sancti Fictitii, episcopi."))

    def test_printed_accents_kept_and_ligature_stop_word(self):
        self.assertEqual(p.opening_phrase("Fictópoli in Gállia, sanctæ Fictæ, vírginis."),
                         "Fictópoli in Gállia")
        self.assertEqual(p.opening_phrase("Fictópoli, beátæ Fictæ."), "Fictópoli")

    def test_marker_word_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli, translátio sancti Ficti."), "Fictopoli")

    def test_time_tail_is_stripped(self):
        self.assertEqual(p.opening_phrase("Fictopoli item in Fictia, eódem die et anno, beáti Ficti."),
                         "Fictopoli item in Fictia")
        self.assertEqual(p.opening_phrase("Ibídem, eódem die et anno, beáti Ficti."), "Ibídem")

    def test_no_stop_word_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Fictis transactis temporibus Fictus nascitur."))

    def test_split_lead(self):
        self.assertEqual(p.split_lead("Ibídem"), ("back", None))
        self.assertEqual(p.split_lead("Item"), ("back", None))
        self.assertEqual(p.split_lead("Item Fictópoli"), ("place", "Fictópoli"))
        self.assertEqual(p.split_lead("Item, in Fictia"), ("place", "in Fictia"))
        self.assertEqual(p.split_lead("Ibídem in cœmetério Ficti"), ("extend", "Ibídem in cœmetério Ficti"))
        self.assertEqual(p.split_lead("Fictopoli in Fictia"), ("place", "Fictopoli in Fictia"))


if __name__ == "__main__":
    unittest.main()
