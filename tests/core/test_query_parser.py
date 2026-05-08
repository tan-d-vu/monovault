import pytest

from src.core.query_parser import AndNode, OrNode, TermNode, evaluate, parse
from src.models.track import Track


def _make_track(
    title="Title",
    artist="Artist",
    album="Album",
    categories=None,
    track_id=1,
) -> Track:
    return Track(
        id=track_id,
        file_path=f"/tmp/t{track_id}.mp3",
        title=title,
        artist=artist,
        album=album,
        duration=180.0,
        categories=categories or [],
        album_art=None,
        folder_path="/tmp",
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParse:
    def test_empty_string_returns_none(self):
        assert parse("") is None

    def test_whitespace_only_returns_none(self):
        assert parse("   ") is None

    def test_single_term_returns_term_node(self):
        assert parse("rock") == TermNode("rock")

    def test_space_separated_terms_fold_into_and_chain(self):
        assert parse("a b") == AndNode(TermNode("a"), TermNode("b"))

    def test_three_space_terms_fold_left_to_right(self):
        assert parse("a b c") == AndNode(AndNode(TermNode("a"), TermNode("b")), TermNode("c"))

    def test_explicit_and_operator(self):
        assert parse("a && b") == AndNode(TermNode("a"), TermNode("b"))

    def test_or_operator(self):
        assert parse("a || b") == OrNode(TermNode("a"), TermNode("b"))

    def test_and_binds_tighter_than_or(self):
        assert parse("a || b && c") == OrNode(TermNode("a"), AndNode(TermNode("b"), TermNode("c")))

    def test_dangling_and_ignored(self):
        assert parse("rock &&") == TermNode("rock")

    def test_dangling_or_ignored(self):
        assert parse("rock ||") == TermNode("rock")

    def test_leading_operator_ignored(self):
        assert parse("|| rock") == TermNode("rock")

    def test_only_operators_returns_none(self):
        assert parse("&&") is None

    def test_category_term_preserved_as_single_token(self):
        assert parse('category:"rock"') == TermNode('category:"rock"')


# ---------------------------------------------------------------------------
# Evaluator tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEvaluate:
    def test_term_matches_title(self):
        track = _make_track(title="Rock Anthem")
        assert evaluate(TermNode("rock"), track) is True

    def test_term_matches_artist(self):
        track = _make_track(artist="Jazz Masters")
        assert evaluate(TermNode("jazz"), track) is True

    def test_term_matches_album(self):
        track = _make_track(album="Blues Collection")
        assert evaluate(TermNode("blues"), track) is True

    def test_term_matches_category(self):
        track = _make_track(categories=["workout"])
        assert evaluate(TermNode("workout"), track) is True

    def test_term_no_match(self):
        track = _make_track(title="Rock", artist="Artist", album="Album")
        assert evaluate(TermNode("jazz"), track) is False

    def test_term_match_is_case_insensitive(self):
        track = _make_track(title="ROCK")
        assert evaluate(TermNode("rock"), track) is True

    def test_category_prefix_substring_match(self):
        track = _make_track(categories=["rockabilly"])
        assert evaluate(TermNode("category:rock"), track) is True

    def test_category_prefix_substring_no_match(self):
        track = _make_track(categories=["jazz"])
        assert evaluate(TermNode("category:rock"), track) is False

    def test_category_prefix_exact_match(self):
        track = _make_track(categories=["rock"])
        assert evaluate(TermNode('category:"rock"'), track) is True

    def test_category_prefix_exact_excludes_superstring(self):
        track = _make_track(categories=["rockabilly"])
        assert evaluate(TermNode('category:"rock"'), track) is False

    def test_category_prefix_exact_case_insensitive(self):
        track = _make_track(categories=["Rock"])
        assert evaluate(TermNode('category:"rock"'), track) is True

    def test_category_empty_quotes_matches_untagged(self):
        track = _make_track(categories=[])
        assert evaluate(TermNode('category:""'), track) is True

    def test_category_empty_quotes_excludes_tagged(self):
        track = _make_track(categories=["rock"])
        assert evaluate(TermNode('category:""'), track) is False

    def test_and_node_requires_both(self):
        track = _make_track(title="Rock Jazz")
        assert evaluate(AndNode(TermNode("rock"), TermNode("jazz")), track) is True
        assert evaluate(AndNode(TermNode("rock"), TermNode("blues")), track) is False

    def test_and_node_short_circuits(self):
        track = _make_track(title="Rock")
        assert evaluate(AndNode(TermNode("jazz"), TermNode("rock")), track) is False

    def test_or_node_either_matches(self):
        track = _make_track(title="Rock")
        assert evaluate(OrNode(TermNode("rock"), TermNode("jazz")), track) is True
        assert evaluate(OrNode(TermNode("jazz"), TermNode("blues")), track) is False

    def test_and_over_or_precedence(self):
        # "solo || beta && gamma" → OrNode(solo, AndNode(beta, gamma))
        node = OrNode(TermNode("solo"), AndNode(TermNode("beta"), TermNode("gamma")))

        track_solo = _make_track(title="solo", artist="nobody", album="nothing")
        assert evaluate(node, track_solo) is True

        track_beta_gamma = _make_track(title="beta gamma", artist="nobody", album="nothing")
        assert evaluate(node, track_beta_gamma) is True

        track_beta = _make_track(title="beta", artist="nobody", album="nothing")
        assert evaluate(node, track_beta) is False
