#!/usr/bin/env python3
"""Jev suggestions on the gazetteer review cards (`resolve_place` ops); see
docs/superpowers/specs/2026-10-21-gazetteer-jev-design.md.

`suggest` writes `jev` on every card Jev answers (no threshold: the curator sees the probability) and
removes it from a card that cannot be asked or answered. `jev` is kept apart from `suggested`,
`decision` and `edited`, which this never writes. Answers are cached in .cache/typesafe/ (git
ignored), so a re-run asks nothing already asked. `jev` holds no 2004 text: the queue is a public file.

  python3 suggest_places.py evaluate <round1.json> /path/to/martyrology-texts [--repo repo_root]

`evaluate` asks Jev about the round-1 cards the gazetteer settled (each with its settled candidate, and
again without it, where the right answer is a reject) and prints the agreement per threshold. It writes
nothing.

  python3 suggest_places.py prefill <changeset.json> --threshold X

`prefill` takes Jev's item picks (accept/edit) at probability >= X, with a country, on undecided cards
(`decision`/`edited`, plus `"prefilled": "jev"`). It never rejects and never touches a decided card.

Usage:
  python3 suggest_places.py suggest <changeset.json> /path/to/martyrology-texts [--repo repo_root]

The key: TYPESAFE_API_KEY, else ~/.config/typesafe/api_key. Standard library only.
"""

import json
import sys
from pathlib import Path

import gazetteer_jev as gj
import mentions_jev as mj
from extract_places import EDITION_EN
from extract_typology import latin_texts, load_texts


def load_texts_for(texts_repo, repo_root):
    """The Latin and English texts by eulogy ID."""
    entries = json.loads((Path(repo_root) / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    texts_repo = Path(texts_repo)
    return {"la": latin_texts(entries, load_texts(texts_repo)),
            "en": latin_texts(entries, load_texts(texts_repo, EDITION_EN))}


def request_for(op, texts):
    """The card's request, from the first occurrence whose Latin text exists; None when none has one."""
    for mrid in op.get("occurrences") or []:
        la_text = texts["la"].get(mrid)
        if la_text:
            return gj.place_request(op, gj.latin_clause(la_text, op["la"]),
                                    gj.english_clause(texts["en"].get(mrid), op))
    return None


def ask(op, texts, client):
    """(suggestion, error); (None, None) when the card cannot be asked. A refused key is raised."""
    body = request_for(op, texts)
    if body is None:
        return None, None
    try:
        response = client.ask(body)
    except mj.KeyRefused:
        raise
    except mj.TypeSafeError as e:
        return None, str(e)
    s = gj.place_suggestion(op, response.get("answers") or {}, response.get("model", mj.MODEL))
    return s, None if s else "the answer named no option the request offered"


def require_key(ops, texts, client):
    """Stop before any card changes when there is no key and some card's request is not cached."""
    if getattr(client, "key", True):
        return
    for op in ops:
        body = request_for(op, texts)
        if body is not None and not client.cached(body):
            raise mj.TypeSafeError("no TypeSafe key: set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key")


def suggest_ops(ops, texts, client):
    scope = [op for op in ops if op.get("op") == "resolve_place"]
    require_key(scope, texts, client)
    counts = {"suggested": 0, "skipped": len(ops) - len(scope), "errors": 0}
    for op in scope:
        s, error = ask(op, texts, client)
        op.pop("jev", None)
        if s is None and error is None:
            counts["skipped"] += 1
        elif error:
            counts["errors"] += 1
            print(f"no suggestion: {op['id']}: {error}", file=sys.stderr)
        else:
            op["jev"] = s
            counts["suggested"] += 1
    return counts


def write_changeset(path, doc):
    """The queue's own format (build_gazetteer.write_state), so a run does not reformat the file."""
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _accept_country(op, q):
    """The country build_gazetteer._resolve applies to an accept of `q`."""
    suggested = op.get("suggested") or {}
    if suggested.get("wikidata") == q and suggested.get("country"):
        return suggested["country"]
    return next((c.get("country") for c in op["candidates"] if c["wikidata"] == q), None)


def prefill_ops(ops, threshold):
    """Write Jev's item picks (accept/edit, probability >= threshold, with a country, among the
    candidates) onto undecided cards. Never a reject, never a decided card."""
    counts = {"accept": 0, "edit": 0, "skipped": 0}
    for op in ops:
        if op.get("op") != "resolve_place":
            continue
        jev = op.get("jev") or {}
        q = jev.get("wikidata")
        ok = (op.get("decision") is None and jev.get("decision") in ("accept", "edit")
              and jev.get("probability", 0) >= threshold and jev.get("country")
              and q in [c["wikidata"] for c in op.get("candidates") or []])
        if not ok:
            counts["skipped"] += 1
        elif q == gj.default_qid(op) and _accept_country(op, q) == jev["country"]:
            op["decision"], op["edited"], op["prefilled"] = "accept", None, "jev"
            counts["accept"] += 1
        else:
            op["decision"], op["prefilled"] = "edit", "jev"
            op["edited"] = {"wikidata": q, "country": jev["country"]}
            counts["edit"] += 1
    return counts


THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]


def calibration_set(round1_ops, places):
    """(op, expected QID or None): each settled card with its settled candidate, then without it."""
    pairs = []
    for op in round1_ops:
        settled = places.get(op.get("id")) or {}
        qid = settled.get("wikidata")
        if settled.get("status") not in ("reviewed", "auto") or not qid:
            continue
        candidates = op.get("candidates") or []
        if qid not in [c.get("wikidata") for c in candidates]:
            continue
        base = {k: v for k, v in op.items() if k != "suggested"}
        pairs.append((base, qid))
        others = [c for c in candidates if c.get("wikidata") != qid]
        if others:
            pairs.append((dict(base, candidates=others), None))
    return pairs


def evaluate_ops(pairs, texts, client):
    require_key([op for op, _ in pairs], texts, client)
    rows = []
    for op, expected in pairs:
        s, error = ask(op, texts, client)
        if s is None:
            if error:
                print(f"no suggestion: {op['id']}: {error}", file=sys.stderr)
            continue
        rows.append({"id": op["id"], "expected": expected, "picked": s.get("wikidata"),
                     "probability": s["probability"], "negative": expected is None})
    return rows


def _rate(rows, t):
    answered = [r for r in rows if r["probability"] >= t]
    agree = sum(1 for r in answered if r["picked"] == r["expected"])
    return f"{agree}/{len(answered)} agree ({100 * agree / len(answered) if answered else 0.0:.1f}%)"


def report(rows, thresholds):
    positives = [r for r in rows if not r["negative"]]
    negatives = [r for r in rows if r["negative"]]
    out = [f"{t}  positives {_rate(positives, t)}  negatives {_rate(negatives, t)}" for t in thresholds]
    out.append("disagreements at 0.9:")
    for r in rows:
        if r["probability"] >= 0.9 and r["picked"] != r["expected"]:
            out.append(f"  {r['id']} [{'negative' if r['negative'] else 'positive'}]: "
                       f"expected {r['expected'] or 'none'}, picked {r['picked'] or 'none'} p={r['probability']}")
    return "\n".join(out)


def prefill_main(argv):
    args, threshold = [], None
    it = iter(argv)
    for a in it:
        if a == "--threshold":
            threshold = next(it, None)
        else:
            args.append(a)
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        sys.exit(__doc__)
    if len(args) != 1 or not 0 <= threshold <= 1:
        sys.exit(__doc__)
    path = Path(args[0])
    doc = json.loads(path.read_text(encoding="utf-8"))
    counts = prefill_ops(doc["operations"], threshold)
    write_changeset(path, doc)
    print(f"{path}: {counts}")


def main(argv):
    if argv and argv[0] == "prefill":
        return prefill_main(argv[1:])
    if not argv or argv[0] not in ("suggest", "evaluate"):
        sys.exit(__doc__)
    args, repo = [], Path(__file__).resolve().parent.parent
    it = iter(argv[1:])
    for a in it:
        if a == "--repo":
            repo = Path(next(it))
        else:
            args.append(a)
    if len(args) != 2:
        sys.exit(__doc__)
    path, texts_repo = Path(args[0]), Path(args[1])
    texts = load_texts_for(texts_repo, repo)
    client = mj.TypeSafe(mj.api_key(), repo / ".cache" / "typesafe")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if argv[0] == "evaluate":
        places = json.loads((repo / "data" / "gazetteer.json").read_text(encoding="utf-8"))["places"]
        pairs = calibration_set(doc["operations"], places)
        try:
            print(report(evaluate_ops(pairs, texts, client), THRESHOLDS))
        except mj.TypeSafeError as e:
            sys.exit(str(e))
        return
    try:
        counts = suggest_ops(doc["operations"], texts, client)
    except mj.TypeSafeError as e:  # a refused key, or no key with requests to make: nothing written
        sys.exit(str(e))
    write_changeset(path, doc)
    print(f"{path}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:])
