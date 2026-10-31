#!/usr/bin/env python3
"""Lint the eulogy IDs of the registry: grammar, uniqueness, and identity consistency.

    python3 scripts/lint_ids.py [path/to/martyrology-texts] [--json]

Checks (errors fail, warnings inform; data/id_lint_exceptions.json lists errors the curator is
still deciding):

- grammar       every ID is mr:MMDD-slug, a real day, lowercase ASCII words joined by hyphens;
- unique        no ID is used twice, current or deprecated (an ID is never reused);
- same-subject  the eulogies whose single subject is the same person (data/person_items.json)
                name that person alike on every day (an -et-socii tail or a joint eulogy's other
                names aside);
- twin          a deprecated ID and its same_eulogy current twin should carry the same slug (warning);
- ae            a place in the slug keeps the printed æ/œ: cordubae, not cordube (needs the texts);
- cross-day     a "cuius memoria cras/heri agitur" reference and the eulogy it points to name their
                saint alike (needs the texts); a reference to another subject's feast is a warning;
- bare          a single-person eulogy whose slug is a bare name (warning; drafts under review).

The URI scheme (CatholicOS/cdcf-uri-scheme) owns the grammar; this script owns the checks only the
registry's data can decide.
"""
import calendar
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ID = re.compile(r"^mr:(\d{2})(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
EXCEPTIONS = "data/id_lint_exceptions.json"


def slug(mrid):
    return mrid.split("-", 1)[1]


GROUP_TAIL = re.compile(r"-et-soci(?:i|us|ae)$")


def parts(mrid):
    """The persons a slug names: without the -et-socii tail, split at -et- (cornelius-et-cyprianus)."""
    return set(GROUP_TAIL.sub("", slug(mrid)).split("-et-"))


def agree(a, b):
    """Two slugs name a shared person the same way."""
    return bool(parts(a) & parts(b))


def fold(text):
    text = text.replace("æ", "ae").replace("Æ", "Ae").replace("ǽ", "ae").replace("œ", "oe").replace("Œ", "Oe")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def check_grammar(ids):
    out = []
    for mrid in ids:
        m = ID.match(mrid)
        if not m:
            out.append(("grammar", [mrid], "not mr:MMDD-slug in lowercase ASCII words"))
            continue
        month, day = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12 and 1 <= day <= calendar.monthrange(2004, month)[1]):
            out.append(("grammar", [mrid], f"{month:02d}{day:02d} is not a day"))
    return out


def check_unique(entries):
    seen = defaultdict(int)
    for e in entries:
        seen[e["id"]] += 1
    return [("unique", [mrid], f"used {n} times") for mrid, n in sorted(seen.items()) if n > 1]


def single_subjects(subjects, person_items):
    """mrid -> Wikidata item of the eulogy's one subject, when the subject names one linked person."""
    from persons_text import subject_names
    out = {}
    for mrid, subject in subjects.items():
        names = subject_names(mrid, subject) if subject else []
        if len(names) != 1:
            continue
        qid = ((person_items.get(mrid) or {}).get(names[0]) or {}).get("wikidata")
        if qid:
            out[mrid] = qid
    return out


def check_same_subject(subject_qids):
    by_qid = defaultdict(list)
    for mrid, qid in subject_qids.items():
        by_qid[qid].append(mrid)
    out = []
    for qid, mrids in sorted(by_qid.items()):
        if any(not agree(a, b) for a in mrids for b in mrids):
            out.append(("same-subject", sorted(mrids), f"one subject ({qid}), several slugs"))
    return out


def check_twins(entries, current):
    out = []
    for e in entries:
        if e.get("deprecated"):
            for twin in e.get("same_eulogy", []):
                if twin in current and not agree(twin, e["id"]):
                    out.append(("twin", [e["id"], twin], "deprecated twin with another slug"))
    return out


def check_ae(current, texts):
    out = []
    for mrid in current:
        words = set(re.findall(r"[a-z]+", fold(texts.get(mrid, ""))))
        for token in slug(mrid).split("-")[1:]:
            for diphthong in ("ae", "oe"):
                if token.endswith("e") and token[:-1] + diphthong in words and token not in words:
                    out.append(("ae", [mrid], f"'{token}' where the text prints '{token[:-1]}{diphthong}'"))
    return out


def check_cross_day(current, texts, subject_qids):
    """A reference and the eulogy it resolves to name their shared saint alike; when both subjects are
    known to be different persons (a reference to a group feast), it is only a warning."""
    from extract_typology import find_offday_targets
    from extract_subjects import fold as tfold
    entries = {mrid: (m, d, tfold(texts.get(mrid, ""))) for mrid, (m, d) in current.items()}
    targets, _ = find_offday_targets(entries)
    out = []
    for target, (_, source) in sorted(targets.items()):
        if agree(target, source):
            continue
        qa, qb = subject_qids.get(source), subject_qids.get(target)
        other = (qa and qb and qa != qb) or slug(source).split("-")[0] != slug(target).split("-")[0]
        out.append(("cross-day-other" if other else "cross-day", [source, target],
                    "points to another subject's eulogy" if other else "a reference and its eulogy carry different slugs"))
    return out


def check_bare(subjects):
    from persons_text import subject_names
    out = []
    for mrid, subject in subjects.items():
        names = subject_names(mrid, subject) if subject else []
        if len(names) == 1 and "-" not in slug(mrid):
            out.append(("bare", [mrid], "a single name with no discriminator"))
    return out


ERRORS = {"grammar", "unique", "same-subject", "ae", "cross-day"}


def lint(root=ROOT, texts_repo=None):
    from persons_text import name_subjects
    entries = json.loads((root / "data/martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    current = {e["id"]: (e["month"], e["day"]) for e in entries if not e.get("deprecated")}
    subjects = {k: v for k, v in name_subjects(root, "la").items() if k in current}
    person_items = json.loads((root / "data/person_items.json").read_text(encoding="utf-8"))["persons"]
    found = check_grammar([e["id"] for e in entries]) + check_unique(entries)
    subject_qids = single_subjects(subjects, person_items)
    found += check_same_subject(subject_qids) + check_twins(entries, current)
    found += check_bare(subjects)
    if texts_repo:
        from extract_typology import latin_texts, load_texts
        texts = latin_texts(entries, load_texts(Path(texts_repo)))
        found += check_ae(current, texts) + check_cross_day(current, texts, subject_qids)
    path = root / EXCEPTIONS
    excepted = json.loads(path.read_text(encoding="utf-8"))["exceptions"] if path.exists() else []
    known = {(x["check"], tuple(sorted(x["ids"]))) for x in excepted}
    errors = [f for f in found if f[0] in ERRORS and (f[0], tuple(sorted(f[1]))) not in known]
    warnings = [f for f in found if f not in errors]
    return errors, warnings


def main(argv):
    texts = next((a for a in argv if not a.startswith("--")), None)
    errors, warnings = lint(ROOT, texts)
    if "--json" in argv:
        print(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=1))
    else:
        counts = defaultdict(int)
        for check, _, _ in warnings:
            counts[check] += 1
        for check, ids, why in errors:
            print(f"ERROR {check}: {', '.join(ids)}: {why}")
        print(f"{len(errors)} errors; warnings: {dict(sorted(counts.items())) or 'none'}"
              + ("" if texts else " (texts not given: ae and cross-day not checked)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
