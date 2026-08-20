"""
Layer 1: Terminological Tagging (Exact Match / Synonym Expansion)

Uses spaCy's PhraseMatcher to find exact matches of ontology concepts
and their generated synonyms within FOA text (title + description + eligibility).

Confidence is always 1.0 for matches at this layer.
"""

import logging
import re
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import spacy
from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans

from ..ontology.store import OntologyConcept, OntologyStore
from .evidence import TagEvidence

logger = logging.getLogger(__name__)

# ── Scope filters ──────────────────────────────────────────────────────────
#
# Layer 1 matched 51 concepts across the 20-FOA gold set and 30 of them were
# wrong — a 41% precision rate for what is deterministic exact string matching.
# In every case the match itself was *correct*: the word really was present.
# What was missing is any notion of aboutness, while the annotation codebook
# asks for a concept's "primary focus, not merely mentioned".
#
# Each filter below rejects a context in which a term demonstrably does not
# indicate subject matter. All five were validated against the gold set before
# being added: together they remove 9 false positives and no true positives.
# Enumerations were tested and deliberately rejected — "computing,
# communications, healthcare, energy and other critical technologies" yields a
# true positive (Energy) and a false positive (Good Health) from one list, so
# list membership carries no signal.

# "science, technology, engineering, and mathematics (STEM)" names a
# field-agnostic acronym, not the FOA's discipline. Only matches lying inside
# the idiom are rejected, and only for the words the idiom itself supplies —
# an earlier proximity-based version also discarded a legitimate "students"
# match sitting next to one.
_STEM_IDIOM = re.compile(
    r"science\s*,\s*technology\s*,\s*engineering\s*,?\s*(?:and\s+|&\s*)?mathematic\w*",
    re.I,
)
_STEM_IDIOM_WORDS = frozenset({"science", "sciences", "technology", "engineering", "mathematics"})

# Referral prose directs proposals at a *different* programme, so the unit it
# names is explicitly out of scope: "natural hazard characterization is
# supported through programs in the NSF Directorate for Geosciences".
_REFERRAL = re.compile(
    r"(should be (?:submitted|directed|sent)|may be (?:submitted|more appropriate)"
    r"|more appropriate (?:as|for)|(?:is|are) supported through|submit to the)",
    re.I,
)

# NSF's standing mission and broadening-participation sentences appear near
# verbatim in most solicitations and describe the agency, not the opportunity.
_MISSION = re.compile(
    r"(all fields of science and engineering|health and vitality of science and engineering"
    r"|underrepresented in STEM|broadening participation|scientific and engineering enterprise"
    r"|commitment to (?:ensuring|diversity))",
    re.I,
)

# Permissive modality marks an optional technique rather than the subject:
# "Proposals may use machine learning to advance the research."
_PERMISSIVE = re.compile(
    r"(may (?:use|include|involve|also|address|employ)|could (?:use|include|involve)"
    r"|are encouraged to use|optionally)",
    re.I,
)

# Statute and programme proper names — "Small Business Technology Transfer",
# "... Economic Security Act" — are titles, not topics.
_PROPER_NAME_TAIL = re.compile(r"\b(Act|Initiative|Transfer|Scholarship)\b")

# How far to look for each cue. Referral and permissive cues precede their
# target, so those look backwards only; span.sent was tried first and fired on
# unrelated clauses of the very long sentences these documents contain.
_LOOKBACK_REFERRAL = 90
_LOOKBACK_PERMISSIVE = 60
_WINDOW_MISSION = 110
_LOOKAHEAD_PROPER_NAME = 26


class L1Tagger:
    """Terminological tagger using spaCy PhraseMatcher."""

    NEGATION_TERMS = {"not", "no", "excluding", "without", "except", "outside", "non"}

    def __init__(self, spacy_model: str = "en_core_web_lg"):
        self.spacy_model = spacy_model
        self.nlp = None
        self.matcher = None
        self.concept_lookup: Dict[str, OntologyConcept] = {}

    def load_model(self) -> None:
        """Load the spaCy model if not already loaded."""
        if self.nlp is None:
            try:
                # Enable parser for dependency checking, disable ner to save time
                self.nlp = spacy.load(self.spacy_model, disable=["ner"])
            except OSError:
                logger.error(
                    "spaCy model '%s' not found. "
                    "Run: python -m spacy download %s",
                    self.spacy_model,
                    self.spacy_model,
                )
                raise

    def build_matcher(self, store: OntologyStore) -> None:
        """Build the PhraseMatcher from ontology concepts and synonyms."""
        self.load_model()
        assert self.nlp is not None

        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.concept_lookup = {}

        concepts = store.get_all_concepts()
        count = 0

        for concept in concepts:
            self.concept_lookup[concept.concept_id] = concept

            # Match label
            patterns = [self.nlp.make_doc(concept.label)]

            # Match synonyms
            for syn in concept.synonyms:
                if syn:
                    patterns.append(self.nlp.make_doc(syn))

            # Add patterns to matcher using concept_id as match ID
            self.matcher.add(concept.concept_id, patterns)
            count += len(patterns)

        logger.info(
            "Built L1 PhraseMatcher with %d patterns across %d concepts",
            count,
            len(concepts),
        )

    @staticmethod
    def out_of_scope_context(doc: Doc, span: Span) -> Optional[str]:
        """
        Return the name of the scope filter rejecting this match, or None.

        A match is rejected when its surrounding text shows the term is being
        used for something other than the opportunity's subject matter. The
        name is returned rather than a bool so the reason can be logged and
        tested individually.
        """
        text = doc.text
        start, end = span.start_char, span.end_char

        # Backward cues qualify the clause they introduce, so the window is
        # clipped at the start of the match's own sentence as well as at a
        # character budget. Without the sentence floor, "Proposals may use
        # machine learning ... Machine learning is the central concern" had the
        # first sentence's cue reject the second sentence's genuine match.
        sent_start = span.sent.start_char

        if span.text.lower() in _STEM_IDIOM_WORDS and any(
            m.start() <= start and end <= m.end() for m in _STEM_IDIOM.finditer(text)
        ):
            return "stem_idiom"

        if _REFERRAL.search(text[max(sent_start, start - _LOOKBACK_REFERRAL):start]):
            return "referral"

        if _MISSION.search(
            text[max(0, start - _WINDOW_MISSION):min(len(text), end + _WINDOW_MISSION)]
        ):
            return "agency_mission"

        if _PERMISSIVE.search(text[max(sent_start, start - _LOOKBACK_PERMISSIVE):start]):
            return "permissive"

        if span.text[:1].isupper() and _PROPER_NAME_TAIL.search(
            text[end:end + _LOOKAHEAD_PROPER_NAME]
        ):
            return "proper_name"

        return None

    def tag_text(
        self,
        text: str,
        excluded_spans: Optional[List[Tuple[int, int, FrozenSet[str]]]] = None,
    ) -> List[TagEvidence]:
        """
        Scan text and return evidence for all matched concepts.

        `excluded_spans` suppresses categories over character ranges, given as
        `(start_char, end_char, categories)`, so a section can be disqualified
        from producing certain tags without being removed from the text —
        removing it would shift Layer 2's chunk boundaries.
        """
        if not text or not self.matcher or not self.nlp:
            return []

        doc: Doc = self.nlp(text)

        # Keep only the longest match where several overlap at one position.
        # The matcher reports both a concept's label and its synonyms, so
        # "rural communities" also produces a bare "rural" hit at the same
        # place. The bare hit is reported first, is correctly rejected by the
        # modifier check below as an adjective, and used to consume the
        # concept's one slot — silently hiding the full-label match that would
        # have been accepted. filter_spans prefers the longest span, so the
        # label wins over its own synonym.
        spans = [
            Span(doc, start, end, label=match_id)
            for match_id, start, end in self.matcher(doc)
        ]

        evidence_list: List[TagEvidence] = []
        seen_concepts: Set[str] = set()

        for span in filter_spans(spans):
            start, end = span.start, span.end
            concept_id = self.nlp.vocab.strings[span.label]

            # Only record the first occurrence per concept to avoid duplicate spam
            if concept_id in seen_concepts:
                continue

            concept = self.concept_lookup.get(concept_id)
            if not concept:
                continue

            # Checked before the concept is marked as seen, so a match falling
            # in an excluded region doesn't block a legitimate one later in the
            # document.
            if excluded_spans:
                match_start = doc[start].idx
                if any(
                    lo <= match_start < hi and concept.category in categories
                    for lo, hi, categories in excluded_spans
                ):
                    continue

            # Contextual Dependency Checks
            is_valid = True

            # 1. Dependency Negation Check
            # Look at the root of the match and its ancestors/children
            match_span = doc[start:end]
            root_token = match_span.root

            # Check immediate children of the root for a negation modifier ('neg')
            if any(child.dep_ == "neg" for child in root_token.children):
                is_valid = False

            # Also check if the head of the root is negated (e.g., "does not fund housing")
            if any(child.dep_ == "neg" for child in root_token.head.children):
                is_valid = False

            # 2. Metaphorical / Compound Modifier Check
            # Single-word terms that frequently appear as modifiers in compound nouns
            # where the concept doesn't actually apply. E.g. "food security" ≠ National Defense,
            # "machine learning" ≠ Quality Education, "housing insecure" ≠ Housing policy.
            #
            # Restricted to single-token matches, which is what the heuristic was
            # always described as covering. Without that guard it also rejected
            # multi-word exact label matches whenever the phrase's head noun
            # happened to be an ambiguous word: "machine learning" was discarded
            # because "learning" heads a compound, and the six-token match on
            # "good health and well-being" because "health" sits in a
            # prepositional phrase. A multi-word match is specific enough that
            # the surrounding syntax is not evidence against it.
            ambiguous_terms = {
                "ecosystem", "travel", "environment", "system", "space", "model",
                "security", "learning", "education", "equity", "housing",
                "survey", "poverty", "energy", "health", "defense",
                "rural", "urban", "student", "veteran",
                "statistics", "transportation", "transport",
            }
            if is_valid and len(match_span) == 1 and root_token.text.lower() in ambiguous_terms:
                # If the match is a single token used as a modifier/compound, reject it.
                # "npadvmod" catches hyphenated compound-adjective patterns like
                # "energy-efficient system components", where "energy" modifies
                # "efficient" rather than standing for the National Defense/Energy
                # concept itself.
                if root_token.dep_ in {"amod", "compound", "nmod", "pobj", "npadvmod"} or \
                   any(child.dep_ in {"amod", "compound"} for child in root_token.children):
                    is_valid = False

            # 3. Scope Check
            # Rejects matches whose surrounding text shows the term names
            # something other than the opportunity's subject: an acronym
            # expansion, a referral to another programme, agency mission
            # boilerplate, an optional technique, or a proper name.
            if is_valid and self.out_of_scope_context(doc, match_span) is not None:
                is_valid = False

            if not is_valid:
                continue

            # Marked as seen only once a match is actually accepted. Marking it
            # earlier meant the first *rejected* occurrence consumed the
            # concept's single slot, so a later legitimate mention was never
            # considered: "energy-efficient components ... energy remains the
            # central concern" returned nothing at all, because the compound
            # modifier was rejected and the clean subject mention never looked
            # at. The excluded_spans check above was already written this way;
            # the dependency checks were not.
            seen_concepts.add(concept_id)

            # Grab context window (up to 10 tokens before and after)
            context_start = max(0, start - 10)
            context_end = min(len(doc), end + 10)
            snippet = doc[context_start:context_end].text

            evidence_list.append(
                TagEvidence(
                    concept_id=concept.concept_id,
                    label=concept.label,
                    category=concept.category,
                    source_layer="layer_1_terminological",
                    confidence=1.0,  # Exact matches are always 1.0 confidence
                    context_snippet=snippet,
                    ontology_concept_id=concept.concept_id,
                )
            )

        return evidence_list
