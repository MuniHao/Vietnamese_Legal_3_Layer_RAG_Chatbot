"""
Document endpoints - viewing, saving, tags, export, share
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pathlib import Path
from datetime import datetime
import logging

from models.database import get_db, User, Document, SavedDocument, DocumentTag
from api.auth_dependencies import get_current_user, get_current_user_optional
from api.models import TagCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("/saved")
async def get_saved_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(100, ge=1, le=100)
):
    """Get all saved documents for current user"""
    logger.info(f"Getting saved documents for user {current_user.user_id}, skip={skip}, limit={limit}")
    
    skip = skip if skip is not None and skip >= 0 else 0
    limit = limit if limit is not None and 1 <= limit <= 100 else 100
    
    try:
        saved_docs = db.query(SavedDocument).options(
            joinedload(SavedDocument.document)
        ).filter(
            SavedDocument.user_id == current_user.user_id
        ).order_by(SavedDocument.created_at.desc()).offset(skip).limit(limit).all()
        
        logger.info(f"Found {len(saved_docs)} saved documents")
        
        documents = []
        for saved in saved_docs:
            try:
                doc = saved.document
                if doc is None:
                    doc = db.query(Document).filter(Document.id == saved.document_id).first()
                    if doc is None:
                        continue
                
                title = str(doc.title) if doc.title else "N/A"
                if isinstance(doc.title, list):
                    title = " ".join(str(item) for item in doc.title)
                
                effective_date_str = None
                if doc.effective_date:
                    if isinstance(doc.effective_date, datetime):
                        effective_date_str = doc.effective_date.isoformat()
                    else:
                        effective_date_str = str(doc.effective_date)
                
                saved_at_str = datetime.utcnow().isoformat()
                if saved.created_at:
                    if isinstance(saved.created_at, datetime):
                        saved_at_str = saved.created_at.isoformat()
                    else:
                        saved_at_str = str(saved.created_at)
                
                doc_id = int(doc.id) if doc.id is not None else None
                if doc_id is None:
                    continue
                
                doc_data = {
                    "id": doc_id,
                    "title": title,
                    "doc_number": str(doc.doc_number) if doc.doc_number is not None else None,
                    "doc_type": str(doc.doc_type) if doc.doc_type is not None else None,
                    "issuing_agency": str(doc.issuing_agency) if doc.issuing_agency is not None else None,
                    "effective_date": effective_date_str,
                    "status": str(doc.status) if doc.status is not None else None,
                    "file_url": str(doc.file_url) if doc.file_url is not None else None,
                    "source_url": str(doc.source_url) if doc.source_url is not None else None,
                    "saved_at": saved_at_str
                }
                
                documents.append(doc_data)
                
            except Exception as e:
                logger.error(f"Error processing saved document {saved.id}: {e}", exc_info=True)
                continue
        
        total = db.query(SavedDocument).filter(
            SavedDocument.user_id == current_user.user_id
        ).count()
        
        return {
            "documents": documents,
            "total": int(total),
            "skip": int(skip),
            "limit": int(limit)
        }
        
    except Exception as e:
        logger.error(f"Error getting saved documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get saved documents: {str(e)}")


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific document by ID"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": document.id,
            "title": document.title,
            "doc_number": document.doc_number,
            "issuing_agency": document.issuing_agency,
            "doc_type": document.doc_type,
            "signing_date": document.signing_date.isoformat() if document.signing_date else None,
            "effective_date": document.effective_date.isoformat() if document.effective_date else None,
            "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None,
            "status": document.status,
            "summary": document.summary,
            "html_content": document.html_content,
            "text_content": document.text_content,
            "source_url": document.source_url,
            "file_url": document.file_url,
            "created_at": document.created_at.isoformat() if document.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document retrieval error: {e}")
        raise HTTPException(status_code=500, detail=f"Document retrieval failed: {str(e)}")


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Serve document file from local filesystem"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document.file_url:
            raise HTTPException(status_code=404, detail="Document file not found")
        
        base_dir = Path("/Users/nhathao/Documents/NienLuan/Data/Document-Word")
        file_path = base_dir / document.file_url
        
        try:
            file_path = file_path.resolve()
            base_dir = base_dir.resolve()
            file_path.relative_to(base_dir)
        except (ValueError, OSError):
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Path is not a file")
        
        media_type = None
        if file_path.suffix.lower() == '.pdf':
            media_type = 'application/pdf'
        elif file_path.suffix.lower() in ['.doc', '.docx']:
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if file_path.suffix.lower() == '.docx' else 'application/msword'
        
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File serving error: {e}")
        raise HTTPException(status_code=500, detail=f"File serving failed: {str(e)}")





@router.post("/{document_id}/save")
async def save_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a document to user's favorites"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        existing = db.query(SavedDocument).filter(
            SavedDocument.user_id == current_user.user_id,
            SavedDocument.document_id == document_id
        ).first()
        
        if existing:
            return {"message": "Document already saved", "saved": True}
        
        saved_doc = SavedDocument(
            user_id=current_user.user_id,
            document_id=document_id
        )
        db.add(saved_doc)
        db.commit()
        db.refresh(saved_doc)
        
        return {"message": "Document saved successfully", "saved": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving document: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save document: {str(e)}")


@router.delete("/{document_id}/save")
async def unsave_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a document from user's favorites"""
    try:
        saved_doc = db.query(SavedDocument).filter(
            SavedDocument.user_id == current_user.user_id,
            SavedDocument.document_id == document_id
        ).first()
        
        if not saved_doc:
            raise HTTPException(status_code=404, detail="Document not in saved list")
        
        db.delete(saved_doc)
        db.commit()
        
        return {"message": "Document removed from saved list", "saved": False}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unsaving document: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to unsave document: {str(e)}")


@router.get("/{document_id}/is-saved")
async def check_document_saved(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if a document is saved by current user"""
    try:
        saved = db.query(SavedDocument).filter(
            SavedDocument.user_id == current_user.user_id,
            SavedDocument.document_id == document_id
        ).first()
        
        return {"saved": saved is not None}
        
    except Exception as e:
        logger.error(f"Error checking saved status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check saved status: {str(e)}")


@router.post("/{document_id}/tags")
async def add_tag_to_document(
    document_id: int,
    tag: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a tag to a document"""
    try:
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        existing = db.query(DocumentTag).filter(
            DocumentTag.user_id == current_user.user_id,
            DocumentTag.document_id == document_id,
            DocumentTag.tag_name == tag.tag_name.strip()
        ).first()
        
        if existing:
            return {"message": "Tag already exists", "added": True}
        
        doc_tag = DocumentTag(
            user_id=current_user.user_id,
            document_id=document_id,
            tag_name=tag.tag_name.strip()
        )
        db.add(doc_tag)
        db.commit()
        db.refresh(doc_tag)
        
        return {"message": "Tag added successfully", "tag": doc_tag.tag_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tag: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add tag: {str(e)}")


@router.delete("/{document_id}/tags/{tag_name}")
async def remove_tag_from_document(
    document_id: int,
    tag_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a tag from a document"""
    try:
        doc_tag = db.query(DocumentTag).filter(
            DocumentTag.user_id == current_user.user_id,
            DocumentTag.document_id == document_id,
            DocumentTag.tag_name == tag_name
        ).first()
        
        if not doc_tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        db.delete(doc_tag)
        db.commit()
        
        return {"message": "Tag removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing tag: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove tag: {str(e)}")


@router.get("/{document_id}/tags")
async def get_document_tags(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tags for a document"""
    try:
        tags = db.query(DocumentTag).filter(
            DocumentTag.user_id == current_user.user_id,
            DocumentTag.document_id == document_id
        ).order_by(DocumentTag.tag_name).all()
        
        return [{"tag_name": tag.tag_name, "created_at": tag.created_at.isoformat()} for tag in tags]
        
    except Exception as e:
        logger.error(f"Error getting tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get tags: {str(e)}")


@router.get("/{document_id}/export")
async def export_document(
    document_id: int,
    format: str = Query(..., regex="^(pdf|docx|doc)$"),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export a document to PDF, DOCX, or DOC format"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        base_dir = Path("/Users/nhathao/Documents/NienLuan/Data/Document-Word")
        
        if document.file_url:
            file_path = base_dir / document.file_url
            try:
                file_path = file_path.resolve()
                base_dir = base_dir.resolve()
                file_path.relative_to(base_dir)
            except (ValueError, OSError):
                raise HTTPException(status_code=403, detail="Invalid file path")
            
            if file_path.exists() and file_path.is_file():
                file_ext = file_path.suffix.lower()
                if (format == "pdf" and file_ext == ".pdf") or \
                   (format == "docx" and file_ext == ".docx") or \
                   (format == "doc" and (file_ext == ".doc" or ".pdf.doc" in file_path.name.lower())):
                    media_type = {
                        "pdf": "application/pdf",
                        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "doc": "application/msword"
                    }.get(format, "application/octet-stream")
                    
                    return FileResponse(
                        path=str(file_path),
                        media_type=media_type,
                        filename=f"{document.title}_{document.id}.{format}"
                    )
        
        if not document.html_content and not document.text_content:
            raise HTTPException(status_code=404, detail="No content available for export")
        
        raise HTTPException(
            status_code=501,
            detail=f"Export to {format} from content is not yet implemented. Please use the original file if available."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{document_id}/share")
async def get_share_link(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get shareable link for a document"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document.source_url:
            return {
                "share_url": document.source_url,
                "type": "source"
            }
        else:
            return {
                "share_url": f"/document-viewer/{document_id}",
                "type": "internal"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting share link: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get share link: {str(e)}")

