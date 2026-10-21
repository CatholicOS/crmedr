#!/usr/bin/env python3
"""Jev suggestions on the gazetteer review cards (`resolve_place` ops); see
docs/superpowers/specs/2026-10-21-gazetteer-jev-design.md.

`suggest` writes `jev` on every card Jev answers (no threshold: the curator sees the probability) and
removes it from a card that cannot be asked or answered. `jev` is kept apart from `suggested`,
`decision` and `edited`, which this never writes. Answers are cached in .cache/typesafe/ (git
ignored), so a re-run asks nothing already asked. `jev` holds no 2004 text: the queue is a public file.

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


def main(argv):
    if not argv or argv[0] != "suggest":
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
    try:
        counts = suggest_ops(doc["operations"], texts, client)
    except mj.TypeSafeError as e:  # a refused key, or no key with requests to make: nothing written
        sys.exit(str(e))
    write_changeset(path, doc)
    print(f"{path}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:])
