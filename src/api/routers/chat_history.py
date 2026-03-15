"""
Chat history and session management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from models.database import get_db, User, ChatSession, ChatMessage, MessageSender
from api.auth_dependencies import get_current_user, get_current_user_optional
from api.models import ChatSessionCreate, ChatSessionResponse, ChatMessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat History"])


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get user's chat sessions - returns empty list if not authenticated"""
    try:
        if not current_user:
            logger.info("Request to /api/chat/sessions without authentication - returning empty list")
            return []
        
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id
        ).order_by(ChatSession.created_at.desc()).all()
        
        session_responses = []
        for session in sessions:
            message_count = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.session_id
            ).count()
            
            session_responses.append(ChatSessionResponse(
                session_id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                message_count=message_count
            ))
        
        return session_responses
        
    except Exception as e:
        logger.error(f"Error getting chat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat sessions")


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get messages from a specific chat session"""
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        return [
            ChatMessageResponse(
                message_id=msg.message_id,
                sender=msg.sender.value if isinstance(msg.sender, MessageSender) else msg.sender,
                message_text=msg.message_text,
                created_at=msg.created_at,
                confidence=msg.confidence
            )
            for msg in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat messages")


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session"""
    try:
        session = ChatSession(
            user_id=current_user.user_id,
            title=session_data.title
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse(
            session_id=session.session_id,
            title=session.title,
            created_at=session.created_at,
            message_count=0
        )
        
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create chat session")


@router.put("/sessions/{session_id}")
async def update_chat_session(
    session_id: int,
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chat session title"""
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session.title = session_data.title
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse(
            session_id=session.session_id,
            title=session.title,
            created_at=session.created_at,
            message_count=len(session.messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update chat session")


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session"""
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return {"message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete chat session")

