"""Health check endpoint."""

from fastapi import APIRouter, Depends

from ...storage.database import Database
from ..deps import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Database = Depends(get_db)):
    """Health check with summary statistics."""
    stats = db.get_stats()
    return {
        "status": "healthy",
        "total_foas": stats["total_foas"],
        "open_foas": stats["open_foas"],
        "total_tags": stats["total_tags"],
        "last_ingestion": stats["last_ingestion"],
    }
