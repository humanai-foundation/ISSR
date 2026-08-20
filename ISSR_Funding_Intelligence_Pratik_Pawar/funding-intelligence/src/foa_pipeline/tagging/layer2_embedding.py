"""
Layer 2: Semantic Embedding Tagging

Uses sentence-transformers to map FOA text chunks and ontology concept
descriptions into a shared embedding space. Tags are assigned based on
cosine similarity exceeding a configurable threshold.

Includes precomputation utilities to cache ontology embeddings.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

import numpy as np

from ..ontology.store import OntologyConcept, OntologyStore
from .evidence import TagEvidence

logger = logging.getLogger(__name__)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class L2Tagger:
    """Semantic tagger using dense embeddings."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        thresholds: Optional[Dict[str, float]] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.model_name = model_name
        self.thresholds = thresholds or {"default": 0.75}
        self.cache_dir = cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.model = None
        self.concept_embeddings: Dict[str, np.ndarray] = {}
        self.concept_lookup: Dict[str, OntologyConcept] = {}

    def load_model(self) -> None:
        """Load the sentence-transformer model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                logger.info("Loaded embedding model: %s", self.model_name)
            except ImportError:
                logger.error("sentence-transformers not installed.")
                raise

    def build_embeddings(self, store: OntologyStore, force_recompute: bool = False) -> None:
        """
        Build embeddings for all ontology concepts.
        Caches to disk if cache_dir is provided.
        """
        self.load_model()
        assert self.model is not None

        cache_path_npy = self.cache_dir / "concept_embeddings.npy" if self.cache_dir else None
        cache_path_json = self.cache_dir / "concept_ids.json" if self.cache_dir else None

        concepts = store.get_all_concepts()
        self.concept_lookup = {c.concept_id: c for c in concepts}

        if (
            not force_recompute
            and cache_path_npy
            and cache_path_npy.exists()
            and cache_path_json
            and cache_path_json.exists()
        ):
            # Load from cache
            try:
                emb_matrix = np.load(cache_path_npy)
                with open(cache_path_json) as f:
                    concept_ids = json.load(f)

                if len(concept_ids) == len(concepts):
                    for cid, emb in zip(concept_ids, emb_matrix):
                        self.concept_embeddings[cid] = emb
                    logger.info("Loaded %d concept embeddings from cache", len(concept_ids))
                    return
                else:
                    logger.info("Cache size mismatch, recomputing embeddings.")
            except Exception as exc:
                logger.warning("Failed to load embeddings cache: %s", exc)

        # Compute embeddings
        logger.info("Computing embeddings for %d concepts...", len(concepts))
        texts_to_embed = []
        concept_ids = []

        for concept in concepts:
            # Embed label + description + synonyms for a richer representation
            text = concept.label
            if concept.description:
                text += ". " + concept.description
            if concept.synonyms:
                text += ". Synonyms: " + ", ".join(concept.synonyms[:5])

            texts_to_embed.append(text)
            concept_ids.append(concept.concept_id)

        emb_matrix = self.model.encode(texts_to_embed, convert_to_numpy=True)

        for cid, emb in zip(concept_ids, emb_matrix):
            self.concept_embeddings[cid] = emb

        # Save to cache
        if cache_path_npy and cache_path_json:
            np.save(cache_path_npy, emb_matrix)
            with open(cache_path_json, "w") as f:
                json.dump(concept_ids, f)
            logger.info("Saved embeddings cache to %s", self.cache_dir)

    def chunk_text(self, text: str, chunk_size: int = 250, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks (words)."""
        return [c for c, _start, _end in self.chunk_text_with_spans(text, chunk_size, overlap)]

    def chunk_text_with_spans(
        self, text: str, chunk_size: int = 250, overlap: int = 50
    ) -> List[Tuple[str, int, int]]:
        """
        Chunk text, also returning each chunk's character span in the original.

        The spans let a caller suppress specific categories for the part of a
        document they don't apply to (for example, not inferring target
        populations from an eligibility section) without deleting that text.
        Deleting it would shift every downstream chunk boundary and perturb
        categories that had nothing to do with the exclusion.

        Chunk strings are whitespace-normalised, matching the original
        behaviour, so they will not be byte-identical to `text[start:end]`.
        """
        words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        if not words:
            return []

        chunks: List[Tuple[str, int, int]] = []
        for i in range(0, len(words), chunk_size - overlap):
            window = words[i:i + chunk_size]
            if not window:
                break
            chunks.append((" ".join(w[0] for w in window), window[0][1], window[-1][2]))
            if i + chunk_size >= len(words):
                break
        return chunks

    @staticmethod
    def combine_scores(
        body_sim: float, title_sim: float, weight: float, combine: str = "blend"
    ) -> float:
        """
        Fold a title score into a body score.

        "blend" is a weighted average, so it lowers the score of any concept the
        title does not mention — which means it also acts as an implicit
        threshold increase, not purely as title evidence. "max" only ever
        promotes. A weight of 0 returns the body score untouched under either.
        """
        if weight <= 0.0:
            return body_sim
        if combine == "max":
            return max(body_sim, title_sim)
        return (1.0 - weight) * body_sim + weight * title_sim

    @staticmethod
    def _suppressed_categories(
        chunk_start: int,
        chunk_end: int,
        excluded_spans: Optional[List[Tuple[int, int, FrozenSet[str]]]],
    ) -> FrozenSet[str]:
        """Categories to suppress for a chunk, by majority character overlap."""
        if not excluded_spans:
            return frozenset()

        chunk_len = max(chunk_end - chunk_start, 1)
        suppressed: set = set()
        for lo, hi, categories in excluded_spans:
            overlap = min(chunk_end, hi) - max(chunk_start, lo)
            if overlap > 0 and overlap / chunk_len > 0.5:
                suppressed |= set(categories)
        return frozenset(suppressed)

    def _best_scores(
        self,
        text: str,
        excluded_spans: Optional[List[Tuple[int, int, FrozenSet[str]]]] = None,
    ) -> Tuple[List[str], Dict[str, Tuple[float, int]]]:
        """
        Highest cosine score per concept across all chunks, and its chunk index.

        Split out of `tag_text` so that scoring and thresholding are separable:
        the discipline benchmark needs a *ranking* over concepts, which
        thresholded output cannot provide. Keeping one implementation means the
        benchmark measures the production scoring path rather than a
        reimplementation that could drift from it.
        """
        if not text or not self.model or not self.concept_embeddings:
            return [], {}

        spans = self.chunk_text_with_spans(text)
        if not spans:
            return [], {}

        chunks = [c for c, _s, _e in spans]
        suppressed_per_chunk = [
            self._suppressed_categories(start, end, excluded_spans)
            for _c, start, end in spans
        ]

        # Embed all chunks at once
        chunk_embs = self.model.encode(chunks, convert_to_numpy=True)

        best: Dict[str, Tuple[float, int]] = {}
        for i, chunk_emb in enumerate(chunk_embs):
            suppressed = suppressed_per_chunk[i]
            for concept_id, concept_emb in self.concept_embeddings.items():
                if self.concept_lookup[concept_id].category in suppressed:
                    continue
                sim = cosine_similarity(chunk_emb, concept_emb)
                current = best.get(concept_id)
                if current is None or sim > current[0]:
                    best[concept_id] = (sim, i)

        return chunks, best

    def score_concepts(
        self,
        text: str,
        category: Optional[str] = None,
        excluded_spans: Optional[List[Tuple[int, int, FrozenSet[str]]]] = None,
    ) -> Dict[str, float]:
        """
        Unthresholded cosine score for every concept, optionally one category.

        This is the ranking view of Layer 2, used for benchmarks that ask "is
        the right concept ranked first" rather than "did it clear a threshold".
        """
        _chunks, best = self._best_scores(text, excluded_spans)
        return {
            concept_id: score
            for concept_id, (score, _index) in best.items()
            if category is None or self.concept_lookup[concept_id].category == category
        }

    def tag_text(
        self,
        text: str,
        excluded_spans: Optional[List[Tuple[int, int, FrozenSet[str]]]] = None,
        title: Optional[str] = None,
        title_weight: float = 0.0,
        title_combine: str = "blend",
    ) -> List[TagEvidence]:
        """
        Embed text chunks and find ontology concepts above threshold.

        `excluded_spans` suppresses categories over character ranges, given as
        `(start_char, end_char, categories)`. A chunk is treated as belonging to
        an excluded region when the majority of its characters fall inside it —
        chunks overlap by design, so requiring only partial overlap would
        suppress chunks that are mostly ordinary programme text.

        `title` is scored as its own unit rather than left buried in the body.
        An FOA title averages 59 characters against ~3,100 of description, so
        within a 250-word chunk it contributes almost nothing, even though a
        title is the most information-dense part of the document.

        `title_combine` selects how the two scores meet:
          - "blend": ``(1 - w) * body + w * title`` — lowers scores for concepts
            absent from the title, so it tightens as well as promotes.
          - "max": ``max(body, title)`` — title can only add evidence.

        ``title_weight=0`` reproduces the body-only behaviour exactly under
        either mode.
        """
        # Best body score per concept, and the chunk that produced it. Scoring
        # is separated from thresholding because the title has to be folded in
        # before the threshold is applied — testing each chunk in isolation
        # would decide a concept's fate before the title was consulted.
        chunks, best_body = self._best_scores(text, excluded_spans)
        if not chunks:
            return []

        title_emb = None
        if title and title.strip() and title_weight > 0.0 and self.model is not None:
            title_emb = self.model.encode([title], convert_to_numpy=True)[0]
        use_title = title_emb is not None

        evidence_dict: Dict[str, TagEvidence] = {}
        for concept_id, (body_sim, chunk_index) in best_body.items():
            concept = self.concept_lookup[concept_id]

            score = body_sim
            if use_title and title_emb is not None:
                score = self.combine_scores(
                    body_sim,
                    cosine_similarity(title_emb, self.concept_embeddings[concept_id]),
                    title_weight,
                    title_combine,
                )

            # Threshold: per-concept override takes priority over the category
            # default (a concept persistently over-triggered by generic
            # boilerplate can be tightened without raising the threshold for
            # its whole category and losing recall on the rest of it).
            threshold = self.thresholds.get(
                concept_id,
                self.thresholds.get(concept.category, self.thresholds.get("default", 0.75)),
            )
            if score < threshold:
                continue

            chunk = chunks[chunk_index]
            evidence_dict[concept_id] = TagEvidence(
                concept_id=concept.concept_id,
                label=concept.label,
                category=concept.category,
                source_layer="layer_2_embedding",
                confidence=score,
                context_snippet=chunk[:500] + ("..." if len(chunk) > 500 else ""),
                ontology_concept_id=concept.concept_id,
            )

        return list(evidence_dict.values())
