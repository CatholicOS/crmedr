"""Jev (TypeSafe System One) requests and suggestions on the gazetteer review cards (`resolve_place`
ops); see docs/superpowers/specs/2026-10-21-gazetteer-jev-design.md, "1. The Jev request" and
"2. What goes on the card".

One request per card: what the phrase stands for (a place, a people, a relative place, not a place)
and, when the card has candidates, which one is the place. Only one Latin and one English clause are
sent, never a whole eulogy, and no coordinates. A suggestion is only ever shown to the curator.

Standard library only.
"""

import re

from gazetteer_text import fold, parse_italian
from mentions_jev import MODEL
from subject_jev import MAX_CLAUSE, _choice, _sentences, _window

KINDS = ("place", "people", "relative", "not_place")

KIND_CRITERIA = {
    "place": ("a settlement, site, building, region or country: a place one could find on a map; also a "
              "council named by its city (Chalcedonense, Ephesinum), and a church or see named by its "
              "city (Ecclesia Romana, sedes Romana, Ecclesia Constantinopolitana)"),
    "people": ("a nationality or a people (anglus, polonus, a tribe or a kingdom named by its people, "
               "Merciorum)"),
    "relative": ("a place named only in relation to the eulogy (this city, the same monastery), which the "
                 "phrase alone does not identify"),
    "not_place": "not a place at all",
}

NONE_REASON = "Jev: none of the candidates is this place"
KIND_REASONS = {
    "people": "Jev: a nationality or people, and no candidate is its item",
    "relative": "Jev: the place depends on its eulogy",
    "not_place": "Jev: not a place",
}
assert set(KIND_REASONS) == set(KINDS) - {"place"}


# The clauses sent

def _fold_with_origin(text):
    """(fold(text), index in `text` of each character of it): fold changes lengths (ligatures,
    collapsed whitespace), so an index in the folded string is mapped back through this."""
    out, origin = [], []
    for i, ch in enumerate(text):
        piece = " " if ch.isspace() else fold(ch)
        if piece == " " and (not out or out[-1] == " "):
            continue
        out.extend(piece)
        origin.extend([i] * len(piece))
    while out and out[-1] == " ":
        out.pop()
        origin.pop()
    return "".join(out), origin


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
        folded, origin = _fold_with_origin(sentence)
        at = folded.find(key)
        if key and at >= 0:
            return _window(sentence, origin[at])
    return _window(sentences[0][1], 0)


def prints(la_text, la):
    """Whether the Latin text prints the phrase `la`: exactly, else folded."""
    if not la or not la_text:
        return False
    return la in la_text or fold(la) in _fold_with_origin(la_text)[0]


def english_clause(en_text, op):
    """The first English sentence naming (as a whole word) a candidate's label or an Italian head of the
    card, windowed at the name; else the first sentence; "" for empty text."""
    sentences = _sentences(en_text or "")
    if not sentences:
        return ""
    names = [c.get("label") for c in op.get("candidates") or []]
    names += [h for it in op.get("it") or [] for h in parse_italian(it)["heads"]]
    names = [n for n in (fold(n) for n in names if n) if n]
    for _, sentence in sentences:
        folded, origin = _fold_with_origin(sentence)
        hits = [m.start() for m in (re.search(r"\b" + re.escape(n) + r"\b", folded) for n in names) if m]
        if hits:
            return _window(sentence, origin[min(hits)])
    return _window(sentences[0][1], 0)


# The request

def _candidate(c):
    out = {k: c.get(k) for k in ("wikidata", "label", "description", "country", "la", "p9314")}
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
            "instructions": PICK_INSTRUCTIONS,
            "criteria": criteria}
    return {"model": MODEL, "state": state, "questions": questions}


# The curator's convention (2026-10-21, as the round-1 decisions apply it): the place as it continues
# today when it still exists on the same spot; a historical item only for a separate site, a building
# or a historical territory; and a place "near" X is not X.
PICK_INSTRUCTIONS = (
    "Which of the `candidates` (Wikidata items) is the place named by the phrase `la` (Italian: `it`) in "
    "`latin_clause` and `english_clause`, a eulogy of the Roman Martyrology? When the place still exists "
    "on the same spot, choose the item for the town or city as it is today (Tivoli for Tibur, "
    "Aix-en-Provence for Aquae Sextiae, Toulouse rather than Roman Tolosa). Choose an item for the ancient "
    "or historical place only when it is a separate site from today's town (ruins or an archaeological "
    "site, as Caesarea Maritima), when the phrase names a building (a monastery, abbey, church, castle or "
    "camp, rather than the town or mountain it stands in or on), or when it names a historical territory "
    "(a Roman province or historical region, rather than a modern region or continent of the same name). "
    "When the phrase names a place near another (prope, apud, iuxta: near, at), the near place is not that "
    "other one. When the phrase names a nationality or a people (polonus, anglus, hibernus, Merciorum, "
    "Galliarum: the Gauls), "
    "choose the item of that people, or of the kingdom named by its people (the Kingdom of Mercia). When "
    "the phrase is the adjective of a monastery (Cluniacensis: of Cluny) or the island of a monastery in a "
    "eulogy of its monks (insula Lirinensis), choose the monastery or abbey rather than its town or island; "
    "so too for the monastery's own place name in such a eulogy (Cluniaci: at Cluny Abbey). When the "
    "phrase names a council by its city (Chalcedonense, Ephesinum), choose the council's item; a church "
    "or see named by its city (Ecclesia Romana: the Diocese of Rome; sedes Romana: the Holy See; "
    "Ecclesia Constantinopolitana: the Ecumenical Patriarchate), the see's item. Asia and "
    "Africa are the continents, unless the phrase names the Roman province (Africa Proconsularis). "
    "Answer none if no candidate is this place."
)


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
    cands = op.get("candidates") or []
    # A people takes its item (the curator's convention, 2026-10-22): its pick is read as a place's is.
    if kind[0] not in ("place", "people") or (kind[0] == "people" and not cands):
        return {"decision": "reject", "reason": KIND_REASONS[kind[0]], **base}
    if not cands:
        return base
    ids = [f"c{i}" for i in range(len(cands))]
    chosen = _choice(answers.get("pick"), ids + ["none"])
    if chosen is None:
        return None
    pick, probability, confidence = chosen
    base.update(probability=probability, confidence=confidence)
    if pick == "none":
        return {"decision": "reject", "reason": NONE_REASON if kind[0] == "place" else KIND_REASONS["people"],
                **base}
    cand = cands[ids.index(pick)]
    out = {"decision": "accept" if cand["wikidata"] == default_qid(op) else "edit", "wikidata": cand["wikidata"]}
    if cand.get("country"):
        out["country"] = cand["country"]
    return {**out, **base}
