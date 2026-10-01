"""Parse the place phrases of data/places.json for the gazetteer.

Pure functions, standard library only: the Italian head toponyms, regions and
modern-country claims of an Italian (CEI) place phrase, and the candidate
nominatives of a Latin one. See docs/superpowers/specs/2026-10-01-gazetteer-design.md.
"""

import re
import unicodedata

from countries_it import COUNTRY_IT


def fold(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    return " ".join(s.lower().split())


_COUNTRY = {fold(k): v for k, v in COUNTRY_IT.items()}
# Wikidata's P297 also holds withdrawn and reserved codes; Jersey has no Italian
# label in the query. XK (Kosovo) is user-assigned but kept, since Wikidata uses it.
NOT_ASSIGNED = {"AN", "CP", "CQ", "DD", "DG", "PC", "YU"}
ISO_CODES = frozenset(set(COUNTRY_IT.values()) - NOT_ASSIGNED | {"JE"})


# The registry's conventions for a place's country (#12 review): the whole Holy
# Land is PS, as for the registry's own `country`.
COUNTRY_CONVENTIONS = {"IL": "PS"}


def convention(iso):
    return COUNTRY_CONVENTIONS.get(iso, iso)


def country_of(name):
    iso = _COUNTRY.get(fold(name))
    return convention(iso) if iso else None


# The preposition that opens an Italian place phrase ("A", "Presso", "Nell’").
LEAD_IT = re.compile(
    r"^(?:(?:nei pressi di|vicino al|vicino alla|vicino a|presso|nella|nelle|nello|negli|nel|nei"
    r"|sulla|sulle|sul|sui|alla|al|ad|a|in|da)\s+|(?:nei pressi d|vicino all|nell|sull|all)')",
    re.IGNORECASE)
# Where the head toponym ends and a region or modern-country note begins.
CONNECTOR_IT = re.compile(
    r",|\s(?:in|nel|nella|nelle|nello|nei|negli|presso|vicino a|vicino al|vicino alla|sul|sulla|sulle"
    r"|sui|sempre|ancora|ora|oggi|lungo|tra|fra|nei pressi di)(?=\s)|\s(?:nell|sull|all)'")
# A site noun before the proper name ("monastero di X", "località X").
SITE_IT = re.compile(
    r"^(?:localit[àa]\s+|(?:citt[àa]|cittadina|territorio|isola|monastero|eremo|abbazia|villaggio"
    r"|fortezza|regione|diocesi|castello|borgo|villa|contrada|frazione)\b[^,]*?\s"
    r"(?:di\s+|del\s+|della\s+|dell'|d'))(?=[A-ZÀ-ÖØ-Þ])")
# Words before the name in a region or modern-country segment.
SEGMENT_PREFIX_IT = re.compile(
    r"^(?:(?:il|lo|la|i|gli|le)\s+|l')?(?:(?:territorio|regione)\s+(?:di\s+|del\s+|della\s+|dell'|d'))?"
    r"(?:(?:odiern[oa]|attuale|antic[oa])\s+)?")


MODERN_IT = re.compile(r"odiern|attuale")


def _follows_modern(s, cuts, i):
    """'ora in X', 'oggi in X': the cut before 'in' is 'ora' or 'oggi' with
    nothing between them."""
    if i == 0:
        return False
    prev = cuts[i - 1]
    return prev.group(0).strip() in ("ora", "oggi") and not s[prev.end():cuts[i].start()].strip(" ,")


def _dedupe(xs):
    return list(dict.fromkeys(x for x in xs if x))


def parse_italian(it):
    s = it.replace("’", "'").strip()
    m = LEAD_IT.match(s)
    if m:
        s = s[m.end():]
    cuts = list(CONNECTOR_IT.finditer(s))
    head = (s[:cuts[0].start()] if cuts else s).strip(" ,")
    heads = []
    if head:
        site_text = head[0].lower() + head[1:]
        site = SITE_IT.match(site_text)
        if site:
            heads = [site_text, site_text[site.end():].strip()]
        elif head[0].isupper():
            heads = [head]
    regions, claims = [], []
    for i, cut in enumerate(cuts):
        end = cuts[i + 1].start() if i + 1 < len(cuts) else len(s)
        seg = s[cut.end():end].strip(" ,")
        prefix = SEGMENT_PREFIX_IT.match(seg).group(0)
        seg = seg[len(prefix):].strip()
        if not seg:
            continue
        # Only explicit modern wording states a modern country ("nell'odierna X",
        # "oggi in X", "ora X"); a bare "in Siria" may name the ancient region.
        explicit = MODERN_IT.search(prefix) or (cut.group(0).strip() in ("ora", "oggi")
                                               or _follows_modern(s, cuts, i))
        iso = country_of(seg)
        if iso and explicit:
            claims.append(iso)
        elif seg[0].isupper():
            regions.append(seg)
    return {"heads": _dedupe(h.replace("'", "’") for h in heads),
            "regions": _dedupe(r.replace("'", "’") for r in regions),
            "claims": _dedupe(claims)}


LEAD_LA = {"in", "ad", "apud", "prope", "iuxta", "item", "ibidem", "inter", "sub", "super", "circa"}
WORD_LA = re.compile(r"[^\W\d_]+")
# Ending of a locative or ablative -> endings of the nominatives it may come from.
# This only adds evidence, so a missing form sends the place to review.
LATIN_ENDINGS = [
    ("ibus", ("es", "a")), ("ine", ("o",)), ("one", ("o",)), ("ae", ("a", "ae")),
    ("ii", ("ium", "ius", "ii")), ("is", ("a", "ae", "i", "is", "um", "us")),
    ("i", ("um", "us", "ium", "i", "is", "a")), ("o", ("um", "us", "o", "a")),
    ("e", ("is", "e", "es")), ("a", ("a",)),
]


def latin_nominatives(la):
    """Nominatives of the head words: the capitalized words before the first
    connector (in, prope, apud...); a region named after it is not the place."""
    out = set()
    started = False
    for word in WORD_LA.findall(la):
        w = fold(word)
        if w in LEAD_LA:
            if started:
                break
            continue
        if not word[0].isupper():
            continue
        started = True
        out.add(w)
        for ending, noms in LATIN_ENDINGS:
            if w.endswith(ending) and len(w) > len(ending) + 1:
                stem = w[: -len(ending)]
                out.update(stem + n for n in noms)
    return out
