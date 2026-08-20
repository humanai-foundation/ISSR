"""FOA opportunities CRUD endpoints."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...storage.database import Database
from ..deps import get_db

router = APIRouter()


@router.get("")
def list_opportunities(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    agency: Optional[str] = Query(default=None),
    sort: str = Query(default="posted_date"),
    order: str = Query(default="DESC"),
    db: Database = Depends(get_db),
):
    """List FOA records with filtering, pagination, and sorting."""
    records, total = db.list_foas(
        status=status,
        agency_code=agency,
        page=page,
        size=size,
        sort_by=sort,
        sort_order=order,
    )

    return {
        "items": _strip_raw_payload(records),
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size > 0 else 0,
    }


@router.get("/recent")
def recent_opportunities(
    limit: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_db),
):
    """Get opportunities posted in the last 7 days."""
    records, total = db.list_foas(
        status="open",
        page=1,
        size=limit,
        sort_by="posted_date",
        sort_order="DESC",
    )
    return {
        "items": _strip_raw_payload(records),
        "total": total,
    }


@router.get("/facets")
def opportunity_facets(
    status: Optional[str] = Query(default=None),
    agency: Optional[str] = Query(default=None),
    db: Database = Depends(get_db),
):
    """
    Per-dimension counts for the sidebar facets, e.g. status: open[118].

    Declared before /{foa_id} for the same reason /recent is above: a
    dynamic path segment would otherwise shadow this literal one and every
    request here would 404 as "FOA not found" instead of matching.
    """
    facets = db.get_facet_counts(status=status, agency_code=agency)
    return {
        "status": facets["status"],
        "agency": facets["agency_code"],
    }


@router.get("/{foa_id}")
def get_opportunity(foa_id: str, db: Database = Depends(get_db)):
    """Get a single FOA record by ID."""
    record = db.get_foa(foa_id)
    if not record:
        raise HTTPException(status_code=404, detail="FOA not found")
    # Remove raw payload from response (too large for API)
    record.pop("raw_payload", None)
    return record


def _strip_raw_payload(records):
    """Remove raw_payload from list items to keep responses small."""
    for r in records:
        r.pop("raw_payload", None)
    return records
