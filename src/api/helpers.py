"""
Helper functions for API endpoints
"""
import logging
import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from utils.text_processor import get_text_processor

logger = logging.getLogger(__name__)
text_processor = get_text_processor()


def process_conversation_services(
    session_id: int,
    user_message: str,
    assistant_response: str,
    db: Session,
    message_count: int = 0
):
    """
    Processing memory summarization and topic extraction after save the conversation
    
    Args:
        session_id: Session ID (integer) - REQUIRED to save into the database
        user_message: User message
        assistant_response: Assistant response
        db: Database session
        message_count: Current message count (for summarization trigger)
    """
    if not session_id:
        logger.warning("Cannot process conversation services: session_id is required")
        return
    
    # Validate session exists
    from models.database import ChatSession
    session_exists = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()
    
    if not session_exists:
        logger.warning(f"Session {session_id} does not exist, skipping conversation services")
        return
    
    try:
        logger.info(f"🔄 Processing conversation services for session {session_id} (message_count={message_count})")
        # Import services
        from services.memory_service import get_memory_service
        from services.topic_service import get_topic_service
        
        memory_service = get_memory_service()
        topic_service = get_topic_service()
        
        # 1. Extract và lưu topics (cần session_id)
        if topic_service.enabled:
            try:
                topics = topic_service.extract_topics(user_message, assistant_response)
                if topics:
                    topic_service.save_topics(session_id, topics, db)
                    logger.info(f"Extracted and saved {len(topics)} topics for session {session_id}: {topics}")
                else:
                    logger.debug(f"No topics extracted for session {session_id}")
            except Exception as e:
                logger.error(f"Topic extraction failed for session {session_id}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # 2. Summarize conversation if need (cần session_id)
        if memory_service.enabled and memory_service.should_summarize(message_count):
            try:
                # Get messages from database by session_id
                from models.database import ChatMessage, MessageSender
                messages_list = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at.asc()).limit(
                    memory_service.max_messages_before_summary
                ).all()
                
                messages = [
                    {
                        "role": "user" if msg.sender == MessageSender.USER else "assistant",
                        "content": msg.message_text
                    }
                    for msg in messages_list
                ]
                
                if messages:
                    # Get existing summary (session_id neeeded)
                    existing_summary = memory_service.get_conversation_summary(session_id, db)
                    
                    # Generate new summary
                    summary = memory_service.summarize_conversation(messages, existing_summary)
                    
                    if summary:
                        memory_service.save_conversation_summary(session_id, summary, message_count, db)
                        logger.info(f"Generated and saved conversation summary for session {session_id} ({message_count} messages)")
                    else:
                        logger.debug(f"No summary generated for session {session_id}")
            except Exception as e:
                logger.error(f"Conversation summarization failed for session {session_id}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
    except ImportError:
        # Services are not available, skip
        pass
    except Exception as e:
        logger.warning(f"Error processing conversation services: {e}")


def _validate_document_relevance(query: str, doc: Dict[str, Any]) -> bool:
    """Validate if document is actually relevant to the query using strict keyword matching"""
    query_lower = query.lower()
    doc_title = doc.get('title', '').lower()
    doc_content = doc.get('content', '').lower()
    
    # Use VietnameseTextProcessor to detect important phrases
    query_phrases, doc_phrases = text_processor.find_phrase_matches(
        query, 
        doc_content[:3000],
        doc_title
    )
    
    if query_phrases and doc_phrases:
        return True
    
    if query_phrases and not doc_phrases:
        similarity = doc.get('similarity_score', 0.0)
        if similarity >= 0.65:
            return True
        return False
    
    query_terms = text_processor.extract_key_terms(
        query_lower,
        remove_stop_words=True,
        remove_generic_terms=True
    )
    
    similarity = doc.get('similarity_score', 0.0)
    similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.35'))
    
    if len(query_terms) == 0:
        return similarity >= similarity_threshold + 0.15
    
    title_matches = sum(1 for term in query_terms if term in doc_title and len(term) > 2)
    content_matches = sum(1 for term in query_terms if term in doc_content[:3000] and len(term) > 2)
    
    total_matches = title_matches + content_matches
    
    if title_matches >= 1 and total_matches >= 2:
        return True
    
    if total_matches >= 3:
        return True
    
    if total_matches >= 2 and similarity >= similarity_threshold:
        return True
    
    if title_matches >= 1 and similarity >= 0.5:
        return True
    
    if total_matches >= 1 and similarity >= 0.55:
        return True
    
    if similarity >= 0.65:
        longer_terms = [term for term in query_terms if len(term) >= 4]
        if longer_terms:
            if any(term in doc_content[:3000] for term in longer_terms):
                return True
    
    return False


def _filter_relevant_documents(query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter documents to only include truly relevant ones"""
    relevant_docs = []
    for doc in docs:
        is_relevant = _validate_document_relevance(query, doc)
        if is_relevant:
            relevant_docs.append(doc)
            logger.info(f"Document accepted: {doc.get('title', 'N/A')[:50]}... (similarity: {doc.get('similarity_score', 0.0):.3f})")
        else:
            logger.warning(f"Document filtered out: {doc.get('title', 'N/A')[:50]}... (similarity: {doc.get('similarity_score', 0.0):.3f}, low relevance)")
    
    return relevant_docs


def _format_sources_section(similar_docs: List[Dict[str, Any]]) -> str:
    """Format sources section for response"""
    if not similar_docs:
        return ""
    
    valid_docs = [doc for doc in similar_docs if isinstance(doc, dict)]
    if not valid_docs:
        return ""
    
    seen = set()
    unique_docs = []
    for doc in valid_docs:
        metadata = doc.get('metadata', {})
        if isinstance(metadata, dict):
            document_id = metadata.get('document_id')
        else:
            document_id = None
        
        if document_id:
            key = document_id
        else:
            key = (doc.get('title', ''), doc.get('source_url', ''))
        
        if key not in seen:
            seen.add(key)
            unique_docs.append(doc)
    
    sources_parts = []
    
    for doc in unique_docs[:5]:
        title = doc.get('title', 'N/A')
        source_url = doc.get('source_url', '')
        
        metadata = doc.get('metadata', {})
        if isinstance(metadata, dict):
            document_id = metadata.get('document_id')
        else:
            document_id = None
        
        if document_id:
            sources_parts.append(f"- [{title}](lawchat://document/{document_id})")
        elif source_url:
            sources_parts.append(f"- [{title}]({source_url})")
        else:
            sources_parts.append(f"- {title}")
    
    return "\n".join(sources_parts)


def _generate_fallback_answer(query: str, similar_docs: List[Dict[str, Any]]) -> str:
    """Generate a simple fallback answer when LLM fails"""
    valid_docs = [doc for doc in similar_docs if isinstance(doc, dict)]
    
    if not valid_docs:
        return f"""Xin lỗi, tôi không tìm thấy thông tin liên quan trực tiếp đến câu hỏi: "{query}".

Để được tư vấn chính xác hơn, bạn nên:
1. Thử diễn đạt lại câu hỏi một cách cụ thể hơn
2. Liên hệ trực tiếp với cơ quan có thẩm quyền liên quan
3. Tham khảo ý kiến của luật sư chuyên nghiệp"""

    top_doc = valid_docs[0]
    doc_title = top_doc.get('title', '')
    doc_content = top_doc.get('content', '')
    
    answer_parts = []
    
    if doc_content:
        sentences = doc_content.split('.')
        extracted_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30 and extracted_count < 3:
                answer_parts.append(sentence + ".")
                extracted_count += 1
        
        if extracted_count == 0:
            answer_parts.append(f"Dựa trên văn bản pháp luật: {doc_title}.")
    else:
        answer_parts.append(f"Dựa trên văn bản pháp luật: {doc_title}.")
    
    answer_parts.append(f"Dựa theo {doc_title}.")
    
    return "\n".join(answer_parts)

