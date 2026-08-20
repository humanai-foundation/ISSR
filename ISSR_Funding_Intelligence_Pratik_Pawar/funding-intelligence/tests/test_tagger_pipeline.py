"""Tests for the tagging pipeline orchestrator.

Uses a mock L2 tagger to avoid downloading the full sentence-transformers model
in unit tests. The L1 tagger uses the real spaCy model for accuracy.
"""

from unittest.mock import MagicMock

import pytest

from foa_pipeline.config import Config
from foa_pipeline.ontology.store import OntologyStore
from foa_pipeline.ontology.synonyms import expand_synonyms_for_store
from foa_pipeline.tagging.evidence import TagEvidence
from foa_pipeline.tagging.pipeline import TaggerPipeline


@pytest.fixture(scope="module")
def ontology_store(tmp_path_factory):
    """Build a test ontology with concepts and synonyms."""
    tmp = tmp_path_factory.mktemp("pipeline_ontology")
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
        # Hierarchical: sdg_13_1 is a child of sdg_13
        "sdg_13_1,Climate Adaptation,research_domain,sdg_13,Adapting to climate change impacts\n"
    )
    store = OntologyStore(tmp / "test.db")
    store.load_from_csv(csv_path, "test")
    expand_synonyms_for_store(store)
    return store


@pytest.fixture(scope="module")
def pipeline_config(tmp_path_factory):
    """Minimal config for pipeline tests."""
    tmp = tmp_path_factory.mktemp("config")
    return Config(
        grants_gov_base_url="https://api.grants.gov/v1/api",
        grants_gov_search_endpoint="search2",
        grants_gov_fetch_endpoint="fetchOpportunity",
        grants_gov_page_size=25,
        grants_gov_max_pages=1,
        grants_gov_query="{}",
        nsf_rss_url="https://example.com/rss",
        nsf_scraper_rate_limit=10.0,
        nsf_scraper_max_concurrent=1,
        sqlite_db_path=tmp / "queue.db",
        app_db_path=tmp / "app.db",
        raw_output_dir=tmp / "raw",
        normalised_output_dir=tmp / "normalised",
        embeddings_cache_dir=tmp / "embeddings",
        ontology_dir=tmp / "ontology",
        evaluation_dir=tmp / "evaluation",
        spacy_model="en_core_web_lg",
        embedding_model="sentence-transformers/all-mpnet-base-v2",
        cosine_thresholds={"default": 0.75},
        enable_layer3_llm=False,
        ollama_base_url="http://localhost:11434",
        ollama_model="mistral:7b-instruct",
        api_host="127.0.0.1",
        api_port=8000,
        api_reload=False,
        log_level="DEBUG",
        user_agent="test-agent",
        schema_version="1.0",
    )


@pytest.fixture(scope="module")
def pipeline(pipeline_config, ontology_store):
    """Build a TaggerPipeline with L2 mocked out.

    We mock L2 so unit tests don't download the 420MB model.
    L1 uses the real spaCy model for accuracy.
    """
    p = TaggerPipeline(pipeline_config, ontology_store)

    # Mock L2 to return a fixed set of evidence
    mock_l2 = MagicMock()
    mock_l2.tag_text.return_value = [
        TagEvidence(
            concept_id="sdg_01",
            label="No Poverty",
            category="research_domain",
            source_layer="layer_2_embedding",
            confidence=0.82,
            context_snippet="economic disadvantage in rural areas",
            ontology_concept_id="sdg_01",
        ),
    ]
    mock_l2.build_embeddings = MagicMock()
    p.l2 = mock_l2

    # Initialize L1 (real)
    p.l1.build_matcher(ontology_store)
    p.is_initialized = True
    return p


class TestTaggerPipelineIntegration:
    """Integration tests for the full tagging pipeline."""

    def test_tags_sample_foa(self, pipeline, sample_foa):
        """Pipeline should produce tags for a well-described FOA."""
        tags = pipeline.tag_record(sample_foa)
        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_returns_dicts(self, pipeline, sample_foa):
        """Pipeline output should be list of dicts (not TagEvidence)."""
        tags = pipeline.tag_record(sample_foa)
        for tag in tags:
            assert isinstance(tag, dict)

    def test_tag_schema_format(self, pipeline, sample_foa):
        """Each tag dict should have required keys matching the JSON schema."""
        tags = pipeline.tag_record(sample_foa)
        required_keys = {
            "tag_id", "label", "category", "source_layer",
            "confidence", "context_snippet", "ontology_concept_id"
        }
        for tag in tags:
            for key in required_keys:
                assert key in tag, f"Missing key: {key}"

    def test_l1_tags_have_full_confidence(self, pipeline, sample_foa):
        """L1 terminological tags should have confidence 1.0."""
        tags = pipeline.tag_record(sample_foa)
        l1_tags = [t for t in tags if t["source_layer"] == "layer_1_terminological"]
        for tag in l1_tags:
            assert tag["confidence"] == 1.0

    def test_l2_tags_have_cosine_confidence(self, pipeline, sample_foa):
        """L2 embedding tags should have confidence < 1.0."""
        tags = pipeline.tag_record(sample_foa)
        l2_tags = [t for t in tags if t["source_layer"] == "layer_2_embedding"]
        for tag in l2_tags:
            assert 0 < tag["confidence"] < 1.0

    def test_category_values_valid(self, pipeline, sample_foa):
        """All tags should have valid category values."""
        valid_categories = {"research_domain", "method", "population", "sponsor_theme"}
        tags = pipeline.tag_record(sample_foa)
        for tag in tags:
            assert tag["category"] in valid_categories

    def test_empty_foa_produces_no_tags(self, pipeline):
        """FOA with no text fields should produce no tags."""
        empty_foa = {
            "foa_id": "empty-test",
            "title": "",
            "program_description": "",
            "eligibility_description": "",
        }
        tags = pipeline.tag_record(empty_foa)
        assert tags == []


class TestTaggerPipelineHierarchy:
    """Test hierarchical propagation in the pipeline."""

    def test_child_tag_propagates_to_parent(self, pipeline):
        """If a child SDG target is tagged, the parent goal should also be tagged."""
        foa_with_child = {
            "foa_id": "hierarchy-test",
            "title": "Climate Adaptation Research",
            "program_description": (
                "This research focuses on climate adaptation strategies "
                "in coastal communities threatened by rising sea levels."
            ),
            "eligibility_description": "",
        }
        tags = pipeline.tag_record(foa_with_child)
        concept_ids = {t["ontology_concept_id"] for t in tags}

        # If sdg_13_1 (Climate Adaptation) is tagged, sdg_13 (Climate Action) should propagate
        if "sdg_13_1" in concept_ids:
            assert "sdg_13" in concept_ids, "Parent SDG not propagated from child"


class TestLLMBackstopTrigger:
    """The LLM classification backstop must fire only when every cheaper
    layer (L1, L2, L3, CFDA) found literally nothing -- never as a way to
    add more tags to an FOA that already has some."""

    def _empty_pipeline(self, pipeline_config, ontology_store, enable_llm_backstop):
        p = TaggerPipeline(pipeline_config, ontology_store, enable_llm_backstop=enable_llm_backstop)
        p.l1 = MagicMock()
        p.l1.tag_text.return_value = []
        p.l2 = MagicMock()
        p.l2.tag_text.return_value = []
        p.llm_classifier = MagicMock()
        p.llm_classifier.classify.return_value = [
            TagEvidence(
                concept_id="sdg_01",
                label="No Poverty",
                category="research_domain",
                source_layer="layer_5_llm_classify",
                confidence=0.75,
                context_snippet="stand-in evidence from the mocked backstop",
                ontology_concept_id="sdg_01",
            ),
        ]
        p.is_initialized = True
        p.llm_backstop_active = enable_llm_backstop
        return p

    def _foa(self):
        return {
            "foa_id": "backstop-test",
            "title": "Some Program",
            "program_description": "Substantive but otherwise unmatched program text.",
            "eligibility_description": "",
        }

    def test_fires_when_nothing_else_found_and_flag_enabled(self, pipeline_config, ontology_store):
        p = self._empty_pipeline(pipeline_config, ontology_store, enable_llm_backstop=True)
        tags = p.tag_record(self._foa())
        assert any(t["source_layer"] == "layer_5_llm_classify" for t in tags)
        p.llm_classifier.classify.assert_called_once()

    def test_does_not_fire_when_flag_disabled(self, pipeline_config, ontology_store):
        p = self._empty_pipeline(pipeline_config, ontology_store, enable_llm_backstop=False)
        tags = p.tag_record(self._foa())
        assert tags == []
        p.llm_classifier.classify.assert_not_called()

    def test_does_not_fire_when_l1_already_found_something(self, pipeline_config, ontology_store):
        p = self._empty_pipeline(pipeline_config, ontology_store, enable_llm_backstop=True)
        p.l1.tag_text.return_value = [
            TagEvidence(
                concept_id="sdg_13",
                label="Climate Action",
                category="research_domain",
                source_layer="layer_1_terminological",
                confidence=1.0,
                context_snippet="climate action",
                ontology_concept_id="sdg_13",
            ),
        ]
        tags = p.tag_record(self._foa())
        assert any(t["ontology_concept_id"] == "sdg_13" for t in tags)
        assert not any(t["source_layer"] == "layer_5_llm_classify" for t in tags)
        p.llm_classifier.classify.assert_not_called()

    def test_does_not_fire_on_empty_text_regardless_of_flag(self, pipeline_config, ontology_store):
        p = self._empty_pipeline(pipeline_config, ontology_store, enable_llm_backstop=True)
        empty_foa = {"foa_id": "empty", "title": "", "program_description": ""}
        tags = p.tag_record(empty_foa)
        assert tags == []
        p.llm_classifier.classify.assert_not_called()


class TestTaggerPipelineMerging:
    """Test L1/L2 merge logic."""

    def test_l1_takes_priority(self, pipeline):
        """If L1 and L2 both find the same concept, L1 should take priority."""
        # Create a FOA that will match both L1 and the mocked L2
        foa = {
            "foa_id": "merge-test",
            "title": "No Poverty Research Program",
            "program_description": (
                "This program addresses no poverty through "
                "community development and economic growth."
            ),
            "eligibility_description": "",
        }
        tags = pipeline.tag_record(foa)
        # Check that sdg_01 (No Poverty) appears — it could come from L1 (exact) or L2 (mock)
        poverty_tags = [t for t in tags if t["ontology_concept_id"] == "sdg_01"]
        if poverty_tags:
            # L1 should take priority with confidence 1.0
            assert poverty_tags[0]["source_layer"] == "layer_1_terminological"
            assert poverty_tags[0]["confidence"] == 1.0


class TestL1L2Corroboration:
    """An L1 exact-match answers "does this string appear", not "is this
    concept what the FOA is about" -- e.g. nsf_bio firing on a circuits FOA
    because "biology" appears once as an application area (see Documentation/EVALUATION.md,
    the CSCS false positive). For categories in l1_corroboration_categories,
    an L1 hit must also be found by L2 independently, or it's suppressed."""

    def _l1_evidence(self, concept_id, category, label="Some Concept"):
        return TagEvidence(
            concept_id=concept_id,
            label=label,
            category=category,
            source_layer="layer_1_terminological",
            confidence=1.0,
            context_snippet="stand-in L1 evidence",
            ontology_concept_id=concept_id,
        )

    def _l2_evidence(self, concept_id, category, confidence=0.5, label="Some Concept"):
        return TagEvidence(
            concept_id=concept_id,
            label=label,
            category=category,
            source_layer="layer_2_embedding",
            confidence=confidence,
            context_snippet="stand-in L2 evidence",
            ontology_concept_id=concept_id,
        )

    def _pipeline(self, pipeline_config, ontology_store, l1_evidence, l2_evidence,
                  corroboration_categories=("sponsor_theme",)):
        from dataclasses import replace

        config = replace(pipeline_config, l1_corroboration_categories=list(corroboration_categories))
        p = TaggerPipeline(config, ontology_store)
        p.l1 = MagicMock()
        p.l1.tag_text.return_value = l1_evidence
        p.l2 = MagicMock()
        p.l2.tag_text.return_value = l2_evidence
        p.is_initialized = True
        return p

    def _foa(self):
        return {
            "foa_id": "corroboration-test",
            "title": "Some Program",
            "program_description": "Substantive program text.",
            "eligibility_description": "",
        }

    def test_uncorroborated_l1_hit_suppressed_in_gated_category(self, pipeline_config, ontology_store):
        # L1 finds great_02 (sponsor_theme, gated); L2 finds nothing for it.
        p = self._pipeline(
            pipeline_config, ontology_store,
            l1_evidence=[self._l1_evidence("great_02", "sponsor_theme")],
            l2_evidence=[self._l2_evidence("sdg_01", "research_domain")],  # unrelated concept
        )
        tags = p.tag_record(self._foa())
        assert not any(t["ontology_concept_id"] == "great_02" for t in tags)

    def test_corroborated_l1_hit_survives_in_gated_category(self, pipeline_config, ontology_store):
        # L1 and L2 both independently find great_02 -- should survive, at L1's confidence.
        p = self._pipeline(
            pipeline_config, ontology_store,
            l1_evidence=[self._l1_evidence("great_02", "sponsor_theme")],
            l2_evidence=[self._l2_evidence("great_02", "sponsor_theme", confidence=0.4)],
        )
        tags = p.tag_record(self._foa())
        matches = [t for t in tags if t["ontology_concept_id"] == "great_02"]
        assert len(matches) == 1
        assert matches[0]["source_layer"] == "layer_1_terminological"
        assert matches[0]["confidence"] == 1.0

    def test_uncorroborated_l1_hit_survives_in_ungated_category(self, pipeline_config, ontology_store):
        # research_domain is not in the gated set here -- old behaviour (L1
        # always wins) must be unchanged for every category not opted in.
        p = self._pipeline(
            pipeline_config, ontology_store,
            l1_evidence=[self._l1_evidence("sdg_13", "research_domain")],
            l2_evidence=[],
            corroboration_categories=("sponsor_theme",),
        )
        tags = p.tag_record(self._foa())
        assert any(t["ontology_concept_id"] == "sdg_13" for t in tags)

    def test_empty_corroboration_list_disables_the_gate_entirely(self, pipeline_config, ontology_store):
        p = self._pipeline(
            pipeline_config, ontology_store,
            l1_evidence=[self._l1_evidence("great_02", "sponsor_theme")],
            l2_evidence=[],
            corroboration_categories=(),
        )
        tags = p.tag_record(self._foa())
        assert any(t["ontology_concept_id"] == "great_02" for t in tags)
