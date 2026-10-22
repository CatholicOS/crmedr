#!/usr/bin/env python3
"""Jev's century estimates of the eulogies' dates: calibration and data/date_estimates.json.

See docs/superpowers/specs/2026-10-22-eulogy-dates-design.md, "The era estimate", and
scripts/dates_jev.py for the request (one Latin and one English sentence per eulogy).

Usage:
  python3 scripts/estimate_dates.py evaluate /path/to/martyrology-texts [repo_root]
  python3 scripts/estimate_dates.py estimate /path/to/martyrology-texts [repo_root]

evaluate asks Jev on every eulogy dated by its persons' death dates (data/dates.json, source
wikidata) and prints, at each threshold, how many it estimates and how many of those fall in the
right century or within one; then the estimates that miss. estimate asks Jev on every current
eulogy without a curated or death date and writes data/date_estimates.json (the pick, its
probability and confidence; no text). extract_dates.py turns the estimates at or above its
ESTIMATE_MIN into dates. Answers are cached in .cache/typesafe/ (git-ignored); without a key and
with requests to make, it stops before asking. The key: TYPESAFE_API_KEY, else
~/.config/typesafe/api_key. Standard library only.
"""

import json
import sys
from pathlib import Path

import dates_jev as dj
import mentions_jev as mj
from extract_places import EDITION_EN
from extract_typology import latin_texts, load_texts

THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
ESTIMATES = "data/date_estimates.json"
DECIDED_SOURCES = ("curated", "wikidata")


def _body(mid, texts, typology, bounds):
    return dj.request_for(texts["la"].get(mid), texts["en"].get(mid), typology.get(mid), bounds.get(mid))


def require_key(ids, texts, typology, bounds, client):
    """Stop before any request when there is no key and some request is not cached."""
    if getattr(client, "key", True):
        return
    for mid in ids:
        body = _body(mid, texts, typology, bounds)
        if body is not None and not client.cached(body):
            raise mj.TypeSafeError("no TypeSafe key: set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key")


def rows_for(ids, texts, typology, bounds, client, failed=None):
    """{id: estimate, or None when there is no Latin text, the answer is unusable or the request fails};
    the IDs whose request failed are added to `failed`. A refused key is raised."""
    require_key(ids, texts, typology, bounds, client)
    out = {}
    for mid in ids:
        body = _body(mid, texts, typology, bounds)
        if body is None:
            out[mid] = None
            continue
        try:
            response = client.ask(body)
        except mj.KeyRefused:
            raise
        except mj.TypeSafeError as e:
            print(f"no estimate: {mid}: {e}", file=sys.stderr)
            out[mid] = None
            if failed is not None:
                failed.add(mid)
            continue
        out[mid] = dj.estimate_of((response.get("answers") or {}).get("century"))
    return out


def merged_estimates(previous, rows, failed):
    """The estimates to write: each usable answer, and for a request that failed, the previous
    estimate, so a transient failure does not drop it."""
    out = {m: r for m, r in rows.items() if r}
    out.update({m: previous[m] for m in failed if m in previous})
    return dict(sorted(out.items()))


def estimate_ids(current_ids, dates):
    """The current eulogies to estimate: those without a curated or death date."""
    return sorted(m for m in current_ids if dates.get(m, {}).get("source") not in DECIDED_SOURCES)


def _shown(date):
    return str(date["year"]) if "year" in date else f"{date.get('from', '…')}–{date.get('to', '…')}"


def _share(n, total):
    return round(100 * n / total) if total else 0


def calibration(rows, truths, thresholds):
    """The agreement table of the estimates against the death dates, and the misses."""
    out = [f"{len(truths)} eulogies dated by death dates; {sum(1 for r in rows.values() if r)} answered"]
    for t in thresholds:
        covered = [m for m, r in rows.items() if r and r["century"] != "cannot_tell" and r["probability"] >= t]
        right = [m for m in covered if dj.agrees(rows[m]["century"], truths[m])[0]]
        near = [m for m in covered if dj.agrees(rows[m]["century"], truths[m])[1]]
        out.append(f"  ≥{t:.2f}: {len(covered)} estimated ({_share(len(covered), len(truths))}%), "
                   f"{len(right)} right ({_share(len(right), len(covered))}%), "
                   f"{len(near)} within one century ({_share(len(near), len(covered))}%)")
    out.append("misses:")
    for m, r in sorted(rows.items()):
        if r and r["century"] != "cannot_tell" and not dj.agrees(r["century"], truths[m])[0]:
            out.append(f"  {m} {r['century']} p={r['probability']} died {_shown(truths[m])}")
    return "\n".join(out)


def load(repo_root, texts_repo):
    data = repo_root / "data"
    read = lambda name: json.loads((data / name).read_text(encoding="utf-8"))  # noqa: E731
    entries = read("martyrology_ids.json")["entries"]
    texts = {"la": latin_texts(entries, load_texts(texts_repo)),
             "en": latin_texts(entries, load_texts(texts_repo, EDITION_EN))}
    current = {e["id"] for e in entries if not e.get("deprecated")}
    return (current, texts, read("typology.json")["typology"], read("edition_bounds.json")["bounds"],
            read("dates.json")["dates"])


def main(argv):
    if len(argv) < 2 or argv[0] not in ("evaluate", "estimate"):
        print(__doc__, file=sys.stderr)
        return 2
    command, texts_repo = argv[0], Path(argv[1])
    repo_root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
    current, texts, typology, bounds, dates = load(repo_root, texts_repo)
    client = mj.TypeSafe(mj.api_key(), repo_root / ".cache" / "typesafe")
    try:
        if command == "evaluate":
            truths = {m: d for m, d in dates.items() if d.get("source") == "wikidata"}
            rows = rows_for(sorted(truths), texts, typology, bounds, client)
            print(calibration(rows, truths, THRESHOLDS))
            return 0
        failed = set()
        rows = rows_for(estimate_ids(current, dates), texts, typology, bounds, client, failed)
    except mj.TypeSafeError as e:
        print(e, file=sys.stderr)
        return 1
    path = repo_root / ESTIMATES
    previous = json.loads(path.read_text(encoding="utf-8"))["estimates"] if path.exists() else {}
    estimates = merged_estimates(previous, rows, failed)
    doc = {"$comment": "Jev's estimate of the century each current eulogy without a curated or death "
                       "date is set in: the pick (bc, c1..c21, cannot_tell), its probability and the "
                       "answer's confidence. No text. Generated by scripts/estimate_dates.py estimate; "
                       "extract_dates.py writes the picks at or above its ESTIMATE_MIN into data/dates.json.",
           "model": mj.MODEL, "estimates": estimates}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {ESTIMATES}: {len(estimates)} estimates of {len(rows)} eulogies asked"
          + (f"; {len(failed)} requests failed, their previous estimates kept" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
