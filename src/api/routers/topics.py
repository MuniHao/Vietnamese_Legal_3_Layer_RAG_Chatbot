"""
Topics and Categories endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
import logging

from models.database import get_db, Topic, Category, Document, DocumentCategoryMap

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Topics & Categories"])


@router.get("/topics")
async def get_topics(
    db: Session = Depends(get_db)
):
    """Get all topics"""
    try:
        logger.info("Fetching topics from database...")
        topics = db.query(Topic).order_by(Topic.ordering.asc(), Topic.id.asc()).all()
        logger.info(f"Found {len(topics)} topics")
        return [
            {
                "id": topic.id,
                "title": topic.title,
                "description": topic.description,
                "code": topic.code,
                "ordering": topic.ordering,
            }
            for topic in topics
        ]
    except Exception as e:
        logger.error(f"Error getting topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get topics: {str(e)}")


@router.get("/topics/{topic_id}/categories")
async def get_categories_by_topic(
    topic_id: int,
    db: Session = Depends(get_db)
):
    """Get all categories for a specific topic"""
    try:
        categories = db.query(Category).filter(
            Category.topic_id == topic_id
        ).order_by(Category.id.asc()).all()
        return [
            {
                "id": category.id,
                "title": category.title,
                "short_title": category.short_title,
                "description": category.description,
                "topic_id": category.topic_id,
            }
            for category in categories
        ]
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/categories/{category_id}/documents")
async def get_documents_by_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Get all documents for a specific category"""
    try:
        query = select(Document).join(
            DocumentCategoryMap,
            Document.id == DocumentCategoryMap.document_id
        ).where(
            DocumentCategoryMap.category_id == category_id
        ).order_by(Document.id.asc())
        
        documents = db.execute(query).scalars().all()
        
        logger.info(f"Found {len(documents)} documents for category {category_id}")
        
        return [
            {
                "id": doc.id,
                "title": doc.title,
                "doc_number": doc.doc_number,
                "doc_type": doc.doc_type,
                "issuing_agency": doc.issuing_agency,
                "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
                "status": doc.status,
                "file_url": doc.file_url,
                "html_content": doc.html_content,
            }
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Error getting documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")

