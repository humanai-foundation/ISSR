"""
Grant matching: researcher profile → ranked FOA recommendations.

Combines dense vector similarity (FAISS) with explicit ontology tag overlap
using the hybrid relevance score documented in Documentation/MATCHING.md:

    hybrid_score = (COSINE_WEIGHT * cosine_similarity)
                 + (TAG_WEIGHT * tag_overlap_ratio)

Dense vectors alone drift toward loose thematic association; ontology tags
alone miss nuanced phrasing. Combining them keeps the ranking anchored to
explicit, auditable concept matches while still tolerating paraphrase.

CLI: python -m foa_pipeline.cli search --profile "computational social science" --k 10
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from ..storage.database import Database
from .vector_index import VectorIndex

logger = logging.getLogger(__name__)

# Weights from Documentation/MATCHING.md. They should sum to 1.0 to keep hybrid_score in [0, 1].
COSINE_WEIGHT = 0.7
TAG_WEIGHT = 0.3

# FAISS is queried for more candidates than the caller asked for, so an FOA with
# strong tag overlap but middling cosine similarity can still be promoted into
# the final top-k by the re-ranking step below.
CANDIDATE_POOL_MULTIPLIER = 3


def extract_profile_tags(profile_text: str, tagger: Any) -> Set[str]:
    """
    Tag a researcher profile with the same ontology used for FOAs.

    Returns the set of matched concept IDs. Failure to tag is not fatal — the
    caller falls back to cosine-only ranking.
    """
    try:
        tags = tagger.tag_record({"program_description": profile_text})
    except Exception as exc:
        logger.warning(
            "Could not tag researcher profile (%s); falling back to cosine-only ranking.",
            exc,
        )
        return set()

    return {t["ontology_concept_id"] for t in tags if t.get("ontology_concept_id")}


def compute_tag_overlap(
    profile_tags: Set[str], foa_tags: Set[str]
) -> Tuple[float, List[str]]:
    """
    Fraction of the profile's concepts that the FOA also carries.

    Uses the containment ratio from Documentation/MATCHING.md (|profile ∩ foa| / |profile|)
    rather than full Jaccard: a broad FOA carrying many extra tags should not be
    penalised for covering everything the researcher actually asked for.
    """
    if not profile_tags:
        return 0.0, []

    matched = sorted(profile_tags & foa_tags)
    return len(matched) / len(profile_tags), matched


def match_profile_to_foas(
    profile_text: str,
    db: Database,
    vector_index: VectorIndex,
    tagger: Optional[Any] = None,
    k: int = 10,
    threshold: float = 0.0,
    cosine_weight: float = COSINE_WEIGHT,
    tag_weight: float = TAG_WEIGHT,
) -> List[Dict[str, Any]]:
    """
    Rank FOAs against a researcher profile using the hybrid relevance score.

    `tagger` is an initialised TaggerPipeline. If omitted, ranking degrades to
    pure cosine similarity (tag_overlap_ratio = 0.0 everywhere) rather than
    failing, so matching still works without the ontology/spaCy stack loaded.

    Each result carries `cosine_score`, `tag_overlap_ratio`, `matched_tags`, and
    the combined `hybrid_score`, so a ranking can be explained to a user rather
    than presented as an opaque number.
    """
    if not profile_text or not profile_text.strip():
        return []

    candidates = vector_index.search(
        profile_text,
        k=max(k * CANDIDATE_POOL_MULTIPLIER, k),
        threshold=threshold,
        db=db,
    )
    if not candidates:
        return []

    profile_tags = extract_profile_tags(profile_text, tagger) if tagger else set()
    if not profile_tags:
        logger.info("No ontology tags derived from profile; ranking on cosine similarity alone.")

    ranked: List[Dict[str, Any]] = []
    for foa in candidates:
        foa_tag_labels = {
            t["ontology_concept_id"]: t["label"]
            for t in db.get_tags_for_foa(foa["foa_id"])
            if t.get("ontology_concept_id")
        }
        overlap_ratio, matched_ids = compute_tag_overlap(
            profile_tags, set(foa_tag_labels)
        )

        cosine = float(foa.get("similarity_score", 0.0))
        foa["cosine_score"] = round(cosine, 4)
        foa["tag_overlap_ratio"] = round(overlap_ratio, 4)
        foa["matched_tags"] = [foa_tag_labels[cid] for cid in matched_ids]
        foa["hybrid_score"] = round(
            cosine_weight * cosine + tag_weight * overlap_ratio, 4
        )
        ranked.append(foa)

    ranked.sort(key=lambda f: f["hybrid_score"], reverse=True)
    return ranked[:k]
