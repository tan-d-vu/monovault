# Boolean Search Implementation Plan

## Overview

Add `&&` (AND) and `||` (OR) boolean operators to the search bar, with spaces acting as
implicit AND. Parsing and evaluation live in a new `src/core/query_parser.py` module;
`SearchController` uses it to filter tracks directly, removing its dependency on
`repo.search()`.

## Confirmed Behaviour

| Input | Meaning |
|---|---|
| `rock jazz` | tracks matching `rock` AND `jazz` (any field each) |
| `rock && jazz` | same as above |
| `rock \|\| jazz` | tracks matching `rock` OR `jazz` |
| `a \|\| b && c` | `a OR (b AND c)` — AND binds tighter |
| `category:rock && hello` | category contains "rock" AND any field contains "hello" |
| `category:"rock" \|\| jazz` | exact category "rock" OR any-field "jazz" |
| `rock &&` | dangling operator ignored → same as `rock` |
| `category:""` | untagged tracks (no categories) — existing behaviour preserved |

## Files Changed

### 1. New — `src/core/query_parser.py`

**AST nodes** (frozen dataclasses):
```
TermNode(value: str)
AndNode(left: QueryNode, right: QueryNode)
OrNode(left: QueryNode, right: QueryNode)
QueryNode = TermNode | AndNode | OrNode
```

**`parse(query: str) -> QueryNode | None`**

Tokenisation steps (executed in order, respecting precedence):
1. Split by `||` → OR operands
2. Within each OR operand, split by `&&` → AND operands
3. Within each AND operand, split by whitespace → individual `TermNode`s
4. Trim each segment; skip empty strings (handles dangling operators)
5. Fold AND operands left-to-right into `AndNode` chains
6. Fold OR operands left-to-right into `OrNode` chains

Returns `None` for empty/whitespace-only input.

**`evaluate(node: QueryNode, track: Track) -> bool`**

Recursive; dispatches on node type:
- `TermNode`: call `_match_term(value, track)`
- `AndNode`: short-circuit `evaluate(left) and evaluate(right)`
- `OrNode`: short-circuit `evaluate(left) or evaluate(right)`

**`_match_term(value: str, track: Track) -> bool`**

- If `value` starts with `category:` (case-insensitive):
  - Quoted suffix `"..."` → exact case-insensitive match against track categories
  - Empty quoted `""` → `len(track.categories) == 0`
  - Bare suffix → substring match against track categories
- Otherwise → case-insensitive substring match against title, artist, album, any category

### 2. Modified — `src/ui/controllers/search_controller.py`

- Remove `_parse_category_query` and `_filter_by_category_value` (absorbed into `query_parser`)
- `search_immediate`: parse query with `parse()`; if `None`, return `get_all_tracks()`; else filter `get_all_tracks()` with `evaluate()`
- `repo.search()` is no longer called (controller owns all filtering)
- Public interface and signal contract unchanged

### 3. New — `tests/core/test_query_parser.py`

Parser unit tests:
- Empty string → `None`
- Single term → `TermNode`
- Spaces → `AndNode` chain
- `&&` explicit → `AndNode`
- `||` → `OrNode`
- Mixed: `a || b && c` → `OrNode(TermNode(a), AndNode(TermNode(b), TermNode(c)))`
- Dangling `&&` / `||` → ignored cleanly

Evaluator unit tests against `Track` fixtures:
- Plain term: title match, artist match, album match, category match
- `category:rock` substring match
- `category:"rock"` exact match / no superstring match
- `category:""` untagged
- AND: both must match
- OR: either matches
- AND > OR precedence

### 4. Updated — `tests/ui/test_search_controller.py`

- `TestSearchController.test_search_immediate_with_query`: replace `repo.search` mock assertion with actual track filtering (controller no longer delegates to `repo.search`)
- `test_plain_search_unchanged`: update same way
- Add `TestBooleanSearch` class:
  - `test_spaces_act_as_and`
  - `test_ampersand_and`
  - `test_pipe_or`
  - `test_and_or_precedence`
  - `test_category_and_plain_term`
  - `test_dangling_operator_ignored`

## Non-goals

- No parentheses / grouping
- No NOT / negation
- `category:"multi word"` with spaces inside quotes is not supported (each space-separated word becomes its own token); document as known limitation
- `LibraryManager.search()` is left untouched (still usable by direct callers)
