"""
Collections endpoints - user document collections/folders
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from models.database import get_db, User, Collection, CollectionDocument, Document
from api.auth_dependencies import get_current_user
from api.models import CollectionCreate, CollectionUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collections", tags=["Collections"])


@router.post("")
async def create_collection(
    collection: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new collection"""
    try:
        new_collection = Collection(
            user_id=current_user.user_id,
            name=collection.name,
            description=collection.description,
            color=collection.color or "#2196F3"
        )
        db.add(new_collection)
        db.commit()
        db.refresh(new_collection)
        
        return {
            "id": new_collection.id,
            "name": new_collection.name,
            "description": new_collection.description,
            "color": new_collection.color,
            "created_at": new_collection.created_at.isoformat(),
            "document_count": 0
        }
        
    except Exception as e:
        logger.error(f"Error creating collection: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


@router.get("")
async def get_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all collections for current user"""
    try:
        collections = db.query(Collection).filter(
            Collection.user_id == current_user.user_id
        ).order_by(Collection.created_at.desc()).all()
        
        result = []
        for coll in collections:
            doc_count = db.query(CollectionDocument).filter(
                CollectionDocument.collection_id == coll.id
            ).count()
            
            result.append({
                "id": coll.id,
                "name": coll.name,
                "description": coll.description,
                "color": coll.color,
                "created_at": coll.created_at.isoformat(),
                "updated_at": coll.updated_at.isoformat() if coll.updated_at else None,
                "document_count": doc_count
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get collections: {str(e)}")


@router.get("/{collection_id}")
async def get_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific collection"""
    try:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        doc_count = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id
        ).count()
        
        return {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "color": collection.color,
            "created_at": collection.created_at.isoformat(),
            "updated_at": collection.updated_at.isoformat() if collection.updated_at else None,
            "document_count": doc_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get collection: {str(e)}")


@router.put("/{collection_id}")
async def update_collection(
    collection_id: int,
    collection: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a collection"""
    try:
        coll = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not coll:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        if collection.name is not None:
            coll.name = collection.name
        if collection.description is not None:
            coll.description = collection.description
        if collection.color is not None:
            coll.color = collection.color
        
        coll.updated_at = datetime.now()
        db.commit()
        db.refresh(coll)
        
        doc_count = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id
        ).count()
        
        return {
            "id": coll.id,
            "name": coll.name,
            "description": coll.description,
            "color": coll.color,
            "created_at": coll.created_at.isoformat(),
            "updated_at": coll.updated_at.isoformat() if coll.updated_at else None,
            "document_count": doc_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating collection: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update collection: {str(e)}")


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a collection"""
    try:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        db.delete(collection)
        db.commit()
        
        return {"message": "Collection deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")


@router.post("/{collection_id}/documents/{document_id}")
async def add_document_to_collection(
    collection_id: int,
    document_id: int,
    notes: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a document to a collection"""
    try:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        existing = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == document_id
        ).first()
        
        if existing:
            if notes is not None:
                existing.notes = notes
                db.commit()
            return {"message": "Document already in collection", "added": True}
        
        coll_doc = CollectionDocument(
            collection_id=collection_id,
            document_id=document_id,
            notes=notes
        )
        db.add(coll_doc)
        db.commit()
        db.refresh(coll_doc)
        
        return {"message": "Document added to collection", "added": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding document to collection: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add document to collection: {str(e)}")


@router.delete("/{collection_id}/documents/{document_id}")
async def remove_document_from_collection(
    collection_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a document from a collection"""
    try:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        coll_doc = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == document_id
        ).first()
        
        if not coll_doc:
            raise HTTPException(status_code=404, detail="Document not in collection")
        
        db.delete(coll_doc)
        db.commit()
        
        return {"message": "Document removed from collection", "removed": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing document from collection: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove document from collection: {str(e)}")


@router.get("/{collection_id}/documents")
async def get_collection_documents(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """Get all documents in a collection"""
    try:
        collection = db.query(Collection).filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.user_id
        ).first()
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        coll_docs = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id
        ).order_by(CollectionDocument.added_at.desc()).offset(skip).limit(limit).all()
        
        documents = []
        for coll_doc in coll_docs:
            doc = coll_doc.document
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
                "notes": coll_doc.notes,
                "added_at": coll_doc.added_at.isoformat()
            })
        
        total = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id
        ).count()
        
        return {
            "documents": documents,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get collection documents: {str(e)}")

