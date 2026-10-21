"""Jev (TypeSafe System One) requests and suggestions on the gazetteer review cards (`resolve_place`
ops); see docs/superpowers/specs/2026-10-21-gazetteer-jev-design.md, "1. The Jev request" and
"2. What goes on the card".

One request per card: what the phrase stands for (a place, a people, a relative place, not a place)
and, when the card has candidates, which one is the place. Only one Latin and one English clause are
sent, never a whole eulogy, and no coordinates. A suggestion is only ever shown to the curator.

Standard library only.
"""

from gazetteer_text import fold, parse_italian
from mentions_jev import MODEL
from subject_jev import MAX_CLAUSE, _choice, _sentences, _window

KINDS = ("place", "people", "relative", "not_place")

KIND_CRITERIA = {
    "place": "a settlement, site, building, region or country: a place one could find on a map",
    "people": "a nationality or a people (anglus, polonus, a tribe named as people), not a place",
    "relative": ("a place named only in relation to the eulogy (this city, the same monastery), which the "
                 "phrase alone does not identify"),
    "not_place": "not a place at all",
}

NONE_REASON = "Jev: none of the candidates is this place"
KIND_REASONS = {
    "people": "Jev: a nationality or people, not a place",
    "relative": "Jev: the place depends on its eulogy",
    "not_place": "Jev: not a place",
}
assert set(KIND_REASONS) == set(KINDS) - {"place"}


# The clauses sent

def latin_clause(la_text, la):
    """The sentence of the Latin text holding the phrase `la` (exact, then folded); else the first
    sentence; "" for empty text. At most MAX_CLAUSE characters."""
    sentences = _sentences(la_text or "")
    if not sentences:
        return ""
    for _, sentence in sentences:
        at = sentence.find(la)
        if la and at >= 0:
            return _window(sentence, at)
    key = fold(la or "")
    for _, sentence in sentences:
        at = fold(sentence).find(key)
        if key and at >= 0:
            return _window(sentence, 0 if len(sentence) <= MAX_CLAUSE else at)
    return _window(sentences[0][1], 0)


def english_clause(en_text, op):
    """The first English sentence naming a candidate's label or an Italian head of the card; else the
    first sentence; "" for empty text."""
    sentences = _sentences(en_text or "")
    if not sentences:
        return ""
    names = [c.get("label") for c in op.get("candidates") or []]
    names += parse_italian(op.get("it") or "")["heads"]
    names = [n for n in (fold(n) for n in names if n) if n]
    for _, sentence in sentences:
        folded = fold(sentence)
        if any(n in folded for n in names):
            return _window(sentence, 0)
    return _window(sentences[0][1], 0)


# The request

def _candidate(c):
    out = {k: c.get(k) for k in ("wikidata", "label", "description", "country", "types", "la", "p9314")}
    return out


def place_request(op, la_clause, en_clause):
    """The request for one card: `kind` always; `pick` among the candidates (c0..cN, in op order, or
    none) when it has any."""
    cands = op.get("candidates") or []
    ids = [f"c{i}" for i in range(len(cands))]
    state = {"la": op["la"], "it": op.get("it"), "latin_clause": la_clause, "english_clause": en_clause}
    if cands:
        state["candidates"] = {cid: _candidate(c) for cid, c in zip(ids, cands)}
    questions = {"kind": {
        "type": "choice",
        "instructions": ("What does the phrase `la` (in Italian, `it`) stand for in `latin_clause`, a eulogy "
                         "of the Roman Martyrology (`english_clause` is its English)?"),
        "criteria": KIND_CRITERIA}}
    if cands:
        criteria = {cid: f"`candidates.{cid}`: {c['wikidata']} {c.get('label') or ''}".rstrip()
                    + (f" ({c['description']})" if c.get("description") else "")
                    for cid, c in zip(ids, cands)}
        criteria["none"] = "None of these items is this place."
        questions["pick"] = {
            "type": "choice",
            "instructions": ("Which of the `candidates` (Wikidata items) is the place named by the phrase `la` "
                             "(Italian: `it`) in `latin_clause` and `english_clause`? Answer none if no "
                             "candidate is this place."),
            "criteria": criteria}
    return {"model": MODEL, "state": state, "questions": questions}


# The reading

def default_qid(op):
    """The item an accept applies: `suggested.wikidata`, else the first candidate's; None without either."""
    cands = op.get("candidates") or []
    return (op.get("suggested") or {}).get("wikidata") or (cands[0]["wikidata"] if cands else None)


def place_suggestion(op, answers, model=MODEL):
    """The card's suggestion: reject (a non-place kind, or none of the candidates), accept (Jev picks
    the default item), edit (another candidate); on a card without candidates only `kind`, plus a
    reject when it is not a place. None when an answer names no request option."""
    answers = answers or {}
    kind = _choice(answers.get("kind"), KINDS)
    if kind is None:
        return None
    base = {"kind": kind[0], "probability": kind[1], "confidence": kind[2], "model": model}
    if kind[0] != "place":
        return {"decision": "reject", "reason": KIND_REASONS[kind[0]], **base}
    cands = op.get("candidates") or []
    if not cands:
        return base
    ids = [f"c{i}" for i in range(len(cands))]
    chosen = _choice(answers.get("pick"), ids + ["none"])
    if chosen is None:
        return None
    pick, probability, confidence = chosen
    base.update(probability=probability, confidence=confidence)
    if pick == "none":
        return {"decision": "reject", "reason": NONE_REASON, **base}
    cand = cands[ids.index(pick)]
    out = {"decision": "accept" if cand["wikidata"] == default_qid(op) else "edit", "wikidata": cand["wikidata"]}
    if cand.get("country"):
        out["country"] = cand["country"]
    return {**out, **base}
