"""Tests for the hybrid grant matcher (researcher profile → ranked FOAs)."""

from foa_pipeline.matching.matcher import (
    COSINE_WEIGHT,
    TAG_WEIGHT,
    compute_tag_overlap,
    extract_profile_tags,
    match_profile_to_foas,
)


class FakeVectorIndex:
    """Stand-in for VectorIndex that returns canned FAISS hits."""

    def __init__(self, results):
        self._results = results
        self.last_k = None

    def search(self, query, k=10, threshold=0.0, db=None):
        self.last_k = k
        self.last_db = db
        return [dict(r) for r in self._results]


class FakeDatabase:
    """Stand-in for Database exposing only get_tags_for_foa."""

    def __init__(self, tags_by_foa):
        self._tags = tags_by_foa

    def get_tags_for_foa(self, foa_id):
        return self._tags.get(foa_id, [])


class FakeTagger:
    """Stand-in for TaggerPipeline returning canned profile tags."""

    def __init__(self, concept_ids=(), raises=False):
        self._concept_ids = list(concept_ids)
        self._raises = raises

    def tag_record(self, record):
        if self._raises:
            raise RuntimeError("tagger unavailable")
        return [
            {"ontology_concept_id": cid, "label": cid.upper()}
            for cid in self._concept_ids
        ]


def _tag(concept_id, label=None):
    return {"ontology_concept_id": concept_id, "label": label or concept_id.upper()}


class TestComputeTagOverlap:
    """The tag overlap ratio defined in Documentation/MATCHING.md."""

    def test_no_profile_tags_returns_zero(self):
        ratio, matched = compute_tag_overlap(set(), {"sdg_03"})
        assert ratio == 0.0
        assert matched == []

    def test_no_foa_tags_returns_zero(self):
        ratio, matched = compute_tag_overlap({"sdg_03"}, set())
        assert ratio == 0.0
        assert matched == []

    def test_full_overlap_returns_one(self):
        ratio, matched = compute_tag_overlap({"sdg_03", "method_01"}, {"sdg_03", "method_01"})
        assert ratio == 1.0
        assert matched == ["method_01", "sdg_03"]

    def test_matches_matching_md_worked_example(self):
        """Documentation/MATCHING.md: profile has 4 tags, 2 match -> ratio 0.5."""
        profile = {"pop_06", "method_01", "sdg_03", "great_02"}
        foa = {"pop_06", "method_01"}
        ratio, matched = compute_tag_overlap(profile, foa)
        assert ratio == 0.5
        assert matched == ["method_01", "pop_06"]

    def test_ratio_is_containment_not_jaccard(self):
        """Extra FOA tags must not dilute the score (containment, not Jaccard)."""
        profile = {"method_01"}
        foa = {"method_01", "sdg_01", "sdg_02", "great_09"}
        ratio, _ = compute_tag_overlap(profile, foa)
        assert ratio == 1.0  # Jaccard would give 0.25

    def test_matched_ids_are_sorted(self):
        _, matched = compute_tag_overlap({"z_c", "a_a", "m_b"}, {"z_c", "a_a", "m_b"})
        assert matched == sorted(matched)


class TestExtractProfileTags:
    def test_returns_concept_ids(self):
        tagger = FakeTagger(["method_01", "pop_01"])
        assert extract_profile_tags("some profile", tagger) == {"method_01", "pop_01"}

    def test_tagger_failure_degrades_to_empty_set(self):
        """A broken tagger must not crash matching — it falls back to cosine-only."""
        assert extract_profile_tags("some profile", FakeTagger(raises=True)) == set()

    def test_skips_tags_without_concept_id(self):
        class PartialTagger:
            def tag_record(self, record):
                return [{"label": "X"}, {"ontology_concept_id": "sdg_03", "label": "Y"}]

        assert extract_profile_tags("p", PartialTagger()) == {"sdg_03"}


class TestMatchProfileToFoas:
    def test_empty_profile_returns_no_results(self):
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.9}])
        assert match_profile_to_foas("", FakeDatabase({}), index) == []
        assert match_profile_to_foas("   ", FakeDatabase({}), index) == []

    def test_no_candidates_returns_empty(self):
        assert match_profile_to_foas("profile", FakeDatabase({}), FakeVectorIndex([])) == []

    def test_hybrid_score_combines_both_signals(self):
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.8}])
        db = FakeDatabase({"a": [_tag("method_01"), _tag("sdg_03")]})
        results = match_profile_to_foas(
            "profile", db, index, tagger=FakeTagger(["method_01", "pop_01"]), k=1
        )

        assert len(results) == 1
        # profile has 2 tags, 1 matches -> overlap 0.5
        assert results[0]["tag_overlap_ratio"] == 0.5
        assert results[0]["cosine_score"] == 0.8
        expected = round(COSINE_WEIGHT * 0.8 + TAG_WEIGHT * 0.5, 4)
        assert results[0]["hybrid_score"] == expected

    def test_tag_overlap_can_outrank_higher_cosine(self):
        """The whole point of the hybrid score: tags can promote a weaker vector hit."""
        index = FakeVectorIndex([
            {"foa_id": "vector_favourite", "similarity_score": 0.60},
            {"foa_id": "tag_favourite", "similarity_score": 0.55},
        ])
        db = FakeDatabase({
            "vector_favourite": [],
            "tag_favourite": [_tag("method_01"), _tag("pop_01")],
        })
        results = match_profile_to_foas(
            "profile", db, index, tagger=FakeTagger(["method_01", "pop_01"]), k=2
        )

        assert [r["foa_id"] for r in results] == ["tag_favourite", "vector_favourite"]

    def test_without_tagger_falls_back_to_cosine_only(self):
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.8}])
        db = FakeDatabase({"a": [_tag("method_01")]})
        results = match_profile_to_foas("profile", db, index, tagger=None, k=1)

        assert results[0]["tag_overlap_ratio"] == 0.0
        assert results[0]["matched_tags"] == []
        assert results[0]["hybrid_score"] == round(COSINE_WEIGHT * 0.8, 4)

    def test_matched_tags_are_human_readable_labels(self):
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.5}])
        db = FakeDatabase({"a": [_tag("method_01", "Machine Learning")]})
        results = match_profile_to_foas(
            "profile", db, index, tagger=FakeTagger(["method_01"]), k=1
        )
        assert results[0]["matched_tags"] == ["Machine Learning"]

    def test_forwards_db_to_vector_index_search(self):
        """
        vector_index.search() accepts an optional per-call `db` because a
        cached, cross-request VectorIndex holds no connection of its own (see
        api/deps.py get_vector_index). match_profile_to_foas must forward its
        own `db` argument through, or a cached index has no way to resolve
        tags/records and raises at request time -- caught only by an
        end-to-end run against a live server, not by these unit tests alone.
        """
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.5}])
        db = FakeDatabase({})
        match_profile_to_foas("profile", db, index, k=1)
        assert index.last_db is db

    def test_retrieves_wider_candidate_pool_than_k(self):
        """Re-ranking needs headroom, or tag overlap could never promote anything."""
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.5}])
        match_profile_to_foas("profile", FakeDatabase({}), index, k=5)
        assert index.last_k > 5

    def test_respects_k_limit(self):
        index = FakeVectorIndex([
            {"foa_id": f"foa_{i}", "similarity_score": 0.9 - i * 0.1} for i in range(6)
        ])
        results = match_profile_to_foas("profile", FakeDatabase({}), index, k=3)
        assert len(results) == 3

    def test_results_sorted_by_hybrid_score_descending(self):
        index = FakeVectorIndex([
            {"foa_id": "low", "similarity_score": 0.2},
            {"foa_id": "high", "similarity_score": 0.9},
            {"foa_id": "mid", "similarity_score": 0.5},
        ])
        results = match_profile_to_foas("profile", FakeDatabase({}), index, k=3)
        scores = [r["hybrid_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_custom_weights_are_honoured(self):
        index = FakeVectorIndex([{"foa_id": "a", "similarity_score": 0.5}])
        db = FakeDatabase({"a": [_tag("method_01")]})
        results = match_profile_to_foas(
            "profile", db, index, tagger=FakeTagger(["method_01"]), k=1,
            cosine_weight=0.0, tag_weight=1.0,
        )
        assert results[0]["hybrid_score"] == 1.0
