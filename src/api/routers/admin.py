"""
Admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from models.database import get_db
from services.rag_service import rag_service
from api.auth_dependencies import require_admin
from api.models import StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/create-embeddings")
async def create_embeddings(
    batch_size: int = Query(10, description="Number of documents to process"),
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create embeddings for documents (admin only)"""
    try:
        # This is a placeholder - implement actual embedding creation logic
        return {"message": "Embedding creation started", "batch_size": batch_size}
    except Exception as e:
        logger.error(f"Error creating embeddings: {e}")
        raise HTTPException(status_code=500, detail="Failed to create embeddings")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db)
):
    """Get system statistics"""
    try:
        stats = rag_service.get_stats(db)
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

