# Jev suggestions on the Italian mention review cards — design

Issue: [#97](https://github.com/CatholicOS/crmedr/issues/97). Date: 2026-10-15. Builds on
`scripts/extract_mentions.py` (the review change-set) and `scripts/mentions_italian.py`
(the matcher's name runs).

## Goal

Give every Italian person-mention review card a suggested decision from Jev, TypeSafe's
System One model, with a probability and a confidence, so the curator confirms or overrides it
instead of deciding each card from scratch. The curator still decides every card: a suggestion
is never applied by itself, and the exported change-set is the same as today.

Success is measured before anything ships: the suggestions are evaluated against the cards the
curator has already decided, and a confidence threshold is chosen from that evaluation.

## Decisions

- **Offline batch in crmedr** (approach A). A script adds `suggested` to each card of a review
  change-set before it is uploaded to the server's change-set directory. No frontend request
  ever calls TypeSafe, and the API key never leaves the curator's machine.
- **Sending the cards' context is acceptable** (the curator's ruling, 2026-10-15): each card
  quotes a sentence or two of the CEI 2004 text around one name, sent to TypeSafe under its
  standard terms (not used for training; retained per its Data Processing Agreement) to
  adjudicate it, not to reproduce it. Only the card's own `context` is sent, never a whole
  eulogy, and never anything else from martyrology-texts.
- **Jev picks; code copies.** Jev never writes a span: it chooses among candidate spans the
  matcher finds (TypeSafe's pre-parsed value extraction pattern), or "none", and code copies
  the chosen span's offsets exactly. A suggestion can only ever be a span that exists.
- **The model is pinned** to a versioned ID (`jev-1.14.0`), never the `jev-latest` alias, so
  answers and the threshold do not drift; a new version is adopted by re-running the
  evaluation. The answering model is recorded on each suggestion.
- **Standard library only**, like every crmedr script: the HTTP API through `urllib`, not the
  TypeSafe SDK.
- **The key** is read from `TYPESAFE_API_KEY`, else from `~/.config/typesafe/api_key` (the file
  the curator keeps, mode 600). It is never printed, logged or written anywhere.
- **Scope:** Italian person `add_mention` cards (edition `martyrologium_romanum_2004_it_IT`).
  Place cards, Latin cards, gazetteer and person-item cards are out of scope; the same pattern
  can extend to them later.

## The cards and the questions

A card's `reasoning` tells its kind (set by `extract_mentions.py`):

| Kind | Reasoning | Question |
|---|---|---|
| repeat | "`<name>` matched again: …" | `identity` (Choice) |
| position | "… proposed by its place in the list" | `span` (Choice) |
| not found | "`<name>` was not found", no span | `span` (Choice) |

Any other card gets no question and no suggestion.

### State (one request per card)

```json
{
  "eulogy": "<eulogy ID>",
  "where": "text | footnote 1",
  "person": {"latin_name": "Pompeia", "n": 2, "italian_forms": ["Pompea", "Pompeia"]},
  "persons_in_this_place": [{"latin_name": "Potamia"}, {"latin_name": "Pompeia"}, {"latin_name": "Rodana"}, {"latin_name": "Pompeia", "n": 2}],
  "neighbours": {"before": {"latin_name": "Potamia", "marked_as": "Potamia"},
                 "after": {"latin_name": "Rodana", "marked_as": "Rodana"}},
  "context": "<the card's context>",
  "proposed": "<the card's form, or null>",
  "candidates": {"c1": {"words": "…", "at": 12}, "c2": {"words": "…", "at": 40}}
}
```

`persons_in_this_place` is the eulogy's persons printed in the same text or footnote, in the
Latin print order, with their `n`. `neighbours` are, for a person of a list, the persons printed just before
and after them in the Latin order, with the words the Italian is already marked with for them
when those words lie inside the card's context (`marked_as`, else null): a card's context is
only about 40 characters either side of its span (the whole footnote for a not-found card), too
short to count "the 2nd Pompeia" in a long list, and the neighbours carry that position.
`candidates` (span cards only) are the matcher's name runs (`mentions_italian.runs`) that lie
wholly inside the card's context, numbered in print order, with their offset in the context;
a repeat card has none, its question is about the `proposed` words.
Offsets are code-point positions in `context`; the script converts them to the card's UTF-16
eulogy offsets with `context_start`.

### `identity` (repeat cards)

Choice; instructions: "The `person` is already marked earlier in this text. Do the words
`proposed` name the same person again?" Criteria:

- `same_person`: the same person named again. In running text, and in a pair of saints, a name
  printed again is the same person unless the text says it is another ("un altro", "un'altra").
- `another_person`: another person who bears the same name: the text says so ("un altro
  Dionigi"), or the name is printed again in a list of martyrs, where a repeated name is always
  a different person.
- `not_this_person`: the words are not this person at all: an institution, church, order or
  place named after the saint ("l'Ordine Ospedaliero di San Giovanni di Dio"), a title, or a
  different saint of the same name named for comparison.

Suggestion: `same_person` → accept; `another_person`, `not_this_person` → reject.

### `span` (position and not-found cards)

Choice; instructions: "Which of the `candidates` are the words that name the `person` (the
`n`th person of that name in `persons_in_this_place`, in the Italian edition's translation of
the Latin list)? Answer none if no candidate names them." Criteria: one option per candidate
(`c1` … `cN`, each described by its words), plus `none`: "no candidate names this person:
they are not printed in this context, or only inside a longer name of someone else".

Suggestion: the candidate equal to `proposed` → accept; another candidate → edit with that
candidate's span; `none` → reject. A not-found card with no candidates gets no request.

## Components

1. **`scripts/mentions_jev.py`**: pure functions, no network:
   - `card_kind(op)` → `"repeat" | "position" | "not_found" | None`;
   - `candidates(op, persons)` → the candidate spans of a card's context;
   - `request_for(op, persons, marks)` → the request body (state, questions, model), `marks`
     being the eulogy's current Italian marks in `data/mentions.json` (for `neighbours`);
   - `suggestion(op, answer, cands)` → the `suggested` object, or None.
   Plus `TypeSafe`, a small client: `POST https://api.typesafe.ai/v1/systemone`, bearer key,
   retries 429, 529 and 5xx with exponential backoff (5 attempts), stops on 400 and 401 with the
   API's message, never logs the key or the body.
2. **The cache**: each response stored in `.cache/typesafe/<sha256 of the request body>.json`
   (`.cache/` is git-ignored). A cached request costs nothing; changing a question's wording
   changes its hash, so stale answers are never reused.
3. **`scripts/suggest_mentions.py`**:
   - `suggest <review.json> [--min-confidence X]` writes `suggested` on every in-scope card
     whose answer reaches the threshold, and removes a stale `suggested` from the others; it
     never touches `decision` or `edited`. The default threshold is a constant set from the
     evaluation (below).
   - `evaluate <decided.json>... [--weak <decided.json>...]` asks (or reads from the cache)
     every decided card, compares the suggestion with the curator's decision, and prints, per
     kind: the cards, the agreement at each threshold from 0.0 to 0.9, the share of cards that
     would get a suggestion, and every disagreement (ID, decision, suggestion, probability).
     `--weak` files are reported apart (decisions taken by rule on the curator's behalf, not by
     the curator).
   - Both refuse to run without a key unless every request is cached.

The `suggested` object on a card:

```json
"suggested": {"decision": "edit", "start": 229, "end": 234, "form": "Elpis",
              "probability": 0.91, "confidence": 0.87, "model": "jev-1.14.0"}
```

(`start`, `end`, `form` only for `edit`; offsets in UTF-16, as everywhere in the change-set.)

## Frontend (martyrology-frontend)

- `AddMentionOp` gains `suggested?: { decision: "accept" | "reject" | "edit"; start?; end?;
  form?; probability: number; confidence: number; model: string } | null`.
- MentionCard shows, under the reasoning: "Jev suggests: accept / reject / mark these words:
  «…»" with the confidence as a percentage; an `edit` suggestion is previewed in the passage
  (dashed underline, distinct from the proposed span).
- A "Take the suggestion" button records exactly the decision the curator would record by hand
  (`accept`, `reject`, or `edit` with the suggested span). The export is unchanged, so
  `extract_mentions.py apply` needs no change.
- Messages in the six languages.

## Evaluation

- Strict: the curator's own decided Italian files: `mentions-review-it-01.decided.json`,
  `-02.decided.json` (with the second Ianuaria flipped to accept, as the curator ruled) and
  `-06.decided.json`.
- Weak (`--weak`): the March–December decisions taken by the curator's rules
  (`mentions-it-decided-all.json` in the session scratchpad, months 03–12).
- The decided files stay outside the repository (they quote the 2004 text).
- The threshold: the lowest confidence at which the strict agreement is at least 95%; if no
  threshold reaches it with at least a third of the cards suggested, the suggestions are not
  shipped and the result is reported to the curator instead.

## Error handling

- No key and uncached requests: stop before the first request.
- 401: stop, "the TypeSafe key was refused".
- 400 (a request too long or malformed): that card gets no suggestion; the run goes on and
  reports it.
- 429/529/5xx after five attempts: that card gets no suggestion; reported.
- An answer naming an option the request did not offer: no suggestion; reported.

## Testing

- `tests/test_mentions_jev.py`, offline: card kinds; neighbours (Latin order, `marked_as` only
  inside the context); candidates (runs inside the context only,
  offsets converted to UTF-16 with `context_start`, the proposed span among them); the request
  body (state fields, the pinned model, the options); `suggestion` for every answer; the cache
  key; the client's retry, stop and key-redaction behaviour with a fake transport.
- `suggest` and `evaluate` on a fixture change-set with canned answers in a temporary cache:
  no network in the test suite.
- Frontend: MentionCard shows a suggestion, previews an edit, and "Take the suggestion" records
  the same decision record as the manual buttons; no suggestion, no button.

## Out of scope

- Place, Latin, gazetteer and person-item cards.
- Live suggestions from the frontend (approach B).
- Any automatic decision.

## Evaluation result (2026-10-15, jev-1.14.0)

Strict (the curator's decisions, January, February and June): 24 in-scope cards (repeat 7,
position 10, not found 7). At the chosen threshold, confidence ≥ 0.90: 12 suggested (50%),
12 agree (100%). Below it the bar is missed (≥ 0.80: 16 suggested, 94% agree), so the
threshold is 0.90. Of the 5 strict disagreements at any confidence, none reaches 0.90.

Weak (decided by the curator's rules, March–December): 97 cards; at ≥ 0.90, 66 suggested (68%),
60 agree (91%). The high-confidence disagreements fall in two groups, both for the curator to
weigh before trusting the suggestions on such cards:

- **Repeat cards the rules reject**: an institution named after the saint accepted as the saint
  (0308, 0.95), a namesake relative (1226, 0.92; 1122, 0.85), a name printed twice in a list
  (1124, 0.91), a condensed group (1217, 0.98). The criteria state these cases; the model still
  misses some.
- **Spans the candidates cannot hold**: the right words open with a lowercase word ("santo
  ladrone", "beata Maria Vergine …"), so they are never a name run, and the model picks a
  sub-span or none with high confidence (0325, 0.97; 0915, 0.98). A wider candidate set
  (honorific-led runs) would fix this class.

The strict set is small (24 cards, 12 suggested): the threshold should be re-checked as the
curator decides more cards (each decided file adds to `evaluate`).

