"""Jev (TypeSafe System One) suggestions for the Italian person-mention review cards
(CatholicOS/crmedr#97); see docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md.

Jev never writes a span: it chooses among the name runs the matcher finds in a card's context
(or answers whether a repeated name is the same person), and code copies the chosen span.
Offsets: `at` in code points within a card's context; `start`/`end` in UTF-16 code units within
the eulogy's text or footnote, as everywhere in the change-sets.

Standard library only.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

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
