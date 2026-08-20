# Ontology Design Document

> This document describes the controlled ontology used by the FOA semantic tagging pipeline. It covers the design rationale, category definitions, concept schema, synonym governance, tagging logic, and versioning strategy.

---

## 1. Design Rationale

### Problem Statement

Research development officers at institutions like the University of Alabama's ISSR must manually scan hundreds of Funding Opportunity Announcements (FOAs) from Grants.gov and NSF to find relevant opportunities for faculty researchers. This process is fragmented because:

- FOAs use inconsistent terminology across agencies
- There is no universal classification system for federal research funding
- The same research area may be described differently in different solicitations

### Why a Controlled Ontology?

A controlled ontology provides a **stable, reproducible vocabulary** that maps the unstructured natural language of FOA descriptions into a structured classification framework. This enables:

1. **Consistent tagging** — The same FOA will always receive the same tags regardless of when or how many times the pipeline runs
2. **Downstream grant matching** — Faculty research profiles can be expressed in the same vocabulary as FOA tags, enabling automated matching
3. **Interpretability** — Every tag carries provenance metadata (source layer, confidence score, triggering text) so a human reviewer can audit the classification

### Scope and Boundaries

This ontology is intentionally **lightweight and focused on US federal research funding**. It is not intended to be a comprehensive knowledge graph of all science. The design prioritises:

- **Breadth over depth** — Covering the major dimensions a research officer cares about (domain, method, population, sponsor theme) rather than deeply modeling any single dimension
- **Actionability** — Every concept should help a user decide whether an FOA is relevant to a specific researcher
- **Extensibility** — New concepts can be added via CSV files without code changes

---

## 2. Category Definitions

The ontology organises concepts into four categories. Each category captures a distinct dimension of a funding opportunity:

### 2.1 Research Domains (`research_domain`)

**Definition:** The primary scientific or scholarly subject areas addressed by the funding opportunity.

**Source:** UN Sustainable Development Goals (SDG) framework, adapted for research classification.

**Design Decision:** The UN SDGs were selected because they provide a cross-disciplinary framework that spans natural sciences, social sciences, engineering, and humanities — matching the breadth of ISSR's research portfolio. The SDGs are internationally recognised, publicly documented, and map well to the broad thematic areas of US federal funding.

**Known Limitation:** SDGs are policy-oriented categories (e.g., "No Poverty", "Climate Action"), not scientific disciplines. They are intentionally broad to capture thematic alignment rather than narrow disciplinary matching. For downstream grant matching, these should be supplemented with faculty expertise keywords.

**Status: superseded for domain classification.** This limitation was empirically confirmed, not just theorized: gold-standard evaluation shows `research_domain` (SDGs) at F1=0.222, while the `research_discipline` category (§2.1a, added later using NSF Directorates) reaches F1=0.554 on the same evaluation set — better than double. `research_domain` is retained as a secondary/legacy taxonomy for policy-level thematic framing (useful for "which SDG does this align with" reporting), but `research_discipline` should be treated as the primary signal for actual subject-matter/domain classification.

**Concepts:** 17 top-level goals (sdg_01 through sdg_17), each with a natural-language description used for embedding-based matching.

**Inclusion Criteria:** A concept belongs in this category if it describes *what the research is about* (the subject matter), not *how it is done* (that belongs in Methods) or *who it serves* (that belongs in Populations).

### 2.1a Research Disciplines (`research_discipline`)

**Definition:** The academic/scientific discipline or directorate under which the funding opportunity is organised.

**Source:** NSF Directorates and Divisions (e.g., Engineering, Geosciences, Biological Sciences, Computer and Information Science and Engineering).

**Design Decision:** Added after the initial four-category design (§2.1–2.4) to address the UN SDGs' known coarseness for domain classification (see §2.1 above). NSF's own directorate structure is the vocabulary NSF solicitations are actually organised around, so it maps far more directly onto how program officers and researchers describe a funding opportunity's discipline than a policy framework like the SDGs does.

**Concepts:** 8 directorate-level concepts.

**Inclusion Criteria:** Same subject-matter criterion as Research Domains (§2.1) — this category is a finer-grained, NSF-specific alternative for the same "what is this research about" question, not a distinct dimension.

### 2.2 Methods and Approaches (`method`)

**Definition:** Research methodologies, analytical techniques, or computational approaches mentioned in the FOA as either required or encouraged.

**Source:** Custom vocabulary derived from common terminology in NSF and NIH solicitations.

**Design Decision:** No standard taxonomy of research methods exists that spans all disciplines. We constructed a custom vocabulary by reviewing 50+ FOAs and extracting recurring methodological terms. This was then validated against existing method ontologies (SAGE Research Methods, JARS standards) for completeness.

**Concepts:** 25 method concepts (method_01 through method_25), including computational methods (ML, NLP, computer vision), empirical methods (RCT, longitudinal study, survey research), and participatory methods (CBPR, citizen science).

**Inclusion Criteria:** A concept belongs here if it describes *how the research is conducted* — the tools, study designs, or analytical approaches. Generic terms like "research" or "analysis" are excluded because they match nearly all FOAs and provide no discriminative value.

### 2.3 Target Populations (`population`)

**Definition:** The demographic groups, communities, or populations that the funding opportunity specifically targets or intends to benefit.

**Source:** Custom vocabulary derived from federal grant eligibility language and NIH population-focused solicitations.

**Design Decision:** Population-focused funding is a core use case for ISSR, which serves social science and public health researchers. This category enables filtering FOAs by the communities they serve, which is a primary search criterion for many faculty.

**Concepts:** 20 population concepts (pop_01 through pop_20), covering age groups (children, older adults), socioeconomic groups (low-income, homeless), identity groups (racial minorities, LGBTQ+), and occupational groups (healthcare workers, first responders).

**Inclusion Criteria:** A concept belongs here if it describes *who the research is about or who it serves*. Generic terms like "people" or "participants" are excluded. The concept must refer to a specific, identifiable demographic or community group.

### 2.4 Sponsor Themes (`sponsor_theme`)

**Definition:** High-level federal mission priorities that describe the policy context under which the funding is allocated.

**Source:** GREAT Act (Grants Reporting Efficiency and Agreements Transparency Act) Mission Categories — the official US federal taxonomy for classifying research and development spending.

**Design Decision:** The GREAT Act categories are the authoritative classification used by OMB and federal agencies to report R&D expenditures to Congress. Using them ensures our sponsor theme tags align with the vocabulary that agencies themselves use internally, and provides a stable, government-maintained reference point.

**Concepts:** 14 mission categories (great_01 through great_14), including National Defense, Health, Energy, General Science, Education and Training, etc.

**Inclusion Criteria:** A concept belongs here if it describes *why the government is funding this research* — the federal mission or policy objective. This is distinct from the research domain (what the science is about) and captures the sponsor's strategic intent.

---

## 3. Concept Schema

Every concept in the ontology follows a consistent schema stored in CSV files under `data/ontology/`:

| Field | Type | Description |
|---|---|---|
| `concept_id` | `string` | Unique identifier (e.g., `sdg_01`, `method_05`, `great_03`) |
| `label` | `string` | Human-readable concept name (e.g., "Machine Learning") |
| `category` | `enum` | One of: `research_domain`, `method`, `population`, `sponsor_theme` |
| `parent_id` | `string?` | ID of parent concept for hierarchical propagation (nullable) |
| `description` | `string` | Natural-language definition used as the target for L2 embedding similarity |

### Concept ID Convention

- `sdg_XX` — UN Sustainable Development Goals (research domains)
- `great_XX` — GREAT Act Mission Categories (sponsor themes)
- `method_XX` — Research methods and approaches
- `pop_XX` — Target populations

### Hierarchical Relationships

Concepts can form parent-child hierarchies via the `parent_id` field. When a child concept is matched, the pipeline automatically propagates the tag to its parent. This ensures hierarchical completeness (e.g., matching SDG Target 1.1 automatically tags SDG Goal 1: No Poverty).

Currently, the ontology is flat (no child concepts are defined). The hierarchy mechanism is implemented and tested, ready for future use when sub-domain taxonomies are added.

---

## 4. Synonym Governance

Each concept is expanded with synonyms to improve recall in Layer 1 (terminological matching). Synonyms are generated from three sources:

### 4.1 Sources

1. **WordNet (NLTK)** — Automated synset expansion from the Princeton WordNet lexical database
2. **Manual Abbreviations** — A curated dictionary in `synonym_expander.py` mapping concepts to common abbreviations (e.g., "machine learning" → "ML", "randomized controlled trial" → "RCT")
3. **Domain-Specific Expansions** — Manually added terms that WordNet misses (e.g., "climate action" → "climate change", "global warming", "climate adaptation")

### 4.2 Noise Control

Uncontrolled synonym expansion is the primary source of false positives in terminological matching. The following governance rules are enforced:

1. **Blacklist** — The `NOISY_SYNONYMS` set in `synonym_expander.py` blocks 42+ overly generic WordNet terms (e.g., "transport", "energy", "security", "field", "study") that match nearly all FOAs
2. **Minimum Length Filter** — Synonyms shorter than 4 characters are excluded to prevent matching on noise tokens
3. **Context-Aware Rejection** — Layer 1 uses spaCy dependency parsing to reject matches where the synonym appears as a compound modifier rather than a standalone concept (e.g., rejecting "food security" when matching "National Defense" via the synonym "security")

### 4.3 Adding New Synonyms

To add synonyms for a concept:
1. Add entries to the `ABBREVIATIONS` dictionary in `synonym_expander.py`
2. Run `python -m foa_pipeline.cli setup-ontology` to rebuild the synonym table
3. Run `python -m foa_pipeline.cli precompute-embeddings` to update embeddings
4. Run the evaluation to verify the change did not degrade precision

---

## 5. Tagging Logic: Text → Structured Category

The mapping from raw FOA text to structured ontology tags uses a three-layer cascade:

### Layer 1: Terminological Matching (spaCy PhraseMatcher)

- **Input:** Full FOA text (title + program_description + eligibility_description + additional_info)
- **Process:** spaCy PhraseMatcher scans for exact occurrences of concept labels and their synonyms, using lemmatised token matching (case-insensitive)
- **Output:** `TagEvidence` with `confidence=1.0` and the matched text span as `context_snippet`
- **Role:** High-precision anchor. Every L1 match is treated as a confirmed tag

### Layer 2: Semantic Embedding (all-mpnet-base-v2)

- **Input:** Same full text, chunked into 384-token segments
- **Process:** Each chunk is embedded using `sentence-transformers/all-mpnet-base-v2` and compared via cosine similarity against pre-computed ontology concept description embeddings
- **Output:** `TagEvidence` with `confidence=cosine_similarity` and the highest-scoring chunk as `context_snippet`
- **Role:** Recall booster. Captures implicit semantic relationships that exact matching misses (e.g., an FOA about "coral reef monitoring" matching "Life Below Water" even though neither exact term appears)
- **Thresholds:** Category-specific cosine similarity minimums (configurable in `config.py`)

### Layer 3: LLM Disambiguation (Mistral-7B via Ollama) — Stretch Goal

- **Trigger:** Only activates when L2's top-2 candidates in the same category are within 0.05 cosine similarity of each other (genuine ambiguity)
- **Process:** Sends the FOA text and both candidate concepts to a local LLM with a structured prompt requesting a binary choice
- **Role:** Precision filter for ambiguous cases. Expected to handle <5% of all tags

### Merge Rules

1. L1 tags always take priority (confidence 1.0)
2. L2 contributes new concepts not already found by L1 — even in categories where L1 already tagged something
3. Top-N cap per category prevents any single category from dominating the tag set
4. CFDA crosswalk provides a recall backstop for sponsor themes when no other match is found

### Evidence Provenance

Every tag carries an `TagEvidence` record containing:

| Field | Description |
|---|---|
| `source_layer` | `layer_1_terminological`, `layer_2_embedding`, or `layer_3_llm` |
| `confidence` | 1.0 for L1 exact matches, cosine similarity for L2, LLM confidence for L3 |
| `context_snippet` | The specific text (up to 500 chars) that triggered the match |

This provenance chain makes every tag fully auditable.

---

## 6. Versioning and Extension

### Adding a New Concept

1. Add a row to the appropriate CSV file in `data/ontology/`
2. Run `python -m foa_pipeline.cli setup-ontology` to load it into SQLite
3. Optionally add manual synonyms in `synonym_expander.py`
4. Run `python -m foa_pipeline.cli precompute-embeddings` to generate the L2 embedding
5. Run `python -m foa_pipeline.cli tag-all` to re-tag all FOAs

### Adding a New Category

1. Create a new CSV file in `data/ontology/` following the schema
2. Register it in `ontology_store.py` → `load_all_ontologies()` → `file_source_map`
3. Add a threshold entry in `config.py` → `cosine_thresholds`
4. Update the evaluation gold standard with expected tags for the new category

### Schema Version

The ontology is versioned alongside the data schema (`schema_version: "1.0"` in `config.py`). Breaking changes to concept IDs or category names require a schema version bump.

### Current Concept Counts

| Category | Source File | Count |
|---|---|---|
| Research Domains | `un_sdg_goals.csv` | 17 |
| Sponsor Themes | `great_act_categories.csv` | 14 |
| Methods | `research_methods.csv` | 25 |
| Populations | `populations.csv` | 20 |
| Research Disciplines | `nsf_directorates.csv` | 8 |
| **Total** | | **84** |

---

## 7. Known Limitations and Future Work

1. **Research domain granularity — addressed.** UN SDGs are policy-oriented, not discipline-specific. This is no longer purely theoretical: the `research_discipline` category (§2.1a, NSF Directorates) was added and empirically outperforms `research_domain`/SDGs by more than 2x F1 (0.554 vs 0.222) on the gold evaluation set. `research_domain` remains for policy-level thematic framing but should not be relied on for primary domain classification. OECD Fields of Science remains a possible future addition for non-NSF sources.
2. **No inter-annotator agreement** — The gold standard was labeled by a single annotator. An LLM-generated silver-standard set (`eval_set_50.json`) exists for threshold-tuning validation, but it cannot substitute for a second human annotator (see `EVALUATION.md` §2a) — it would be circular, since it uses the same model family as Layer 3 disambiguation. Genuine inter-annotator agreement remains unmeasured; future work should add a real second human annotation pass using [ANNOTATION_CODEBOOK.md](ANNOTATION_CODEBOOK.md).
3. **Flat hierarchy** — The current ontology is effectively flat (no parent-child relationships defined). The hierarchy propagation mechanism is implemented but unused. Future work should define sub-domain and sub-method hierarchies
4. **Method detection is context-dependent** — Merely mentioning "machine learning" in an FOA does not mean the FOA *requires* ML. Future work should distinguish between "mentioned" and "required" methods. Partial mitigation applied: false-positive-prone concepts (e.g. Citizen Science) now support per-concept cosine thresholds (`config.py`'s `cosine_thresholds`, checked before the category default) instead of only per-category ones, and false-negative-prone concept descriptions were enriched with paraphrases observed in real false negatives — but distinguishing "mentioned in passing" from "required" still needs deeper work (e.g. a requirement-cue heuristic keyed on nearby verbs like "require"/"must").

---

*Document Version: 1.0 | Last Updated: July 5, 2026 | Author: Pratik Pawar*
