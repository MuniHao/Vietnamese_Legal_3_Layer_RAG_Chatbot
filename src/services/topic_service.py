"""
Topic Service
Track and using topic history to improve context
"""
import os
import logging
import requests
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import re

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

class TopicService:
    """Service use to track and topic history"""
    
    def __init__(self):
        self.enabled = os.getenv('USE_TOPIC_HISTORY', 'True').lower() == 'true'
        self.topic_model = os.getenv('TOPIC_MODEL', 'qwen2.5:1.5b')  # Small Model to extract topics
        self.topic_url = os.getenv('LOCAL_LLM_URL', 'http://localhost:11434')
        self.max_topics_per_conversation = int(os.getenv('MAX_TOPICS_PER_CONVERSATION', '5'))
        
        # Legal topic keywords để hỗ trợ extraction
        self.legal_topics = {
            'lao động': ['lao động', 'hợp đồng lao động', 'tiền lương', 'sa thải', 'thôi việc'],
            'đất đai': ['đất đai', 'quyền sử dụng đất', 'tranh chấp đất', 'giấy chứng nhận', 'sổ đỏ'],
            'hôn nhân': ['hôn nhân', 'ly hôn', 'kết hôn', 'giấy chứng nhận kết hôn'],
            'thuế': ['thuế', 'nộp thuế', 'khai thuế', 'thuế thu nhập'],
            'bảo hiểm': ['bảo hiểm', 'bảo hiểm xã hội', 'bảo hiểm y tế', 'bảo hiểm thất nghiệp'],
            'tranh chấp': ['tranh chấp', 'khởi kiện', 'tòa án', 'giải quyết tranh chấp'],
            'hành chính': ['thủ tục hành chính', 'giấy tờ', 'hồ sơ', 'cơ quan có thẩm quyền']
        }
        
        if not self.enabled:
            logger.info("Topic history is disabled")
    
    def extract_topics(self, query: str, response: Optional[str] = None) -> List[str]:
        """
        Extract topics từ query và response
        
        Args:
            query: User query
            response: Assistant response (optional)
            
        Returns:
            List of topics
        """
        if not self.enabled:
            return []
        
        topics = []
        
        # 1. Extract by keyword matching
        query_lower = query.lower()
        for topic, keywords in self.legal_topics.items():
            if any(keyword in query_lower for keyword in keywords):
                if topic not in topics:
                    topics.append(topic)
        
        # 2. Extract by LLM if needed
        if len(topics) < 2 and response:
            try:
                llm_topics = self._extract_topics_with_llm(query, response)
                for topic in llm_topics:
                    if topic not in topics:
                        topics.append(topic)
            except Exception as e:
                logger.debug(f"LLM topic extraction failed: {e}")
        
        return topics[:self.max_topics_per_conversation]
    
    def _extract_topics_with_llm(self, query: str, response: str) -> List[str]:
        """Extract topics using LLM"""
        try:
            prompt = f"""Hãy xác định các chủ đề pháp lý chính từ câu hỏi và câu trả lời sau:

Câu hỏi: {query}
Câu trả lời: {response[:500]}

Hãy liệt kê 2-3 chủ đề chính (mỗi chủ đề 1-3 từ). Trả lời dạng danh sách, mỗi dòng một chủ đề.

Chủ đề:"""
            
            payload = {
                "model": self.topic_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 100
                }
            }
            
            response_llm = requests.post(
                f"{self.topic_url}/api/chat",
                json=payload,
                timeout=10
            )
            
            if response_llm.status_code == 200:
                result = response_llm.json()
                
                # Handle different response formats from Ollama
                content = ""
                if isinstance(result, dict):
                    message = result.get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content', '').strip()
                    elif isinstance(message, str):
                        content = message.strip()
                    if not content:
                        content = result.get('response', '').strip()
                elif isinstance(result, str):
                    content = result.strip()
                
                # Parse topics from response
                topics = []
                for line in content.split('\n'):
                    line = line.strip()
                    # Remove numbering and formatting
                    line = re.sub(r'^[-•\d\.\)]\s*', '', line)
                    if line and len(line) < 30:  # Topic shouldn't too long
                        topics.append(line.lower())
                
                return topics[:3]
            
            return []
            
        except Exception as e:
            logger.debug(f"Error in LLM topic extraction: {e}")
            return []
    
    def get_topic_history(self, session_id: Optional[int], db: Session) -> List[str]:
        """
        Get topic history from database
        
        Args:
            session_id: Session ID (integer) - REQUIRED to query database
            db: Database session
            
        Returns:
            List of topics
        """
        if not self.enabled:
            return []
        
        if not session_id:
            # session_id do not exist → cannot query database
            return []
        
        try:
            # Query by session_id 
            query = text("""
                SELECT DISTINCT topic_name
                FROM conversation_topics
                WHERE session_id = :session_id
                ORDER BY last_mentioned DESC
                LIMIT :max_topics
            """)
            
            results = db.execute(query, {
                "session_id": session_id,
                "max_topics": self.max_topics_per_conversation
            }).fetchall()
            
            topics = [row.topic_name for row in results]
            return topics
            
        except Exception as e:
            logger.debug(f"Error getting topic history (table may not exist): {e}")
            return []
    
    def save_topics(self, session_id: int, topics: List[str], db: Session):
        """
        Save topics into database
        
        Args:
            session_id: Session ID (integer) - REQUIRED
            topics: List of topics
            db: Database session
        """
        if not self.enabled or not topics:
            return
        
        if not session_id:
            logger.warning("Cannot save topics: session_id is required")
            return
        
        try:
            for topic in topics:
                topic_name = topic.lower()
                # Insert or update topic
                query = text("""
                    INSERT INTO conversation_topics (session_id, topic_name, first_mentioned, last_mentioned, mention_count)
                    VALUES (:session_id, :topic_name, :first_mentioned, :last_mentioned, 1)
                    ON CONFLICT (session_id, topic_name) 
                    DO UPDATE SET 
                        last_mentioned = :last_mentioned,
                        mention_count = conversation_topics.mention_count + 1
                """)
                
                now = datetime.utcnow()
                db.execute(query, {
                    "session_id": session_id,
                    "topic_name": topic_name,
                    "first_mentioned": now,
                    "last_mentioned": now
                })
            
            db.commit()
            logger.info(f"Saved {len(topics)} topics for session {session_id}")
            
        except Exception as e:
            logger.warning(f"Error saving topics (table may not exist): {e}")
            db.rollback()
    
    def get_topic_context(self, session_id: Optional[int], db: Session) -> str:
        """
        Get topic context to add to the RAG prompt
        
        Args:
            session_id: Session ID (integer) - REQUIRED to query database
            db: Database session
            
        Returns:
            Topic context string
        """
        if not self.enabled:
            return ""
        
        topics = self.get_topic_history(session_id, db)
        
        if topics:
            topics_text = ", ".join(topics)
            return f"**Topics discussed:** {topics_text}"
        
        return ""
    
    def enhance_query_with_topics(self, query: str, topics: List[str]) -> str:
        """
        Enhance query with topic context
        
        Args:
            query: Original query
            topics: List of topics
            
        Returns:
            Enhanced query
        """
        if not self.enabled or not topics:
            return query
        
        # Adding topic keywords into query to improve retrieval
        topics_text = " ".join(topics)
        enhanced = f"{query} {topics_text}"
        
        logger.debug(f"Enhanced query with topics: {enhanced}")
        return enhanced

# Singleton instance
_topic_service = None

def get_topic_service() -> TopicService:
    """Get singleton instance of TopicService"""
    global _topic_service
    if _topic_service is None:
        _topic_service = TopicService()
    return _topic_service
