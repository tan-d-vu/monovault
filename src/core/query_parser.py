"""Boolean query parser and evaluator for track search."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.track import Track

_CATEGORY_PREFIX = "category:"


@dataclass(frozen=True)
class TermNode:
    value: str


@dataclass(frozen=True)
class AndNode:
    left: QueryNode
    right: QueryNode


@dataclass(frozen=True)
class OrNode:
    left: QueryNode
    right: QueryNode


QueryNode = TermNode | AndNode | OrNode


def parse(query: str) -> QueryNode | None:
    """Parse a boolean search query into an AST. Returns None for empty/whitespace input."""
    or_nodes: list[QueryNode] = []

    for or_part in query.split("||"):
        and_nodes: list[QueryNode] = []

        for and_part in or_part.split("&&"):
            for term in and_part.split():
                and_nodes.append(TermNode(term))

        if not and_nodes:
            continue

        and_tree: QueryNode = and_nodes[0]
        for node in and_nodes[1:]:
            and_tree = AndNode(and_tree, node)

        or_nodes.append(and_tree)

    if not or_nodes:
        return None

    or_tree: QueryNode = or_nodes[0]
    for node in or_nodes[1:]:
        or_tree = OrNode(or_tree, node)

    return or_tree


def evaluate(node: QueryNode, track: Track) -> bool:
    """Recursively evaluate a parsed AST node against a track."""
    if isinstance(node, TermNode):
        return _match_term(node.value, track)
    if isinstance(node, AndNode):
        return evaluate(node.left, track) and evaluate(node.right, track)
    return evaluate(node.left, track) or evaluate(node.right, track)


def _match_term(value: str, track: Track) -> bool:
    if value.lower().startswith(_CATEGORY_PREFIX):
        rest = value[len(_CATEGORY_PREFIX):]
        if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
            inner = rest[1:-1]
            if inner == "":
                return len(track.categories) == 0
            return any(c.lower() == inner.lower() for c in track.categories)
        target = rest.lower()
        return any(target in c.lower() for c in track.categories)

    needle = value.lower()
    return (
        needle in track.title.lower()
        or needle in track.artist.lower()
        or needle in track.album.lower()
        or any(needle in c.lower() for c in track.categories)
    )
