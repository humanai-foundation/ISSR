"""
Tests for category suppression over character ranges.

This exists so a section of an FOA can be disqualified from producing certain
tags (populations must not come from eligibility text) without deleting it —
deleting shifts Layer 2's chunk boundaries and perturbs unrelated categories,
which was measured at -0.049 global F1.
"""

import numpy as np
import pytest

from foa_pipeline.ontology.store import OntologyConcept
from foa_pipeline.tagging.layer2_embedding import L2Tagger

POPULATION = frozenset({"population"})


def _concept(concept_id, category):
    return OntologyConcept(
        concept_id=concept_id,
        label=concept_id.replace("_", " ").title(),
        category=category,
        parent_id=None,
        source_ontology="custom",
        description=None,
    )


class _StubModel:
    """Returns a fixed vector per text, so cosine scores are predictable."""

    def __init__(self, vectors):
        self.vectors = vectors

    def encode(self, texts, convert_to_numpy=True):
        return np.array([self.vectors[t] for t in texts], dtype=float)


class TestChunkSpans:
    def test_spans_locate_chunks_in_the_original_text(self):
        tagger = L2Tagger()
        text = " ".join(f"word{i}" for i in range(600))
        spans = tagger.chunk_text_with_spans(text, chunk_size=250, overlap=50)

        assert len(spans) > 1
        for chunk, start, end in spans:
            assert start < end <= len(text)
            # Chunks are whitespace-normalised, so compare first/last tokens
            # rather than expecting a byte-identical slice.
            original = text[start:end]
            assert original.split()[0] == chunk.split()[0]
            assert original.split()[-1] == chunk.split()[-1]

    def test_chunks_overlap_as_configured(self):
        tagger = L2Tagger()
        text = " ".join(f"w{i}" for i in range(500))
        spans = tagger.chunk_text_with_spans(text, chunk_size=100, overlap=20)
        assert spans[1][1] < spans[0][2], "second chunk should start before the first ends"

    def test_chunk_text_still_returns_plain_strings(self):
        """The original API is unchanged for callers that don't need spans."""
        tagger = L2Tagger()
        text = " ".join(f"w{i}" for i in range(300))
        plain = tagger.chunk_text(text)
        with_spans = tagger.chunk_text_with_spans(text)
        assert plain == [c for c, _s, _e in with_spans]
        assert all(isinstance(c, str) for c in plain)

    def test_empty_text(self):
        assert L2Tagger().chunk_text_with_spans("") == []
        assert L2Tagger().chunk_text_with_spans("   ") == []


class TestSuppressionRule:
    """A chunk counts as excluded only on majority overlap."""

    def test_no_spans_suppresses_nothing(self):
        assert L2Tagger._suppressed_categories(0, 100, None) == frozenset()
        assert L2Tagger._suppressed_categories(0, 100, []) == frozenset()

    def test_fully_inside_excluded_region_is_suppressed(self):
        assert L2Tagger._suppressed_categories(
            10, 20, [(0, 100, POPULATION)]
        ) == POPULATION

    def test_no_overlap_is_not_suppressed(self):
        assert L2Tagger._suppressed_categories(
            200, 300, [(0, 100, POPULATION)]
        ) == frozenset()

    def test_minority_overlap_is_not_suppressed(self):
        """A chunk that is mostly programme text keeps its tags."""
        # 10 of 100 characters fall inside the excluded region.
        assert L2Tagger._suppressed_categories(
            90, 190, [(0, 100, POPULATION)]
        ) == frozenset()

    def test_majority_overlap_is_suppressed(self):
        # 90 of 100 characters fall inside the excluded region.
        assert L2Tagger._suppressed_categories(
            10, 110, [(0, 100, POPULATION)]
        ) == POPULATION

    def test_exactly_half_is_not_suppressed(self):
        """Ties resolve toward keeping the tag."""
        assert L2Tagger._suppressed_categories(
            50, 150, [(0, 100, POPULATION)]
        ) == frozenset()

    def test_multiple_spans_union_their_categories(self):
        result = L2Tagger._suppressed_categories(
            0, 10,
            [(0, 100, frozenset({"population"})), (0, 100, frozenset({"method"}))],
        )
        assert result == frozenset({"population", "method"})


class TestScoreConcepts:
    """
    The unthresholded ranking view of Layer 2.

    Extracted from `tag_text` so the discipline benchmark can rank concepts
    rather than threshold them. These tests pin the contract that makes the two
    callers share one scoring implementation.
    """

    def _tagger(self):
        tagger = L2Tagger()
        tagger.model = _StubModel({
            "alpha beta": np.array([1.0, 0.0]),
        })
        tagger.concept_embeddings = {
            "d1": np.array([1.0, 0.0]),    # identical -> 1.0
            "d2": np.array([0.0, 1.0]),    # orthogonal -> 0.0
            "m1": np.array([1.0, 1.0]),    # 45 degrees -> ~0.707
        }
        tagger.concept_lookup = {
            "d1": _concept("d1", "research_discipline"),
            "d2": _concept("d2", "research_discipline"),
            "m1": _concept("m1", "method"),
        }
        return tagger

    def test_returns_a_score_for_every_concept(self):
        scores = self._tagger().score_concepts("alpha beta")
        assert set(scores) == {"d1", "d2", "m1"}

    def test_scores_are_cosine_similarities(self):
        scores = self._tagger().score_concepts("alpha beta")
        assert scores["d1"] == pytest.approx(1.0)
        assert scores["d2"] == pytest.approx(0.0)
        assert scores["m1"] == pytest.approx(0.7071, abs=1e-3)

    def test_category_filter_restricts_the_output(self):
        scores = self._tagger().score_concepts("alpha beta", category="research_discipline")
        assert set(scores) == {"d1", "d2"}

    def test_is_not_thresholded(self):
        """A zero-similarity concept must still be returned, so it can be ranked."""
        scores = self._tagger().score_concepts("alpha beta")
        assert "d2" in scores

    def test_unknown_category_returns_nothing(self):
        assert self._tagger().score_concepts("alpha beta", category="nope") == {}

    def test_empty_text_returns_nothing(self):
        assert self._tagger().score_concepts("") == {}

    def test_missing_model_returns_nothing_rather_than_raising(self):
        tagger = L2Tagger()
        tagger.concept_embeddings = {"d1": np.array([1.0, 0.0])}
        assert tagger.score_concepts("alpha beta") == {}

    def test_excluded_spans_suppress_a_category(self):
        tagger = self._tagger()
        scores = tagger.score_concepts(
            "alpha beta", excluded_spans=[(0, 100, frozenset({"research_discipline"}))]
        )
        assert set(scores) == {"m1"}


class TestTitleScoreCombination:
    """
    Folding a title score into a body score.

    Measured on both eval sets and left disabled by default: the silver set got
    worse at every weight tried, and the gold set's +0.005 came with precision
    up and recall down, i.e. it behaved as a threshold change rather than as
    title evidence. See Documentation/EVALUATION.md 4d.
    """

    def test_zero_weight_is_a_no_op(self):
        """The default must reproduce body-only scoring exactly."""
        for combine in ("blend", "max"):
            assert L2Tagger.combine_scores(0.42, 0.99, 0.0, combine) == 0.42
            assert L2Tagger.combine_scores(0.42, 0.01, 0.0, combine) == 0.42

    def test_negative_weight_is_also_a_no_op(self):
        assert L2Tagger.combine_scores(0.42, 0.99, -0.5) == 0.42

    def test_blend_is_a_weighted_average(self):
        assert L2Tagger.combine_scores(0.40, 0.80, 0.25) == 0.50

    def test_blend_lowers_score_when_title_is_unrelated(self):
        """This is why blend doubles as a threshold increase."""
        assert L2Tagger.combine_scores(0.60, 0.10, 0.30) < 0.60

    def test_max_never_lowers_the_body_score(self):
        assert L2Tagger.combine_scores(0.60, 0.10, 0.30, "max") == 0.60

    def test_max_promotes_a_strong_title_match(self):
        assert L2Tagger.combine_scores(0.30, 0.75, 0.30, "max") == 0.75

    def test_full_weight_blend_is_title_only(self):
        assert L2Tagger.combine_scores(0.20, 0.90, 1.0) == pytest.approx(0.90)
