"""Tests for the ontology store module."""


from foa_pipeline.ontology.store import OntologyStore


def test_load_and_query(tmp_path, test_config):
    """Test loading ontology CSVs and querying concepts."""
    store = OntologyStore(tmp_path / "test_ontology.db")

    # Load real ontology files
    stats = store.load_all_ontologies(test_config.ontology_dir)

    assert stats.get("great_act_categories.csv", 0) > 0
    assert stats.get("un_sdg_goals.csv", 0) > 0
    assert stats.get("research_methods.csv", 0) > 0
    assert stats.get("populations.csv", 0) > 0

    # Query concepts
    all_concepts = store.get_all_concepts()
    assert len(all_concepts) > 0

    # Query by category
    domains = store.get_concepts_by_category("research_domain")
    assert len(domains) == 17  # 17 SDGs

    methods = store.get_concepts_by_category("method")
    assert len(methods) > 0

    themes = store.get_concepts_by_category("sponsor_theme")
    assert len(themes) == 14  # 14 GREAT Act categories

    populations = store.get_concepts_by_category("population")
    assert len(populations) > 0

    # Query by ID
    sdg1 = store.get_concept_by_id("sdg_01")
    assert sdg1 is not None
    assert sdg1.label == "No Poverty"
    assert sdg1.category == "research_domain"

    # Nonexistent concept
    assert store.get_concept_by_id("nonexistent") is None

    store.close()


def test_synonyms(tmp_path):
    """Test synonym management."""
    store = OntologyStore(tmp_path / "test_syn.db")

    # Add a concept
    store.conn.execute(
        "INSERT INTO ontology_concepts VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("test_01", "Machine Learning", "method", None, "custom", "ML research", None),
    )
    store.conn.commit()

    # Add synonyms
    count = store.add_synonyms("test_01", ["ml", "deep learning", "ai"])
    assert count == 3

    # Retrieve with synonyms
    concept = store.get_concept_by_id("test_01")
    assert concept is not None
    assert "ml" in concept.synonyms
    assert "deep learning" in concept.synonyms

    store.close()


def test_concept_count(tmp_path, test_config):
    """Test concept and synonym counting."""
    store = OntologyStore(tmp_path / "test_count.db")
    store.load_all_ontologies(test_config.ontology_dir)

    assert store.concept_count() > 50  # At least SDGs + GREAT Act + methods + populations
    assert store.synonym_count() == 0  # No synonyms loaded yet (just CSVs)

    store.close()
