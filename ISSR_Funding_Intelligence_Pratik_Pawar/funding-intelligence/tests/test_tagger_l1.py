"""Tests for the Layer 1 spaCy PhraseMatcher tagger."""


import pytest
from spacy.tokens import Span

from foa_pipeline.ontology.store import OntologyStore
from foa_pipeline.ontology.synonyms import expand_synonyms_for_store
from foa_pipeline.tagging.evidence import TagEvidence
from foa_pipeline.tagging.layer1_spacy import L1Tagger


@pytest.fixture(scope="module")
def ontology_with_synonyms(tmp_path_factory):
    """Build a small ontology store with concepts and synonyms.

    Module-scoped because spaCy model loading is expensive.
    """
    tmp = tmp_path_factory.mktemp("ontology")
    csv_path = tmp / "test_concepts.csv"
    csv_path.write_text(
        "concept_id,label,category,parent_id,description\n"
        "sdg_13,Climate Action,research_domain,,Take urgent action to combat climate change\n"
        "sdg_03,Good Health and Well-being,research_domain,,"
        "Ensure healthy lives and promote well-being\n"
        "sdg_01,No Poverty,research_domain,,End poverty in all its forms everywhere\n"
        "great_02,Health,sponsor_theme,,Biomedical and public health research\n"
        "meth_ml,Machine Learning,method,,Subset of AI for learning from data\n"
        "pop_rural,Rural Communities,population,,Rural and non-metropolitan populations\n"
    )
    store = OntologyStore(tmp / "test.db")
    store.load_from_csv(csv_path, "test")
    expand_synonyms_for_store(store)
    return store


@pytest.fixture(scope="module")
def l1_tagger(ontology_with_synonyms):
    """Build an L1 tagger with the test ontology."""
    tagger = L1Tagger(spacy_model="en_core_web_lg")
    tagger.build_matcher(ontology_with_synonyms)
    return tagger


class TestL1TaggerBasic:
    """Basic Layer 1 tagger functionality."""

    def test_empty_text_returns_no_tags(self, l1_tagger):
        """Empty text should produce no evidence."""
        result = l1_tagger.tag_text("")
        assert result == []

    def test_none_text_returns_no_tags(self, l1_tagger):
        """None text should produce no evidence."""
        result = l1_tagger.tag_text(None)
        assert result == []

    def test_returns_tag_evidence_objects(self, l1_tagger):
        """Results should be TagEvidence instances."""
        result = l1_tagger.tag_text("This program supports climate action research.")
        assert all(isinstance(ev, TagEvidence) for ev in result)


class TestL1TaggerMatching:
    """Test that the tagger finds expected concepts in text."""

    def test_finds_exact_label_match(self, l1_tagger):
        """Exact concept label should be matched."""
        result = l1_tagger.tag_text(
            "This program funds climate action initiatives to combat global warming."
        )
        concept_ids = {ev.concept_id for ev in result}
        assert "sdg_13" in concept_ids

    def test_finds_health_label(self, l1_tagger):
        """Health-related concepts should match."""
        result = l1_tagger.tag_text(
            "Research on good health and well-being in underserved communities."
        )
        concept_ids = {ev.concept_id for ev in result}
        assert "sdg_03" in concept_ids or "great_02" in concept_ids

    def test_finds_machine_learning(self, l1_tagger):
        """Method concepts should match."""
        result = l1_tagger.tag_text(
            "We will apply machine learning techniques to analyse survey data."
        )
        concept_ids = {ev.concept_id for ev in result}
        assert "meth_ml" in concept_ids

    def test_finds_population_match(self, l1_tagger):
        """Population concepts should match."""
        result = l1_tagger.tag_text(
            "The study focuses on rural communities in the American South."
        )
        concept_ids = {ev.concept_id for ev in result}
        assert "pop_rural" in concept_ids

    def test_synonym_matching(self, l1_tagger):
        """Synonyms should trigger matches.

        Note: 'ML' (2 chars) is filtered by the synonym expander's >2 char rule.
        We use 'deep learning' which maps to machine learning via ABBREVIATIONS,
        or 'global warming' which maps to Climate Action.
        """
        result = l1_tagger.tag_text(
            "Our study applies global warming mitigation strategies "
            "to vulnerable coastal ecosystems."
        )
        concept_ids = {ev.concept_id for ev in result}
        # "global warming" is a synonym of Climate Action (sdg_13)
        assert "sdg_13" in concept_ids

    def test_no_false_positives_on_unrelated_text(self, l1_tagger):
        """Unrelated text should produce few or no matches."""
        result = l1_tagger.tag_text(
            "The quick brown fox jumps over the lazy dog."
        )
        # Should produce zero or very few matches
        assert len(result) <= 1


class TestL1TaggerProperties:
    """Test properties of L1 tag evidence."""

    def test_confidence_is_always_one(self, l1_tagger):
        """Layer 1 should always assign confidence 1.0."""
        result = l1_tagger.tag_text(
            "This project researches climate action and machine learning."
        )
        for ev in result:
            assert ev.confidence == 1.0

    def test_source_layer_is_terminological(self, l1_tagger):
        """Source layer should be 'layer_1_terminological'."""
        result = l1_tagger.tag_text("Research on climate action.")
        for ev in result:
            assert ev.source_layer == "layer_1_terminological"

    def test_context_snippet_populated(self, l1_tagger):
        """Context snippet should contain text around the match."""
        result = l1_tagger.tag_text(
            "This program supports climate action in developing countries."
        )
        for ev in result:
            assert len(ev.context_snippet) > 0

    def test_concept_id_populated(self, l1_tagger):
        """Each evidence should have a concept_id."""
        result = l1_tagger.tag_text("Machine learning for health.")
        for ev in result:
            assert ev.concept_id is not None
            assert len(ev.concept_id) > 0

    def test_category_is_valid(self, l1_tagger):
        """Category should be one of the valid ontology categories."""
        valid = {"research_domain", "method", "population", "sponsor_theme"}
        result = l1_tagger.tag_text(
            "Climate action and machine learning for rural communities."
        )
        for ev in result:
            assert ev.category in valid


class TestL1TaggerDeduplication:
    """Test that repeated mentions don't produce duplicate tags."""

    def test_deduplicates_repeated_mentions(self, l1_tagger):
        """Same concept mentioned multiple times should only appear once."""
        text = (
            "Climate action is critical. Climate action must be taken now. "
            "We need more climate action research."
        )
        result = l1_tagger.tag_text(text)
        concept_ids = [ev.concept_id for ev in result]
        # Each concept should appear at most once
        assert len(concept_ids) == len(set(concept_ids))


class TestL1TaggerScopeFilters:
    """
    Contexts in which a term does not indicate the opportunity's subject.

    Layer 1 matched 51 concepts across the 20-FOA gold set and 30 were wrong,
    despite every match being a genuine occurrence of the word. The filters
    encode the difference between funding a topic and merely mentioning one.
    """

    def test_referral_to_another_programme_is_rejected(self, l1_tagger):
        """"... is supported through programs in the Directorate for X" is a redirect."""
        text = "Research on natural hazards is supported through programs in climate action."
        assert "sdg_13" not in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_agency_mission_boilerplate_is_rejected(self, l1_tagger):
        text = "Proposals must describe broadening participation efforts in climate action."
        assert "sdg_13" not in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_permissive_modality_is_rejected(self, l1_tagger):
        """An optional technique is not the programme's subject."""
        text = "Proposals may use machine learning to advance the research."
        assert "meth_ml" not in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_proper_name_is_rejected(self, l1_tagger):
        text = "Awards are made under the Climate Action Act of 2021."
        assert "sdg_13" not in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_stem_idiom_is_rejected(self, l1_tagger):
        """The STEM expansion names an acronym, not a discipline."""
        doc = l1_tagger.nlp(
            "Noyce supports talented science, technology, engineering, and mathematics majors."
        )
        idx = [t.i for t in doc if t.text.lower() == "engineering"][0]
        span = Span(doc, idx, idx + 1)
        assert L1Tagger.out_of_scope_context(doc, span) == "stem_idiom"

    def test_stem_idiom_spares_an_adjacent_term(self, l1_tagger):
        """
        A proximity-based version of this filter also discarded the legitimate
        "students" match sitting beside a STEM expansion. Only words inside the
        idiom, and supplied by it, are rejected.
        """
        doc = l1_tagger.nlp(
            "An expanded presence of doctoral students in science, technology, "
            "engineering, and mathematics fields."
        )
        idx = [t.i for t in doc if t.text.lower() == "students"][0]
        assert L1Tagger.out_of_scope_context(doc, Span(doc, idx, idx + 1)) is None

    def test_plain_topical_mention_survives(self, l1_tagger):
        """The filters must not fire on ordinary subject-matter prose."""
        text = "Machine learning can further improve signal processing in these systems."
        assert "meth_ml" in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_cue_after_the_match_does_not_fire(self, l1_tagger):
        """Referral and permissive cues precede their target; look backwards only."""
        text = "This programme funds climate action. Other proposals may use other methods."
        assert "sdg_13" in {ev.concept_id for ev in l1_tagger.tag_text(text)}

    def test_rejected_match_does_not_block_a_later_valid_one(self, l1_tagger):
        """
        A concept is marked as seen only once a match is accepted. Marking it
        earlier let the first rejected occurrence consume the concept's single
        slot, silently hiding a genuine mention further down the document.
        """
        text = (
            "Proposals may use machine learning to advance the research. "
            "Machine learning is the central concern of this programme."
        )
        assert "meth_ml" in {ev.concept_id for ev in l1_tagger.tag_text(text)}


class TestL1TaggerExcludedSpans:
    """Category suppression over character ranges.

    Populations must not be inferred from eligibility text, which states who
    may apply rather than who the research serves (Documentation/ONTOLOGY.md 2.3).
    """

    POPULATION = frozenset({"population"})

    def test_match_inside_excluded_span_is_suppressed(self, l1_tagger):
        text = "Eligible applicants include rural communities and tribal colleges."
        span = [(0, len(text), self.POPULATION)]

        without = {ev.concept_id for ev in l1_tagger.tag_text(text)}
        with_exclusion = {ev.concept_id for ev in l1_tagger.tag_text(text, excluded_spans=span)}

        assert "pop_rural" in without
        assert "pop_rural" not in with_exclusion

    def test_match_outside_excluded_span_survives(self, l1_tagger):
        prefix = "This program studies rural communities in depth. "
        text = prefix + "Eligible applicants include universities."
        span = [(len(prefix), len(text), self.POPULATION)]

        concept_ids = {ev.concept_id for ev in l1_tagger.tag_text(text, excluded_spans=span)}
        assert "pop_rural" in concept_ids

    def test_suppressed_match_does_not_block_a_later_valid_one(self, l1_tagger):
        """
        The exclusion check runs before the concept is marked as seen. Without
        that ordering, an eligibility mention would consume the concept's one
        slot and hide a genuine mention later in the document.
        """
        eligibility = "Eligible applicants include rural communities. "
        body = "The funded research examines rural communities and their health."
        text = eligibility + body
        span = [(0, len(eligibility), self.POPULATION)]

        concept_ids = {ev.concept_id for ev in l1_tagger.tag_text(text, excluded_spans=span)}
        assert "pop_rural" in concept_ids

    def test_other_categories_are_unaffected(self, l1_tagger):
        text = "Eligible applicants must apply machine learning to climate action."
        span = [(0, len(text), self.POPULATION)]

        concept_ids = {ev.concept_id for ev in l1_tagger.tag_text(text, excluded_spans=span)}
        assert "meth_ml" in concept_ids
        assert "sdg_13" in concept_ids

    def test_no_spans_behaves_as_before(self, l1_tagger):
        text = "This program supports rural communities and climate action."
        assert (
            {ev.concept_id for ev in l1_tagger.tag_text(text)}
            == {ev.concept_id for ev in l1_tagger.tag_text(text, excluded_spans=None)}
        )


class TestL1TaggerToTagRecord:
    """Test conversion to the FOA JSON schema tag format."""

    def test_to_tag_record_format(self, l1_tagger):
        """to_tag_record should produce a dict matching the schema spec."""
        result = l1_tagger.tag_text("Research on climate action.")
        if result:
            tag_record = result[0].to_tag_record()
            assert "tag_id" in tag_record
            assert "label" in tag_record
            assert "category" in tag_record
            assert "source_layer" in tag_record
            assert "confidence" in tag_record
            assert "context_snippet" in tag_record
            assert "ontology_concept_id" in tag_record
            # tag_id format: "layer_1_terminological:<concept_id>"
            assert tag_record["tag_id"].startswith("layer_1_terminological:")
