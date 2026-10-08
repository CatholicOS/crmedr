"""Text helpers for the persons each eulogy names (standard library only).

Names are Latin nominatives without honorific. Nothing here stores text: the
helpers read a subject, a footnote or a eulogy and return names.
See docs/superpowers/specs/2026-10-08-persons-design.md.
"""

import re

from gazetteer_text import fold

HONORIFICS = {"sanctus", "sancta", "sancti", "sanctae", "beatus", "beata", "beati", "beatae"}
COMPANION_WORDS = {"socii", "sociae"}

# The eulogies of the Blessed Virgin Mary: one person, "Maria", whatever the
# title (Lourdes, Fatima, Regina, Perdolens...). Other Marias are themselves
# (mr:0909-maria-de-la-cabeza, mr:0820-maria-de-mattias...).
MARIAN_IDS = {
    "mr:0101-maria-dei-genetrix", "mr:0211-maria-de-lourdes", "mr:0513-maria-de-fatima",
    "mr:0531-visitatio-beatae-mariae-virginis", "mr:0716-maria-de-monte-carmelo",
    "mr:0815-assumptio-beatae-mariae-virginis", "mr:0822-maria-regina",
    "mr:0908-nativitas-beatae-mariae-virginis", "mr:0912-nomen-mariae", "mr:0915-maria-perdolens",
    "mr:1007-maria-de-rosario", "mr:1121-praesentatio-beatae-mariae-virginis",
    "mr:1208-conceptio-immaculata-beatae-mariae-virginis", "mr:1212-maria-de-guadalupe",
}
# Celebrations that commemorate a saint but whose subject opens without an
# honorific.
FEAST_PERSONS = {
    "mr:0125-conversio-pauli-apostoli": ["Paulus"],
    "mr:0222-cathedra-petri-apostoli": ["Petrus"],
    "mr:0325-bonus-latro": ["Bonus Latro"],
}
# Subjects with an honorific that name a group, not persons: its members are
# indexed only where a footnote names them.
GROUP_IDS = {
    "mr:0114-monachi-raithi", "mr:0208-martyres-monachi-dii-constantinopolitani",
    "mr:0212-martyres-abitinenses", "mr:0217-septem-fundatores-servorum-mariae",
    "mr:0219-monachi-martyres-palaestinae", "mr:0228-presbyteri-diaconi-plurimi-alexandriae",
    "mr:0306-quadraginta-duo-martyres-syriae", "mr:0309-quadraginta-milites-sebastes",
    "mr:0320-viginti-monachi-palaestinae", "mr:0321-martyres-alexandrini",
    "mr:0405-centum-undecim-viri-novem-mulieres-martyres", "mr:0405-martyres-regiarum",
    "mr:0516-quadraginta-quattuor-monachi-palaestinae", "mr:0521-martyres-alexandriae",
    "mr:0523-martyres-cappadociae", "mr:0523-martyres-mesopotamiae",
    "mr:0524-triginta-octo-martyres-philippopolis", "mr:0708-monachi-abrahamitae",
    "mr:0717-martyres-scillitani", "mr:0722-martyres-massilitani", "mr:0727-septem-dormientes-ephesi",
    "mr:0728-martyres-thebaidis", "mr:0801-septem-fratres-martyres-antiochiae",
    "mr:0809-martyres-constantinopolis", "mr:0810-martyres-alexandriae",
    "mr:0818-martyres-massae-candidae", "mr:1005-martyres-trevirorum",
    "mr:1012-martyres-et-confessores-africae", "mr:1017-martyres-volitani",
    "mr:1021-virgines-coloniae-agrippinae", "mr:1115-viginti-martyres-hipponis-regii",
    "mr:1119-quadraginta-martyres-heracleae", "mr:1206-martyres-africae",
    "mr:1217-quinquaginta-milites-eleutheropolis", "mr:1222-triginta-martyres-romae",
    "mr:1222-quadraginta-tres-monachi-raithi", "mr:1228-innocentes",
}

# An ID whose slug opens with a number or a group word names a group
# ("mr:0205-plurimi-martyres-ponti", "mr:0220-quinque-martyres-tyri").
GROUP_HEADS = {
    "plurimi", "martyres", "milites", "monachi", "virgines", "presbyteri", "innocentes",
    "duo", "tres", "quattuor", "quinque", "sex", "septem", "octo", "novem", "decem", "undecim", "duodecim",
    "tredecim", "quattuordecim", "quindecim", "sedecim", "septendecim", "duodeviginti", "undeviginti",
    "viginti", "triginta", "quadraginta", "quinquaginta", "sexaginta", "septuaginta", "octoginta",
    "nonaginta", "centum", "ducenti", "trecenti", "quadringenti", "quingenti", "sescenti", "septingenti",
    "octingenti", "nongenti", "mille",
}


def name_key(s):
    """A name compared across spellings: accents, case, i/j and u/v folded."""
    return " ".join(fold(s).replace("j", "i").replace("v", "u").replace("'", " ").split())


def subject_names(mrid, subject):
    """The persons a subject of i18n/la.json names, honorific-free, in order."""
    if mrid in MARIAN_IDS:
        return ["Maria"]
    if mrid in FEAST_PERSONS:
        return list(FEAST_PERSONS[mrid])
    if mrid in GROUP_IDS or mrid.split("-", 1)[1].split("-")[0] in GROUP_HEADS:
        return []
    words = subject.split()
    if not words or fold(words[0]) not in HONORIFICS:
        return []
    parts = re.split(r",\s*|\s+et\s+", " ".join(words[1:]))
    return [p.strip() for p in parts if p.strip() and fold(p.strip()) not in COMPANION_WORDS]

# Lowercase words inside a name, kept only when a capitalized word follows.
PARTICLES = {"de", "a", "ab", "van", "von", "di", "da", "du", "la", "le", "y", "dos", "das", "del", "der",
             "den", "ten", "ter", "e"}
FOOTNOTE_OPENING = re.compile(r"^\s*(?:Quorum|Quarum)\s+n[oó]mina\s*:|^\s*Inter\s+quos\s*:", re.I)
WORD = re.compile(r"[^\W\d_][\w'’\-]*")


def _particle_run(words, i):
    """Whether words[i:] is one or more particles followed by a capitalized word ("de la Parilla")."""
    while i < len(words) and fold(words[i].strip(".,;:")) in PARTICLES:
        i += 1
    return 0 < i < len(words) and words[i][:1].isupper()


def _name_at_start(segment):
    """The name a segment opens with, or None: capitalized words, and runs of
    particles followed by a capitalized word, up to the first other lowercase word."""
    words = segment.split()
    while words and fold(words[0]) in HONORIFICS:
        words = words[1:]
    if not words or not words[0][:1].isupper():
        return None  # "e Societate Iesu" describes the name before it
    out = []
    for i, w in enumerate(words):
        bare = w.strip(".,;:")
        if not bare:
            break
        if bare[0].isupper():
            out.append(bare)
        elif fold(bare) in PARTICLES and _particle_run(words, i):
            out.append(bare)
        else:
            break
        if w[-1] in ".,;:":
            break
    return " ".join(out) or None


def footnote_names(text):
    """The names a footnote list gives, in order, and the segments not read."""
    m = FOOTNOTE_OPENING.match(text)
    if not m:
        return [], [text]
    names, skipped = [], []
    body = text[m.end():].strip().rstrip(".")
    for group in body.split(";"):
        segments = [s.strip() for s in group.split(",")]
        for seg in segments:
            # "Michael Kozaki et Thomas": two names in one segment.
            for part in re.split(r"\s+et\s+", seg):
                part = part.strip()
                if not part:
                    continue
                name = _name_at_start(part)
                if name and re.search(r"(?:ae|æ)$", fold(name.split()[0])):
                    skipped.append(part)  # a genitive ("Teresiae Henricae..."): not a nominative to write
                elif name:
                    names.append(name)
                elif part[:1].isupper() or part[:1].isdigit():
                    skipped.append(part)
                # A lowercase segment ("presbyteri ex Ordine...", "eius filius") describes the
                # names before it: dropped.
    return names, skipped

# Genitive ending -> the nominative endings it may come from (personal names).
# Longest first; the lexicon of known names chooses among them.
GENITIVE_ENDINGS = [
    ("entis", ("ens",)), ("antis", ("ans",)), ("onis", ("o", "on")), ("inis", ("o", "en")),
    ("elis", ("el",)), ("idis", ("id", "is")),
    ("icis", ("ix", "ex")), ("ocis", ("ox",)), ("itis", ("es",)), ("ii", ("ius",)),
    ("ae", ("a",)), ("is", ("is", "es", "s")), ("i", ("us", "ius")), ("us", ("us",)),
]
PLURAL_HONORIFIC = re.compile(r"\b(?:sanct|beat)(?:orum|arum)\b")
# Lowercase words between the honorific and the names ("sanctorum martyrum Pauli").
NAME_DESCRIPTORS = {"martyrum", "virginum", "presbyterorum", "episcoporum", "monachorum", "fratrum",
                    "sororum", "coniugum", "confessorum", "diaconorum", "puerorum", "militum", "sacerdotum"}


def nominative(word, lexicon):
    """The nominative of a genitive name, when exactly one possibility is a known name.
    A declined nominative wins over the word itself: "Mariae" is known too, from
    religious names ("a Sacro Corde Mariae"), but the genitive of a person is Maria."""
    key = name_key(word)
    found = _declined(key, lexicon) or ({lexicon[key]} if key in lexicon else set())
    return found.pop() if len(found) == 1 else None


def _genitive_ending(key):
    return any(key.endswith(e) and len(key) > len(e) + 1 for e, _ in GENITIVE_ENDINGS)


def _declined(key, lexicon):
    """The known nominatives a genitive (in name_key form) may come from."""
    for ending, noms in GENITIVE_ENDINGS:
        if key.endswith(ending) and len(key) > len(ending) + 1:
            stem = key[: -len(ending)]
            return {lexicon[stem + n] for n in noms if stem + n in lexicon}
    return set()


def text_companions(text, lexicon):
    """The names after a plural honorific at the head of a eulogy ("sanctorum
    martyrum A, B et C"), as nominatives; forms not surely converted are
    returned apart, as printed."""
    if not PLURAL_HONORIFIC.search(fold(text)):
        return [], []
    words = WORD.findall(text)
    fwords = [fold(w) for w in words]
    start = next(i for i, w in enumerate(fwords) if PLURAL_HONORIFIC.fullmatch(w)) + 1
    while start < len(words) and fwords[start] in NAME_DESCRIPTORS:
        start += 1
    names, uncertain, current, after_particle, skipping = [], [], [], False, False
    tail = text.split(words[start - 1], 1)[1] if start > 0 else text

    def close():
        if current:
            names.append(" ".join(current))
            current.clear()

    for token in re.findall(r"[^\W\d_][\w'’\-]*|[,.;:]", tail):
        if token in ",.;:":
            close()
            after_particle = skipping = False
            if token != ",":
                break
            continue
        f = fold(token)
        if f == "et":
            close()
            after_particle = skipping = False
            continue
        if skipping:
            continue
        if f in ("sociorum", "sociarum"):
            break
        if token[0].islower() and f not in PARTICLES:
            if f in NAME_DESCRIPTORS and not current:
                continue
            break
        if token[0].islower():
            if not current:
                skipping = True  # "e Societate Iesu" describes the name before it
                continue
            current.append(token)
            after_particle = True
            continue
        if after_particle and (_declined(name_key(token), lexicon) or
                               (_genitive_ending(name_key(token)) and name_key(token) not in lexicon)):
            # A genitive after a religious name ("Teresiae a Sancto Augustino Mariae Magdalenae
            # Lidoine"), known or not: where one name ends is not sure, so the whole is reported.
            uncertain.append(" ".join(current + [token]))
            current.clear()
            after_particle, skipping = False, True
            continue
        if after_particle:
            # Not declined after a particle ("a Sancto Augustino"): the known spelling, without
            # the print's stress accents, else as printed.
            current.append(lexicon.get(name_key(token), token))
            continue
        nom = nominative(token, lexicon)
        if nom is None:
            uncertain.append(token)  # the whole name is dropped, never half-written
            current.clear()
            after_particle, skipping = False, True
            continue
        current.append(nom)
    close()
    return names, uncertain
