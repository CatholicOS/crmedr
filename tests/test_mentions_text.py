import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_text as mt  # noqa: E402


class FoldMapTest(unittest.TestCase):
    def test_folds_and_maps_back_to_the_print(self):
        folded, index = mt.fold_map("Cæsaréæ Iulii")
        self.assertEqual(folded, "caesareae iulii")
        start = folded.index("sareae")
        # "æ" folds to two letters; both map back to the one printed character.
        self.assertEqual(mt.to_print(index, start, start + len("sareae")), (2, 7))

    def test_reads_j_and_v_as_i_and_u_and_the_typographic_apostrophe_as_plain(self):
        self.assertEqual(mt.fold_map("Iosephus Vincentius")[0], mt.fold_map("Josephus Uincentius")[0])
        self.assertEqual(mt.fold_map("d’Nevílle")[0], "d'neuille")


class FreeTest(unittest.TestCase):
    def test_touching_is_free_overlapping_is_not(self):
        self.assertTrue(mt.free((5, 9), [(0, 5), (9, 12)]))
        self.assertFalse(mt.free((4, 9), [(0, 5)]))


class Utf16Test(unittest.TestCase):
    def test_counts_characters_outside_the_bmp_twice(self):
        text = "\U0001D510ab"
        self.assertEqual(mt.utf16(text, 2), 3)
        self.assertEqual(mt.from_utf16(text, 3), 2)

    def test_the_bmp_is_one_to_one(self):
        self.assertEqual(mt.utf16("Romæ", 4), 4)
        self.assertEqual(mt.from_utf16("Romæ", 4), 4)


class FindPlaceTest(unittest.TestCase):
    def test_as_printed(self):
        text = "Cæsaréæ in Cappadócia, commemorátio sancti Basilíi, magístri."
        form = "Cæsaréæ in Cappadócia"
        self.assertEqual(mt.find_place(text, form), (0, len(form)))

    def test_after_folding_case_and_accents(self):
        text = "Sempre a Roma, presso la via Appia, beato Nemo."
        start, end = mt.find_place(text, "A Roma")
        self.assertEqual(text[start:end], "a Roma")

    def test_skips_a_taken_span(self):
        self.assertEqual(mt.find_place("Romæ et Romæ", "Romæ", [(0, 4)]), (8, 12))

    def test_not_found(self):
        self.assertIsNone(mt.find_place("Ibídem, beáti Nemo.", "Londínii in Anglia"))


class BackRefTest(unittest.TestCase):
    def test_latin_ibidem(self):
        self.assertEqual(mt.back_ref_span("Ibídem, beáti Thomæ, presbýteri.", "la"), (0, 6))

    def test_italian_covers_the_place_name(self):
        text = "Sempre a Londra, beato Tommaso, sacerdote."
        start, end = mt.back_ref_span(text, "it")
        self.assertEqual(text[start:end], "Sempre a Londra")
        text = "Ivi, santa Nemo, vergine."
        start, end = mt.back_ref_span(text, "it")
        self.assertEqual(text[start:end], "Ivi")

    def test_none_without_a_back_reference(self):
        self.assertIsNone(mt.back_ref_span("Romæ, sancti Nemo.", "la"))
        self.assertIsNone(mt.back_ref_span("A Roma, san Nemo.", "it"))


def span_text(text, found):
    return text[found[0][0]:found[0][1]]


class FindPersonTest(unittest.TestCase):
    def test_verbatim_first(self):
        found = mt.find_person("Romæ, sancta Agnes, virgo.", "Agnes")
        self.assertEqual((span_text("Romæ, sancta Agnes, virgo.", found), found[1]), ("Agnes", "verbatim"))

    def test_a_genitive_by_stem(self):
        text = "Cæsaréæ in Cappadócia, commemorátio sancti Basilíi, magístri."
        found = mt.find_person(text, "Basilius")
        self.assertEqual((span_text(text, found), found[1], found[2]), ("Basilíi", "stem", False))

    def test_across_a_parenthesis(self):
        text = "In Canada, beátæ Nemæ Fictínæ (Nemæ Stellæ) Nemau Fictin, vírginis."
        found = mt.find_person(text, "Nema Fictina Nemau Fictin")
        self.assertEqual((span_text(text, found), found[1]), ("Nemæ Fictínæ (Nemæ Stellæ) Nemau Fictin", "gap"))

    def test_across_cognomento(self):
        text = "Londínii, sancti Nemárdi, cognoménto Fictóris, regis."
        found = mt.find_person(text, "Nemardus Fictor")
        self.assertEqual(span_text(text, found), "Nemárdi, cognoménto Fictóris")

    def test_only_one_gap(self):
        self.assertIsNone(mt.find_person("Romæ, beáti Petri (Ioánnis) Magni (Pauli) Nemínis.", "Petrus Magnus Nemo"))

    def test_a_capital_letter_is_required(self):
        text = "Romæ, pius sacérdos et sanctus Pius papa."
        start = text.index("Pius")
        self.assertEqual(mt.find_person(text, "Pius")[0], (start, start + 4))

    def test_a_name_inside_a_taken_span_is_skipped(self):
        text = "Romæ, beatórum Nemárdi a Fictúra Néma, presbýteri, et Némæ, vírginis."
        first = mt.find_person(text, "Nemardus a Fictura Nema")
        self.assertEqual(span_text(text, first), "Nemárdi a Fictúra Néma")
        second = mt.find_person(text, "Nema", [first[0]])
        self.assertEqual((span_text(text, second), second[2]), ("Némæ", False))

    def test_ambiguous(self):
        text = "Romæ, sanctórum Felícis presbýteri et Felícis diáconi."
        found = mt.find_person(text, "Felix")
        self.assertEqual((found[0], found[2]), ((text.index("Felícis"), text.index("Felícis") + 7), True))

    def test_apostrophe_typographic_in_print(self):
        text = "Marianópoli, beátæ Nemæ Fictínæ d’Nemo, víduæ."
        found = mt.find_person(text, "Nema Fictina d'Nemo")
        self.assertEqual(span_text(text, found), "Nemæ Fictínæ d’Nemo")

    def test_in_order_takes_the_first_printed_match_at_either_step(self):
        text = "Romæ, sanctórum Felícis et Felix."
        found = mt.find_person(text, "Felix", in_order=True)
        self.assertEqual((span_text(text, found), found[1], found[2]), ("Felícis", "stem", True))
        found = mt.find_person(text, "Felix", [found[0]], in_order=True)
        self.assertEqual((span_text(text, found), found[1], found[2]), ("Felix", "verbatim", False))

    def test_not_found(self):
        self.assertIsNone(mt.find_person("Romæ, sancti Nemo.", "Felix"))


class PartialSpanTest(unittest.TestCase):
    def test_the_first_word_by_stem(self):
        text = "Romæ, beáti Nemárdi a Fictúra, presbýteri."
        start, end = mt.partial_span(text, "Nemardus Baptista")
        self.assertEqual(text[start:end], "Nemárdi")

    def test_none(self):
        self.assertIsNone(mt.partial_span("Romæ, sancti Nemo.", "Felix"))


class DeclensionTest(unittest.TestCase):
    def test_a_word_sharing_only_the_start_of_a_name_is_not_it(self):
        self.assertIsNone(mt.find_person("Romæ, Marcélli et Martíni presbyterórum.", "Maria"))
        self.assertIsNone(mt.find_person("Romæ, Annónis presbýteri.", "Anna"))
        self.assertIsNone(mt.find_person("Romæ, Petrónii.", "Petrus"))

    def test_the_real_name_is_found_past_a_similar_word(self):
        text = "Romæ, Marcus et Maríæ."
        self.assertEqual(span_text(text, mt.find_person(text, "Maria")), "Maríæ")
        text = "Romæ, Felicitátis et Felícis."
        self.assertEqual(span_text(text, mt.find_person(text, "Felix")), "Felícis")

    def test_declined_forms_are_found(self):
        cases = [
            ("Cappadócia, sancti Basilíi, epíscopi.", "Basilius", "Basilíi"),
            ("Romæ, sancti Felícis, mártyris.", "Felix", "Felícis"),
            ("Bethlehem, sancti Hierónymi, presbýteri.", "Hieronymus", "Hierónymi"),
            ("Romæ, sancti Gregórii, epíscopi.", "Gregorius", "Gregórii"),
            ("Romæ, sancti Annónis, epíscopi.", "Anno", "Annónis"),
            ("Romæ, sanctam Maríam, vírginem.", "Maria", "Maríam"),
            ("Parísiis, Bessette, presbýteri.", "Bessette", "Bessette"),
        ]
        for text, name, printed in cases:
            with self.subTest(name=name):
                self.assertEqual(span_text(text, mt.find_person(text, name)), printed)

    def test_a_parenthesis_of_sixty_characters_is_a_gap_and_sixty_one_is_not(self):
        inside = "x" * 58
        text = "Romæ, beátæ Maríæ (" + inside + ") Annæ, vírginis."
        self.assertEqual(span_text(text, mt.find_person(text, "Maria Anna")), "Maríæ (" + inside + ") Annæ")
        longer = "Romæ, beátæ Maríæ (" + "x" * 59 + ") Annæ, vírginis."
        self.assertIsNone(mt.find_person(longer, "Maria Anna"))

    def test_consonant_stems_decline(self):
        cases = [
            ("Londínii, sancti Fictóris, regis.", "Fictor", "Fictóris"),
            ("Romæ, sancti Victóris, mártyris.", "Victor", "Victóris"),
            ("Romæ, sancti Cleméntis, mártyris.", "Clemens", "Cleméntis"),
        ]
        for text, name, printed in cases:
            with self.subTest(name=name):
                self.assertEqual(span_text(text, mt.find_person(text, name)), printed)


class FoldMoreLettersTest(unittest.TestCase):
    def test_an_accented_ligature_folds_as_the_ligature(self):
        self.assertEqual(mt.fold_map("Nemǽi Ǽlii")[0], "nemaei aelii")

    def test_the_barred_d_eth_and_slashed_l_fold_to_plain_letters(self):
        self.assertEqual(mt.fold_map("Ðình Đạt Nemała")[0], "dinh dat nemala")

    def test_other_letters_are_unchanged(self):
        self.assertEqual(mt.fold_map("Nemø")[0], "nemø")


class MoreDeclensionsTest(unittest.TestCase):
    def found(self, text, name):
        found = mt.find_person(text, name)
        return span_text(text, found) if found else None

    def test_ius_declines_on_its_stem(self):
        for printed in ("Nemório", "Nemórium", "Nemórii", "Nemóri"):
            with self.subTest(printed=printed):
                self.assertEqual(self.found(f"Romæ, sancto {printed}, epíscopo.", "Nemorius"), printed)
        self.assertIsNone(self.found("Romæ, sancto Nemoriáno, epíscopo.", "Nemorius"))

    def test_greek_as_declines_in_the_first_declension(self):
        for printed in ("Nemæ", "Nemam", "Nemas"):
            with self.subTest(printed=printed):
                self.assertEqual(self.found(f"Romæ, sancti {printed}, apóstoli.", "Nemas"), printed)
        self.assertIsNone(self.found("Romæ, sancti Nemáni, apóstoli.", "Nemas"))

    def test_es_declines_on_a_t_stem(self):
        self.assertEqual(self.found("Romæ, sanctæ Nemétis, vírginis.", "Nemes"), "Nemétis")
        self.assertIsNone(self.found("Romæ, sanctæ Nemetéllæ, vírginis.", "Nemes"))

    def test_a_consonant_ending_declines_on_the_whole_word(self):
        cases = [("Romæ, sancti Nemaélis, archángeli.", "Nemael", "Nemaélis"),
                 ("Romæ, sancti Nemiónis, mónachi.", "Nemion", "Nemiónis"),
                 ("Romæ, sancti Nemídis, regis.", "Nemid", "Nemídis"),
                 ("Romæ, sancti Nemáris, regis.", "Nemar", "Nemáris"),
                 ("Romæ, sancti Nemahæ, patriárchæ.", "Nemaham", "Nemahæ")]
        for text, name, printed in cases:
            with self.subTest(name=name):
                self.assertEqual(self.found(text, name), printed)
        self.assertIsNone(self.found("Romæ, sancti Nemaelíni, mónachi.", "Nemael"))
        self.assertIsNone(self.found("Romæ, sancti Nemioníni, mónachi.", "Nemion"))

    def test_am_declines_only_on_the_whole_word_or_with_ae(self):
        self.assertEqual(self.found("Romæ, sancti Nemahámi, patriárchæ.", "Nemaham"), "Nemahámi")
        self.assertIsNone(self.found("Romæ, sancti Nemahánæ, patriárchæ.", "Nemaham"))
        self.assertIsNone(self.found("Romæ, sancti Nemahis, patriárchæ.", "Nemaham"))


class SeparatorTest(unittest.TestCase):
    def test_a_hyphen_or_apostrophe_may_join_the_words_of_a_name(self):
        text = "In Coréa, sancti Pauli Nem Nŭm-ka, mártyris."
        self.assertEqual(span_text(text, mt.find_person(text, "Paulus Nem Num Ka")), "Pauli Nem Nŭm-ka")
        text = "In Hibérnia, beáti Patrícii O’Nemo, epíscopi."
        self.assertEqual(span_text(text, mt.find_person(text, "Patricius O Nemo")), "Patrícii O’Nemo")

    def test_the_last_word_is_not_the_start_of_a_hyphenated_word(self):
        self.assertIsNone(mt.find_person("In Coréa, sancti Pauli Nem Nŭm-ka, mártyris.", "Paulus Nem Num"))


class OrdinalTest(unittest.TestCase):
    def test_a_numeral_is_found_as_its_ordinal_after_papa(self):
        cases = [("Romæ, sancti Nemónis papæ Décimi, qui.", "Nemo X", "Nemónis papæ Décimi"),
                 ("Romæ, sancti Nemélli Primi, papæ.", "Nemellus I", "Nemélli Primi"),
                 ("Romæ, beáti Nemónis papæ Vigésimi Tértii.", "Nemo XXIII", "Nemónis papæ Vigésimi Tértii"),
                 ("Romæ, sancti Nemónis papæ Tértii Décimi.", "Nemo XIII", "Nemónis papæ Tértii Décimi"),
                 ("Romæ, sancti Nemónis papæ Quinti.", "Nemo V", "Nemónis papæ Quinti")]
        for text, name, printed in cases:
            with self.subTest(name=name):
                self.assertEqual(span_text(text, mt.find_person(text, name)), printed)

    def test_a_numeral_as_printed_is_still_itself(self):
        text = "In Coréa, sancti Alexii U Nem, mártyris."
        self.assertEqual(span_text(text, mt.find_person(text, "Alexius U Nem")), "Alexii U Nem")

    def test_another_ordinal_is_not_the_numeral(self):
        self.assertIsNone(mt.find_person("Romæ, sancti Nemónis papæ Primi.", "Nemo II"))
        self.assertIsNone(mt.find_person("Romæ, sancti Nemónis papæ Décimi Tértii.", "Nemo X"))


if __name__ == "__main__":
    unittest.main()
