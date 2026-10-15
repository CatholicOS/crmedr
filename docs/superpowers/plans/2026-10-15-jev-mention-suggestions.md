# Jev suggestions on the Italian mention review cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Jev (TypeSafe System One) suggestion, with probability and confidence, to every in-scope Italian person-mention review card, evaluated against the curator's decisions before it ships, and show it on MentionCard with a "Take the suggestion" button.

**Architecture:** crmedr gains `scripts/mentions_jev.py` (pure card → request → suggestion functions, plus a cached stdlib HTTP client) and `scripts/suggest_mentions.py` (`suggest` writes `suggested` onto a review change-set; `evaluate` scores suggestions against decided change-sets). Jev only picks among candidate spans the matcher finds (or answers a same/another/not-this-person Choice); code copies spans. martyrology-frontend's MentionCard displays `suggested` and records it as an ordinary decision.

**Tech Stack:** Python 3 standard library (crmedr scripts, unittest run by pytest); TypeScript/React/Next.js with next-intl and vitest (martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md`

## Global Constraints

- Standard library only in crmedr scripts: the HTTP API through `urllib`, not the TypeSafe SDK.
- The model is pinned: `MODEL = "jev-1.14.0"`, never `jev-latest`.
- Endpoint: `POST https://api.typesafe.ai/v1/systemone`, header `Authorization: Bearer <key>`.
- The key is read from `TYPESAFE_API_KEY`, else from `~/.config/typesafe/api_key`; it is never printed, logged, written, or put in an exception message.
- Only a card's own `context` is sent, never a whole eulogy or anything else from martyrology-texts.
- Responses are cached in `.cache/typesafe/<sha256 of the request body>.json` (`.cache/` is git-ignored).
- Scope: `add_mention` cards of kind `person` in edition `martyrologium_romanum_2004_it_IT`.
- `suggest` never touches `decision` or `edited`; nothing is ever applied without the curator.
- Review and decided change-sets quote the 2004 text: they stay outside every repository (CHANGESETS_DIR on the server, the scratchpad locally). Never commit `*.decided.json` or `:Zone.Identifier` files.
- Never `git add` the whole crmedr `data/` or `docs/` directory; add files by name.
- Ship gate: suggestions ship only if, on the strict set, some confidence threshold gives ≥ 95% agreement with ≥ 1/3 of the cards suggested; otherwise the result is reported to the curator and nothing ships.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf`.

## Review Focus

1. A decided January/February card whose own person is now marked in `data/mentions.json` (the decision was applied): its correct span must still be a candidate, or the evaluation would score "none" as right. Test: `test_the_cards_own_person_does_not_hide_a_candidate` (Task 1).
2. A context with a character outside the BMP: candidate and mark offsets must convert between code points and UTF-16 exactly. Test: `test_offsets_are_utf16_across_a_non_bmp_character` (Task 1).
3. An answer naming an option the request did not offer (or a non-choice answer): no suggestion, never a crash. Test: `test_an_unknown_option_gives_no_suggestion` (Task 2).
4. A question's wording changed between runs: the cache must not return the old wording's answer. Test: `test_the_cache_key_changes_with_the_question` (Task 3).
5. Re-running `suggest` with a higher threshold: a `suggested` from an earlier run that no longer reaches it is removed, and `decision`/`edited` are never touched. Test: `test_a_stale_suggestion_is_removed_and_decisions_are_kept` (Task 4).

---

### Task 1: Card kinds, persons in place, neighbours and candidates

**Files:**
- Create: `scripts/mentions_jev.py`
- Test: `tests/test_mentions_jev.py`

**Interfaces:**
- Consumes: `mentions_italian.runs(text, taken=())` → list of code-point `(start, end)`; `mentions_text.utf16(text, i)`, `mentions_text.from_utf16(text, u)`.
- Produces:
  - `ITALIAN = "martyrologium_romanum_2004_it_IT"`, `MODEL = "jev-1.14.0"`
  - `card_kind(op: dict) -> str | None` (`"repeat"`, `"position"`, `"not_found"`)
  - `place_persons(op: dict, persons: list[dict], latin_marks: list[dict]) -> list[dict]`
  - `neighbours(op: dict, ordered: list[dict], it_marks: list[dict]) -> dict` (`{"before": {...}|None, "after": {...}|None}`)
  - `candidates(op: dict, it_marks: list[dict]) -> list[dict]`, each `{"id": "c1", "words": str, "at": int, "start": int, "end": int}` (`at` code points in the context; `start`/`end` UTF-16 in the eulogy text or footnote)

- [ ] **Step 1: Write the failing tests**

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_jev as mj  # noqa: E402

IT = "martyrologium_romanum_2004_it_IT"
FN = {"footnote": 1}


def card(reasoning, name="Pompeia", n=None, form="Pompea", context="santi Potamia, Pompea, Rodana, Biblis",
         context_start=100, start=None, end=None, where=FN):
    op = {"op": "add_mention", "kind": "person", "edition": IT, "eulogy": "mr:0602-x", "where": where,
          "name": name, "form": form, "context": context, "context_start": context_start, "reasoning": reasoning,
          "decision": None, "edited": None}
    if n:
        op["n"] = n
    if form is not None:
        i = context.index(form)
        op["start"], op["end"] = context_start + i, context_start + i + len(form)
    else:
        op["start"] = op["end"] = None
    if start is not None:
        op["start"], op["end"] = start, end
    return op


def mark(name, context, word, context_start=100, n=None, where=FN, kind="person"):
    i = context.index(word)
    m = {"kind": kind, "where": where, "start": context_start + i, "end": context_start + i + len(word), "name": name}
    if n:
        m["n"] = n
    return m


class CardKindTest(unittest.TestCase):
    def test_the_three_kinds_and_the_rest(self):
        self.assertEqual(mj.card_kind(card("Pothinus matched again: mark it if it names this person once more")), "repeat")
        self.assertEqual(mj.card_kind(card("Pompeia was not found by name: proposed by its place in the list")), "position")
        self.assertEqual(mj.card_kind(card("Helpis was not found", form=None)), "not_found")
        self.assertIsNone(mj.card_kind(card("Pompeia is named inside a place phrase, which was kept")))
        self.assertIsNone(mj.card_kind(dict(card("Pompeia was not found"), edition="martyrologium_romanum_2004")))
        self.assertIsNone(mj.card_kind(dict(card("Pompeia was not found"), kind="place")))


class PlacePersonsTest(unittest.TestCase):
    def test_persons_of_the_cards_place_in_latin_print_order(self):
        persons = [{"name": "Rodana", "where": FN}, {"name": "Potamia", "where": FN}, {"name": "Pothinus", "where": "text"},
                   {"name": "Pompeia", "where": FN}, {"name": "Biblis", "where": FN}]
        latin = [{"kind": "person", "where": FN, "name": "Potamia", "start": 5},
                 {"kind": "person", "where": FN, "name": "Pompeia", "start": 9},
                 {"kind": "person", "where": FN, "name": "Rodana", "start": 15}]
        ordered = mj.place_persons(card("x proposed by its place in the list"), persons, latin)
        # Unmarked in the Latin (Biblis) last, in persons.json order.
        self.assertEqual([p["name"] for p in ordered], ["Potamia", "Pompeia", "Rodana", "Biblis"])


class NeighboursTest(unittest.TestCase):
    def test_the_persons_before_and_after_with_their_marked_words_inside_the_context(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ordered = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}, {"name": "Rodana", "where": FN}]
        it_marks = [mark("Potamia", op["context"], "Potamia")]  # Rodana not marked
        self.assertEqual(mj.neighbours(op, ordered, it_marks),
                         {"before": {"latin_name": "Potamia", "marked_as": "Potamia"},
                          "after": {"latin_name": "Rodana", "marked_as": None}})

    def test_a_mark_outside_the_context_is_not_quoted(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ordered = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}]
        far = {"kind": "person", "where": FN, "name": "Potamia", "start": 10, "end": 17}
        self.assertEqual(mj.neighbours(op, ordered, [far])["before"], {"latin_name": "Potamia", "marked_as": None})

    def test_the_first_of_a_list_has_no_before(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        self.assertIsNone(mj.neighbours(op, [{"name": "Pompeia", "where": FN}], [])["before"])


class CandidatesTest(unittest.TestCase):
    def test_free_name_runs_of_the_context_in_utf16_eulogy_offsets(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ctx = op["context"]
        it_marks = [mark("Potamia", ctx, "Potamia"), mark("Rodana", ctx, "Rodana")]
        cands = mj.candidates(op, it_marks)
        self.assertEqual([(c["id"], c["words"]) for c in cands], [("c1", "Pompea"), ("c2", "Biblis")])
        self.assertEqual((cands[0]["start"], cands[0]["end"]), (op["start"], op["end"]))
        self.assertEqual(cands[0]["at"], ctx.index("Pompea"))

    def test_the_cards_own_person_does_not_hide_a_candidate(self):
        # A decided card whose decision was applied: Pompeia is marked now, and must stay a candidate.
        op = card("Pompeia was not found by name: proposed by its place in the list")
        it_marks = [mark("Pompeia", op["context"], "Pompea")]
        self.assertIn("Pompea", [c["words"] for c in mj.candidates(op, it_marks)])

    def test_another_n_of_the_same_name_does_hide_it(self):
        op = card("Pompeia was not found by name: proposed by its place in the list", n=2)
        it_marks = [mark("Pompeia", op["context"], "Pompea")]  # the first Pompeia
        self.assertNotIn("Pompea", [c["words"] for c in mj.candidates(op, it_marks)])

    def test_offsets_are_utf16_across_a_non_bmp_character(self):
        ctx = "𝔄 santi Potamia, Pompea"
        op = card("Pompeia was not found by name: proposed by its place in the list", context=ctx, form=None,
                  start=None, end=None)
        cands = mj.candidates(op, [])
        pompea = next(c for c in cands if c["words"] == "Pompea")
        # 𝔄 is two UTF-16 code units: the eulogy offset is one more than the code-point index.
        self.assertEqual(pompea["start"], 100 + ctx.index("Pompea") + 1)
        self.assertEqual(pompea["at"], ctx.index("Pompea"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'mentions_jev'`

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: all pass. If `runs` returns a run for the leading lowercase word "santi", that is a test-data assumption failing, not the code: `runs` only starts runs at capitalized words, so "santi" is never a run.

- [ ] **Step 5: Run the whole suite and commit**

Run: `python3 -m pytest -q`
Expected: all pass.

```bash
git add scripts/mentions_jev.py tests/test_mentions_jev.py
git commit -m "mentions_jev: card kinds, persons in place, neighbours and candidate spans (#97)"
```

### Task 2: The request body and the suggestion

**Files:**
- Modify: `scripts/mentions_jev.py`
- Test: `tests/test_mentions_jev.py`

**Interfaces:**
- Consumes: Task 1's `card_kind`, `place_persons`, `neighbours`, `candidates`, `MODEL`; `mentions_italian.ItalianNames.forms(mrid, name) -> list[str]`.
- Produces:
  - `request_for(op, persons, latin_marks, it_marks, names) -> tuple[dict | None, list[dict]]`: the request body (`{"model", "state", "questions"}`) and the candidates; `(None, [])` when the card is out of scope or a span card has no candidate.
  - `suggestion(op, answer: dict, cands: list[dict], model: str) -> dict | None`: `{"decision": "accept"|"reject"|"edit", ["start", "end", "form",] "probability", "confidence", "model"}`.
  - `IDENTITY` (the repeat Choice question dict), `span_question(cands) -> dict`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_mentions_jev.py`, before `if __name__`)

```python
import mentions_italian as mi  # noqa: E402

NAMES = mi.ItalianNames({"mr:0101-a": "Sanctae Pompeia et Potamia"}, {"mr:0101-a": "Sante Pompea e Potamia"})
PERSONS = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}, {"name": "Rodana", "where": FN}]
LATIN = [{"kind": "person", "where": FN, "name": n, "start": i} for i, n in enumerate(["Potamia", "Pompeia", "Rodana"])]


class RequestTest(unittest.TestCase):
    def test_a_span_card_asks_one_choice_over_its_candidates_and_none(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        body, cands = mj.request_for(op, PERSONS, LATIN, [mark("Potamia", op["context"], "Potamia")], NAMES)
        self.assertEqual(body["model"], "jev-1.14.0")
        self.assertEqual(list(body["questions"]), ["span"])
        q = body["questions"]["span"]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(list(q["criteria"]), [c["id"] for c in cands] + ["none"])
        state = body["state"]
        self.assertEqual(state["person"], {"latin_name": "Pompeia", "italian_forms": ["Pompea", "Pompeia"]})
        self.assertEqual(state["where"], "footnote 1")
        self.assertEqual(state["proposed"], "Pompea")
        self.assertEqual(state["neighbours"]["before"], {"latin_name": "Potamia", "marked_as": "Potamia"})
        self.assertEqual(state["candidates"], {c["id"]: {"words": c["words"], "at": c["at"]} for c in cands})
        self.assertEqual([p["latin_name"] for p in state["persons_in_this_place"]], ["Potamia", "Pompeia", "Rodana"])

    def test_a_repeat_card_asks_the_identity_choice_without_candidates(self):
        op = card("Pothinus matched again: mark it if it names this person once more", name="Pothinus",
                  form="Potino", context="il nonagenario vescovo Potino rese", where="text")
        body, cands = mj.request_for(op, [{"name": "Pothinus", "where": "text"}], [], [], NAMES)
        self.assertEqual(list(body["questions"]), ["identity"])
        self.assertEqual(list(body["questions"]["identity"]["criteria"]),
                         ["same_person", "another_person", "not_this_person"])
        self.assertNotIn("candidates", body["state"])
        self.assertEqual(cands, [])

    def test_out_of_scope_or_no_candidate_gives_no_request(self):
        self.assertEqual(mj.request_for(card("Pompeia is named inside a place phrase"), PERSONS, LATIN, [], NAMES),
                         (None, []))
        op = card("Helpis was not found", name="Helpis", form=None, context="sono: santi e martiri")
        self.assertEqual(mj.request_for(op, PERSONS, LATIN, [], NAMES), (None, []))


def choice(pick, probabilities, confidence=0.9):
    return {"type": "choice", "choice": pick, "probabilities": probabilities, "confidence": confidence}


class SuggestionTest(unittest.TestCase):
    def setUp(self):
        self.op = card("Pompeia was not found by name: proposed by its place in the list")
        self.cands = mj.candidates(self.op, [mark("Potamia", self.op["context"], "Potamia"),
                                             mark("Rodana", self.op["context"], "Rodana")])

    def test_the_proposed_candidate_is_an_accept(self):
        s = mj.suggestion(self.op, choice("c1", {"c1": 0.93, "c2": 0.05, "none": 0.02}), self.cands, "jev-1.14.0")
        self.assertEqual(s, {"decision": "accept", "probability": 0.93, "confidence": 0.9, "model": "jev-1.14.0"})

    def test_another_candidate_is_an_edit_with_its_span(self):
        s = mj.suggestion(self.op, choice("c2", {"c1": 0.1, "c2": 0.85, "none": 0.05}), self.cands, "jev-1.14.0")
        c2 = self.cands[1]
        self.assertEqual((s["decision"], s["start"], s["end"], s["form"]), ("edit", c2["start"], c2["end"], "Biblis"))

    def test_none_is_a_reject(self):
        s = mj.suggestion(self.op, choice("none", {"c1": 0.1, "c2": 0.1, "none": 0.8}), self.cands, "jev-1.14.0")
        self.assertEqual(s["decision"], "reject")

    def test_repeat_answers(self):
        op = card("Pothinus matched again: mark it if it names this person once more", name="Pothinus",
                  form="Potino", context="vescovo Potino rese", where="text")
        probs = {"same_person": 0.8, "another_person": 0.15, "not_this_person": 0.05}
        self.assertEqual(mj.suggestion(op, choice("same_person", probs), [], "m")["decision"], "accept")
        self.assertEqual(mj.suggestion(op, choice("another_person", probs), [], "m")["decision"], "reject")
        self.assertEqual(mj.suggestion(op, choice("not_this_person", probs), [], "m")["decision"], "reject")

    def test_an_unknown_option_gives_no_suggestion(self):
        self.assertIsNone(mj.suggestion(self.op, choice("c9", {"c9": 1.0}), self.cands, "m"))
        self.assertIsNone(mj.suggestion(self.op, {"type": "noul", "noul": 0.9}, self.cands, "m"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: FAIL with `AttributeError: module 'mentions_jev' has no attribute 'request_for'`

- [ ] **Step 3: Write the implementation** (append to `scripts/mentions_jev.py`)

```python
IDENTITY = {
    "type": "choice",
    "instructions": ("The `person` is already marked earlier in this text or footnote. Do the words `proposed`, "
                     "printed in `context`, name the same person again?"),
    "criteria": {
        "same_person": ("The same person named again. In running text, and in a pair of saints, a name printed "
                        "again is the same person unless the text says it is another (\"un altro\", \"un'altra\")."),
        "another_person": ("Another person who bears the same name: the text says so (\"un altro Dionigi\"), or the "
                           "name is printed again in a list of martyrs, where a repeated name is always a different "
                           "person."),
        "not_this_person": ("Not this person at all: an institution, church, order or place named after the saint "
                            "(\"l'Ordine Ospedaliero di San Giovanni di Dio\"), a title, or a different saint of the "
                            "same name named for comparison."),
    },
}


def span_question(cands):
    criteria = {c["id"]: f"the words \"{c['words']}\" (at character {c['at']} of `context`)" for c in cands}
    criteria["none"] = ("No candidate names this person: they are not printed in this context, or only inside a "
                        "longer name of someone else.")
    return {
        "type": "choice",
        "instructions": ("Which of the `candidates` are the words that name the `person` in this Italian text: the "
                         "person of that Latin name (and number `n`, when given) among `persons_in_this_place`, "
                         "printed in the Latin order, so between the `neighbours`? Answer none if no candidate "
                         "names them."),
        "criteria": criteria,
    }


def request_for(op, persons, latin_marks, it_marks, names):
    """The request for one card and its candidates; (None, []) when the card is out of scope, or a
    span card whose context holds no candidate."""
    kind = card_kind(op)
    if kind is None:
        return None, []
    ordered = place_persons(op, persons, latin_marks)
    person = {"latin_name": op["name"]}
    if op.get("n"):
        person["n"] = op["n"]
    person["italian_forms"] = names.forms(op["eulogy"], op["name"])[:4]
    where = "text" if op["where"] == "text" else f"footnote {op['where']['footnote']}"
    state = {
        "eulogy": op["eulogy"],
        "where": where,
        "person": person,
        "persons_in_this_place": [{"latin_name": p["name"], **({"n": p["n"]} if p.get("n") else {})}
                                  for p in ordered],
        "neighbours": neighbours(op, ordered, it_marks),
        "context": op["context"],
        "proposed": op.get("form"),
    }
    if kind == "repeat":
        return {"model": MODEL, "state": state, "questions": {"identity": IDENTITY}}, []
    cands = candidates(op, it_marks)
    if not cands:
        return None, []
    state["candidates"] = {c["id"]: {"words": c["words"], "at": c["at"]} for c in cands}
    return {"model": MODEL, "state": state, "questions": {"span": span_question(cands)}}, cands


REPEAT_DECISIONS = {"same_person": "accept", "another_person": "reject", "not_this_person": "reject"}


def suggestion(op, answer, cands, model):
    """The card's suggestion from Jev's answer, or None when the answer is not a usable choice."""
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        return None
    pick = answer.get("choice")
    probability = (answer.get("probabilities") or {}).get(pick)
    if probability is None:
        return None
    base = {"probability": round(probability, 4), "confidence": round(answer.get("confidence", 0.0), 4),
            "model": model}
    if card_kind(op) == "repeat":
        decision = REPEAT_DECISIONS.get(pick)
        return {"decision": decision, **base} if decision else None
    if pick == "none":
        return {"decision": "reject", **base}
    c = next((c for c in cands if c["id"] == pick), None)
    if c is None:
        return None
    if (op.get("start"), op.get("end")) == (c["start"], c["end"]):
        return {"decision": "accept", **base}
    return {"decision": "edit", "start": c["start"], "end": c["end"], "form": c["words"], **base}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: all pass. `italian_forms` for Pompeia is `["Pompea", "Pompeia"]` because `ItalianNames` puts the subject pair's form first and the stored name last; if it differs, print `NAMES.forms("mr:0602-x", "Pompeia")` and check the lexicon learned "Pompeia" → "Pompea" from the fixture pair before touching the code.

- [ ] **Step 5: Run the whole suite and commit**

Run: `python3 -m pytest -q`
Expected: all pass.

```bash
git add scripts/mentions_jev.py tests/test_mentions_jev.py
git commit -m "mentions_jev: the request body and the suggestion for a card (#97)"
```

### Task 3: The cached TypeSafe client

**Files:**
- Modify: `scripts/mentions_jev.py`
- Test: `tests/test_mentions_jev.py`

**Interfaces:**
- Produces:
  - `API_URL = "https://api.typesafe.ai/v1/systemone"`, `KEY_FILE = Path.home() / ".config" / "typesafe" / "api_key"`
  - `api_key(env=os.environ, key_file=KEY_FILE) -> str | None`
  - `class TypeSafeError(Exception)`, `class KeyRefused(TypeSafeError)`
  - `class TypeSafe(key, cache_dir, post=http_post, sleep=time.sleep, attempts=5)` with `ask(body: dict) -> dict` (the full response: `{"model", "answers", "usage"}`) and `cached(body: dict) -> bool`
  - `cache_key(body: dict) -> str`

- [ ] **Step 1: Write the failing tests** (append before `if __name__`)

```python
import json  # noqa: E402
import tempfile  # noqa: E402

BODY = {"model": "jev-1.14.0", "state": {"context": "x"}, "questions": {"span": {"type": "choice"}}}
OK = (200, json.dumps({"model": "jev-1.14.0", "answers": {"span": {"type": "choice"}}}).encode())


class FakePost:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, data, key):
        self.calls.append((url, json.loads(data), key))
        return self.responses.pop(0)


class ClientTest(unittest.TestCase):
    def client(self, post, key="sk-secret"):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.slept = []
        return mj.TypeSafe(key, Path(self.tmp.name), post=post, sleep=self.slept.append)

    def test_asks_once_then_reads_the_cache(self):
        post = FakePost(OK)
        ts = self.client(post)
        self.assertEqual(ts.ask(BODY)["model"], "jev-1.14.0")
        self.assertTrue(ts.cached(BODY))
        ts.ask(BODY)
        self.assertEqual(len(post.calls), 1)
        self.assertEqual(post.calls[0][0], "https://api.typesafe.ai/v1/systemone")

    def test_the_cache_key_changes_with_the_question(self):
        other = json.loads(json.dumps(BODY))
        other["questions"]["span"]["instructions"] = "reworded"
        self.assertNotEqual(mj.cache_key(BODY), mj.cache_key(other))
        self.assertEqual(mj.cache_key(BODY), mj.cache_key(json.loads(json.dumps(BODY))))

    def test_retries_overload_with_backoff(self):
        post = FakePost((429, b"{}"), (529, b"{}"), OK)
        self.client(post).ask(BODY)
        self.assertEqual(self.slept, [1, 2])

    def test_a_refused_key_stops_and_never_shows_the_key(self):
        ts = self.client(FakePost((401, b'{"error": "bad key"}')))
        with self.assertRaises(mj.KeyRefused) as e:
            ts.ask(BODY)
        self.assertNotIn("sk-secret", str(e.exception))

    def test_a_bad_request_is_an_error_with_the_apis_message(self):
        ts = self.client(FakePost((400, b'{"error": "max_tokens_exceeded"}')))
        with self.assertRaises(mj.TypeSafeError) as e:
            ts.ask(BODY)
        self.assertIn("max_tokens_exceeded", str(e.exception))
        self.assertNotIsInstance(e.exception, mj.KeyRefused)

    def test_gives_up_after_the_attempts(self):
        ts = self.client(FakePost(*[(503, b"{}")] * 5))
        with self.assertRaises(mj.TypeSafeError):
            ts.ask(BODY)
        self.assertEqual(len(self.slept), 5)

    def test_no_key_is_an_error_only_when_a_request_is_needed(self):
        post = FakePost(OK)
        with_key = self.client(post)
        with_key.ask(BODY)  # fills the cache
        without = mj.TypeSafe(None, Path(self.tmp.name), post=FakePost())
        self.assertEqual(without.ask(BODY)["model"], "jev-1.14.0")
        with self.assertRaises(mj.TypeSafeError):
            without.ask(dict(BODY, state={"context": "y"}))

    def test_the_key_from_the_environment_else_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "api_key"
            f.write_text("from-file\n")
            self.assertEqual(mj.api_key({"TYPESAFE_API_KEY": "from-env"}, f), "from-env")
            self.assertEqual(mj.api_key({}, f), "from-file")
            self.assertIsNone(mj.api_key({}, Path(d) / "missing"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: FAIL with `AttributeError: module 'mentions_jev' has no attribute 'TypeSafe'`

- [ ] **Step 3: Write the implementation**

Add at the top of `scripts/mentions_jev.py`, after the docstring:

```python
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
```

Append:

```python
API_URL = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = Path.home() / ".config" / "typesafe" / "api_key"
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}


class TypeSafeError(Exception):
    """A request TypeSafe did not answer; its message never holds the key."""


class KeyRefused(TypeSafeError):
    """401: the key was refused; the run stops."""


def api_key(env=os.environ, key_file=KEY_FILE):
    """The key from TYPESAFE_API_KEY, else from the curator's key file; None when there is none."""
    key = (env.get("TYPESAFE_API_KEY") or "").strip()
    if not key and key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
    return key or None


def _encode(body):
    return json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")


def cache_key(body):
    return hashlib.sha256(_encode(body)).hexdigest()


def http_post(url, data, key, timeout=60):
    """POST `data` with the key; (status, raw body)."""
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "crmedr-suggest-mentions"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _message(raw):
    return raw.decode("utf-8", "replace")[:300]


class TypeSafe:
    """The System One endpoint, each answer cached under the hash of its request."""

    def __init__(self, key, cache_dir, post=http_post, sleep=time.sleep, attempts=5):
        self.key, self.cache_dir, self.post, self.sleep, self.attempts = key, Path(cache_dir), post, sleep, attempts

    def _path(self, body):
        return self.cache_dir / f"{cache_key(body)}.json"

    def cached(self, body):
        return self._path(body).exists()

    def ask(self, body):
        path = self._path(body)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        if not self.key:
            raise TypeSafeError("no TypeSafe key: set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key")
        status, raw = None, b""
        for attempt in range(self.attempts):
            status, raw = self.post(API_URL, _encode(body), self.key)
            if status == 200:
                out = json.loads(raw)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                return out
            if status == 401:
                raise KeyRefused("the TypeSafe key was refused")
            if status not in RETRY_STATUSES:
                raise TypeSafeError(f"HTTP {status}: {_message(raw)}")
            self.sleep(2 ** attempt)
        raise TypeSafeError(f"HTTP {status} after {self.attempts} attempts: {_message(raw)}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest -q tests/test_mentions_jev.py`
Expected: all pass. `test_gives_up_after_the_attempts` expects 5 sleeps: the loop sleeps after each of the five failed attempts (1, 2, 4, 8, 16 s; the tests record them instead of sleeping).

- [ ] **Step 5: Run the whole suite and commit**

Run: `python3 -m pytest -q`
Expected: all pass.

```bash
git add scripts/mentions_jev.py tests/test_mentions_jev.py
git commit -m "mentions_jev: a cached TypeSafe client, the key never shown (#97)"
```

### Task 4: `suggest_mentions.py`: suggest and evaluate

**Files:**
- Create: `scripts/suggest_mentions.py`
- Test: `tests/test_suggest_mentions.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`card_kind`, `request_for`, `suggestion`, `TypeSafe`, `TypeSafeError`, `KeyRefused`, `api_key`, `ITALIAN`); `mentions_italian.ItalianNames`.
- Produces:
  - `DEFAULT_MIN_CONFIDENCE = 1.0` (no suggestion until Task 5 sets it from the evaluation)
  - `load_data(repo_root) -> dict` with keys `persons` (`{mrid: [person]}`, Latin persons.json), `latin` and `italian` (`{mrid: [mark]}` from data/mentions.json), `names` (`ItalianNames`)
  - `ask_card(op, data, client) -> tuple[dict | None, str | None]`: the unthresholded suggestion and an error message
  - `suggest_ops(ops, data, client, min_confidence) -> dict` counts `{"suggested", "below", "skipped", "errors"}`; mutates `ops` in place (only the `suggested` key)
  - `curator_decision(op) -> tuple`: `("accept",)`, `("reject",)` or `("edit", start, end)`; an edit equal to the proposed span counts as accept
  - `evaluate_ops(ops, data, client) -> list[dict]` rows `{"id", "kind", "decision", "suggested"}` (`suggested` None when no answer)
  - `report(rows, thresholds) -> str`
  - `main(argv)`

- [ ] **Step 1: Write the failing tests**

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_italian as mi  # noqa: E402
import mentions_jev as mj  # noqa: E402
import suggest_mentions as sm  # noqa: E402

IT = "martyrologium_romanum_2004_it_IT"
FN = {"footnote": 1}
CTX = "santi Potamia, Pompea, Rodana"


def op(reasoning, name="Pompeia", form="Pompea", decision=None, edited=None, oid="a"):
    i = CTX.index(form) if form else None
    return {"op": "add_mention", "id": oid, "kind": "person", "edition": IT, "eulogy": "mr:0602-x", "where": FN,
            "name": name, "form": form, "start": 100 + i if form else None, "end": 100 + i + len(form) if form else None,
            "context": CTX, "context_start": 100, "reasoning": reasoning, "decision": decision, "edited": edited}


DATA = {"persons": {"mr:0602-x": [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN},
                                  {"name": "Rodana", "where": FN}]},
        "latin": {"mr:0602-x": []},
        "italian": {"mr:0602-x": [{"kind": "person", "where": FN, "name": "Potamia", "start": 106, "end": 113},
                                  {"kind": "person", "where": FN, "name": "Rodana", "start": 123, "end": 129}]},
        "names": mi.ItalianNames({}, {})}
POSITION = "Pompeia was not found by name: proposed by its place in the list"


class StubClient:
    """Answers every span question with `pick` at `confidence`."""

    def __init__(self, pick="c1", confidence=0.9, error=None):
        self.pick, self.confidence, self.error, self.bodies = pick, confidence, error, []

    def ask(self, body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        q = next(iter(body["questions"]))
        options = list(body["questions"][q]["criteria"])
        probs = {o: (0.9 if o == self.pick else 0.1 / (len(options) - 1)) for o in options}
        return {"model": "jev-1.14.0", "answers": {q: {"type": "choice", "choice": self.pick,
                                                      "probabilities": probs, "confidence": self.confidence}}}


class SuggestTest(unittest.TestCase):
    def test_writes_a_suggestion_at_or_above_the_threshold(self):
        ops = [op(POSITION)]
        counts = sm.suggest_ops(ops, DATA, StubClient("c1", 0.9), 0.8)
        self.assertEqual(ops[0]["suggested"]["decision"], "accept")
        self.assertEqual(counts, {"suggested": 1, "below": 0, "skipped": 0, "errors": 0})

    def test_a_stale_suggestion_is_removed_and_decisions_are_kept(self):
        ops = [op(POSITION, decision="reject", edited={"reason": "x"})]
        ops[0]["suggested"] = {"decision": "accept", "probability": 0.99, "confidence": 0.99, "model": "old"}
        counts = sm.suggest_ops(ops, DATA, StubClient("c1", 0.5), 0.8)
        self.assertNotIn("suggested", ops[0])
        self.assertEqual((ops[0]["decision"], ops[0]["edited"]), ("reject", {"reason": "x"}))
        self.assertEqual(counts["below"], 1)

    def test_an_out_of_scope_card_is_skipped_without_a_request(self):
        client = StubClient()
        counts = sm.suggest_ops([op("Pompeia is named inside a place phrase, which was kept")], DATA, client, 0.0)
        self.assertEqual((counts["skipped"], client.bodies), (1, []))

    def test_an_api_error_leaves_the_card_without_a_suggestion(self):
        ops = [op(POSITION)]
        counts = sm.suggest_ops(ops, DATA, StubClient(error=mj.TypeSafeError("HTTP 400: too long")), 0.0)
        self.assertNotIn("suggested", ops[0])
        self.assertEqual(counts["errors"], 1)

    def test_a_refused_key_stops_the_run(self):
        with self.assertRaises(mj.KeyRefused):
            sm.suggest_ops([op(POSITION)], DATA, StubClient(error=mj.KeyRefused("refused")), 0.0)


class EvaluateTest(unittest.TestCase):
    def test_the_curators_decision_with_an_edit_on_the_proposed_span_as_accept(self):
        self.assertEqual(sm.curator_decision(op(POSITION, decision="accept")), ("accept",))
        same = op(POSITION, decision="edit")
        same["edited"] = {"start": same["start"], "end": same["end"], "form": "Pompea"}
        self.assertEqual(sm.curator_decision(same), ("accept",))
        self.assertEqual(sm.curator_decision(op(POSITION, decision="edit", edited={"start": 1, "end": 4, "form": "x"})),
                         ("edit", 1, 4))

    def test_rows_and_the_report(self):
        ops = [op(POSITION, decision="accept", oid="a"), op(POSITION, decision="reject", oid="b"),
               op(POSITION, decision=None, oid="c")]
        rows = sm.evaluate_ops(ops, DATA, StubClient("c1", 0.9))
        self.assertEqual([r["id"] for r in rows], ["a", "b"])  # undecided cards are not evaluated
        text = sm.report(rows, [0.0, 0.95])
        self.assertIn("position: 2 cards", text)
        self.assertIn("≥0.00: 2 suggested (100%), 1 agree (50%)", text)
        self.assertIn("≥0.95: 0 suggested (0%)", text)
        self.assertIn("b: decided ('reject',), suggested ('accept',) p=0.9", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest -q tests/test_suggest_mentions.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'suggest_mentions'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Jev suggestions on the Italian person-mention review cards (CatholicOS/crmedr#97).

`suggest` writes `suggested` ({decision, start/end/form for an edit, probability, confidence,
model}) on every in-scope card of a review change-set whose answer reaches the threshold, and
removes it from the others; it never touches `decision` or `edited`. `evaluate` compares the
suggestions with decided change-sets and prints, per kind, the agreement at each threshold.
Answers are cached in .cache/typesafe/, so a re-run asks nothing already asked. The change-sets
quote the 2004 text: keep them outside the repository. See
docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md.

Usage:
  python3 suggest_mentions.py suggest <review.json> [--min-confidence X] [--repo repo_root]
  python3 suggest_mentions.py evaluate <decided.json>... [--weak <decided.json>...] [--repo repo_root]

The key: TYPESAFE_API_KEY, else ~/.config/typesafe/api_key. Standard library only.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import mentions_jev as mj
from mentions_italian import ItalianNames

# Set from the evaluation (docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md):
# 1.0 suggests nothing until then.
DEFAULT_MIN_CONFIDENCE = 1.0
THRESHOLDS = [round(0.1 * i, 2) for i in range(10)] + [0.95]


def _read(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def load_data(repo_root):
    data = Path(repo_root) / "data"
    mentions = _read(data / "mentions.json")["editions"]
    return {"persons": _read(data / "persons.json")["editions"]["martyrologium_romanum_2004"],
            "latin": mentions["martyrologium_romanum_2004"],
            "italian": mentions[mj.ITALIAN],
            "names": ItalianNames(_read(Path(repo_root) / "i18n" / "la.json", {}),
                                  _read(Path(repo_root) / "i18n" / "it.json", {}))}


def ask_card(op, data, client):
    """The card's suggestion before any threshold, and an error message; (None, None) when the card
    is out of scope or has no candidate. A refused key is raised: the run stops."""
    mrid = op["eulogy"]
    body, cands = mj.request_for(op, data["persons"].get(mrid, []), data["latin"].get(mrid, []),
                                 data["italian"].get(mrid, []), data["names"])
    if body is None:
        return None, None
    try:
        response = client.ask(body)
    except mj.KeyRefused:
        raise
    except mj.TypeSafeError as e:
        return None, str(e)
    question = next(iter(body["questions"]))
    s = mj.suggestion(op, (response.get("answers") or {}).get(question), cands, response.get("model", mj.MODEL))
    return s, None if s else "the answer named no option the request offered"


def suggest_ops(ops, data, client, min_confidence):
    counts = {"suggested": 0, "below": 0, "skipped": 0, "errors": 0}
    for op in ops:
        if mj.card_kind(op) is None:
            counts["skipped"] += 1
            continue
        s, error = ask_card(op, data, client)
        op.pop("suggested", None)
        if error:
            counts["errors"] += 1
            print(f"no suggestion: {op['id']}: {error}", file=sys.stderr)
        elif s is None:
            counts["skipped"] += 1
        elif s["confidence"] >= min_confidence:
            op["suggested"] = s
            counts["suggested"] += 1
        else:
            counts["below"] += 1
    return counts


def curator_decision(op):
    decision, edited = op.get("decision"), op.get("edited") or {}
    if decision == "edit":
        span = (edited.get("start"), edited.get("end"))
        return ("accept",) if span == (op.get("start"), op.get("end")) else ("edit", *span)
    return (decision,)


def _suggested(s):
    if s is None:
        return None
    return ("edit", s["start"], s["end"]) if s["decision"] == "edit" else (s["decision"],)


def evaluate_ops(ops, data, client):
    rows = []
    for op in ops:
        kind = mj.card_kind(op)
        if kind is None or op.get("decision") not in ("accept", "reject", "edit"):
            continue
        s, _ = ask_card(op, data, client)
        rows.append({"id": op["id"], "kind": kind, "decision": curator_decision(op), "suggested": s})
    return rows


def report(rows, thresholds):
    out = []
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    for kind, rs in [("all", rows)] + sorted(by_kind.items()):
        out.append(f"{kind}: {len(rs)} cards")
        for t in thresholds:
            covered = [r for r in rs if r["suggested"] and r["suggested"]["confidence"] >= t]
            agree = [r for r in covered if _suggested(r["suggested"]) == r["decision"]]
            share = round(100 * len(covered) / len(rs)) if rs else 0
            line = f"  ≥{t:.2f}: {len(covered)} suggested ({share}%)"
            if covered:
                line += f", {len(agree)} agree ({round(100 * len(agree) / len(covered))}%)"
            out.append(line)
    out.append("disagreements:")
    for r in rows:
        if r["suggested"] and _suggested(r["suggested"]) != r["decision"]:
            out.append(f"  {r['id']}: decided {r['decision']}, suggested {_suggested(r['suggested'])} "
                       f"p={r['suggested']['probability']} c={r['suggested']['confidence']}")
    return "\n".join(out)


def _args(argv):
    flags, files, weak, target = {}, [], [], None
    it = iter(argv)
    for a in it:
        if a == "--min-confidence":
            flags["min"] = float(next(it))
        elif a == "--repo":
            flags["repo"] = next(it)
        elif a == "--weak":
            target = weak
        else:
            (target if target is not None else files).append(a)
    return flags, files, weak


def main(argv):
    if not argv or argv[0] not in ("suggest", "evaluate"):
        sys.exit(__doc__)
    flags, files, weak = _args(argv[1:])
    if not files:
        sys.exit(__doc__)
    repo = Path(flags.get("repo") or Path(__file__).resolve().parent.parent)
    data = load_data(repo)
    client = mj.TypeSafe(mj.api_key(), repo / ".cache" / "typesafe")
    try:
        if argv[0] == "suggest":
            path = Path(files[0])
            doc = json.loads(path.read_text(encoding="utf-8"))
            counts = suggest_ops(doc["operations"], data, client, flags.get("min", DEFAULT_MIN_CONFIDENCE))
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{path}: {counts}")
            return
        strict = [op for f in files for op in json.loads(Path(f).read_text(encoding="utf-8"))["operations"]]
        strict_ids = {op["id"] for op in strict}
        weak_ops = [op for f in weak for op in json.loads(Path(f).read_text(encoding="utf-8"))["operations"]
                    if op["id"] not in strict_ids]
        print("== strict (the curator's decisions)")
        print(report(evaluate_ops(strict, data, client), THRESHOLDS))
        if weak_ops:
            print("== weak (decided by the curator's rules)")
            print(report(evaluate_ops(weak_ops, data, client), THRESHOLDS))
    except mj.KeyRefused as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest -q tests/test_suggest_mentions.py`
Expected: all pass. In the fixture, Potamia is marked at 106–113 and Rodana at 123–129 (`100 + CTX.index(...)`), so the only free run is "Pompea" (`c1`), the proposed span: `c1` is an accept.

- [ ] **Step 5: Run the whole suite and commit**

Run: `python3 -m pytest -q`
Expected: all pass.

```bash
git add scripts/suggest_mentions.py tests/test_suggest_mentions.py
git commit -m "suggest_mentions: suggest on a review change-set, evaluate against decided ones (#97)"
```

### Task 5: Live evaluation and the threshold

This task calls the TypeSafe API with the decided cards' contexts (the curator approved sending them, 2026-10-15). It needs the key (env or `~/.config/typesafe/api_key`).

**Files:**
- Modify: `scripts/suggest_mentions.py` (`DEFAULT_MIN_CONFIDENCE`)
- Modify: `docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md` (append an "Evaluation result" section)

- [ ] **Step 1: Prepare the strict and weak files outside the repo**

```bash
S=/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad
F=/home/johnrdorazio/development/CatholicOS_org/martyrology-frontend/changesets
mkdir -p $S/jev-eval
cp $F/mentions-review-it-01.decided.json $F/mentions-review-it-06.decided.json $S/jev-eval/
python3 - <<EOF
import json
p = "$F/mentions-review-it-02.decided.json"; d = json.load(open(p))
for o in d["operations"]:
    if o["id"] == "martyrologium_romanum_2004_it_IT|mr:0212-martyres-abitinenses|footnote:1|657":
        o["decision"] = "accept"   # the curator's ruling: the second Ianuaria is another person
json.dump(d, open("$S/jev-eval/mentions-review-it-02.decided.json", "w"), ensure_ascii=False)
EOF
ls $S/jev-eval
```

Expected: the three files listed.

- [ ] **Step 2: Run the evaluation**

```bash
cd /home/johnrdorazio/development/CatholicOS_org/crmedr
python3 scripts/suggest_mentions.py evaluate $S/jev-eval/*.decided.json --weak $S/mentions-it-decided-all.json > $S/jev-eval/report.txt 2>&1; tail -60 $S/jev-eval/report.txt
```

Expected: a strict and a weak block, each with per-kind threshold lines and the disagreements. A second run must print the same report without network calls (all answers cached).

- [ ] **Step 3: Apply the ship gate**

On the strict `all` block: find the lowest threshold whose agreement is ≥ 95% with ≥ 33% of the cards suggested.
- If one exists: set `DEFAULT_MIN_CONFIDENCE` to it in `scripts/suggest_mentions.py`.
- If none exists: leave `DEFAULT_MIN_CONFIDENCE = 1.0`, skip Tasks 6–7's shipping steps, and report the table and the disagreements to the curator. Stop here.

- [ ] **Step 4: Record the result in the spec**

Append to the spec, with the actual numbers (counts only, no quoted text):

```markdown
## Evaluation result (2026-10-15, jev-1.14.0)

Strict: <N> cards (repeat <a>, position <b>, not found <c>). At the chosen threshold <T>:
<k> suggested (<share>%), <m> agree (<agreement>%). Weak: <N'> cards, <agreement'>% at <T>.
Disagreements on the strict set: <count>, by kind: <…>.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/suggest_mentions.py docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md
git commit -m "suggest_mentions: the confidence threshold from the evaluation (#97)"
```

### Task 6: MentionCard shows the suggestion (martyrology-frontend)

Work in `/home/johnrdorazio/development/CatholicOS_org/martyrology-frontend` on a new branch `feat/mention-suggestions` from `main`.

**Files:**
- Modify: `lib/changeset.ts` (`AddMentionOp`)
- Modify: `components/MentionCard.tsx`
- Modify: `messages/{en,it,fr,de,es,pt}.json` (`Review.mention`)
- Test: `components/__tests__/MentionCard.test.tsx`

**Interfaces:**
- Consumes: the `suggested` object of Task 4.
- Produces: `MentionSuggestion` type exported from `lib/changeset.ts`.

- [ ] **Step 1: Write the failing tests** (in the `describe("MentionCard")` block)

```tsx
  it("shows Jev's suggestion with its confidence, and takes it as the curator's own decision", () => {
    const { onDecide } = renderCard(add({ suggested: { decision: "accept", probability: 0.93, confidence: 0.87, model: "jev-1.14.0" } }));
    expect(screen.getByText("Jev suggests: accept (87%)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Take the suggestion" }));
    expect(onDecide).toHaveBeenCalledWith(ID, { decision: "accept" });
  });

  it("takes an edit suggestion as an edit with the suggested words", () => {
    const suggested = { decision: "edit" as const, start: 156, end: 172, form: "Fictíni et Ficti", probability: 0.8, confidence: 0.7, model: "jev-1.14.0" };
    const { onDecide } = renderCard(add({ suggested }));
    expect(screen.getByText("Jev suggests: mark «Fictíni et Ficti» (70%)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Take the suggestion" }));
    expect(onDecide).toHaveBeenCalledWith(ID, { decision: "edit", edited: { start: 156, end: 172, form: "Fictíni et Ficti" } });
  });

  it("shows a reject suggestion, and no suggestion line or button without one", () => {
    renderCard(add({ suggested: { decision: "reject", probability: 0.9, confidence: 0.9, model: "jev-1.14.0" } }));
    expect(screen.getByText("Jev suggests: reject (90%)")).toBeInTheDocument();
    cleanup();
    renderCard(add());
    expect(screen.queryByText(/Jev suggests/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Take the suggestion" })).toBeNull();
  });
```

Add `cleanup` to the file's imports from `@/test/intl` if it re-exports it, else from `@testing-library/react`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run components/__tests__/MentionCard.test.tsx`
Expected: FAIL: TypeScript rejects `suggested` on `AddMentionOp`, or "Unable to find an element with the text: Jev suggests: accept (87%)".

- [ ] **Step 3: Add the type** (`lib/changeset.ts`, before `AddMentionOp`)

```ts
/** Jev's suggestion on a mention card (crmedr scripts/suggest_mentions.py): never a decision by itself. */
export interface MentionSuggestion {
  decision: "accept" | "reject" | "edit";
  /** An edit's words, in the same offsets as the op. */
  start?: number;
  end?: number;
  form?: string;
  probability: number;
  confidence: number;
  model: string;
}
```

and in `AddMentionOp`, after `form: string | null;`:

```ts
  /** Jev's suggestion, when its confidence reached crmedr's threshold. */
  suggested?: MentionSuggestion | null;
```

- [ ] **Step 4: Show and take the suggestion** (`components/MentionCard.tsx`)

After `const decided = …` add:

```tsx
  const suggested = op.op === "add_mention" ? (op.suggested ?? null) : null;
  const suggestedRecord: DecisionRecord | null = suggested
    ? suggested.decision === "edit" && suggested.start != null && suggested.end != null && suggested.form
      ? { decision: "edit", edited: { start: suggested.start, end: suggested.end, form: suggested.form } }
      : suggested.decision === "edit" ? null : { decision: suggested.decision }
    : null;
  // A suggested accept is takeable only when the op itself can be accepted.
  const canTake = suggestedRecord !== null && (suggestedRecord.decision !== "accept" || canAccept);
```

After the `{op.reasoning && …}` line add:

```tsx
      {suggested && (
        <p className="mb-2 text-xs text-slate-700 dark:text-slate-300">
          {t("suggests", {
            what: suggested.decision === "edit" ? t("suggestEdit", { form: suggested.form ?? "" }) : t(`suggest.${suggested.decision}`),
            confidence: Math.round(suggested.confidence * 100),
          })}
        </p>
      )}
```

In the `!editing` button row, before the Accept button:

```tsx
          {suggestedRecord && (
            <button type="button" disabled={!canTake} className={`${button} bg-indigo-600 hover:bg-indigo-700`} onClick={() => onDecide(uid, suggestedRecord)}>
              {t("take")}
            </button>
          )}
```

Check the `edited` shape `DecisionRecord` accepts for an edit (the existing "Save the words" handler sends `{ decision: "edit", edited: picked }` with `picked` from `editedSpan`): if `editedSpan` returns more fields than `{ start, end, form }`, match its shape.

- [ ] **Step 5: Messages** (`Review.mention`, after `"kept"`)

- en: `"suggests": "Jev suggests: {what} ({confidence}%)", "suggest": {"accept": "accept", "reject": "reject"}, "suggestEdit": "mark «{form}»", "take": "Take the suggestion"`
- it: `"suggests": "Jev suggerisce: {what} ({confidence}%)", "suggest": {"accept": "accettare", "reject": "respingere"}, "suggestEdit": "segnare «{form}»", "take": "Accogli il suggerimento"`
- fr: `"suggests": "Jev suggère : {what} ({confidence} %)", "suggest": {"accept": "accepter", "reject": "rejeter"}, "suggestEdit": "marquer « {form} »", "take": "Suivre la suggestion"`
- de: `"suggests": "Jev schlägt vor: {what} ({confidence} %)", "suggest": {"accept": "annehmen", "reject": "ablehnen"}, "suggestEdit": "„{form}“ markieren", "take": "Vorschlag übernehmen"`
- es: `"suggests": "Jev sugiere: {what} ({confidence} %)", "suggest": {"accept": "aceptar", "reject": "rechazar"}, "suggestEdit": "marcar «{form}»", "take": "Seguir la sugerencia"`
- pt: `"suggests": "Jev sugere: {what} ({confidence}%)", "suggest": {"accept": "aceitar", "reject": "rejeitar"}, "suggestEdit": "marcar «{form}»", "take": "Seguir a sugestão"`

Insert with a script that keeps each file's formatting (load, insert the keys after `kept` in `Review.mention`, dump with the file's indent and `ensure_ascii=False`, trailing newline), then `git diff --stat messages` must show only additions.

- [ ] **Step 6: Run the tests, typecheck and lint**

Run: `npx vitest run && npx tsc --noEmit -p . && npx eslint components/MentionCard.tsx lib/changeset.ts components/__tests__/MentionCard.test.tsx`
Expected: all tests pass, no type or lint errors. The messages-parity test (every locale has the en keys) passes only if all six files got the keys.

- [ ] **Step 7: Update the spec and commit**

The passage keeps its current/proposed marks; an edit suggestion shows its words in the suggestion line rather than a dashed preview in the passage (the passage renderer has two mark kinds; a third is not worth its cost). In crmedr, replace the spec's sentence "an `edit` suggestion is previewed in the passage (dashed underline, distinct from the proposed span)" with "an `edit` suggestion shows its words in the suggestion line («…»)", and commit that in crmedr.

```bash
git add lib/changeset.ts components/MentionCard.tsx components/__tests__/MentionCard.test.tsx messages/*.json
git commit -m "MentionCard: Jev's suggestion and a Take the suggestion button (crmedr#97)"
```

### Task 7: Suggest on the open review files, PRs

- [ ] **Step 1: Suggest on the open Italian review files** (only if Task 5 passed the gate)

The open cards are on the server (`mentions-review-it-07.json`, `mentions-review-it-09.json`; June is decided). Regenerate them from crmedr `main` exactly as before (`extract_mentions.py … --review $S/mentions-review.json`, split by month with `base.edition` = the Italian edition), then:

```bash
python3 scripts/suggest_mentions.py suggest $S/cs-it/mentions-review-it-07.json
python3 scripts/suggest_mentions.py suggest $S/cs-it/mentions-review-it-09.json
```

Expected: each prints its counts. Do **not** upload them: replacing files on the server is the curator's call, asked for after the PRs merge.

- [ ] **Step 2: Push and open the PRs**

crmedr: push `docs/jev-mention-suggestions`, open a PR "Jev suggestions on the Italian mention review cards (#97)" with the evaluation table (counts only). martyrology-frontend: push `feat/mention-suggestions`, open a PR referencing it. Both bodies end with the session's PR footer. Merge order: crmedr first (the frontend only reads a field crmedr writes, so either order is safe; no API release is needed, the change-sets are served from CHANGESETS_DIR).
