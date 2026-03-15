"""
Memory Service
Summary-based memory with conversation summarization
"""
import os
import logging
import requests
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

class MemoryService:
    """Service for managing conversation memory with summarization"""
    
    def __init__(self):
        self.enabled = os.getenv('USE_SUMMARY_MEMORY', 'True').lower() == 'true'
        self.summary_model = os.getenv('SUMMARY_MODEL', 'qwen2.5:1.5b') # Small model used for summarization
        self.summary_url = os.getenv('LOCAL_LLM_URL', 'http://localhost:11434')
        self.max_messages_before_summary = int(os.getenv('MAX_MESSAGES_BEFORE_SUMMARY', '10'))
        self.summary_threshold = int(os.getenv('SUMMARY_THRESHOLD', '8'))  # Summarize when there are >= 8 messages
        
        if not self.enabled:
            logger.info("Summary-based memory is disabled")
    
    def get_conversation_summary(self, session_id: Optional[int], db: Session) -> Optional[str]:
        """
        Get conversation summary from the database
        
        Args:
            session_id: Session ID (integer) - REQUIRED for querying the database
            db: Database session
            
        Returns:
            Summary string or None
        """
        if not self.enabled:
            return None
        
        if not session_id:
            # No session_id → cannot query the database
            return None
        
        try:
            # Query using session_id (correct schema)
            query = text("""
                SELECT summary_text
                FROM conversation_summaries
                WHERE session_id = :session_id
                ORDER BY last_updated DESC
                LIMIT 1
            """)
            
            result = db.execute(query, {"session_id": session_id}).fetchone()
            
            if result:
                return result.summary_text
            return None
            
        except Exception as e:
            # Table may not exist yet
            logger.debug(f"Error getting summary (table may not exist): {e}")
            return None
    
    def save_conversation_summary(self, session_id: int, summary: str, message_count: int, db: Session):
        """
        Save conversation summary to the database
        
        Args:
            session_id: Session ID (integer) - REQUIRED
            summary: Summary text
            message_count: Number of messages summarized
            db: Database session
        """
        if not self.enabled:
            return
        
        if not session_id:
            logger.warning("Cannot save summary: session_id is required")
            return
        
        try:
            # Insert or update summary using session_id (correct schema)
            query = text("""
                INSERT INTO conversation_summaries (session_id, summary_text, message_count, last_updated, created_at)
                VALUES (:session_id, :summary_text, :message_count, :last_updated, :created_at)
                ON CONFLICT (session_id) 
                DO UPDATE SET 
                    summary_text = :summary_text, 
                    message_count = :message_count,
                    last_updated = :last_updated
            """)
            
            db.execute(query, {
                "session_id": session_id,
                "summary_text": summary,
                "message_count": message_count,
                "last_updated": datetime.utcnow(),
                "created_at": datetime.utcnow()
            })
            db.commit()
            
            logger.info(f"Saved summary for session {session_id} ({message_count} messages)")
            
        except Exception as e:
            logger.warning(f"Error saving summary (table may not exist): {e}")
            db.rollback()
    
    def summarize_conversation(
        self, 
        messages: List[Dict[str, Any]],
        existing_summary: Optional[str] = None
    ) -> str:
        """
        Summarize conversation messages
        
        Args:
            messages: List of messages (dict with 'role' and 'content')
            existing_summary: Existing summary to update
            
        Returns:
            Summary string
        """
        if not self.enabled or not messages:
            return ""
        
        try:
            # Format messages
            messages_text = ""
            for msg in messages[-self.max_messages_before_summary:]:  # Only use the most recent messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                messages_text += f"{role}: {content}\n"
            
            # Tạo prompt
            if existing_summary:
                prompt = f"""Hãy cập nhật tóm tắt cuộc hội thoại pháp lý dựa trên các tin nhắn mới.

Tóm tắt hiện tại:
{existing_summary}

Các tin nhắn mới:
{messages_text}

Hãy cập nhật tóm tắt để:
1. Giữ lại thông tin quan trọng từ tóm tắt cũ
2. Thêm thông tin mới từ các tin nhắn
3. Tóm tắt ngắn gọn (tối đa 200 từ)
4. Tập trung vào các chủ đề pháp lý được thảo luận

Tóm tắt đã cập nhật:"""
            else:
                prompt = f"""Hãy tóm tắt cuộc hội thoại pháp lý sau:

Các tin nhắn:
{messages_text}

Hãy tóm tắt:
1. Chủ đề chính được thảo luận
2. Các câu hỏi và câu trả lời quan trọng
3. Các văn bản pháp luật được đề cập
4. Tóm tắt ngắn gọn (tối đa 200 từ)

Tóm tắt:"""
            
            # Call summary model
            payload = {
                "model": self.summary_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 300  # Summary does not need to be long
                }
            }
            
            response = requests.post(
                f"{self.summary_url}/api/chat",
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle different response formats from Ollama
                summary = ""
                if isinstance(result, dict):
                    message = result.get('message', {})
                    if isinstance(message, dict):
                        summary = message.get('content', '').strip()
                    elif isinstance(message, str):
                        summary = message.strip()
                    if not summary:
                        summary = result.get('response', '').strip()
                elif isinstance(result, str):
                    summary = result.strip()
                
                if summary:
                    logger.info(f"Generated summary: {len(summary)} chars")
                    return summary
                else:
                    return existing_summary or ""
            else:
                logger.warning(f"Summary generation failed with status {response.status_code}")
                return existing_summary or ""
                
        except Exception as e:
            logger.warning(f"Error in summarization: {e}")
            return existing_summary or ""
    
    def should_summarize(self, message_count: int) -> bool:
        """
        Check whether summarization should be triggered
        
        Args:
            message_count: Current number of messages
            
        Returns:
            True if summarization should be performed
        """
        if not self.enabled:
            return False
        
        return message_count >= self.summary_threshold and message_count % self.max_messages_before_summary == 0
    
    def get_memory_context(
        self, 
        session_id: Optional[int],
        db: Session,
        recent_messages: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Get memory context for RAG (summary + recent messages)
        
        Args:
            session_id: Session ID (integer) - REQUIRED for querying the database
            db: Database session
            recent_messages: Recent messages (optional)
            
        Returns:
            Memory context string
        """
        if not self.enabled:
            return ""
        
        context_parts = []
        
        # Get summary from database (requires session_id)
        if session_id:
            summary = self.get_conversation_summary(session_id, db)
            if summary:
                context_parts.append(f"**Conversation summary:**\n{summary}")
        
        # Add recent messages if available
        if recent_messages:
            recent_text = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in recent_messages[-3:]  # Last 3 messages
            ])
            context_parts.append(f"**Recent messages:**\n{recent_text}")
        
        return "\n\n".join(context_parts) if context_parts else ""

# Singleton instance
_memory_service = None

def get_memory_service() -> MemoryService:
    """Get singleton instance of MemoryService"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
