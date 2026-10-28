#!/usr/bin/env python3
"""Review the persons of the eulogies whose text lists names extract_persons.py could not read.

A name in a list of companions is read only when its genitive surely gives a known nominative
("Accúrsii" is not known, so Accursius and every name after him could be lost). For each such
eulogy `draft` writes a set_persons card (crmedr-changeset/v1): the text persons read now, the
printed forms not read, and a drafted list read through to its end, each unknown genitive given
its likeliest nominative (declension rules, the commoner known name first) and, from the Italian
text, its Italian form. The curator accepts the list, edits it, or rejects it; `apply` writes the
decided lists to data/persons_curated.json (with their Italian forms, for the Italian matcher),
keeping each eulogy's footnote persons. The cards quote the 2004 texts: write them outside the
repository.

Usage:
  python3 persons_review.py draft /path/to/martyrology-texts <out.json> [repo_root]
  python3 persons_review.py apply <decided.json> [repo_root]

Standard library only.
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path

from extract_persons import EDITION, _load_footnotes, build_lexicon, eulogy_persons
from extract_typology import latin_texts, load_texts
from gazetteer_text import fold
from persons_text import GENITIVE_ENDINGS, name_key, name_subjects

SCHEMA = "crmedr-changeset/v1"
EDITION_IT = "martyrologium_romanum_2004_it_IT"
# The second declension in -er ("Alexándri" Alexander) and third-declension stems GENITIVE_ENDINGS
# leaves to the lexicon ("Felicitátis" Felicitas, "Audífacis" Audifax, "Victóris" Victor), before -is.
ENDINGS = ([("atis", ("as",)), ("acis", ("ax",)), ("oris", ("or",)), ("eris", ("er",)), ("idis", ("is", "id"))]
           + GENITIVE_ENDINGS[:-2] + [("ri", ("er",))] + GENITIVE_ENDINGS[-2:])
VOWELS = set("aeiouyæœ")
STRESS = {"́"}  # the print's stress accent (á, é, í, ó, ú, ý, ǽ)
ROUNDS = 8  # a list read on name by name: at most this many unknown names in a row


def unstressed(word):
    """The word without the print's stress accents, other letters kept ("Ǽmiliæ" Æmiliæ)."""
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", word) if c not in STRESS))


def guesses(word, lexicon, freq):
    """The nominatives a printed genitive may come from, likeliest first: the known names (the
    commoner first), then by ending, the most specific first. A word with no genitive ending (a
    surname: "Ménard", "Fenn") is its own nominative, as printed."""
    key = name_key(word)
    plain = unstressed(word)
    if plain.endswith("æ"):
        plain = plain[:-1] + "ae"
    out = []
    for ending, noms in ENDINGS:
        if key.endswith(ending) and len(key) > len(ending) + 1 and len(plain) > len(ending):
            stem = plain[: -len(ending)]
            if ending == "ri" and (len(stem) < 2 or stem[-1].lower() in VOWELS):
                continue  # "Agathodóri" Agathodorus: -er only after a consonant ("Alexándri")
            out += [stem + n for n in noms if not (stem.endswith("i") and n == "ius")]
    if not out:
        return [word]
    out = list(dict.fromkeys(out))
    known = sorted((c for c in out if name_key(c) in lexicon), key=lambda c: -freq[lexicon[name_key(c)]])
    return list(dict.fromkeys([lexicon[name_key(c)] for c in known] + out))


def _sound(word):
    """A spelling compared across Latin and Italian: Phlegon and Flegonte, Theodorus and Teodoro."""
    s = fold(word).replace("ph", "f").replace("th", "t").replace("ch", "c").replace("y", "i")
    s = s.replace("ae", "e").replace("oe", "e").replace("x", "s").replace("h", "").replace("j", "i")
    return s.replace("k", "c")


ITALIAN_WORD = re.compile(r"\b[A-ZÀ-Ý][\w’']+")


def italian_form(name, text_it):
    """The Italian word of the text that begins most like the (one-word) Latin name's stem, a
    vowel apart at most ("Accursius" Accorsio, "Phlegon" Flegonte); None when no word is alike
    enough, or for a name of several words (the matcher translates their given names itself)."""
    if not name or " " in name or not text_it:
        return None
    sound = _sound(name)
    stem = re.sub(r"(ius|us|um|a|as|es|is|er|o|on|or|ix|ax|ex|ens|ans)$", "", sound) or sound
    if len(stem) < 3:
        return None
    best, score = None, (0.0, 0.0)
    for word in dict.fromkeys(ITALIAN_WORD.findall(text_it)):
        w = _sound(word)
        r = SequenceMatcher(None, stem, w[: len(stem)]).ratio() if w[:1] == stem[:1] else 0.0
        if r >= min(0.8, 1 - 1 / len(stem)) - 1e-9 and (r, SequenceMatcher(None, sound, w).ratio()) > score:
            best, score = word, (r, SequenceMatcher(None, sound, w).ratio())
    return best


def _text_names(persons):
    return [p for p in persons if p["where"] == "text"]


def draft_op(mrid, subject, text, text_it, lexicon, freq):
    """The set_persons card of a eulogy whose text names are not all read, else None."""
    persons, issues = eulogy_persons(mrid, subject, text, [], lexicon, {})
    if not issues["uncertain"]:
        return None
    readings, alternatives, drafted = {}, {}, persons
    for _ in range(ROUNDS):
        drafted, iss = eulogy_persons(mrid, subject, text, [], lexicon, {}, readings)
        new = [u for u in iss["uncertain"] if " " not in u and u not in readings]
        if not new:
            break
        for u in new:
            g = guesses(u, lexicon, freq)
            readings[u], alternatives[g[0]] = g[0], (u, g[1:4])
    out = []
    for p in _text_names(drafted):
        q = {k: v for k, v in p.items() if k != "where"}
        if p["name"] in alternatives:
            printed, alt = alternatives[p["name"]]
            q.update({"it": italian_form(p["name"], text_it), "printed": printed, "alternatives": alt})
        out.append(q)
    return {"op": "set_persons", "uid": f"persons:{mrid}", "id": mrid,
            "current": [p["name"] for p in _text_names(persons)], "unread": list(issues["uncertain"]),
            "persons": out, "context": {"la": text, "it": text_it}, "decision": None, "edited": None}


def _decided_persons(op):
    """The text persons a decided card gives ([{name, it?}]), or None (rejected or undecided)."""
    if op.get("decision") == "accept":
        return op.get("persons") or []
    if op.get("decision") == "edit":
        return (op.get("edited") or {}).get("persons") or []
    return None


def apply_decisions(changeset, curated, persons):
    """(data/persons_curated.json with the decided lists, how many): each list replaces the
    eulogy's text persons, numbered when a name is given twice, its footnote persons kept."""
    if changeset.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    out, n = dict(curated), 0
    for op in changeset.get("operations", []):
        decided = _decided_persons(op) if op.get("op") == "set_persons" else None
        if decided is None:
            continue
        names = [(p.get("name") or "").strip() for p in decided]
        if not any(names):
            raise ValueError(f"{op['id']}: the decided list has no persons")
        drafted = {p["name"]: p for p in op.get("persons") or []}  # an edit keeps a drafted person's other names
        seen, entries = Counter(), []
        for p, name in zip(decided, names, strict=True):
            if not name:
                continue
            seen[name_key(name)] += 1
            e = {"name": name}
            if seen[name_key(name)] > 1:
                e["n"] = seen[name_key(name)]
            also = p.get("also") or (drafted.get(name) or {}).get("also")
            if also:
                e["also"] = also
            e["where"] = "text"
            if (p.get("it") or "").strip():
                e["it"] = p["it"].strip()
            entries.append(e)
        out[op["id"]] = entries + [p for p in persons.get(op["id"], []) if p["where"] != "text"]
        n += 1
    return out, n


def draft(texts_repo, out_path, repo_root):
    root = Path(repo_root)
    entries = json.loads((root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    current = [e for e in entries if not e.get("deprecated")]
    current.sort(key=lambda e: (e["month"], e["day"], e.get("entry") or 0))
    subjects = name_subjects(root, "la")
    curated = json.loads((root / "data" / "persons_curated.json").read_text(encoding="utf-8"))
    texts = latin_texts(entries, load_texts(Path(texts_repo), EDITION))
    texts_it = latin_texts(entries, load_texts(Path(texts_repo), EDITION_IT))
    footnotes = _load_footnotes(Path(texts_repo) / "data" / "editions" / EDITION)
    lexicon = build_lexicon({e["id"]: subjects.get(e["id"], "") for e in current}, footnotes)
    persons = json.loads((root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
    freq = Counter(w for ps in persons.values() for p in ps for w in p["name"].split())
    ops = [op for e in current if e["id"] not in curated
           if (op := draft_op(e["id"], subjects.get(e["id"], ""), texts.get(e["id"], ""),
                              texts_it.get(e["id"], ""), lexicon, freq))]
    doc = {"schema": SCHEMA, "generated_by": "crmedr scripts/persons_review.py",
           "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "base": {"edition": EDITION, "registry": "data/martyrology_ids.json"}, "operations": ops}
    Path(out_path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(ops)


def main(argv):
    if len(argv) >= 3 and argv[0] == "draft":
        root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
        print(f"wrote {argv[2]}: {draft(argv[1], argv[2], root)} set_persons cards")
    elif len(argv) >= 2 and argv[0] == "apply":
        root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
        path = root / "data" / "persons_curated.json"
        curated = json.loads(path.read_text(encoding="utf-8"))
        persons = json.loads((root / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][EDITION]
        out, n = apply_decisions(json.loads(Path(argv[1]).read_text(encoding="utf-8")), curated, persons)
        out = {k: out[k] for k in [k for k in out if k.startswith("$")] + sorted(k for k in out if not k.startswith("$"))}
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}: {n} eulogies' persons; run extract_persons.py and extract_mentions.py again")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
