"""Jev (TypeSafe System One) suggestions for the Italian person-mention review cards
(CatholicOS/crmedr#97); see docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md.

Jev never writes a span: it chooses among the name runs the matcher finds in a card's context
(or answers whether a repeated name is the same person), and code copies the chosen span.
Offsets: `at` in code points within a card's context; `start`/`end` in UTF-16 code units within
the eulogy's text or footnote, as everywhere in the change-sets.

Standard library only.
"""

from mentions_italian import runs
from mentions_text import from_utf16, utf16

ITALIAN = "martyrologium_romanum_2004_it_IT"
MODEL = "jev-1.14.0"


def card_kind(op):
    """"repeat" (a name matched again), "position" (proposed by its place in a list), "not_found",
    or None for a card out of scope."""
    if op.get("op") != "add_mention" or op.get("kind") != "person" or op.get("edition") != ITALIAN:
        return None
    reasoning = op.get("reasoning") or ""
    if "matched again" in reasoning:
        return "repeat"
    if "proposed by its place in the list" in reasoning:
        return "position"
    if reasoning.endswith("was not found"):
        return "not_found"
    return None


def _who(p):
    return p.get("name"), p.get("n")


def place_persons(op, persons, latin_marks):
    """The eulogy's persons printed where the card is (its text or its footnote), in the Latin
    print order; persons the Latin does not mark come last, in persons.json order."""
    here = [p for p in persons if p["where"] == op["where"]]
    rank = {_who(m): m["start"] for m in latin_marks if m["kind"] == "person" and m["where"] == op["where"]}
    order = sorted(range(len(here)), key=lambda i: (rank.get(_who(here[i]), float("inf")), i))
    return [here[i] for i in order]


def _window(op):
    """The card's context as a UTF-16 range of the eulogy text or footnote."""
    start = op["context_start"]
    return start, start + utf16(op["context"], len(op["context"]))


def _local(op, m):
    """A mark inside the card's context as a code-point span of the context; None outside it."""
    lo, hi = _window(op)
    if m["start"] < lo or m["end"] > hi:
        return None
    ctx = op["context"]
    return from_utf16(ctx, m["start"] - lo), from_utf16(ctx, m["end"] - lo)


def neighbours(op, ordered, it_marks):
    """The persons printed just before and after the card's person in `ordered`, each with the
    words the Italian marks for them inside the card's context (`marked_as`, else None)."""
    who = (op.get("name"), op.get("n"))
    i = next((k for k, p in enumerate(ordered) if _who(p) == who), None)

    def describe(p):
        if p is None:
            return None
        span = next((s for m in it_marks if m["kind"] == "person" and m["where"] == op["where"]
                     and _who(m) == _who(p) and (s := _local(op, m))), None)
        out = {"latin_name": p["name"]}
        if p.get("n"):
            out["n"] = p["n"]
        out["marked_as"] = op["context"][span[0]:span[1]] if span else None
        return out

    before = ordered[i - 1] if i is not None and i > 0 else None
    after = ordered[i + 1] if i is not None and i + 1 < len(ordered) else None
    return {"before": describe(before), "after": describe(after)}


def candidates(op, it_marks):
    """The name runs of the card's context not covered by another mark (the card's own person may
    be marked already, after its decision was applied), numbered c1, c2… in print order."""
    ctx, (lo, hi) = op["context"], _window(op)
    who = (op.get("name"), op.get("n"))
    taken = []
    for m in it_marks:
        if m["where"] != op["where"] or m["end"] <= lo or m["start"] >= hi:
            continue
        if m["kind"] == "person" and _who(m) == who:
            continue
        a = from_utf16(ctx, max(0, m["start"] - lo))
        b = from_utf16(ctx, min(m["end"], hi) - lo)
        taken.append((a, b))
    out = []
    for i, (a, b) in enumerate(runs(ctx, taken), start=1):
        out.append({"id": f"c{i}", "words": ctx[a:b], "at": a,
                    "start": lo + utf16(ctx, a), "end": lo + utf16(ctx, b)})
    return out
