"""
Grant matching: researcher profile -> ranked FOA recommendations.

Wraps matching/matcher.py's hybrid score (0.7 cosine similarity + 0.3 ontology
tag overlap, Documentation/MATCHING.md) and, when a local LLM is reachable, layers a
plain-language explanation and a coarse relevance judgement onto the top
results via matching/explain.py. The hybrid ranking itself never depends on
the LLM being available -- explanations are additive and degrade to a
deterministic templated sentence, so this endpoint never 5xxs because Ollama
is down.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...matching.explain import (
    annotate_with_explanations,
    iter_explanations,
    relevance_sorted_window,
)
from ...matching.matcher import match_profile_to_foas
from ...storage.database import Database
from ..deps import (
    get_app_config,
    get_db,
    get_match_explainer,
    get_tagger_pipeline,
    get_vector_index,
)

router = APIRouter()


class MatchRequest(BaseModel):
    profile_text: str = Field(..., min_length=10, max_length=5000)
    k: int = Field(default=10, ge=1, le=50)
    threshold: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Minimum cosine similarity for the FAISS candidate pool, pre hybrid re-rank.",
    )
    status: Optional[str] = "open"
    explain: bool = Field(
        default=True,
        description=(
            "Generate an LLM explanation and relevance rating for the top "
            "results (see MATCH_EXPLAIN_TOP_K). Ranking itself is unaffected "
            "by this flag either way."
        ),
    )


def _rank_foas(req: MatchRequest, db: Database) -> Optional[List[Dict[str, Any]]]:
    """
    Shared ranking step for both the atomic and streaming endpoints. Never
    touches the LLM -- explanation is a separate, later step in both callers.

    Returns None if the FAISS index isn't built yet, distinct from an empty
    list (index missing vs. index built but nothing matched).
    """
    index = get_vector_index()
    if index.index is None:
        return None

    tagger = get_tagger_pipeline()
    results = match_profile_to_foas(
        req.profile_text, db, index, tagger=tagger, k=req.k, threshold=req.threshold
    )

    if req.status:
        results = [r for r in results if r.get("status") == req.status]

    return results


@router.post("")
def match_profile(req: MatchRequest, db: Database = Depends(get_db)):
    """
    Rank FOAs against a free-text researcher profile.

    Base ranking is the hybrid score: dense vector similarity from FAISS
    combined with explicit ontology-tag overlap between the profile and each
    FOA. If `explain` is true and results were found, the top
    `MATCH_EXPLAIN_TOP_K` are additionally annotated with a `match_explanation`
    sentence and an `llm_relevance` tier, and that window is re-sorted by
    relevance (hybrid_score breaks ties) -- so the LLM can refine the order of
    candidates the hybrid score already surfaced, but cannot promote a
    candidate it never reviewed.

    One atomic response after everything (including all explanations)
    completes -- see `POST /stream` for the same ranking delivered
    incrementally, which is what the web frontend actually uses.
    """
    results = _rank_foas(req, db)

    if results is None:
        return {
            "items": [],
            "total": 0,
            "llm_available": False,
            "message": "FAISS index not found. Run `make precompute-embeddings` then `make tag`.",
        }

    llm_available = False
    if req.explain and results:
        config = get_app_config()
        explainer = get_match_explainer()
        outcome = annotate_with_explanations(
            req.profile_text, results, explainer, config.match_explain_top_k
        )
        results = outcome["items"]
        llm_available = outcome["llm_available"]

    return {
        "items": results,
        "total": len(results),
        "llm_available": llm_available,
        "message": "Match successful" if results else "No matching FOAs found for this profile.",
    }


@router.post("/stream")
def match_profile_stream(req: MatchRequest, db: Database = Depends(get_db)):
    """
    Same ranking and explanation as `POST /api/match`, delivered
    incrementally as newline-delimited JSON instead of one response at the
    end.

    Explaining the top MATCH_EXPLAIN_TOP_K results is the slow part (a
    sequential local-LLM call per candidate, seconds each -- parallelising
    them was measured and found not to help: this Ollama setup processes
    concurrent requests one at a time regardless). This lets a client render
    the ranked list the instant it's ready and fill in each card's
    explanation as it individually completes, instead of one ~30-100s wait
    for a fully-assembled response. Each line is one JSON object:

        {"type": "ranked", "items": [...], "total": N, "message": "..."}
        {"type": "explanation", "foa_id": "...", "match_explanation": "...",
         "llm_relevance": "strong"|"moderate"|"weak"|null}
            -- one per explained candidate, in completion order (matches
               ranked order here, since explanations run sequentially, but
               callers should key on foa_id rather than arrival position)
        {"type": "reorder", "foa_ids": [...]}
            -- only sent when the LLM was available: the explained window's
               final relevance order, matching what the atomic endpoint
               already returns pre-sorted. Sent once, after every
               explanation in the window has arrived, not per-item -- so a
               client can reveal explanations progressively without cards
               jumping around mid-stream, then settle into final order once.
        {"type": "done", "llm_available": bool}

    Ranking itself never depends on the LLM -- "ranked" always arrives fast,
    matching the atomic endpoint's own guarantee that it never 5xxs because
    Ollama is down.
    """
    results = _rank_foas(req, db)

    def event_stream():
        if results is None:
            yield json.dumps({
                "type": "ranked",
                "items": [],
                "total": 0,
                "explain_window_size": 0,
                "message": (
                    "FAISS index not found. Run `make precompute-embeddings` then `make tag`."
                ),
            }) + "\n"
            yield json.dumps({"type": "done", "llm_available": False}) + "\n"
            return

        config = get_app_config()
        explain_top_k = config.match_explain_top_k if (req.explain and results) else 0
        explainer = get_match_explainer() if explain_top_k else None
        window = results[:explain_top_k]

        yield json.dumps({
            "type": "ranked",
            "items": results,
            "total": len(results),
            # How many leading items to expect an "explanation" event for,
            # so a client can render a per-card pending state for exactly
            # the right cards instead of guessing from arrival order alone.
            "explain_window_size": len(window),
            "message": (
                "Match successful" if results else "No matching FOAs found for this profile."
            ),
        }) + "\n"

        llm_available = False
        for foa, llm_available in iter_explanations(
            req.profile_text, results, explainer, explain_top_k
        ):
            yield json.dumps({
                "type": "explanation",
                "foa_id": foa["foa_id"],
                "match_explanation": foa["match_explanation"],
                "llm_relevance": foa["llm_relevance"],
            }) + "\n"

        if llm_available:
            ordered = relevance_sorted_window(window)
            yield json.dumps({
                "type": "reorder",
                "foa_ids": [f["foa_id"] for f in ordered],
            }) + "\n"

        yield json.dumps({"type": "done", "llm_available": llm_available}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
