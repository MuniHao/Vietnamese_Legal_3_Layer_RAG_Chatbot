"""
Helper utilities to map conversation_id (string) ↔ session_id (integer)
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def get_session_id_from_conversation_id(
    conversation_id: str,
    db: Session,
    user_id: Optional[int] = None
) -> Optional[int]:
    """
    Map conversation_id (string) to session_id (integer)
    
    Args:
        conversation_id: Conversation ID string (e.g., "conv_1234567890" or "session_123")
        db: Database session
        user_id: Optional user_id to validate that the session belongs to that user
        
    Returns:
        session_id (integer) or None if not found
    """
    if not conversation_id:
        return None
    
    # If conversation_id is numeric, it might directly be a session_id
    try:
        session_id = int(conversation_id)
        # Validate that session_id exists and belongs to the user (if user_id is provided)
        if user_id:
            try:
                query = text("""
                    SELECT session_id
                    FROM chat_sessions
                    WHERE session_id = :session_id AND user_id = :user_id
                """)
                result = db.execute(query, {"session_id": session_id, "user_id": user_id}).fetchone()
                if result:
                    return session_id
                else:
                    logger.debug(f"Session {session_id} does not belong to user {user_id}")
                    return None
            except Exception as e:
                logger.debug(f"Error validating session {session_id}: {e}")
                return None
        return session_id
    except ValueError:
        pass
    
    # If conversation_id has the format "session_{id}", extract session_id
    if conversation_id.startswith("session_"):
        try:
            session_id = int(conversation_id.replace("session_", ""))
            # Validate that session_id exists and belongs to the user (if user_id is provided)
            if user_id:
                try:
                    query = text("""
                        SELECT session_id
                        FROM chat_sessions
                        WHERE session_id = :session_id AND user_id = :user_id
                    """)
                    result = db.execute(query, {"session_id": session_id, "user_id": user_id}).fetchone()
                    if result:
                        return session_id
                    else:
                        logger.debug(f"Session {session_id} does not belong to user {user_id}")
                        return None
                except Exception as e:
                    logger.debug(f"Error validating session {session_id}: {e}")
                    return None
            return session_id
        except ValueError:
            pass
    
    # If no format matches, return None
    # DO NOT fallback to the user's latest session to avoid retrieving context from an old session
    logger.debug(f"Could not find session_id from conversation_id: {conversation_id}")
    return None


def get_conversation_id_from_session_id(
    session_id: int,
    db: Session
) -> Optional[str]:
    """
    Map session_id (integer) to conversation_id (string)
    Generate a conversation_id from session_id for use in buffer memory
    
    Args:
        session_id: Session ID integer
        db: Database session
        
    Returns:
        conversation_id string (e.g., "session_123")
    """
    if not session_id:
        return None
    
    # Generate conversation_id from session_id
    return f"session_{session_id}"


def get_or_create_conversation_id(
    session_id: Optional[int],
    conversation_id: Optional[str],
    db: Session,
    user_id: Optional[int] = None
) -> tuple[Optional[str], Optional[int]]:
    """
    Get or create conversation_id and session_id mapping
    
    Args:
        session_id: Session ID (if available)
        conversation_id: Conversation ID (if available)
        db: Database session
        user_id: Optional user_id
        
    Returns:
        Tuple (conversation_id, session_id)
    """
    # If session_id exists, generate conversation_id from it
    if session_id:
        conv_id = get_conversation_id_from_session_id(session_id, db)
        return (conv_id, session_id)
    
    # If conversation_id exists, find session_id
    if conversation_id:
        sess_id = get_session_id_from_conversation_id(conversation_id, db, user_id)
        if sess_id:
            return (conversation_id, sess_id)
        # If session_id is not found, keep the original conversation_id
        return (conversation_id, None)
    
    # If neither exists, return None
    return (None, None)