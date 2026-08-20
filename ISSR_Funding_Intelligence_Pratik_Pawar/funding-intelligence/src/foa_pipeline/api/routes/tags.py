"""Tag and ontology browsing endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...storage.database import Database
from ..deps import get_db

router = APIRouter()


@router.get("")
def list_tags(
    category: Optional[str] = Query(default=None),
    db: Database = Depends(get_db),
):
    """List all tag usage statistics, optionally filtered by category."""
    stats = db.get_tag_stats()
    if category:
        stats = [s for s in stats if s.get("category") == category]
    return {"tags": stats, "total": len(stats)}


@router.get("/categories")
def tag_categories(db: Database = Depends(get_db)):
    """Get tag categories with counts."""
    stats = db.get_tag_stats()
    categories = {}
    for s in stats:
        cat = s.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"category": cat, "concept_count": 0, "total_uses": 0}
        categories[cat]["concept_count"] += 1
        categories[cat]["total_uses"] += s.get("count", 0)
    return {"categories": list(categories.values())}


@router.get("/{concept_id}")
def tag_detail(
    concept_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """Get details for a specific tag concept and FOAs tagged with it."""
    records, total = db.get_foas_by_tag(concept_id, page=page, size=size)
    for r in records:
        r.pop("raw_payload", None)
    return {
        "concept_id": concept_id,
        "foas": records,
        "total": total,
        "page": page,
        "size": size,
    }
