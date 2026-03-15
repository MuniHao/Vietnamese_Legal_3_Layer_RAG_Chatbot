"""
Search endpoints for legal documents
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from models.database import get_db
from services.rag_service import rag_service
from api.models import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Search for legal documents"""
    try:
        logger.info(f"Search request: {request.query}")
        
        results = rag_service.search_similar_documents(
            request.query, 
            db, 
            top_k=request.top_k,
            use_reranker=True
        )
        
        return SearchResponse(
            results=results,
            total_found=len(results)
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("", response_model=SearchResponse)
async def search_documents_get(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
    db: Session = Depends(get_db)
):
    """Search for legal documents (GET method)"""
    try:
        logger.info(f"Search request (GET): {query}")
        
        results = rag_service.search_similar_documents(
            query, 
            db, 
            top_k=top_k,
            use_reranker=True
        )
        
        return SearchResponse(
            results=results,
            total_found=len(results)
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

