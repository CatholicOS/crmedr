"""Locate the persons and places a eulogy names (standard library only).

Pure functions over a printed text and the names and place designations crmedr
already holds. They return spans, (start, end) offsets in the printed text, and
never text. Matching runs on a folded copy whose every character maps back to
the printed character it comes from, so a span found in the copy is a span in
the print. See martyrology-frontend's
docs/superpowers/specs/2026-10-09-eulogy-markup-design.md.
"""

import re
import unicodedata

from extract_places import base_copy
from persons_text import PARTICLES

# Folded as name_key folds names: æ/œ spelled out (accented or not), j/v read as
# i/u, ’ as '. The barred d and eth of Vietnamese names ("Ðình") and the Polish ł,
# which have no decomposition, read as d and l.
LIGATURES = {"æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe"}
LETTERS = {"j": "i", "v": "u", "’": "'", "đ": "d", "ð": "d", "ł": "l"}


def fold_map(text):
    """`text` folded for matching (accents stripped, lowercase, æ/œ spelled out,
    j/v read as i/u), and for each folded character the index of the printed
    character it comes from."""
    out, index = [], []
    for i, c in enumerate(text):
        base = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
        base = base if len(base) == 1 else c
        if base in LIGATURES:  # "ǽ" as "æ"
            f = LIGATURES[base]
        else:
            f = "".join(LETTERS.get(x, x) for x in base.lower())
        out.append(f)
        index += [i] * len(f)
    return "".join(out), index


def to_print(index, start, end):
    """The printed span of the folded span [start, end)."""
    return index[start], index[end - 1] + 1


def free(span, taken):
    """Whether `span` overlaps none of the spans in `taken` (touching is not overlapping)."""
    return all(span[1] <= s or span[0] >= e for s, e in taken)


def utf16(text, i):
    """Code-point offset `i` in `text` as a UTF-16 offset, the unit JavaScript strings count in."""
    return i + sum(1 for c in text[:i] if ord(c) > 0xFFFF)


def from_utf16(text, u):
    """UTF-16 offset `u` in `text` as a code-point offset."""
    i = n = 0
    while n < u and i < len(text):
        n += 2 if ord(text[i]) > 0xFFFF else 1
        i += 1
    return i


# The opening words that set a eulogy at the place of the one before it
# (data/places.json gives such a eulogy `via` and its root's designation).
BACK_REF_LA = re.compile(r"(?:Ibidem|Item)\b")
BACK_REF_IT = re.compile(r"(?:(?:Sempre|Ancora)\s|Ivi\b|Nello stesso luogo\b|Nella stessa citta\b)[^,;:]*")


def find_place(text, form, taken=()):
    """The first free span of a place designation in `text`: as printed, else
    after folding (the Italian "A Roma" is printed "a Roma" after "Sempre")."""
    start = text.find(form)
    while start >= 0:
        if free((start, start + len(form)), taken):
            return start, start + len(form)
        start = text.find(form, start + 1)
    folded, index = fold_map(text)
    target = fold_map(form)[0]
    start = folded.find(target) if target else -1
    while start >= 0:
        span = to_print(index, start, start + len(target))
        if free(span, taken):
            return span
        start = folded.find(target, start + 1)
    return None


def back_ref_span(text, lang):
    """The opening words that set a eulogy at the place of the one before:
    "Ibídem" or "Item" (Latin); "Sempre a Londra", "Ivi" (Italian, the place's
    name included). None when the text does not open with them."""
    copy = base_copy(text)  # one character to one: offsets in the copy are printed offsets
    m = (BACK_REF_LA if lang == "la" else BACK_REF_IT).match(copy)
    if not m:
        return None
    return 0, len(copy[:m.end()].rstrip())


# Between two words of a name: a space, or a hyphen or apostrophe ("Nŭm-ka",
# "O’Nemo", where the name has a space), or (in the third step only) one
# parenthesis ("Nemónis (Fictíni) Nemau") or cognomento phrase
# ("Nemónis, cognoménto Fictóris"). A parenthesis is at most MAX_PAREN
# characters with its brackets; see _paren_ok.
SEP = r"(?:\s+|[-'])"
WIDE_GAP = r"(?:\s+|[-']|\s*\([^)]*\)\s*|\s*,\s*cognomento\s+)"
MAX_PAREN = 60

# The last letters of a name word (Hebrew and Greek names) that declines in the
# third declension on the whole word.
CONSONANT_STEMS = set("dlmnr")


def _declined(word):
    """The (stem, endings) pairs a folded Latin name word declines by, from its
    nominative ending (longest first). A word with no such ending declines not at
    all: a foreign surname is found only as printed."""
    if word.endswith("ius"):  # Gregorius, Gregorii, Gregorio, Gregorium, Gregori
        return [(word[:-2], ["us", "i", "o", "um", ""])]
    if word.endswith("us"):
        return [(word[:-2], ["us", "i", "o", "um", "e"])]
    if word.endswith("ia") or word.endswith("a"):
        return [(word[:-1], ["a", "ae", "am"])]
    if word.endswith("is"):
        return [(word[:-2], ["is", "i", "em", "e", "idis", "idi"])]
    if word.endswith("ix"):
        return [(word[:-1] + "c", ["is", "i", "em", "e"])]
    if word.endswith("ex"):
        return [(word[:-2] + "ic", ["is", "i", "em", "e"])]
    if word.endswith("o"):
        return [(word, ["", "nis", "ni", "nem", "ne"]),
                (word[:-1], ["inis", "ini", "inem", "ine"])]
    if word.endswith("er"):
        endings = ["", "i", "o", "um", "is", "em", "e"]
        return [(word, endings), (word[:-2] + "r", endings)]
    if word.endswith("as"):  # Greek first declension (Thomas, Thomae), or a t stem
        return [(word[:-2], ["as", "ae", "am", "a"]), (word[:-2] + "at", ["is", "i", "em", "e"])]
    if word.endswith("es"):  # also a t stem: Agnes, Agnetis
        return [(word[:-2], ["es", "is", "i", "em", "e", "ae"]), (word[:-1] + "t", ["is", "i", "em", "e"])]
    if word.endswith("or"):
        return [(word, ["", "is", "i", "em", "e"])]
    if word.endswith("ns"):
        return [(word[:-1] + "t", ["is", "i", "em", "e"])]
    if word.endswith("am"):  # Abraham, Abrahae
        return [(word, ["", "is", "i", "em", "e"]), (word[:-2], ["ae"])]
    if word[-1:] in CONSONANT_STEMS:  # Michael, Simon, David, Gaspar: Michaelis, Simonis
        return [(word, ["", "is", "i", "em", "e"])]
    return []


# A pope's or king's numeral ("Gregorius X") is printed as its ordinal, often
# after "papa" ("Nemónis papæ Décimi"). Folded: v is read as u.
ROMAN = {"i": 1, "u": 5, "x": 10, "l": 50}
UNITS = ["", "primus", "secundus", "tertius", "quartus", "quintus", "sextus", "septimus", "octauus", "nonus"]
TENS = {10: ["decimus"], 20: ["uicesimus", "uigesimus"], 30: ["tricesimus", "trigesimus"]}


def _roman(word):
    """The value of a folded Roman numeral (below 40), else None."""
    if not word or any(c not in ROMAN for c in word):
        return None
    values = [ROMAN[c] for c in word]
    n = sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))
    return n if 0 < n < 40 else None


def _ordinals(n):
    """The ways the ordinal of n is printed, each a list of folded nominative words
    ("tertius decimus" or "decimus tertius"; "undecimus", "duodeuicesimus")."""
    tens, unit = divmod(n, 10)
    if not tens:
        return [[UNITS[unit]]]
    if not unit:
        return [[t] for t in TENS[n]]
    out = [w for t in TENS[tens * 10] for w in ([t, UNITS[unit]], [UNITS[unit], t])]
    if n == 11:
        out.append(["undecimus"])
    if n == 12:
        out.append(["duodecimus"])
    if unit in (8, 9):
        out += [[("duode" if unit == 8 else "unde") + t] for t in TENS.get(tens * 10 + 10, [])]
    return out


# Every ordinal word above, declined: an ordinal is not the start of a longer one
# ("Tértii" in "Tértii Décimi").
ORDINAL_WORDS = sorted({w for n in range(1, 40) for ws in _ordinals(n) for w in ws}, key=lambda w: (-len(w), w))


def _ordinal_pattern(n):
    """The ordinal of n as printed, declined, after an optional "papa" (any case),
    and not followed by another ordinal word."""
    ways = [r"\s+".join(_forms(w) for w in words) for words in _ordinals(n)]
    others = "|".join(_forms(w) for w in ORDINAL_WORDS)
    return r"(?:papa(?:e|m)?\s+)?(?:" + "|".join(ways) + r")(?!\s+(?:" + others + r")\b)"


def _forms(word):
    """A folded name word's printed forms as an alternation: the word itself, or a
    stem of at least two letters with one of its endings (see _declined). A
    particle is only itself."""
    if word in PARTICLES:
        forms = {word}
    else:
        forms = {word} | {stem + e for stem, endings in _declined(word)
                          if len(stem) >= 2 for e in endings}
    return "(?:" + "|".join(re.escape(f) for f in sorted(forms, key=lambda f: (-len(f), f))) + ")"


def _word_pattern(word, last=True):
    """A folded name word as a whole printed word (see _forms); a Roman numeral
    also as its ordinal (see _ordinal_pattern). The last word of a name must end
    the printed word; another is followed by a separator (SEP, WIDE_GAP)."""
    pattern = _forms(word)
    n = _roman(word)
    if n:
        pattern = "(?:" + pattern + "|" + _ordinal_pattern(n) + ")"
    return pattern + (r"(?![\w'\-])" if last else "")


def _paren_ok(printed):
    """Whether every parenthesis in a printed gap is at most MAX_PAREN characters."""
    return all(len(p) <= MAX_PAREN for p in re.findall(r"\([^)]*\)", printed))


def name_patterns(name):
    """How a name is looked for, in order: ("verbatim", the name folded), ("stem",
    its words by stem), ("gap", by stem across one parenthesis or cognomento phrase)."""
    words = [fold_map(w)[0] for w in name.split()]
    stems = [_word_pattern(w, last=i == len(words) - 1) for i, w in enumerate(words)]
    return [("verbatim", r"\b" + SEP.join(map(re.escape, words)) + r"\b"),
            ("stem", r"\b" + SEP.join(stems)),
            ("gap", r"\b" + WIDE_GAP.join(stems))]


def _gaps(matched):
    return matched.count("(") + matched.count("cognomento")


def find_person(text, name, taken=(), in_order=False):
    """The first free span of a person's name in `text`, how it was found
    ("verbatim", "stem", "gap"), and whether another free span matched at the
    same step; None when the name is not found. A match must open with a capital
    letter, so a common word is never marked ("pius" before "Pius"). With
    `in_order`, the first match in print whether verbatim or by stem, for persons
    of one name printed in different cases ("cum ... Felíce", then "Felix")."""
    folded, index = fold_map(text)
    patterns = name_patterns(name)
    verbatim = patterns[0][1]
    for how, pattern in patterns[1:] if in_order else patterns:
        spans = []
        for m in re.finditer(pattern, folded):
            if how == "gap" and _gaps(m.group(0)) > 1:
                continue
            span = to_print(index, m.start(), m.end())
            if how == "gap" and not _paren_ok(text[span[0]:span[1]]):
                continue
            if text[span[0]].isupper() and free(span, taken):
                spans.append(span)
        if spans:
            if in_order and how == "stem":
                start, end = spans[0]
                if re.fullmatch(verbatim, fold_map(text[start:end])[0]):
                    how = "verbatim"
            return spans[0], how, len(spans) > 1
    return None


def partial_span(text, name, taken=()):
    """The first free capitalized match of a name's first word, by stem: where a
    curator starts from for a name not found whole. None when there is none."""
    folded, index = fold_map(text)
    for m in re.finditer(r"\b" + _word_pattern(fold_map(name.split()[0])[0]), folded):
        span = to_print(index, m.start(), m.end())
        if text[span[0]].isupper() and free(span, taken):
            return span
    return None
