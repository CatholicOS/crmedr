"""The Italian (CEI) 2004 edition's forms of the persons of data/persons.json, for marking them in
its texts and footnotes (CatholicOS/crmedr#97).

data/persons.json stores Latin nominatives ("Ioannes Bosco"); the Italian prints Italian forms
("Giovanni Bosco"). The forms are made, never stored:
- the subject: a eulogy's Latin subject in i18n/la.json and its Italian subject in i18n/it.json
  name the same persons in the same order ("Sancti Argeus, Narcissus et Marcellinus" / "Santi
  Argeo, Narciso e Marcellino"), so each person named there has the Italian form beside it;
- the lexicon: the given names those pairs translate (Ioannes → Giovanni, Iosephus → Giuseppe),
  learned from every pair whose names have as many words in both languages, the commonest
  translation of a word winning. A name's leading words are translated and the rest kept as
  printed, from all of them to none: surnames are printed alike in both editions ("Blasco Juan"
  stays, though "Juan" is also a given name);
- the surname: a person not found by any form is looked for by the untranslated end of the name,
  and marked over the run of capitalized words that holds it ("Pietro (Paolo) Kim");
- the position: the persons of a footnote list are printed in the same order in both editions, so
  one left over between two matched neighbours is proposed (never marked) on the one unmarked name
  printed between theirs.

Standard library only.
"""

import collections
import re

from mentions_text import find_person, fold_map, free
from persons_text import name_key

HONORIFIC_LA = re.compile(r"^(?:sanct(?:us|a|i|ae|æ)|beat(?:us|a|i|ae|æ))\s+", re.I)
HONORIFIC_IT = re.compile(r"^(?:sant['’]|santi|sante|santo|santa|san|beati|beate|beato|beata)\s*", re.I)
COMPANIONS_LA = re.compile(r"\s+et\s+soci(?:i|ae|æ)$", re.I)
COMPANIONS_IT = re.compile(r"\s+e\s+compagn[ie]$", re.I)
SPLIT_LA = re.compile(r",\s*|\s+et\s+")
# "Giusta ed Eredina", "Teofilo e Elladio": "e"/"ed" before a capital joins two names.
SPLIT_IT = re.compile(r",\s*|\s+ed?\s+(?=[^\W\d_])")
# The particles a name may hold between its capitalized words ("Teodorico van der Eem").
PARTICLES = {"de", "da", "di", "del", "della", "dello", "delle", "dei", "degli", "des", "du", "van", "von", "der",
             "den", "y", "la", "le", "dos", "das", "do", "d’", "d'"}
# An elided particle and the capitalized word it is printed with ("dell’Immacolata Concezione"): inside a
# run only, never opening one ("religiose dell’Ordine dei Frati Minori").
ELIDED = re.compile(r"^(?:dell|dall|nell|sull)['’](?=[^\W\d_])")
WORD = re.compile(r"\(?[^\W\d_][\w’'\-]*\)?")


def subject_names(subject, lang):
    """The names a subject lists, honorific and companions left out: "Santi Argeo, Narciso e
    Marcellino" → ["Argeo", "Narciso", "Marcellino"]."""
    honorific, companions, split = ((HONORIFIC_LA, COMPANIONS_LA, SPLIT_LA) if lang == "la"
                                    else (HONORIFIC_IT, COMPANIONS_IT, SPLIT_IT))
    s = companions.sub("", honorific.sub("", (subject or "").strip()))
    return [x.strip() for x in split.split(s) if x.strip()]


def fold(s):
    return fold_map(s)[0]


class ItalianNames:
    """The Italian forms to look for, for each person of a eulogy."""

    def __init__(self, la_subjects, it_subjects):
        self.pairs = collections.defaultdict(dict)  # mrid -> {name_key(latin name): italian name}
        counts = collections.defaultdict(collections.Counter)
        for mrid, la in la_subjects.items():
            a, b = subject_names(la, "la"), subject_names(it_subjects.get(mrid, ""), "it")
            if not b or len(a) != len(b):
                continue
            for x, y in zip(a, b, strict=True):
                self.pairs[mrid][name_key(x)] = y
                xs, ys = x.split(), y.split()
                if len(xs) == len(ys):
                    for u, v in zip(xs, ys, strict=True):
                        counts[fold(u)][v] += 1
        # The commonest translation; of two as common, the first in sort order (a stable run).
        self.lexicon = {u: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for u, c in counts.items()}

    def translate(self, word):
        return self.lexicon.get(fold(word), word)

    def forms(self, mrid, name):
        """The forms to look for, most likely first: the subject's, then the name with its leading
        words translated, from all of them to none (the name as stored)."""
        out = []
        if name_key(name) in self.pairs.get(mrid, {}):
            out.append(self.pairs[mrid][name_key(name)])
        words = name.split()
        for i in range(len(words), -1, -1):
            out.append(" ".join([self.translate(w) for w in words[:i]] + words[i:]))
        return list(dict.fromkeys(f for f in out if f.strip()))

    def surname(self, name):
        """The untranslated end of a name, longest first: the words a surname search anchors on."""
        words = name.split()
        out = []
        for i in range(1, len(words)):
            end = " ".join(words[i:])
            if len(end) >= 3 and end[0].isupper() and fold(self.translate(words[i])) == fold(words[i]):
                out.append(end)
        return out


def _capital(word):
    """A capitalized word, also after "(" or an elided particle ("d’Assche")."""
    w = re.sub(r"^\(|^d['’]", "", word)
    return bool(w) and w[0].isupper()


def runs(text, taken=()):
    """The free runs of capitalized words in `text` (code-point spans), where names are printed: the
    words joined by spaces, with particles ("da", "van der") and a parenthesis ("Maria Anna (Maria
    Amandina) Giuliani") inside a run, a run opening and closing with a capitalized word."""
    out, start, end, tail = [], None, None, None
    for m in WORD.finditer(text):
        w = m.group(0)
        joined = start is not None and text[tail:m.start()].strip() == ""
        if joined and ELIDED.match(w) and _capital(ELIDED.sub("", w)):
            end = tail = m.end()
        elif _capital(w):
            if joined:
                end = tail = m.end()
            else:
                if start is not None:
                    out.append((start, end))
                start, end, tail = m.start(), m.end(), m.end()
        elif joined and w.lower() in PARTICLES:
            tail = m.end()  # a run may go on past a particle, but never ends on one
        else:
            if start is not None:
                out.append((start, end))
            start = None
    if start is not None:
        out.append((start, end))
    return [r for r in out if free(r, taken)]


# Where an item of a list or a clause begins: after a comma, semicolon or colon, or " e " / " ed ".
ITEM_START = re.compile(r"(?:[,;:]\s*|\s+ed?\s+|^)")


def surname_span(text, ends, taken, given=(), joined=False):
    """A free span for a person by one of their surname `ends`: the capitalized run holding the
    match, else the match alone; widened back to the start of its list item when that item opens with
    one of the person's `given` names, across an "e" only when the name itself is `joined` by one
    ("Iosephus a Iesu et Maria": "Giuseppe di Gesù e Maria Osés Sainz", never "Maria Luisa … e Maria
    Agostina … Déjardin"). None when no end is found."""
    for end in ends:
        try:
            found = find_person(text, end, taken)
        except re.error:
            continue
        if not found:
            continue
        span = found[0]
        run = next((r for r in runs(text) if r[0] <= span[0] and span[1] <= r[1]), span)
        span = run if free(run, taken) else span
        for sep in sorted(ITEM_START.finditer(text, 0, span[0]), key=lambda m: m.end(), reverse=True):
            at = sep.end()
            item = text[at:span[0]]
            # From the item's first capitalized word: an honorific may open it ("beati Germano …").
            cap = next((m for m in WORD.finditer(item) if _capital(m.group(0))), None)
            if cap is None:
                # The match opens its item: never widened over the item before ("Maria della Pace (Maria
                # Anna) Giuliani" after "Maria Ermellina … Grivot, "), but over the "e" of a joined name.
                if joined and not item.strip() and re.fullmatch(r"\s+ed?\s+", sep.group(0)):
                    continue
                break
            name = item[cap.start():]
            if any(fold(name).startswith(fold(g) + " ") for g in given if g):
                crosses = re.search(r"\sed?\s", text[at + cap.start():span[0]])
                if free((at + cap.start(), span[1]), taken) and (joined or not crosses):
                    span = (at + cap.start(), span[1])
                break
            if re.search(r"[,;:]", item):
                break
        return span
    return None


def _opens_with(run, given):
    """Whether a name run opens with the given name `given` as a whole word."""
    run, given = fold(run), fold(given)
    return run == given or run.startswith(given + " ")


def by_position(text, ranked, found, taken, given=None):
    """Spans proposed for the persons of one footnote list left unfound, by print order: `ranked`
    lists the list's persons in their Latin print order, `found` maps the index of each one found
    to its span. Between two found neighbours, as many free name runs as persons left unfound are
    paired with them in order; when the counts differ ("dell’Ordine dei Frati Minori" is a run too),
    each person takes the next run that opens with one of their `given` names (a list per index), in
    order, and any other gap proposes nothing. Returns {index: span}."""
    out, i = {}, 0
    while i < len(ranked):
        if i in found:
            i += 1
            continue
        j = i
        while j < len(ranked) and j not in found:
            j += 1
        lo = max((found[k][1] for k in found if k < i), default=0)
        hi = min((found[k][0] for k in found if k >= j), default=len(text))
        gap = [r for r in runs(text, taken) if lo <= r[0] and r[1] <= hi]
        if len(gap) == j - i:
            out.update({k: gap[k - i] for k in range(i, j)})
        elif given:
            at = 0
            for k in range(i, j):
                hit = next((x for x in range(at, len(gap))
                            if any(_opens_with(text[gap[x][0]:gap[x][1]], g) for g in given[k] if g)), None)
                if hit is not None:
                    out[k], at = gap[hit], hit + 1
        i = j
    return out
