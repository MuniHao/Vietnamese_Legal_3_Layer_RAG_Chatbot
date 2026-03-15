"""
Chat endpoints - main chat functionality with Gemini API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timedelta
import logging
import os
import time

from models.database import get_db, User, ChatSession, ChatMessage, MessageSender
from api.auth_dependencies import get_current_user_optional
from api.models import ChatMessageRequest, ChatResponse
from services.rag_service import rag_service
from utils.query_enhancer import enhance_query
from utils.conversation_mapper import get_session_id_from_conversation_id, get_conversation_id_from_session_id
from api.helpers import (
    process_conversation_services,
    _filter_relevant_documents,
    _format_sources_section,
    _generate_fallback_answer
)
from utils.citation_manager import get_citation_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# Chat endpoints - endpoint /api/chat/gemini kept here temporarily
# TODO: Move to routers/chat.py after testing
@router.post("/gemini", response_model=ChatResponse)
async def chat_gemini(
    message: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Chat endpoint using Google Gemini API with RAG 3 tầng"""
    # Timing tracking
    timing = {}
    total_start_time = time.time()
    
    try:
        logger.info(f"Received Gemini chat message: {message.message[:50]}...")
        
        # Generate conversation ID if not provided
        conversation_id = message.conversation_id or f"conv_{datetime.utcnow().timestamp()}"
        
        # Map conversation_id → session_id if there is an authenticated user
        # IMPORTANT: Only retrieve session_id if conversation_id matches the current session
        # Avoid falling back to the latest session to prevent retrieving context from the old session
        session_id = None
        if current_user:
            # Find session_id from conversation_id (only if it's an exact match)
            session_id = get_session_id_from_conversation_id(conversation_id, db, current_user.user_id)
            # If not found, session_id = None → a new session will be created after saving the message.
        
        # Get conversation context ONLY from the current session (if a valid session_id exists)
        # Do not get context if a new session is being created
        timing['get_context_start'] = time.time()
        conversation_context = None
        if session_id:
            # Get the context from the current session only, not from other sessions.
            conversation_context = rag_service.get_conversation_context(
                conversation_id or "",
                db=db,
                session_id=session_id
            )
            if conversation_context:
                logger.info(f"Lấy conversation context từ session_id={session_id} ({len(conversation_context)} chars)")
            else:
                logger.debug(f"Không có conversation context cho session_id={session_id} (session mới hoặc chưa có messages)")
        elif conversation_id:
            # If there is no session_id (either not authenticated or a new session),
            # only use buffer memory if an old conversation_id is available
            conversation_context = rag_service.get_conversation_context(
                conversation_id,
                db=db,
                session_id=None
            )
            if conversation_context:
                logger.info(f"Lấy conversation context từ buffer memory (conversation_id={conversation_id})")
        timing['get_context'] = time.time() - timing['get_context_start']
        logger.info(f"Get conversation context: {timing['get_context']:.3f}s")
        
        # Enhance query with conversation context (using Gemini API or simple enhancement)
        timing['query_enhance_start'] = time.time()
        
        # Log query enhancement process
        logger.info("=" * 80)
        logger.info("QUERY ENHANCEMENT PROCESS:")
        logger.info(f"Original Query: {message.message}")
        logger.info(f"Has Conversation Context: {'Yes' if conversation_context else 'No'}")
        if conversation_context:
            context_preview = conversation_context[:200] + "..." if len(conversation_context) > 200 else conversation_context
            logger.info(f"Context Preview: {context_preview}")
        
        enhanced_query = message.message
        if conversation_context:
            # Using query enhancer utility
            enhanced_query = enhance_query(
                message.message,
                conversation_context,
                use_gemini=True  # Using Gemini API to enhance
            )
            
            # Log enhancement results
            if enhanced_query != message.message:
                logger.info("-" * 80)
                logger.info("Query Enhanced Successfully:")
                logger.info(f"   Before: {message.message}")
                logger.info(f"   After:  {enhanced_query}")
                
                # Analyze what changed
                if len(enhanced_query) > len(message.message):
                    added_chars = len(enhanced_query) - len(message.message)
                    logger.info(f"   Changes: Added {added_chars} characters (expanded/clarified)")
                elif len(enhanced_query) < len(message.message):
                    removed_chars = len(message.message) - len(enhanced_query)
                    logger.info(f"   Changes: Removed {removed_chars} characters (simplified)")
                else:
                    logger.info(f"   Changes: Rephrased/clarified (same length)")
            else:
                logger.info("-" * 80)
                logger.info("ℹ️  Query Not Changed (already clear or no enhancement needed)")
        else:
            logger.info("-" * 80)
            logger.info("ℹ️  No Enhancement (no conversation context available)")
        
        logger.info(f"Final Query for Search: {enhanced_query}")
        logger.info("=" * 80)
        
        timing['query_enhance'] = time.time() - timing['query_enhance_start']
        logger.info(f"Query enhancement: {timing['query_enhance']:.3f}s")
        
        # Initialize variables
        similar_docs = []
        similar_docs_raw = []
        
        # Step 0: Check for exact document number match (prioritize exact matching)
        timing['document_detection_start'] = time.time()
        exact_document_found = False
        detected_doc_number = None  # Track detected doc_number để log
        try:
            from services.document_detection_service import get_document_detection_service
            doc_detection_service = get_document_detection_service()
            doc_info = doc_detection_service.extract_document_info(message.message)
            
            if doc_info:
                doc_number = doc_info.get('doc_number')
                detected_doc_number = doc_number
                logger.info(f"Detected document number: {doc_number}")
                
                # Search exact document chunks
                exact_chunks = doc_detection_service.search_document_chunks_by_doc_number(
                    doc_number,
                    db,
                    top_k=int(os.getenv('TOP_K_RETRIEVAL', '8'))
                )
                
                if exact_chunks:
                    logger.info(f"Found {len(exact_chunks)} exact chunks for document {doc_number}")
                    similar_docs_raw = exact_chunks
                    exact_document_found = True
                    # Filter by threshold
                    similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.35'))
                    similar_docs_filtered = []
                    for doc in similar_docs_raw:
                        score = doc.get('combined_score', doc.get('similarity_score', 0.0))
                        if score >= similarity_threshold:
                            similar_docs_filtered.append(doc)
                    similar_docs = _filter_relevant_documents(enhanced_query, similar_docs_filtered)
                    logger.info(f"Using exact document match: {len(similar_docs)} chunks after filtering")
                else:
                    # The document number was detected but not found in the database.
                    logger.warning(f"Document number '{doc_number}' detected but NOT FOUND in database. Falling back to RAG 3-tier search.")
                    logger.info(f"   → Will search semantically for similar documents instead")
        except Exception as e:
            logger.warning(f"Document detection failed: {e}, falling back to RAG 3-tier")
            import traceback
            logger.debug(traceback.format_exc())
        timing['document_detection'] = time.time() - timing['document_detection_start']
        if timing['document_detection'] > 0.001:
            logger.info(f"Document detection: {timing['document_detection']:.3f}s")
        
        # Log flow decision
        if detected_doc_number and not exact_document_found:
            logger.info(f"📋 Flow: Document '{detected_doc_number}' not found → Using semantic search (RAG 3-tier)")
        elif exact_document_found:
            logger.info(f"Flow: Exact document match found → Using exact document chunks")
        else:
            logger.info(f"Flow: No document number detected → Using semantic search (RAG 3-tier)")
        
        # RAG 3 tầng flow: Category → Documents → Chunks (only if the exact document is not found)
        if not exact_document_found:
            # Step 1: Finding the category closest to the question (using enhanced query)
            timing['category_search_start'] = time.time()
            logger.info("Step 1: Searching for similar categories...")
            similar_categories = rag_service.search_similar_categories(
                enhanced_query,  # Using enhanced query
                db,
                top_k=1  # Get the nearest category
            )
            timing['category_search'] = time.time() - timing['category_search_start']
            logger.info(f"⏱️  Category search: {timing['category_search']:.3f}s")
        
            if not similar_categories or not similar_categories[0].get('category_id'):
                # Category not found - no fallback, let the logic for handling "not found" be done later.
                logger.warning("No category found, no documents will be retrieved")
                similar_docs = []
                similar_docs_raw = []
            else:
                # Step 2: Get category_id and filter documents by category.
                category_id = similar_categories[0].get('category_id')
                category_title = similar_categories[0].get('title', 'N/A')
                category_similarity = similar_categories[0].get('similarity_score', 0.0)
                
                logger.info(f"Found category: ID={category_id}, Title={category_title[:50]}..., Similarity={category_similarity:.3f}")
                
                # Step 3: Get documents belong to this  category
                timing['get_documents_start'] = time.time()
                logger.info(f"Step 2: Getting documents for category_id={category_id}...")
                documents = rag_service.get_documents_by_category_ids(
                    db,
                    [category_id]
                )
                timing['get_documents'] = time.time() - timing['get_documents_start']
                logger.info(f"Get documents by category: {timing['get_documents']:.3f}s")
            
                if not documents:
                    # Documents not found in category - no fallback, let the logic for handling "not found" be done later.
                    logger.warning(f"No documents found for category_id={category_id}, no chunks will be retrieved")
                    similar_docs = []
                    similar_docs_raw = []
                else:
                    # Step 4: Finding chunks in filtered documents
                    document_ids = [doc['id'] for doc in documents]
                    logger.info(f"Found {len(documents)} documents, searching for chunks...")
                    
                    timing['chunk_search_start'] = time.time()
                    top_k_retrieval = int(os.getenv('TOP_K_RETRIEVAL', '8'))
                    similar_docs_raw = rag_service.search_document_chunks_by_documents(
                        enhanced_query,  # Using enhanced query instead of original
                        db,
                        document_ids,
                        top_k=top_k_retrieval,
                        use_reranker=True,
                        conversation_context=conversation_context
                    )
                    timing['chunk_search'] = time.time() - timing['chunk_search_start']
                    logger.info(f"Chunk search: {timing['chunk_search']:.3f}s")
                    
                    # Filter by similarity threshold
                    timing['filter_threshold_start'] = time.time()
                    similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.35'))
                    similar_docs_filtered = []
                    for doc in similar_docs_raw:
                        score = doc.get('combined_score', doc.get('similarity_score', 0.0))
                        if score >= similarity_threshold:
                            similar_docs_filtered.append(doc)
                    timing['filter_threshold'] = time.time() - timing['filter_threshold_start']
                    logger.info(f"Filter by threshold: {timing['filter_threshold']:.3f}s")
                    
                    # Additional relevance validation
                    timing['filter_relevance_start'] = time.time()
                    similar_docs = _filter_relevant_documents(enhanced_query, similar_docs_filtered)
                    timing['filter_relevance'] = time.time() - timing['filter_relevance_start']
                    logger.info(f"Filter by relevance: {timing['filter_relevance']:.3f}s")
                    
                    logger.info(f"Category-based search results:")
                    logger.info(f"   - Category: {category_title[:50]}... (ID: {category_id}, similarity: {category_similarity:.3f})")
                    logger.info(f"   - Documents found: {len(documents)}")
                    logger.info(f"   - Chunks found: {len(similar_docs_raw)}")
                    logger.info(f"   - Chunks after filtering: {len(similar_docs)}")
        
        # Displaying embedding_document IDs was choose for gemini endpoint
        if 'similar_docs' in locals() and similar_docs:
            final_top_k = int(os.getenv('FINAL_TOP_K', '5'))
            top_k_used = min(final_top_k, len(similar_docs))
            logger.info("=" * 80)
            logger.info(f"EMBEDDING DOCUMENTS ĐƯỢC CHỌN CHO RAG (GEMINI): {top_k_used}/{len(similar_docs)} documents")
            logger.info("=" * 80)
            for idx, doc in enumerate(similar_docs[:top_k_used], 1):
                chunk_id = doc.get('chunk_id', 'N/A')
                title = doc.get('title', 'N/A')[:60]
                score = doc.get('combined_score', doc.get('similarity_score', 0.0))
                used_marker = "DUNG" if idx <= top_k_used else "BO QUA"
                logger.info(f"  [{idx}] {used_marker} | ID: {chunk_id} | Score: {score:.4f} | Title: {title}...")
            if len(similar_docs) > top_k_used:
                logger.info(f"  {len(similar_docs) - top_k_used} documents còn lại bị bỏ qua (chỉ dùng top {top_k_used})")
            logger.info("=" * 80)
        
        # Ensure variables are defined
        if 'similar_docs_raw' not in locals():
            similar_docs_raw = []
        if 'similarity_threshold' not in locals():
            similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.35'))
        
        # Validate similar_docs is a list of dicts
        timing['validate_docs_start'] = time.time()
        if 'similar_docs' in locals() and similar_docs:
            # Log types before filtering
            if similar_docs:
                types = [type(doc).__name__ for doc in similar_docs[:3]]
                logger.info(f"similar_docs types (first 3): {types}")
            
            # Filter out any non-dict items
            original_count = len(similar_docs)
            similar_docs = [doc for doc in similar_docs if isinstance(doc, dict)]
            filtered_count = original_count - len(similar_docs)
            if filtered_count > 0:
                logger.warning(f"Filtered out {filtered_count} non-dict items from similar_docs")
            if not similar_docs:
                logger.warning("All documents filtered out (not dicts), using empty list")
                similar_docs = []
        timing['validate_docs'] = time.time() - timing['validate_docs_start']
        if timing['validate_docs'] > 0.001:  # log if > 1ms
            logger.info(f"⏱️  Validate documents: {timing['validate_docs']:.3f}s")
        
        if not similar_docs:
            # No relevant documents found
            # Check if document number was detected but not found
            if detected_doc_number and not exact_document_found:
                # Document number detected but not in database
                response_text = f"""Xin lỗi, tôi không tìm thấy văn bản pháp luật "{detected_doc_number}" trong cơ sở dữ liệu hiện tại.

Văn bản này có thể:
- Chưa được cập nhật vào hệ thống
- Không thuộc phạm vi tài liệu pháp luật trong cơ sở dữ liệu
- Có tên/số hiệu khác với tên bạn đã cung cấp

Tôi đã tìm kiếm các văn bản pháp luật tương tự nhưng không tìm thấy kết quả phù hợp.

Để được tư vấn chính xác, bạn có thể:
1. Kiểm tra lại số hiệu văn bản (ví dụ: 47/2014/TT-BTNMT)
2. Thử tìm kiếm bằng từ khóa khác
3. Liên hệ trực tiếp với cơ quan có thẩm quyền liên quan
4. Tham khảo ý kiến của luật sư chuyên nghiệp"""
            elif similar_docs_raw:
                # Validate similar_docs_raw contains dicts
                valid_docs = [doc for doc in similar_docs_raw if isinstance(doc, dict)]
                if valid_docs:
                    max_score = max([doc.get('similarity_score', 0.0) for doc in valid_docs])
                    logger.warning(f"No documents above threshold. Max score: {max_score:.3f} < {similarity_threshold}")
                else:
                    logger.warning("No valid documents found in similar_docs_raw")
                response_text = f"""Xin lỗi, tôi không tìm thấy thông tin pháp luật liên quan trực tiếp đến câu hỏi "{message.message}" trong cơ sở dữ liệu hiện tại.

Để được tư vấn chính xác, bạn có thể:
1. Thử diễn đạt lại câu hỏi một cách cụ thể hơn
2. Liên hệ trực tiếp với cơ quan có thẩm quyền liên quan
3. Tham khảo ý kiến của luật sư chuyên nghiệp"""
            else:
                response_text = "Xin lỗi, tôi không tìm thấy thông tin liên quan trong cơ sở dữ liệu pháp luật."
            
            sources = []
            confidence = 0.0
        else:
            # Create context from relevant documents
            final_top_k = int(os.getenv('FINAL_TOP_K', '5'))
            top_k_used = min(final_top_k, len(similar_docs))
            logger.info(f"Sử dụng {top_k_used}/{len(similar_docs)} documents có score cao nhất cho RAG context (GEMINI)")
            
            timing['get_context_start'] = time.time()
            context = rag_service.get_document_context(
                enhanced_query,  # Using enhanced query
                db, 
                top_k=top_k_used,
                conversation_id=conversation_id,
                documents=similar_docs,
                session_id=session_id  # Pass session_id cho database memory
            )
            timing['get_document_context'] = time.time() - timing['get_context_start']
            logger.info(f"⏱️  Get document context: {timing['get_document_context']:.3f}s")
            
            # Validate context - ensure document content is present.
            context_has_documents = False
            if context:
                # Check if the context contains document content.
                context_lower = context.lower()
                if any(marker in context_lower for marker in [
                    '**các văn bản pháp luật:**',
                    '**tổng hợp các văn bản pháp luật:**',
                    '**tài liệu:**',
                    '**tài liệu 1:**',
                    'luật',
                    'nghị định',
                    'thông tư',
                    'điều',
                    'khoản'
                ]):
                    context_has_documents = True
                    logger.info(f"Context validated: {len(context)} chars, contains document content")
                else:
                    logger.warning(f"Context may not contain documents: {len(context)} chars, preview: {context[:200]}...")
            
            # OPTIMAL Prompt - Minimal and effective for RAG law
            timing['build_prompt_start'] = time.time()
            # Use the same minimalist prompt for both cases.
            prompt = f"""Bạn là hệ thống trả lời câu hỏi pháp luật Việt Nam.

Hãy sử dụng thông tin trong các đoạn văn bản được cung cấp (context) để trả lời.

Nếu không tìm thấy câu trả lời trong context, hãy nói rõ "Không tìm thấy quy định trong tài liệu".

Chỉ trả lời dựa trên nội dung context, không suy đoán ngoài luật.

Trích dẫn số điều/khoản/luật nếu trong context có xuất hiện.

Giải thích ngắn gọn, rõ ràng.

**Câu hỏi:** {message.message}

**Các văn bản pháp luật:**
{context}

**Trả lời:**
                """.strip()
            timing['build_prompt'] = time.time() - timing['build_prompt_start']
            logger.info(f"Build prompt: {timing['build_prompt']:.3f}s")
            
            # Log prompt và context được gửi đến Gemini
            logger.info("=" * 80)
            logger.info("THE PROMPT THAT WAS SEND TO GEMINI API:")
            logger.info(f"Prompt length: {len(prompt)} chars")
            logger.info(f"Context length: {len(context)} chars")
            logger.info(f"Context has documents: {context_has_documents}")
            logger.info("-" * 80)
            logger.info("FULL PROMPT:")
            logger.info(prompt)
            logger.info("=" * 80)
            
            # Call Google Gemini API using google.genai SDK
            timing['gemini_api_start'] = time.time()
            try:
                # Try to import google.genai (new SDK) or google.generativeai (old SDK)
                try:
                    from google import genai
                    use_old_sdk = False
                except ImportError:
                    # Fallback: try alternative import (google-generativeai package)
                    try:
                        import google.generativeai as genai
                        use_old_sdk = True
                    except ImportError:
                        raise ImportError("Please install google-genai package: pip install google-genai")
                
                gemini_api_key = os.getenv("GEMINI_API_KEY")
                gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                
                if not gemini_api_key:
                    raise ValueError("GEMINI_API_KEY not found in environment variables")
                
                if use_old_sdk:
                    # Use old google-generativeai SDK
                    genai.configure(api_key=gemini_api_key)
                    model = genai.GenerativeModel(gemini_model)
                    response = model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0.3,  # Lower temperature to reduce hallucinations (from 0.7 to 0.3)
                            "top_k": 20,  # Lower top_k to make the model more focused (from 40 to 20)
                            "top_p": 0.9,  # Lower top_p (from 0.95 to 0.9)
                            "max_output_tokens": 800,  # Keep unchanged for the old SDK (backup)
                        }
                    )
                    llm_response = response.text if response.text else ""
                    if llm_response:
                        logger.info(f"Gemini (old SDK) response length: {len(llm_response)} chars")
                    else:
                        logger.warning(f"Gemini (old SDK) returned empty response. Response object: {response}")
                        # Try to get candidates if text is empty
                        if hasattr(response, 'candidates') and response.candidates:
                            try:
                                for candidate in response.candidates:
                                    if hasattr(candidate, 'content') and candidate.content:
                                        if hasattr(candidate.content, 'parts'):
                                            for part in candidate.content.parts:
                                                if hasattr(part, 'text') and part.text:
                                                    llm_response += part.text
                                if llm_response:
                                    logger.info(f"Extracted from candidates (old SDK): {len(llm_response)} chars")
                            except Exception as e:
                                logger.warning(f"Failed to extract from candidates (old SDK): {e}")
                else:
                    # Use new google.genai SDK
                    # Try to pass api_key to Client, if not supported, use environment variable
                    try:
                        # Try with api_key parameter
                        client = genai.Client(api_key=gemini_api_key)
                    except TypeError:
                        # If api_key parameter not supported, use environment variable
                        os.environ['GOOGLE_API_KEY'] = gemini_api_key
                        client = genai.Client()
                    
                    # Generate content using SDK
                    response = client.models.generate_content(
                        model=gemini_model,
                        contents=prompt,
                        config={
                            "temperature": 0.3,  # Lower temperature to reduce hallucinations (from 0.7 to 0.3)
                            "top_k": 20,  # Lower top_k to make the model more focused (from 40 to 20)
                            "top_p": 0.9,  # Lower top_p (from 0.95 to 0.9)
                            "max_output_tokens": 4000,  # Increase to 4000 tokens to handle long prompts and misspelled queries
                        }
                    )
                    
                    # Log response structure for debugging
                    logger.info(f"Gemini response type: {type(response)}")
                    
                    # Check finish_reason and safety first
                    finish_reason = None
                    safety_ratings = None
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            finish_reason = candidate.finish_reason
                            logger.info(f"Finish reason: {finish_reason}")
                        if hasattr(candidate, 'safety_ratings'):
                            safety_ratings = candidate.safety_ratings
                            if safety_ratings:
                                logger.info(f"Safety ratings: {safety_ratings}")
                    
                    # Log usage metadata if available
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        usage = response.usage_metadata
                        logger.info(f"Usage - Prompt tokens: {getattr(usage, 'prompt_token_count', 'N/A')}, "
                                  f"Candidates tokens: {getattr(usage, 'candidates_token_count', 'N/A')}, "
                                  f"Total tokens: {getattr(usage, 'total_token_count', 'N/A')}")
                    
                    # Check if blocked by safety
                    if finish_reason and str(finish_reason).upper() in ['SAFETY', 'RECITATION', 'PROHIBITED_CONTENT', 'SPII']:
                        logger.warning(f"Response blocked by safety filter. Finish reason: {finish_reason}")
                    
                    # Extract response text using safe method
                    def extract_gemini_text(response):
                        """Safely extract text from Gemini API response"""
                        # Method 1: Try response.text (property method)
                        try:
                            if hasattr(response, 'text'):
                                text_value = response.text
                                # Handle callable property
                                if callable(text_value):
                                    text_value = text_value()
                                if text_value is not None:
                                    text_str = str(text_value).strip()
                                    # Validate it's actual text, not object representation
                                    if text_str and len(text_str) > 0:
                                        if not text_str.startswith('<') and 'sdk_http_response' not in text_str:
                                            return text_str, "response.text"
                        except Exception as e:
                            logger.debug(f"Method 1 (response.text) failed: {e}")
                        
                        # Method 2: Try candidates[0].content.parts[0].text (most reliable)
                        try:
                            if hasattr(response, 'candidates') and response.candidates:
                                for idx, candidate in enumerate(response.candidates):
                                    if hasattr(candidate, 'content') and candidate.content:
                                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                            text_parts = []
                                            for part in candidate.content.parts:
                                                # Check for text part
                                                if hasattr(part, 'text') and part.text:
                                                    text_parts.append(str(part.text))
                                                # Log if it's a function call or other type
                                                elif hasattr(part, 'function_call'):
                                                    logger.debug(f"Candidate {idx} has function_call, not text")
                                                elif hasattr(part, 'inline_data'):
                                                    logger.debug(f"Candidate {idx} has inline_data, not text")
                                            
                                            if text_parts:
                                                combined_text = ' '.join(text_parts).strip()
                                                if combined_text:
                                                    return combined_text, f"candidates[{idx}].content.parts"
                        except Exception as e:
                            logger.debug(f"Method 2 (candidates) failed: {e}")
                        
                        # Method 3: Try direct content access
                        try:
                            if hasattr(response, 'content') and response.content:
                                if hasattr(response.content, 'parts') and response.content.parts:
                                    text_parts = []
                                    for part in response.content.parts:
                                        if hasattr(part, 'text') and part.text:
                                            text_parts.append(str(part.text))
                                    if text_parts:
                                        combined_text = ' '.join(text_parts).strip()
                                        if combined_text:
                                            return combined_text, "response.content.parts"
                        except Exception as e:
                            logger.debug(f"Method 3 (content) failed: {e}")
                        
                        # Method 4: Try parsed attribute
                        try:
                            if hasattr(response, 'parsed') and response.parsed:
                                parsed = response.parsed
                                if hasattr(parsed, 'text') and parsed.text:
                                    text_str = str(parsed.text).strip()
                                    if text_str:
                                        return text_str, "response.parsed.text"
                        except Exception as e:
                            logger.debug(f"Method 4 (parsed) failed: {e}")
                        
                        return None, None
                    
                    # Extract text using safe method
                    llm_response, extraction_method = extract_gemini_text(response)
                    timing['gemini_api'] = time.time() - timing['gemini_api_start']
                    logger.info(f"Gemini API call: {timing['gemini_api']:.3f}s")
                    
                    if llm_response:
                        logger.info(f"Extracted text from {extraction_method}: {len(llm_response)} chars")
                        # Log preview of response (first 200 chars) - always show for debugging
                        preview = llm_response[:200] + "..." if len(llm_response) > 200 else llm_response
                        logger.info(f"Response preview: {preview}")
                        
                        # Validate extraction by comparing with candidates method
                        if extraction_method == "response.text":
                            # Double-check by trying candidates method
                            try:
                                if hasattr(response, 'candidates') and response.candidates:
                                    candidate = response.candidates[0]
                                    if hasattr(candidate, 'content') and candidate.content:
                                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                            candidate_text_parts = []
                                            for part in candidate.content.parts:
                                                if hasattr(part, 'text') and part.text:
                                                    candidate_text_parts.append(str(part.text))
                                            if candidate_text_parts:
                                                candidate_text = ' '.join(candidate_text_parts).strip()
                                                if candidate_text and candidate_text != llm_response:
                                                    # Compare lengths - if significantly different, log warning
                                                    len_diff = abs(len(candidate_text) - len(llm_response))
                                                    if len_diff > 10:  # More than 10 chars difference
                                                        logger.warning(f"Text mismatch: response.text={len(llm_response)} chars, "
                                                                     f"candidates={len(candidate_text)} chars (diff: {len_diff})")
                                                        logger.warning(f"   response.text preview: {llm_response[:100]}")
                                                        logger.warning(f"   candidates preview: {candidate_text[:100]}")
                                                    else:
                                                        logger.debug(f"Validation: Both methods match (diff: {len_diff} chars)")
                            except Exception as e:
                                logger.debug(f"Validation check failed: {e}")
                        
                        # Check if response seems truncated
                        if hasattr(response, 'usage_metadata') and response.usage_metadata:
                            usage = response.usage_metadata
                            candidate_tokens = getattr(usage, 'candidates_token_count', 0)
                            max_tokens = 4000  # Gemini API max_output_tokens
                            if candidate_tokens >= max_tokens * 0.9:  # Used 90%+ of max tokens
                                logger.warning(f"Response may be truncated: used {candidate_tokens}/{max_tokens} tokens "
                                             f"({candidate_tokens/max_tokens*100:.1f}%)")
                    else:
                        # Detailed error logging
                        logger.error(f"Could not extract text from Gemini response")
                        logger.error(f"   Response type: {type(response)}")
                        logger.error(f"   Has text attr: {hasattr(response, 'text')}")
                        logger.error(f"   Has candidates: {hasattr(response, 'candidates')}")
                        if hasattr(response, 'candidates') and response.candidates:
                            candidate = response.candidates[0]
                            logger.error(f"   Candidate has content: {hasattr(candidate, 'content')}")
                            if hasattr(candidate, 'content') and candidate.content:
                                logger.error(f"   Content has parts: {hasattr(candidate.content, 'parts')}")
                                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                    logger.error(f"   Parts count: {len(candidate.content.parts)}")
                                    for i, part in enumerate(candidate.content.parts):
                                        logger.error(f"   Part {i} type: {type(part)}, has text: {hasattr(part, 'text')}")
                        logger.error(f"   Finish reason: {finish_reason}")
                        if finish_reason:
                            logger.error(f"   Response may be blocked or incomplete due to finish_reason: {finish_reason}")
                
                # Ensure llm_response is not None
                if llm_response is None:
                    llm_response = ""
                
                # If response is empty, use fallback answer
                if not llm_response or len(llm_response.strip()) == 0:
                    logger.warning("Gemini API returned empty response, using fallback answer")
                    answer = _generate_fallback_answer(message.message, similar_docs)
                    sources_section = _format_sources_section(similar_docs)
                    
                    if sources_section:
                        response_text = f"""{answer}

**Các văn bản pháp luật liên quan:**

{sources_section}"""
                    else:
                        response_text = answer
                else:
                    # Format response
                    timing['format_response_start'] = time.time()
                    llm_clean = llm_response
                    if llm_clean and "**Các văn bản pháp luật liên quan:**" in llm_clean:
                        parts = llm_clean.split("**Các văn bản pháp luật liên quan:**")
                        llm_clean = parts[0].strip()
                    
                    # Citation checking
                    timing['citation_check_start'] = time.time()
                    citation_check = rag_service.check_citations(llm_response, similar_docs)
                    timing['citation_check'] = time.time() - timing['citation_check_start']
                    if timing['citation_check'] > 0.001:
                        logger.info(f"itation check: {timing['citation_check']:.3f}s")
                    
                    if citation_check['invalid_citations']:
                        logger.warning(f"Found invalid citations: {citation_check['invalid_citations']}")
                        # Adding invalid citations into config automatically
                        citation_manager = get_citation_manager()
                        citation_manager.add_invalid_citations(citation_check['invalid_citations'])
                    
                    # Append sources section
                    timing['format_sources_start'] = time.time()
                    sources_section = _format_sources_section(similar_docs)
                    timing['format_sources'] = time.time() - timing['format_sources_start']
                    if timing['format_sources'] > 0.001:
                        logger.info(f"⏱️  Format sources: {timing['format_sources']:.3f}s")
                    
                    if sources_section:
                        if "**Các văn bản pháp luật liên quan:**" not in llm_clean:
                            response_text = f"{llm_clean}\n\n**Các văn bản pháp luật liên quan:**\n{sources_section}"
                        else:
                            response_text = llm_clean
                    else:
                        response_text = llm_clean
                    timing['format_response'] = time.time() - timing['format_response_start']
                    if timing['format_response'] > 0.001:
                        logger.info(f"Format response: {timing['format_response']:.3f}s")
                    
            except Exception as e:
                timing['gemini_api'] = time.time() - timing['gemini_api_start']
                logger.error(f"Gemini API call failed: {e}")
                logger.info(f"Gemini API call (failed): {timing['gemini_api']:.3f}s")
                
                # Check error type and provide an appropriate message
                error_str = str(e).lower()

                if "503" in error_str or "unavailable" in error_str or "overloaded" in error_str:
                    error_message = "Gemini API is temporarily overloaded. Please try again in a few seconds."

                elif "quota" in error_str or "rate limit" in error_str or "429" in error_str:
                    error_message = "The API key has exhausted its quota or exceeded the rate limit. Please check the API key or upgrade the plan."

                elif "403" in error_str or "forbidden" in error_str:
                    error_message = "The API key does not have access permission or has been disabled. Please verify the API key."

                else:
                    error_message = f"Error while calling the Gemini API: {str(e)}"
                
                # Fallback response - ensure similar_docs is valid
                valid_similar_docs = [doc for doc in similar_docs if isinstance(doc, dict)] if similar_docs else []
                answer = _generate_fallback_answer(message.message, valid_similar_docs)
                sources_section = _format_sources_section(valid_similar_docs)
                
                if sources_section:
                    response_text = f"""{error_message}

{answer}

**Các văn bản pháp luật liên quan:**

{sources_section}"""
                else:
                    response_text = f"""{error_message}

{answer}"""
            
            # Prepare sources - validate that similar_docs contains dicts
            timing['prepare_sources_start'] = time.time()
            sources = []
            for doc in similar_docs:
                # Validate doc is a dict
                if not isinstance(doc, dict):
                    logger.warning(f"Skipping invalid doc (not a dict): {type(doc)}")
                    continue
                
                try:
                    # Extract document_id, category_id từ metadata
                    metadata = doc.get('metadata', {})
                    document_id = None
                    category_id = None
                    if isinstance(metadata, dict):
                        document_id = metadata.get('document_id')
                        category_id = metadata.get('category_id')
                    
                    source = {
                        "title": doc.get("title", "N/A"),
                        "doc_type": doc.get("doc_type", "N/A"),
                        "source_url": doc.get("source_url", ""),
                        "similarity_score": doc.get("similarity_score", 0.0)
                    }
                    # Adding document_id into the source (if document_id exist)
                    if document_id:
                        source["document_id"] = document_id
                    # chunk_id into the source 
                    if 'chunk_id' in doc:
                        source["chunk_id"] = doc["chunk_id"]
                    # category_id into the  source 
                    if category_id:
                        source["category_id"] = category_id
                    elif 'category_id' in doc:
                        source["category_id"] = doc["category_id"]
                    if 'reranker_score' in doc:
                        source["reranker_score"] = doc["reranker_score"]
                    if 'combined_score' in doc:
                        source["combined_score"] = doc["combined_score"]
                    sources.append(source)
                except Exception as e:
                    logger.warning(f"Error processing doc: {e}, doc type: {type(doc)}")
                    continue
            timing['prepare_sources'] = time.time() - timing['prepare_sources_start']
            if timing['prepare_sources'] > 0.001:
                logger.info(f"⏱️  Prepare sources: {timing['prepare_sources']:.3f}s")
            
            # Calculate confidence - validate docs are dicts
            timing['calculate_confidence_start'] = time.time()
            scores = []
            for doc in similar_docs:
                if isinstance(doc, dict):
                    score = doc.get('combined_score', doc.get('similarity_score', 0.0))
                    scores.append(score)
            confidence = sum(scores) / len(scores) if scores else 0.0
            timing['calculate_confidence'] = time.time() - timing['calculate_confidence_start']
            if timing['calculate_confidence'] > 0.001:
                logger.info(f"⏱️  Calculate confidence: {timing['calculate_confidence']:.3f}s")
        
        # Add to conversation memory
        timing['save_memory_start'] = time.time()
        rag_service.add_message_to_memory(conversation_id, message.message, response_text)
        timing['save_memory'] = time.time() - timing['save_memory_start']
        if timing['save_memory'] > 0.001:
            logger.info(f"⏱️  Save to memory: {timing['save_memory']:.3f}s")
        
        # Save to database if user is authenticated
        if current_user:
            timing['save_db_start'] = time.time()
            try:
                # Check if transaction is in a bad state and rollback if needed
                try:
                    db.execute(text("SELECT 1"))
                except Exception:
                    logger.warning("Transaction in bad state, rolling back...")
                    db.rollback()
                
                # Using session_id from conversation_id , don't use title to find session
                session = None
                if session_id:
                    # Find session by existing session_id 
                    session = db.query(ChatSession).filter(
                        ChatSession.session_id == session_id,
                        ChatSession.user_id == current_user.user_id
                    ).first()
                    if session:
                        logger.debug(f"Found existing session {session_id}: {session.title}")
                
                # If session_id is missing or not found, find the session with the most recent message
                if not session:
                    from datetime import timedelta
                    from models.database import get_vietnam_now, ChatMessage
                    
                    # Find the session with the most recent message (within the last 2 hours)
                    recent_message = db.query(ChatMessage).join(ChatSession).filter(
                        ChatSession.user_id == current_user.user_id,
                        ChatMessage.created_at >= get_vietnam_now() - timedelta(hours=2)
                    ).order_by(ChatMessage.created_at.desc()).first()
                    
                    if recent_message:
                        # Get session from the most recent message.
                        recent_session = db.query(ChatSession).filter(
                            ChatSession.session_id == recent_message.session_id,
                            ChatSession.user_id == current_user.user_id
                        ).first()
                        
                        if recent_session:
                            session = recent_session
                            session_id = recent_session.session_id
                            logger.info(f"Using session {session_id} with recent message (last message: {recent_message.created_at})")
                    else:
                        # If there are no recent messages, look for the most recently created session (within the last 2 hours).
                        recent_session = db.query(ChatSession).filter(
                            ChatSession.user_id == current_user.user_id,
                            ChatSession.created_at >= get_vietnam_now() - timedelta(hours=2)
                        ).order_by(ChatSession.created_at.desc()).first()
                        
                        if recent_session:
                            session = recent_session
                            session_id = recent_session.session_id
                            logger.info(f"Using recent session {session_id} (created {recent_session.created_at})")
                
                if not session:
                    # Create a new session if not found.
                    session = ChatSession(
                        user_id=current_user.user_id,
                        title=message.message[:50] + "..."
                    )
                    db.add(session)
                    try:
                        db.flush()
                        logger.info(f"Created new session {session.session_id}: {session.title}")
                    except Exception as flush_error:
                        logger.error(f"Error during flush: {flush_error}")
                        db.rollback()
                        # If the session cannot be created → do not save to the database (because sometime I test the system from the terminal)
                        logger.warning(f"Cannot create session for user {current_user.user_id}, skipping database save (likely test from terminal)")
                        session = None
                
                # SAVE TO DATABASE ONLY WHEN A VALID SESSION IS AVAILABLE
                if session and session.session_id:
                    user_message = ChatMessage(
                        session_id=session.session_id,
                        sender=MessageSender.USER,
                        message_text=message.message
                    )
                    db.add(user_message)
                    
                    assistant_message = ChatMessage(
                        session_id=session.session_id,
                        sender=MessageSender.ASSISTANT,
                        message_text=response_text,
                        confidence=confidence
                    )
                    db.add(assistant_message)
                    
                    db.commit()
                    timing['save_db'] = time.time() - timing['save_db_start']
                    logger.info(f"⏱️  Save to database: {timing['save_db']:.3f}s")
                    logger.info(f"✅ Chat history saved for user {current_user.user_id} in session {session.session_id}")
                    
                    # Update conversation_id from session_id to sync
                    conversation_id = get_conversation_id_from_session_id(session.session_id, db) or conversation_id
                    
                    # Process memory and topic services (session_id required)
                    timing['process_services_start'] = time.time()
                    message_count = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session.session_id
                    ).count()
                    process_conversation_services(
                        session.session_id,  # Using session_id instead of conversation_id
                        message.message,
                        response_text,
                        db,
                        message_count
                    )
                else:
                    # No valid session found → Do not save to database (tested from terminal)
                    timing['save_db'] = time.time() - timing['save_db_start']
                    logger.debug(f"No valid session for user {current_user.user_id}, skipping database save (likely test from terminal)")
                timing['process_services'] = time.time() - timing['process_services_start']
                if timing['process_services'] > 0.001:
                    logger.info(f"Process conversation services: {timing['process_services']:.3f}s")
                
            except Exception as e:
                if 'process_services_start' in timing:
                    timing['process_services'] = time.time() - timing['process_services_start']
                logger.error(f"Error saving chat history: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                try:
                    db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error during rollback: {rollback_error}")
        
        # Calculate total time and print timing summary
        total_time = time.time() - total_start_time
        timing['total'] = total_time
        
        # Print timing summary
        logger.info("=" * 80)
        logger.info("⏱️  TIMING SUMMARY (RAG System Performance):")
        logger.info("=" * 80)
        for step, duration in sorted(timing.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
            if step.endswith('_start'):
                continue
            percentage = (duration / total_time * 100) if total_time > 0 else 0
            logger.info(f"  {step:30s}: {duration:7.3f}s ({percentage:5.1f}%)")
        logger.info("=" * 80)
        logger.info(f"  {'TOTAL TIME':30s}: {total_time:7.3f}s (100.0%)")
        
        return ChatResponse(
            response=response_text,
            sources=sources,
            confidence=confidence,
            conversation_id=conversation_id
        )
        
    except Exception as e:
        import traceback
        total_time = time.time() - total_start_time if 'total_start_time' in locals() else 0
        logger.error(f"Gemini chat error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if total_time > 0:
            logger.info(f"Total time before error: {total_time:.3f}s")
        raise HTTPException(status_code=500, detail=f"Gemini chat processing failed: {str(e)}")

