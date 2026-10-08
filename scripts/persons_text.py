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


def name_key(s):
    """A name compared across spellings: accents, case, i/j and u/v folded."""
    return " ".join(fold(s).replace("j", "i").replace("v", "u").replace("'", " ").split())


def subject_names(mrid, subject):
    """The persons a subject of i18n/la.json names, honorific-free, in order."""
    if mrid in MARIAN_IDS:
        return ["Maria"]
    if mrid in FEAST_PERSONS:
        return list(FEAST_PERSONS[mrid])
    if mrid in GROUP_IDS:
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
                if name:
                    names.append(name)
                elif part[:1].isupper() or part[:1].isdigit():
                    skipped.append(part)
                # A lowercase segment ("presbyteri ex Ordine...", "eius filius") describes the
                # names before it: dropped.
    return names, skipped
