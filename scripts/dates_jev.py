"""Jev (TypeSafe System One) estimates of the century a eulogy is set in; see
docs/superpowers/specs/2026-10-22-eulogy-dates-design.md, "The era estimate".

One request per eulogy, one Choice question: before Christ, the 1st to the 21st century, or cannot
tell. Only the first sentence of the 2004 Latin and of the English is sent, never a whole eulogy
(the curator's ruling, 2026-10-18; a one-sentence eulogy loses its opening place), with the eulogy's typology and the oldest edition before 2004
that prints it. An estimate is a signal for the place review, never a decision.

Standard library only.
"""

from mentions_jev import MODEL
from subject_jev import _choice, _sentences, _window


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


CENTURIES = range(1, 22)
OPTIONS = ["bc"] + [f"c{n}" for n in CENTURIES] + ["cannot_tell"]
CRITERIA = {"bc": "before Christ (the Old Testament, or the years before the birth of Christ)",
            **{f"c{n}": f"the {_ordinal(n)} century (AD {100 * (n - 1) + 1}–{100 * n})" for n in CENTURIES},
            "cannot_tell": "the clause gives no way to tell when the saint lived or the event took place"}
assert list(CRITERIA) == OPTIONS

INSTRUCTIONS = (
    "In which century did the saint of `latin_clause` (a eulogy of the Roman Martyrology; `english_clause` "
    "is its English) die, or the event it commemorates take place? Use what the clause says (an emperor, a "
    "persecution, a heresy, a religious order, a pope, a modern state) and what is known of the saint it "
    "names. `typology` says what the day marks (dies_natalis: the saint's death). `printed_by`, when "
    "given, is the year of an edition of the Martyrology that already prints this eulogy, so the date is "
    "no later than it."
)


def century_range(option):
    """The years of an option: {from, to}; before Christ only {to: -1}; None for cannot_tell."""
    if option == "bc":
        return {"to": -1}
    if option.startswith("c") and option[1:].isdigit():
        n = int(option[1:])
        return {"from": 100 * (n - 1) + 1, "to": 100 * n}
    return None


def _clause(text):
    """The first sentence, at most MAX_CLAUSE characters. When that is the whole eulogy (one short
    sentence, as most are), its opening place is dropped, so a whole eulogy is never sent; one
    without a comma is not sent at all ("")."""
    sentences = _sentences(text or "")
    if not sentences:
        return ""
    clause = _window(sentences[0][1], 0)
    if clause != text.strip():
        return clause
    return clause.split(",", 1)[1].strip() if "," in clause else ""


def request_for(la_text, en_text, typology, bound):
    """The request for one eulogy; None without a Latin text."""
    la_clause = _clause(la_text)
    if not la_clause:
        return None
    state = {"latin_clause": la_clause, "english_clause": _clause(en_text), "typology": typology,
             "printed_by": bound}
    return {"model": MODEL, "state": state,
            "questions": {"century": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}}}


def estimate_of(answer):
    """{century, probability, confidence} of the century answer; None when it names no option offered."""
    picked = _choice(answer, OPTIONS)
    if picked is None:
        return None
    century, probability, confidence = picked
    return {"century": century, "probability": probability, "confidence": confidence}


def _span(date):
    if "year" in date:
        return date["year"], date["year"]
    return date.get("from", float("-inf")), date.get("to", float("inf"))


def agrees(option, date):
    """(the option's century overlaps the date, a century next to it does too)."""
    years = century_range(option)
    if years is None:
        return False, False
    first, last = years.get("from", float("-inf")), years["to"]
    lo, hi = _span(date)
    return lo <= last and hi >= first, lo <= last + 100 and hi >= first - 100
