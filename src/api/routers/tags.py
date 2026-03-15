"""
Tags endpoints - document tagging system
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from models.database import get_db, User, DocumentTag
from api.auth_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["Tags"])


@router.get("")
async def get_all_user_tags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all unique tags for current user (for autocomplete)"""
    try:
        tags = db.query(DocumentTag.tag_name).filter(
            DocumentTag.user_id == current_user.user_id
        ).distinct().order_by(DocumentTag.tag_name).all()
        
        return [tag[0] for tag in tags]
        
    except Exception as e:
        logger.error(f"Error getting all tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get tags: {str(e)}")


@router.get("/{tag_name}/documents")
async def get_documents_by_tag(
    tag_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """Get all documents with a specific tag"""
    try:
        doc_tags = db.query(DocumentTag).filter(
            DocumentTag.user_id == current_user.user_id,
            DocumentTag.tag_name == tag_name
        ).order_by(DocumentTag.created_at.desc()).offset(skip).limit(limit).all()
        
        documents = []
        for doc_tag in doc_tags:
            doc = doc_tag.document
            documents.append({
                "id": doc.id,
                "title": doc.title,
                "doc_number": doc.doc_number,
                "doc_type": doc.doc_type,
                "issuing_agency": doc.issuing_agency,
                "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
                "status": doc.status,
                "file_url": doc.file_url,
                "source_url": doc.source_url,
                "tagged_at": doc_tag.created_at.isoformat()
            })
        
        total = db.query(DocumentTag).filter(
            DocumentTag.user_id == current_user.user_id,
            DocumentTag.tag_name == tag_name
        ).count()
        
        return {
            "documents": documents,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error getting documents by tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get documents by tag: {str(e)}")

