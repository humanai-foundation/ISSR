"""Search endpoints: keyword (FTS5) and semantic (FAISS)."""

import math
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...storage.database import Database
from ..deps import get_db, get_vector_index

router = APIRouter()


class KeywordSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    status: Optional[str] = None
    agency: Optional[str] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class SemanticSearchRequest(BaseModel):
    profile_text: str = Field(..., min_length=10, max_length=5000)
    k: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Optional[str] = "open"


@router.post("/keyword")
def keyword_search(
    req: KeywordSearchRequest,
    db: Database = Depends(get_db),
):
    """Full-text keyword search using SQLite FTS5."""
    records, total = db.search_fts(
        query=req.query,
        status=req.status,
        agency_code=req.agency,
        page=req.page,
        size=req.size,
    )

    for r in records:
        r.pop("raw_payload", None)

    return {
        "items": records,
        "total": total,
        "page": req.page,
        "size": req.size,
        "pages": math.ceil(total / req.size) if req.size > 0 else 0,
        "query": req.query,
    }


@router.post("/semantic")
def semantic_search(
    req: SemanticSearchRequest,
    db: Database = Depends(get_db),
):
    """
    Semantic similarity search using FAISS.
    Requires FAISS index to be built (run `precompute-embeddings` and `tag-all` first).
    """
    index = get_vector_index()

    if index.index is None:
        return {
            "items": [],
            "total": 0,
            "message": "FAISS index not found. Run `make precompute-embeddings` then `make tag`.",
            "query_length": len(req.profile_text),
        }

    results = index.search(req.profile_text, k=req.k, threshold=req.threshold, db=db)


    # Filter by status if requested
    if req.status:
        results = [r for r in results if r.get("status") == req.status]

    return {
        "items": results,
        "total": len(results),
        "message": "Semantic search successful",
        "threshold_used": req.threshold,
    }
