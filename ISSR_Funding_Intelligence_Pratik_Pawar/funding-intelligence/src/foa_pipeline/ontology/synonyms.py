"""
WordNet-based synonym expansion for ontology concepts.

For each ontology concept label, generates synonyms using:
1. WordNet synsets (via NLTK)
2. Lemmatization variants
3. Common abbreviations (manual dictionary)
"""

import logging
from typing import Dict, List, Set

from .store import OntologyStore

logger = logging.getLogger(__name__)

# Common research domain abbreviations
ABBREVIATIONS: Dict[str, List[str]] = {
    "artificial intelligence": ["ai"],
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "sustainable development goals": ["sdg", "sdgs"],
    "community-based participatory research": ["cbpr"],
    "randomized controlled trial": ["rct"],
    "geographic information system": ["gis"],
    "geospatial analysis": ["gis", "spatial analysis"],
    "social determinants of health": ["sdoh"],
    "science technology engineering mathematics": ["stem"],
    "climate action": ["climate change", "global warming", "climate adaptation"],
    "clean water and sanitation": ["water quality", "water access", "sanitation"],
    "no poverty": ["poverty reduction", "anti-poverty", "economic disadvantage"],
    "zero hunger": ["food security", "food insecurity", "nutrition"],
    "good health and well-being": ["public health", "healthcare", "health outcomes"],
    "quality education": ["educational outcomes", "literacy"],
    "gender equality": ["gender equity", "women empowerment", "gender parity"],
    "affordable and clean energy": ["renewable energy", "solar", "wind energy"],
    "decent work and economic growth": ["employment", "labor market"],
    "reduced inequalities": ["inequality", "disparity"],
    "sustainable cities and communities": ["urban sustainability", "smart cities"],
    "responsible consumption and production": ["circular economy", "waste reduction"],
    "life below water": ["marine", "ocean", "fisheries", "coral reef"],
    "life on land": ["biodiversity", "deforestation", "terrestrial"],
    "peace justice and strong institutions": ["governance", "rule of law", "democracy"],
    "national defense": ["defense", "military", "security", "homeland security"],
    "veterans benefits": ["veteran", "military service", "va"],
    "administration of justice": ["criminal justice", "law enforcement", "corrections"],
    "community and regional development": ["community development", "urban planning", "housing"],
    "income security": ["social welfare", "poverty", "economic security"],
    "survey research": ["survey", "questionnaire", "poll"],
    "mixed methods research": ["mixed methods", "multimethod"],
    "longitudinal study": ["longitudinal", "panel study", "cohort study"],
    "statistical modeling": ["regression", "econometrics"],
    "data science": ["data analytics", "big data", "data mining"],
    "clinical trial": ["clinical study", "medical trial", "phase trial"],
    "policy analysis": ["policy evaluation", "policy research", "public policy"],
    "network analysis": ["social network", "graph analysis"],
    "remote sensing": ["satellite imagery", "aerial survey"],
    "bioinformatics": ["computational biology", "genomics"],
    "rural communities": ["rural", "non-metropolitan", "countryside"],
    "urban communities": ["urban", "metropolitan", "city"],
    "low-income populations": ["low income", "poverty", "economically disadvantaged"],
    "children and youth": ["children", "adolescents", "minors", "youth"],
    "older adults": ["elderly", "aging", "senior citizens", "geriatric"],
    "indigenous peoples": ["native american", "alaska native", "tribal", "first nations"],
    "racial and ethnic minorities": ["minority", "underrepresented", "bipoc"],
    "people with disabilities": ["disability", "disabled", "handicapped", "accessibility"],
    "immigrants and refugees": ["immigrant", "refugee", "asylum", "migrant"],
    "lgbtq+ populations": ["lgbtq", "lgbt", "sexual minority", "gender minority"],
    "incarcerated populations": ["incarcerated", "prisoner", "correctional", "reentry"],
    "homeless populations": ["homeless", "houseless", "unhoused", "housing insecure"],
}


# Noisy/ambiguous terms confirmed as false-positive triggers. These are mostly
# WordNet lemmas that match incidental text in FOAs. Module level so it is built
# once rather than rebuilt for every concept during expansion.
NOISY_SYNONYMS = {
    # Generic words that appear everywhere in grant text
    "travel", "transfer", "ecosystem", "environment", "system",
    "space", "model", "area", "field", "domain", "study",
    "action", "target", "work", "life", "community",
    # WordNet noise for Transportation (great_08)
    "transport", "conveyance", "deportation", "exile",
    "expatriation", "fare", "shipping", "transferral", "transit",
    # WordNet noise for Energy (great_04)
    "push", "vim", "vigor", "vigour", "vitality",
    "zip", "get-up-and-go", "free energy",
    # WordNet noise for Space (great_03)
    "blank", "blank space", "distance", "place", "quad",
    # WordNet noise for Students (pop_12)
    "bookman", "educatee", "scholarly person", "scholar", "pupil",
    # WordNet noise for Veterans (pop_06)
    "old hand", "old stager", "old-timer", "oldtimer",
    "stager", "warhorse",
    # WordNet noise for other concepts
    "descriptive anthropology",  # Ethnography synonym too broad
    "factory farm",  # Agriculture synonym
    "clinical test",  # Too broad for Clinical Trial
    # Confirmed false-positive triggers (removed from ABBREVIATIONS above;
    # blacklisted too so WordNet can't reintroduce them)
    "equity",  # Financial/ownership homonym of DEI "equity"
    "learning",  # Matches inside "machine learning"/"deep learning"
    "statistics",  # Matches org names like "...Center for ... Statistics"
    "job creation",
    # WordNet noise for Engineering (nsf_eng): synonyms of the *verb* "to
    # engineer" ("he engineered the merger"), not the discipline. All seven
    # below were exclusive to nsf_eng, so blacklisting costs no other concept.
    "mastermind", "orchestrate", "organise", "organize", "engine room",
    "direct",
    # "technology" was the single largest source of Layer 1 false positives on
    # the gold set: it fired on "the sociology of science and technology",
    # "human-language technology", and — worst — on "Directorate for
    # Technology, Innovation and Partnerships", whose correct label is nsf_tip.
    # NSF treats technology and engineering as different directorates; the
    # ontology should not equate them.
    "technology",
    # "accessibility" in research prose usually means data or software
    # accessibility ("improve efficiency and accessibility", FAIR principles),
    # not disability. Exclusive to People with Disabilities.
    "accessibility",
}


def expand_synonyms_for_store(store: OntologyStore) -> Dict[str, int]:
    """
    Generate and load synonyms for all ontology concepts.

    Uses WordNet + manual abbreviations. Returns: {concept_id: num_synonyms_added}
    """
    import nltk
    from nltk.corpus import wordnet
    from nltk.stem import WordNetLemmatizer

    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)

    lemmatizer = WordNetLemmatizer()
    stats: Dict[str, int] = {}

    concepts = store.get_all_concepts()
    for concept in concepts:
        synonyms: Set[str] = set()

        # WordNet synonyms from label
        synonyms.update(_get_wordnet_synonyms(concept.label, wordnet))

        # Lemmatized forms (only for single-word labels to prevent splitting)
        words = concept.label.lower().split()
        if len(words) == 1:
            word = words[0]
            lemma = lemmatizer.lemmatize(word)
            if lemma != word and len(lemma) > 2:
                synonyms.add(lemma)
            verb_lemma = lemmatizer.lemmatize(word, pos="v")
            if verb_lemma != word and len(verb_lemma) > 2:
                synonyms.add(verb_lemma)

        # Manual abbreviations. Exact match only - a substring check here
        # (e.g. "health" in "good health and well-being") previously let a
        # concept silently inherit synonyms authored for an unrelated
        # concept in a different category (great_02 "Health" inheriting
        # sdg_03's "healthcare" synonym), causing cross-category false
        # positives.
        label_lower = concept.label.lower()
        for full_form, abbrevs in ABBREVIATIONS.items():
            if full_form == label_lower:
                synonyms.update(a.lower() for a in abbrevs)

        # (Description-derived synonyms removed to prevent noise)

        # Remove the original label and empty/short strings
        synonyms.discard(concept.label.lower())
        synonyms.discard("")

        # ── Synonym Governance Filters ──
        # Filter 1: Noisy/ambiguous terms confirmed as false-positive triggers
        #           (NOISY_SYNONYMS, module level)
        # Filter 2: Minimum length — short synonyms cause too many false positives
        # Filter 3: Not in noisy set
        synonyms = {
            s for s in synonyms
            if len(s) >= 4
            and s.lower() not in NOISY_SYNONYMS
        }

        count = store.add_synonyms(concept.concept_id, list(synonyms))
        stats[concept.concept_id] = count

    total_synonyms = sum(stats.values())
    logger.info(
        "Generated %d synonyms for %d concepts", total_synonyms, len(concepts)
    )
    return stats


def _get_wordnet_synonyms(text: str, wordnet) -> Set[str]:
    """Get WordNet synonyms for the exact phrase only."""
    synonyms: Set[str] = set()
    query = text.lower().replace(" ", "_")
    for synset in wordnet.synsets(query):
        for lemma in synset.lemmas():
            name = lemma.name().replace("_", " ").lower()
            if name != text.lower() and len(name) > 2:
                synonyms.add(name)
    return synonyms
