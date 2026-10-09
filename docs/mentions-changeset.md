# Mention operations in `crmedr-changeset/v1`

`scripts/extract_mentions.py --review PATH` (the option is required, by `apply` too) writes the mentions it could not settle as a change-set, which
martyrology-frontend's Review page shows. It quotes the 2004 texts (`context`), so it is written only outside this
repository, in the frontend's private `CHANGESETS_DIR`, and never committed: the script refuses a path inside the
repository, and `.gitignore` excludes `mentions-review*.json`. `apply` refuses an exported change-set inside the repository too. The operations concern only where a mention's words
are. A mention's Wikidata item is decided by `resolve_person` (person_items.json) and `resolve_place`
(gazetteer.json).

Common fields, all three operations:

| Field | Meaning |
| --- | --- |
| `id` | `<edition>\|<eulogy>\|<where>\|<start>`; `<where>` is `text` or `footnote:<n>`. An `add_mention` with no span ends with the person's name instead of `<start>`, or for a place with the place's QID (`place` when it has none). When two operations would share an id (a `remove_mention` and an `add_mention` at one offset), the second gets `\|<op>` appended. Ids are otherwise opaque. |
| `edition`, `eulogy` | The edition and the ID the edition files the text under. A eulogy whose text is filed under its `same_eulogy` twin is listed under the twin's ID, as in `data/mentions.json`. |
| `where` | `"text"` or `{"footnote": n}`, n counting from 1 in printed order |
| `kind` | `"person"` or `"place"` |
| `start`, `end`, `form` | The span in UTF-16 code units and the words as printed; `null` for an `add_mention` with no span |
| `context`, `context_start` | The words around the span, and the UTF-16 offset in the text (or footnote) at which they begin. The span is at `start - context_start` in `context`. With no span, `context` is the whole text and `context_start` is 0. |
| `reasoning` | Why it is asked |
| `decision` | `null`, then `"accept"`, `"reject"` or `"edit"` |

- `add_mention` (also `name`, for a person; and `edited`): add a mention.
  - The extraction proposes one for a person it did not find (no span, or the first word's span as a starting
    point), for a person named inside a place phrase, which was kept as the place, and for a place whose printed
    form it did not find (no span).
  - An `edited` of `{start, end, form}` replaces the span.
  - An `add_mention` with no span can only be applied as an edit.
- `remove_mention`: remove the mention at `start`–`end`. The extraction proposes one for a place phrase that contains
  a person (one per place, naming every person in it), and for a person whose name matched more than once (the first
  match was marked).
- `set_span` (`from: {start, end}`, `to: {start, end, form}`, `edited`): move a mention's span.
  - The extraction never proposes it; a curator authors it.

`python3 scripts/extract_mentions.py apply <exported.json> /path/to/martyrology-texts --review PATH` writes
each eulogy an accepted operation touches into `data/mentions_curated.json`, as its complete list of
mentions (starting from its curated entry, else from `data/mentions.json`). Each touched span gets a `check`
computed from the texts, in place of the operation's `form`, which is never stored; the entries are written in the
shape and key order of `data/mentions.json`, and a new file gets the curated file's `$comment`. `apply` checks every
curated span against the texts first, writes nothing if one fails, and then extracts again. The QIDs written there
are not used: extraction copies them from the decisions.

Applying any decision for a eulogy replaces that eulogy's extraction with its curated list, so the eulogy's other
undecided operations disappear from the next regenerated change-set. Decide all of a eulogy's operations together.
