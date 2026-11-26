"""Find the Wikidata items crmedr links that have since been merged (redirects) or deleted.

A merge on Wikidata leaves the old QID as a redirect: the reader still resolves it, but labels,
details and portraits come from an empty item, and two QIDs may now name one person.

    python3 scripts/check_redirects.py [repo_root] [--json out.json]

Scans the tracked `data/*.json` and `i18n/*.json`, except the review change-sets (`*_review.json`,
rewritten by each `propose`). A QID counts where a JSON string is exactly a QID or a key is one;
a QID written in prose (a curator note) is not a link. Prints each redirected or deleted QID with
its target and the files that name it; exits 1 when there is any. Network access (wbgetentities,
50 QIDs a request), not cached: a merge since the last run is what it looks for.

After a hit, put the target QID in the curated source (`data/person_items.json`,
`data/eulogy_items.json`, `data/mentions_curated.json`, ...), with a note on the merge, and
regenerate the files built from it (mentions, person details, eulogy item members, dates, registry).
"""
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wikidata  # noqa: E402

QID = re.compile(r"Q[1-9][0-9]*")
BATCH = 50


def qids_in(obj, found=None):
    """The QIDs a parsed JSON value links: strings that are a QID, and keys that are one."""
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if QID.fullmatch(k):
                found.add(k)
            qids_in(v, found)
    elif isinstance(obj, list):
        for v in obj:
            qids_in(v, found)
    elif isinstance(obj, str) and QID.fullmatch(obj):
        found.add(obj)
    return found


def data_files(root):
    """The tracked JSON files to scan (every JSON file when `root` is not a git checkout)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "data", "i18n"],
                             capture_output=True, text=True, check=True).stdout.split()
        paths = [root / p for p in out]
    except (OSError, subprocess.CalledProcessError):
        paths = list((root / "data").glob("*.json")) + list((root / "i18n").glob("*.json"))
    return sorted(p for p in paths if p.suffix == ".json" and p.parent.name in ("data", "i18n")
                  and not p.name.endswith("_review.json"))


def scan(root):
    """{qid: [relative paths of the files that link it]}."""
    where = {}
    for path in data_files(root):
        with open(path, encoding="utf-8") as f:
            for q in qids_in(json.load(f)):
                where.setdefault(q, []).append(path.relative_to(root).as_posix())
    return where


def classify(asked, entities):
    """{qid: {"status": "redirect", "to": target} | {"status": "missing"}} for the asked QIDs
    that are no longer items of their own; `entities` is wbgetentities' answer."""
    stale = {}
    for q in asked:
        e = entities.get(q)
        if e is None:
            continue
        if "missing" in e:
            stale[q] = {"status": "missing"}
        elif "redirects" in e:
            stale[q] = {"status": "redirect", "to": e["redirects"]["to"]}
        elif e.get("id") not in (None, q):
            stale[q] = {"status": "redirect", "to": e["id"]}
    return stale


def fetch(qids, get=wikidata.http_get):
    stale = {}
    for i in range(0, len(qids), BATCH):
        batch = qids[i:i + BATCH]
        url = wikidata.API + "?" + urllib.parse.urlencode(
            {"action": "wbgetentities", "ids": "|".join(batch), "props": "info", "format": "json",
             "maxlag": "5"})
        stale.update(classify(batch, get(url).get("entities", {})))
    return stale


def report(stale, where):
    lines = []
    for q in sorted(stale, key=lambda q: int(q[1:])):
        s = stale[q]
        what = f"redirects to {s['to']}" if s["status"] == "redirect" else "deleted"
        lines.append(f"{q} {what}: {', '.join(where[q])}")
    return lines


def main(argv):
    out = None
    if "--json" in argv:
        i = argv.index("--json")
        if i + 1 >= len(argv):
            sys.exit("usage: check_redirects.py [repo_root] [--json out.json]")
        out, argv = Path(argv[i + 1]), argv[:i] + argv[i + 2:]
    root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parent.parent
    where = scan(root)
    stale = fetch(sorted(where, key=lambda q: int(q[1:])))
    for line in report(stale, where):
        print(line)
    if out:
        out.write_text(json.dumps({q: {**s, "files": where[q]} for q, s in sorted(stale.items())},
                                  indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(where)} QIDs checked; {len(stale)} redirected or deleted", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
