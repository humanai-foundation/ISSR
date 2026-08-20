"""Export endpoints: CSV and JSON download."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ...export.csv_exporter import export_foas_to_csv
from ...storage.database import Database
from ..deps import get_app_config, get_db

router = APIRouter()


def _fetch_export_page(db: Database, status, agency, page, size):
    """
    Fetch one bounded page of records for export.

    Exports previously requested 100,000 rows unconditionally and built the
    whole payload in memory. The CSV exporter sorts globally by tag confidence,
    so it genuinely needs a full page in memory — streaming row-by-row would
    silently drop that ordering. Bounding the page size keeps the memory
    footprint predictable while preserving the sort within what is returned.
    """
    max_rows = get_app_config().api_export_max_rows
    effective_size = min(size or max_rows, max_rows)
    records, total = db.list_foas(
        status=status,
        agency_code=agency,
        page=page,
        size=effective_size,
    )
    return records, total, effective_size


@router.get("/csv")
def export_csv(
    status: Optional[str] = Query(default=None),
    agency: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: Optional[int] = Query(default=None, ge=1),
    db: Database = Depends(get_db),
):
    """Download FOAs as CSV with tag evidence."""
    records, total, effective_size = _fetch_export_page(db, status, agency, page, size)

    csv_content = export_foas_to_csv(records)

    headers = {
        "Content-Disposition": "attachment; filename=foa_export.csv",
        "X-Total-Count": str(total),
        "X-Returned-Count": str(len(records)),
    }
    # Tell the caller when the export is partial, so a truncated file is never
    # mistaken for the complete dataset.
    if total > len(records):
        headers["X-Export-Truncated"] = "true"
        headers["X-Next-Page"] = str(page + 1)

    return Response(content=csv_content, media_type="text/csv", headers=headers)


@router.get("/json")
def export_json(
    status: Optional[str] = Query(default=None),
    agency: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: Optional[int] = Query(default=None, ge=1),
    db: Database = Depends(get_db),
):
    """Download FOAs as JSON."""
    records, total, effective_size = _fetch_export_page(db, status, agency, page, size)

    for r in records:
        r.pop("raw_payload", None)

    return {
        "foas": records,
        "total": total,
        "returned": len(records),
        "page": page,
        "size": effective_size,
        "truncated": total > len(records),
    }
