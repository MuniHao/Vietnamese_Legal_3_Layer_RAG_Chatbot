"""
Query Enhancement Utility
Enhance query with conversation context - use Gemini API
"""
import os
import logging
import re
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

def enhance_query_simple(original_query: str, conversation_context: Optional[str] = None) -> str:
    """
    Simple query enhancement by extracting information from conversation context
    using pattern matching
    
    Args:
        original_query: Original query
        conversation_context: Conversation history
        
    Returns:
        Enhanced query
    """
    if not conversation_context:
        logger.debug("No conversation context provided for query enhancement")
        return original_query
    
    # Debug: log conversation context để kiểm tra
    logger.debug(f"Conversation context for enhancement (first 500 chars): {conversation_context[:500]}")
    
    # Patterns để detect references
    reference_patterns = [
        r'câu hỏi (tôi )?(vừa|mới|trước) (hỏi|đặt)',
        r'câu hỏi (trước|trước đó)',
        r'như (tôi )?(đã|vừa) hỏi',
        r'như (câu hỏi )?(trước|trước đó)',
        r'về (điều|vấn đề) (đó|này|ấy)',
        r'về (vùng|luật|điều|khoản) (đó|này|ấy)',
    ]
    
    # Check nếu query có reference patterns
    query_lower = original_query.lower()
    has_reference = any(re.search(pattern, query_lower) for pattern in reference_patterns)
    
    if not has_reference:
        return original_query
    
    # Extract previous user question from conversation context
    # Look for patterns: "user:" or "Người dùng:" (both English and Vietnamese)
    user_patterns = [
        r'(?:user|người dùng):\s*(.+?)(?:\n|assistant|trợ lý|$)',
        r'(?:user|người dùng):\s*(.+?)(?:\n\n|$)',
    ]
    
    all_matches = []
    for pattern in user_patterns:
        matches = re.findall(pattern, conversation_context, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        all_matches.extend(matches)
    
    if all_matches:
        # Get the previous message before the current one
        # If there are 2+ messages, take the second to last message
        # If there is only 1 message, take that message
        if len(all_matches) >= 2:
            previous_user_message = all_matches[-2].strip()
        else:
            previous_user_message = all_matches[-1].strip()
        
        # Clean up: remove extra whitespace and newlines
        previous_user_message = re.sub(r'\s+', ' ', previous_user_message).strip()
        
        # Ensure this is not the same as the current query
        if previous_user_message and previous_user_message.lower() != original_query.lower():
            logger.info(f"Simple query enhancement: '{original_query}' -> '{previous_user_message}'")
            return previous_user_message
    
    # If not found, try extracting from the previous assistant response
    # Look for patterns: "assistant:" or "Trợ lý:" (both English and Vietnamese)
    assistant_patterns = [
        r'(?:assistant|trợ lý):\s*(.+?)(?:\n|user|người dùng|$)',
        r'(?:assistant|trợ lý):\s*(.+?)(?:\n\n|$)',
    ]
    
    all_assistant_matches = []
    for pattern in assistant_patterns:
        matches = re.findall(pattern, conversation_context, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        all_assistant_matches.extend(matches)
    
    if all_assistant_matches:
        # Get the response before the current one
        if len(all_assistant_matches) >= 2:
            previous_response = all_assistant_matches[-2].strip()
        else:
            previous_response = all_assistant_matches[-1].strip()
        
        # Clean up
        previous_response = re.sub(r'\s+', ' ', previous_response).strip()
        
        # Extract legal keywords from the response
        legal_keywords = re.findall(
            r'(vùng đặc quyền|luật|nghị định|thông tư|điều|khoản|hải lý|biển|kinh tế|đặc quyền|200 hải lý)',
            previous_response,
            re.IGNORECASE
        )
        if legal_keywords:
            # Create query from keywords
            enhanced = ' '.join(legal_keywords[:5])  # Take first 5 keywords
            logger.info(f"Simple query enhancement from response: '{original_query}' -> '{enhanced}'")
            return enhanced
        
        # If no keywords found, try extracting question mentions
        question_mentions = re.findall(
            r'(vùng đặc quyền kinh tế.*?hải lý|chiều rộng.*?vùng đặc quyền|rộng.*?hải lý)',
            previous_response,
            re.IGNORECASE
        )
        if question_mentions:
            enhanced = question_mentions[0]
            logger.info(f"Simple query enhancement from question mention: '{original_query}' -> '{enhanced}'")
            return enhanced
    
    return original_query

def enhance_query_with_gemini(original_query: str, conversation_context: Optional[str] = None) -> Optional[str]:
    """
    Enhance query using Gemini API
    
    Args:
        original_query: Original query
        conversation_context: Conversation history
        
    Returns:
        Enhanced query or None if it fails
    """
    try:
        # Get Gemini API key
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY not found, skipping Gemini query enhancement")
            return None
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')
        model = genai.GenerativeModel(model_name)
        
        # Generate prompt
        if conversation_context:
            prompt = f"""Bạn là trợ lý tìm kiếm pháp lý. Hãy viết lại câu hỏi sau để tìm kiếm tốt hơn trong cơ sở dữ liệu pháp luật.

Lịch sử hội thoại:
{conversation_context}

Câu hỏi gốc: {original_query}

Hãy viết lại câu hỏi để:
1. Làm rõ ý định tìm kiếm (nếu có reference như "câu hỏi trước", hãy thay bằng câu hỏi cụ thể)
2. Thêm từ khóa pháp lý liên quan nếu cần
3. Giữ nguyên ý nghĩa gốc
4. Tối ưu cho tìm kiếm semantic

Chỉ trả lời câu hỏi đã viết lại, không giải thích thêm:"""
        else:
            prompt = f"""Bạn là trợ lý tìm kiếm pháp lý. Hãy viết lại câu hỏi sau để tìm kiếm tốt hơn trong cơ sở dữ liệu pháp luật.

Câu hỏi gốc: {original_query}

Hãy viết lại câu hỏi để:
1. Làm rõ ý định tìm kiếm
2. Thêm từ khóa pháp lý liên quan nếu cần
3. Giữ nguyên ý nghĩa gốc
4. Tối ưu cho tìm kiếm semantic

Chỉ trả lời câu hỏi đã viết lại, không giải thích thêm:"""
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_output_tokens": 200,
            }
        )
        
        if response and response.text:
            enhanced_query = response.text.strip()
            # Remove quotes if present
            enhanced_query = enhanced_query.strip('"').strip("'")
            
            if enhanced_query and enhanced_query != original_query:
                logger.info(f"Gemini query enhancement: '{original_query}' -> '{enhanced_query}'")
                return enhanced_query
        
        return None
        
    except Exception as e:
        logger.debug(f"Gemini query enhancement failed: {e}")
        return None

def enhance_query(original_query: str, conversation_context: Optional[str] = None, use_gemini: bool = True) -> str:
    """
    Enhance query using conversation context
    Try Gemini API first, fallback to simple enhancement
    
    Args:
        original_query: Original query
        conversation_context: Conversation history
        use_gemini: Whether to use Gemini API (default: True)
        
    Returns:
        Enhanced query
    """
    # If no context, return original
    if not conversation_context:
        return original_query
    
    # Try Gemini API first (if enabled)
    if use_gemini:
        enhanced = enhance_query_with_gemini(original_query, conversation_context)
        if enhanced:
            return enhanced
    
    # Fallback to simple enhancement
    return enhance_query_simple(original_query, conversation_context)

