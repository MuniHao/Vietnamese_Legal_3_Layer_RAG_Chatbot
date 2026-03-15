"""
RAG (Retrieval-Augmented Generation) service for legal document search
Improved version with semantic chunking, reranker, and citation checking
"""
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional, Tuple
import logging
import os
import sys
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Add src directory to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from models.database import get_db, Document, Embedding

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

# Import new services
try:
    from services.hybrid_retrieve_service import get_hybrid_retrieve_service
    from services.memory_service import get_memory_service
    from services.topic_service import get_topic_service
    NEW_SERVICES_AVAILABLE = True
except ImportError as e:
    NEW_SERVICES_AVAILABLE = False
    logger.warning(f"New services not available: {e}")

# Simple memory implementation
class ConversationBufferMemory:
    """Simple conversation memory for storing chat history"""
    def __init__(self, memory_key="chat_history", return_messages=True, output_key="output"):
        self.memory_key = memory_key
        self.return_messages = return_messages
        self.output_key = output_key
        self.chat_memory = ChatMemory()
    
class ChatMemory:
    """Simple chat memory storage"""
    def __init__(self):
        self.messages: List[BaseMessage] = []
    
    def add_user_message(self, message: str):
        self.messages.append(HumanMessage(content=message))
    
    def add_ai_message(self, message: str):
        self.messages.append(AIMessage(content=message))

class LegalRAGService:
    """Improved RAG service with semantic chunking, reranker, and citation checking"""
    
    def __init__(self):
        self.embedding_model = None
        self.reranker_model = None
        self.tokenizer = None  # Cache tokenizer to avoid reloading
        self.use_tokenizer = False  # Flag to use tokenizer or estimation
        self.embedding_dimension = int(os.getenv('EMBEDDING_DIMENSION', '1024'))
        self.max_chunk_size = int(os.getenv('MAX_CHUNK_SIZE', '500'))  # 300-500 tokens as recommended
        self.chunk_overlap = int(os.getenv('CHUNK_OVERLAP', '100'))  # ~100 tokens overlap
        self.use_reranker = os.getenv('USE_RERANKER', 'True').lower() == 'true'
        self.rerank_top_k = int(os.getenv('RERANK_TOP_K', '8'))  # Retrieve more before reranking
        self.final_top_k = int(os.getenv('FINAL_TOP_K', '5'))  # Final documents after reranking
        # Conversation memory storage - in production, this should be stored in database
        self.conversation_memories: Dict[str, ConversationBufferMemory] = {}
        
        # Flag to track if services are available
        self.new_services_available = False
        
        # Initialize new services if available
        if NEW_SERVICES_AVAILABLE:  # Module-level check
            try:
                self.hybrid_retrieve_service = get_hybrid_retrieve_service()
                self.memory_service = get_memory_service()
                self.topic_service = get_topic_service()
                self.new_services_available = True
                logger.info("New RAG services initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize new services: {e}")
                self.new_services_available = False
        
    def load_embedding_model(self):
        """Load the embedding model (BAAI/bge-m3 for Vietnamese)"""
        if self.embedding_model is None:
            model_name = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
            logger.info(f"Loading embedding model: {model_name}")
            try:
                self.embedding_model = SentenceTransformer(model_name)
                logger.info("Embedding model loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load embedding model {model_name}: {e}")
                # Fallback to smaller model if needed
                fallback_model = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
                logger.info(f"Falling back to: {fallback_model}")
                self.embedding_model = SentenceTransformer(fallback_model)
                self.embedding_dimension = 384  # Fallback dimension
        else:
            # Model already loaded (preloaded on startup)
            logger.debug("Using preloaded embedding model")
        return self.embedding_model
    
    def load_reranker_model(self):
        """Load the reranker model"""
        if self.reranker_model is None and self.use_reranker:
            model_name = os.getenv('RERANKER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info(f"Loading reranker model: {model_name}")
            try:
                self.reranker_model = CrossEncoder(model_name)
                logger.info("Reranker model loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load reranker model {model_name}: {e}")
                logger.warning("Continuing without reranker...")
                self.use_reranker = False
        else:
            if self.reranker_model:
                logger.debug("Using preloaded reranker model")
        return self.reranker_model
    
    def _get_tokenizer(self):
        """Get tokenizer for token counting (cached)"""
        # If already tried and failed, skip
        if self.tokenizer is False:
            return None
        
        # If already loaded, return cached tokenizer
        if self.tokenizer is not None:
            return self.tokenizer
        
        # Try to load tokenizer once
        try:
            from transformers import AutoTokenizer
            model_name = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
            logger.info(f"Loading tokenizer for {model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.use_tokenizer = True
            logger.info("Tokenizer loaded successfully!")
            return self.tokenizer
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}. Using character-based estimation.")
            self.tokenizer = False  # Mark as failed to avoid retrying
            self.use_tokenizer = False
            return None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tokenizer or character estimation"""
        # Try to use cached tokenizer
        tokenizer = self._get_tokenizer()
        if tokenizer:
            try:
                return len(tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Error encoding text with tokenizer: {e}. Using estimation.")
                # Fall through to estimation
        
        # Fallback: approximate 1 token ≈ 4 characters for Vietnamese
        # This is a reasonable approximation for Vietnamese text
        return len(text) // 4
    
    def _semantic_chunk_text(self, text: str, chunk_by_article: bool = True) -> List[str]:
        """
        Improved semantic chunking for legal documents with dynamic token counting
        - Chunks by Điều/Khoản (Clause/Term) first (for legal documents)
        - Size: 400-500 tokens (configurable via MAX_CHUNK_SIZE)
        - Overlap: 80-120 tokens (configurable via CHUNK_OVERLAP)
        - Uses actual token counting instead of character count
        """
        if not text:
            return []
        
        chunks = []
        
        if chunk_by_article:
            # First, split by Điều (Article) markers - this is the natural structure of legal documents
            # Pattern: "Điều" followed by number, or "Điều" at start of line
            article_pattern = r'(?=Điều\s+\d+)'
            articles = re.split(article_pattern, text)
            
            # Process each article
            for article in articles:
                article = article.strip()
                if not article:
                    continue
                
                # Count tokens for this article
                article_tokens = self._count_tokens(article)
                
                # If article is small enough, add as single chunk
                if article_tokens <= self.max_chunk_size:
                    chunks.append(article)
                else:
                    # Article is too long, need to split further
                    # Split by Khoản (paragraph) markers first
                    khoan_pattern = r'(?=\d+\.\s)'
                    khoans = re.split(khoan_pattern, article)
                    
                    current_chunk = ""
                    current_tokens = 0
                    
                    for khoan in khoans:
                        khoan = khoan.strip()
                        if not khoan:
                            continue
                        
                        khoan_tokens = self._count_tokens(khoan)
                        
                        # If adding this khoan exceeds max size, save current chunk
                        if current_tokens + khoan_tokens > self.max_chunk_size and current_chunk:
                            chunks.append(current_chunk.strip())
                            
                            # Start new chunk with overlap
                            # Get last few sentences for overlap
                            sentences = re.split(r'[.!?。！？]\s+', current_chunk)
                            overlap_sentences = sentences[-3:] if len(sentences) >= 3 else sentences
                            overlap_text = '. '.join(overlap_sentences) + '. ' if overlap_sentences else ''
                            current_chunk = overlap_text + khoan
                            current_tokens = self._count_tokens(current_chunk)
                        else:
                            # Add khoan to current chunk
                            if current_chunk:
                                current_chunk += '\n\n' + khoan
                            else:
                                current_chunk = khoan
                            current_tokens = self._count_tokens(current_chunk)
                    
                    # Add remaining chunk
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
        else:
            # Fallback: chunk by sentences (for non-legal text or categories)
            sentences = re.split(r'([.!?。！？]\s+)', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            current_chunk = ""
            current_tokens = 0
            
            for i, sentence in enumerate(sentences):
                sentence_tokens = self._count_tokens(sentence)
                
                # If adding this sentence exceeds max size, save current chunk
                if current_tokens + sentence_tokens > self.max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # Start new chunk with overlap
                    # Get last few sentences for overlap
                    prev_sentences = re.split(r'[.!?。！？]\s+', current_chunk)
                    overlap_sentences = prev_sentences[-2:] if len(prev_sentences) >= 2 else prev_sentences
                    overlap_text = '. '.join(overlap_sentences) + '. ' if overlap_sentences else ''
                    current_chunk = overlap_text + sentence
                    current_tokens = self._count_tokens(current_chunk)
                else:
                    # Add sentence to current chunk
                    if current_chunk:
                        current_chunk += ' ' + sentence
                    else:
                        current_chunk = sentence
                    current_tokens = self._count_tokens(current_chunk)
            
            # Add remaining chunk
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
        
        # Merge very small chunks with previous ones
        merged_chunks = []
        min_chunk_tokens = self.max_chunk_size // 3  # Minimum chunk size
        
        for chunk in chunks:
            chunk_tokens = self._count_tokens(chunk)
            
            if chunk_tokens < min_chunk_tokens and merged_chunks:
                # Try to merge with previous chunk if still under limit
                prev_chunk = merged_chunks[-1]
                combined_tokens = self._count_tokens(prev_chunk + '\n\n' + chunk)
                
                if combined_tokens <= self.max_chunk_size * 1.2:
                    merged_chunks[-1] = prev_chunk + '\n\n' + chunk
                else:
                    merged_chunks.append(chunk)
            else:
                merged_chunks.append(chunk)
        
        return merged_chunks
    
    def create_embeddings(self, db: Session, batch_size: int = 10):
        """Create embeddings for documents using improved semantic chunking"""
        logger.info("Starting embedding creation process...")
        
        # Get documents without embeddings
        query = text("""
            SELECT d.id, d.title, d.text_content, d.doc_type, d.source_url
            FROM documents d
            LEFT JOIN embeddings e ON d.id = (e.metadata->>'document_id')::integer
            WHERE e.id IS NULL AND d.text_content IS NOT NULL
            LIMIT :limit
        """)
        
        documents = db.execute(query, {"limit": batch_size}).fetchall()
        
        if not documents:
            logger.info("No documents need embeddings")
            return
        
        model = self.load_embedding_model()
        
        for doc in documents:
            try:
                # Split document into semantic chunks (chunk by Điều/Khoản (Clause/Term) for legal documents)
                chunks = self._semantic_chunk_text(doc.text_content, chunk_by_article=True)
                logger.info(f"Document {doc.id}: Created {len(chunks)} semantic chunks")
                
                for i, chunk in enumerate(chunks):
                    # Create embedding with proper encoding for BAAI/bge-m3
                    # BAAI/bge-m3 uses instruction prefix for queries, but not for documents
                    if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
                        # For documents, no prefix needed
                        embedding = model.encode(chunk, normalize_embeddings=True)
                    else:
                        embedding = model.encode(chunk)
                    
                    # Create chunk ID
                    chunk_id = f"doc_{doc.id}_chunk_{i}"
                    
                    # Check if embedding already exists
                    existing = db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
                    if existing:
                        continue
                    
                    # Create new embedding record
                    new_embedding = Embedding(
                        chunk_id=chunk_id,
                        content=chunk,
                        embedding=embedding.tolist(),
                        metadata_json={
                            "document_id": doc.id,
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        },
                        title=doc.title,
                        doc_type=doc.doc_type,
                        source_url=doc.source_url
                    )
                    
                    db.add(new_embedding)
                
                db.commit()
                logger.info(f"Created embeddings for document {doc.id}: {doc.title[:50]}... ({len(chunks)} chunks)")
                
            except Exception as e:
                logger.error(f"Error creating embeddings for document {doc.id}: {e}")
                db.rollback()
                continue
    
    def _split_text(self, text: str) -> List[str]:
        """Legacy split text method - kept for backward compatibility"""
        # Use semantic chunking instead
        return self._semantic_chunk_text(text)

    def create_category_embeddings(self, db: Session, batch_size: int = 10):
        """Create embeddings for categories.content using improved semantic chunking"""
        logger.info("Starting category embedding creation process...")

        # Get categories without embeddings
        query = text(
            """
            SELECT c.id, c.title, c.content, c.source_url
            FROM categories c
            LEFT JOIN embeddings e ON c.id = (e.metadata->>'category_id')::integer
            WHERE e.id IS NULL AND c.content IS NOT NULL AND length(trim(c.content)) > 0
            LIMIT :limit
            """
        )

        categories = db.execute(query, {"limit": batch_size}).fetchall()

        if not categories:
            logger.info("No categories need embeddings")
            return

        model = self.load_embedding_model()

        for cat in categories:
            try:
                # Split category content into semantic chunks (chunk by sentences for categories)
                chunks = self._semantic_chunk_text(cat.content, chunk_by_article=False)
                logger.info(f"Category {cat.id}: Created {len(chunks)} semantic chunks")

                for i, chunk in enumerate(chunks):
                    # Encode chunk
                    if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
                        embedding = model.encode(chunk, normalize_embeddings=True)
                    else:
                        embedding = model.encode(chunk)

                    # Create chunk ID
                    chunk_id = f"cat_{cat.id}_chunk_{i}"

                    # Skip if exists
                    existing = db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
                    if existing:
                        continue

                    # Insert embedding record
                    new_embedding = Embedding(
                        chunk_id=chunk_id,
                        content=chunk,
                        embedding=embedding.tolist(),
                        metadata_json={
                            "category_id": cat.id,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "source": "categories"
                        },
                        title=cat.title,
                        doc_type="category",
                        source_url=cat.source_url
                    )

                    db.add(new_embedding)

                db.commit()
                logger.info(f"Created embeddings for category {cat.id}: {cat.title[:50]}... ({len(chunks)} chunks)")

            except Exception as e:
                logger.error(f"Error creating embeddings for category {cat.id}: {e}")
                db.rollback()
                continue
    
    def rerank_documents(self, query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank documents using cross-encoder reranker for better relevance
        Returns reranked documents with updated scores
        """
        start_time = time.time()
        if not self.use_reranker or not docs:
            return docs
        
        timing = {}
        timing['load_model_start'] = time.time()
        reranker = self.load_reranker_model()
        timing['load_model'] = time.time() - timing['load_model_start']
        if not reranker:
            return docs
        
        try:
            # Prepare pairs for reranking: (query, document_content)
            timing['prepare_pairs_start'] = time.time()
            pairs = [(query, doc.get('content', '')) for doc in docs]
            timing['prepare_pairs'] = time.time() - timing['prepare_pairs_start']
            
            # Get reranker scores
            timing['predict_start'] = time.time()
            rerank_scores = reranker.predict(pairs)
            timing['predict'] = time.time() - timing['predict_start']
            
            # Update documents with reranker scores
            timing['update_scores_start'] = time.time()
            for i, doc in enumerate(docs):
                doc['reranker_score'] = float(rerank_scores[i])
                # Combine similarity score and reranker score
                similarity = doc.get('similarity_score', 0.0)
                doc['combined_score'] = 0.6 * float(rerank_scores[i]) + 0.4 * similarity
            
            # Sort by combined score
            docs_sorted = sorted(docs, key=lambda x: x.get('combined_score', 0.0), reverse=True)
            timing['update_scores'] = time.time() - timing['update_scores_start']
            
            total_time = time.time() - start_time
            logger.info(f"Reranked {len(docs_sorted)} documents")
            logger.info(f"Rerank breakdown: load_model={timing.get('load_model', 0):.3f}s, "
                       f"prepare_pairs={timing.get('prepare_pairs', 0):.3f}s, "
                       f"predict={timing.get('predict', 0):.3f}s, "
                       f"update_scores={timing.get('update_scores', 0):.3f}s, "
                       f"total={total_time:.3f}s")
            return docs_sorted
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            return docs
    
    def get_conversation_memory(self, conversation_id: str) -> ConversationBufferMemory:
        """Get or create conversation memory for a session"""
        if conversation_id not in self.conversation_memories:
            self.conversation_memories[conversation_id] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output"
            )
        return self.conversation_memories[conversation_id]
    
    def add_message_to_memory(self, conversation_id: str, message: str, response: str):
        """Add a conversation turn to memory"""
        memory = self.get_conversation_memory(conversation_id)
        memory.chat_memory.add_user_message(message)
        memory.chat_memory.add_ai_message(response)
    
    def get_conversation_context(
        self, 
        conversation_id: str, 
        max_turns: int = 5, 
        db: Optional[Session] = None,
        session_id: Optional[int] = None
    ) -> str:
        """
        Get recent conversation context for RAG - using summary-based memory if exist
        
        Args:
            conversation_id: Conversation ID (string) - use for buffer memory
            max_turns: the number of nearest turns
            db: Database session
            session_id: Session ID (integer) - use for database memory
        """
        context_parts = []
        
        # Try to use memory service first (summary-based) - need session_id
        if self.new_services_available and hasattr(self, 'memory_service') and db and session_id:
            try:
                # get recent messages from database to add context
                recent_messages = []
                try:
                    from models.database import ChatMessage, MessageSender
                    messages = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id
                    ).order_by(ChatMessage.created_at.desc()).limit(max_turns * 2).all()
                    
                    # Reverse to have the exactly order
                    messages = list(reversed(messages))
                    for msg in messages:
                        role = "user" if msg.sender == MessageSender.USER else "assistant"
                        recent_messages.append({
                            "role": role,
                            "content": msg.message_text
                        })
                    
                    # Format messages for query enhancer (use format "user:" and "assistant:")
                    formatted_messages = []
                    for msg in recent_messages:
                        formatted_messages.append(f"{msg['role']}: {msg['content']}")
                    # adding Vietnam Language format
                    for msg in recent_messages:
                        role_vn = "Người dùng" if msg['role'] == "user" else "Trợ lý"
                        formatted_messages.append(f"{role_vn}: {msg['content']}")
                except Exception as e:
                    logger.debug(f"Error getting recent messages from database: {e}")
                
                # Get memory context from memory service (need session_id)
                context = self.memory_service.get_memory_context(session_id, db, recent_messages)
                if context:
                    context_parts.append(context)
                
                # Adding formatted messages into context to query enhancer can extract
                if recent_messages:
                    formatted_messages = []
                    for msg in recent_messages:
                        formatted_messages.append(f"{msg['role']}: {msg['content']}")
                    # adding Vietnam Language format
                    for msg in recent_messages:
                        role_vn = "Người dùng" if msg['role'] == "user" else "Trợ lý"
                        formatted_messages.append(f"{role_vn}: {msg['content']}")
                    formatted_context = "\n".join(formatted_messages)
                    if formatted_context:
                        context_parts.append(formatted_context)
            except Exception as e:
                logger.debug(f"Memory service context failed: {e}, falling back to buffer memory")
        
        # Fallback to buffer memory (use conversation_id)
        # ONLY retrieve from buffer memory if:
        # 1. conversation_id exists
        # 2. conversation_id is present in buffer memory
        # 3. There is NO session_id (to avoid retrieving context from an old session when creating a new session)
        #    If session_id exists, the context has already been retrieved from the database above
        if conversation_id and not session_id and conversation_id in self.conversation_memories:
            memory = self.conversation_memories[conversation_id]
            messages = memory.chat_memory.messages
            
            # Get last few turns
            recent_messages = messages[-max_turns*2:] if len(messages) > max_turns*2 else messages
            
            buffer_parts = []
            for i in range(0, len(recent_messages), 2):
                if i+1 < len(recent_messages):
                    user_msg = recent_messages[i].content if hasattr(recent_messages[i], 'content') else str(recent_messages[i])
                    ai_msg = recent_messages[i+1].content if hasattr(recent_messages[i+1], 'content') else str(recent_messages[i+1])
                    # Format to extract easily: using both "user:" and "Người dùng:" for more compatible 
                    buffer_parts.append(f"user: {user_msg}\nassistant: {ai_msg}")
                    #adding Vietnamese format  to  display
                    buffer_parts.append(f"Người dùng: {user_msg}\nTrợ lý: {ai_msg}")
            
            if buffer_parts:
                buffer_context = "\n\n".join(buffer_parts)
                if not context_parts:
                    context_parts.append(buffer_context)
                elif "Tin nhắn gần đây" not in context_parts[0]:
                    # Adding buffer context if recent messages havn't existed at the memory service
                    context_parts.append(f"**recent messages:**\n{buffer_context}")
        
        return "\n\n".join(context_parts) if context_parts else ""
    
    def clear_conversation_memory(self, conversation_id: str):
        """Clear conversation memory for a session"""
        if conversation_id in self.conversation_memories:
            del self.conversation_memories[conversation_id]
    
    def search_similar_documents(self, query: str, db: Session, top_k: int = 5, use_reranker: bool = True, conversation_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity
        Optionally uses reranker, query rewrite, and hybrid retrieve to improve relevance
        """
        logger.info(f"Searching for similar documents: {query[:50]}...")
        
        # Step 1: Query Enhancement (using Gemini API or simple enhancement)
        original_query = query
        if conversation_context:
            try:
                from utils.query_enhancer import enhance_query
                query = enhance_query(query, conversation_context, use_gemini=True)
                if query != original_query:
                    logger.info(f"Query enhanced: '{original_query}' -> '{query}'")
            except Exception as e:
                logger.debug(f"Query enhancement failed: {e}, using original query")
                query = original_query
        
        model = self.load_embedding_model()
        
        # Create query embedding - BAAI/bge-m3 uses instruction prefix for queries
        if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
            # Add instruction prefix for queries in BAAI/bge-m3
            query_with_prefix = f"You are searching: {query}"
            query_embedding = model.encode(query_with_prefix, normalize_embeddings=True)
        else:
            query_embedding = model.encode(query)
        
        # Retrieve more documents initially if using reranker
        retrieval_k = self.rerank_top_k if (use_reranker and self.use_reranker) else top_k
        
        # Search using pgvector cosine similarity
        query_embedding_str = str(query_embedding.tolist())
        search_query = text(f"""
            SELECT 
                e.chunk_id,
                e.content,
                e.title,
                e.doc_type,
                e.source_url,
                e.metadata,
                1 - (e.embedding <=> '{query_embedding_str}'::vector) as similarity_score
            FROM embeddings e
            WHERE e.embedding IS NOT NULL
            ORDER BY e.embedding <=> '{query_embedding_str}'::vector
            LIMIT {retrieval_k}
        """)
        
        results = db.execute(search_query).fetchall()
        
        # Format results
        similar_docs = []
        for result in results:
            similar_docs.append({
                "chunk_id": result.chunk_id,
                "content": result.content,
                "title": result.title,
                "doc_type": result.doc_type,
                "source_url": result.source_url,
                "metadata": result.metadata,
                "similarity_score": float(result.similarity_score)
            })
        
        # Step 2: Hybrid Retrieve (BM25 + Vector)
        if self.new_services_available and hasattr(self, 'hybrid_retrieve_service'):
            try:
                similar_docs = self.hybrid_retrieve_service.hybrid_search(
                    original_query,  # Use original query for BM25
                    similar_docs,
                    db,
                    top_k=retrieval_k
                )
                logger.info(f"Hybrid retrieve applied, found {len(similar_docs)} documents")
            except Exception as e:
                logger.warning(f"Hybrid retrieve failed: {e}, using vector results only")
        
        # Step 3: Rerank if enabled
        if use_reranker and self.use_reranker and len(similar_docs) > 1:
            similar_docs = self.rerank_documents(query, similar_docs)
            # Take top k after reranking
            similar_docs = similar_docs[:top_k]
        else:
            # Just take top k
            similar_docs = similar_docs[:top_k]
        
        logger.info(f"Found {len(similar_docs)} similar documents")
        return similar_docs
    
    def search_similar_categories(self, query: str, db: Session, top_k: int = 1) -> List[Dict[str, Any]]:
        """
        Search for similar categories using vector similarity (Layer 2 - RAG 3 Layer)
        Returns categories with their category_id from metadata
        """
        start_time = time.time()
        logger.info(f"Searching for similar categories: {query[:50]}...")
        
        timing = {}
        
        # Load model timing
        timing['load_model_start'] = time.time()
        model = self.load_embedding_model()
        timing['load_model'] = time.time() - timing['load_model_start']
        
        # Create query embedding - BAAI/bge-m3 uses instruction prefix for queries
        timing['encode_query_start'] = time.time()
        if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
            query_with_prefix = f"Bạn đang tìm kiếm: {query}"
            query_embedding = model.encode(query_with_prefix, normalize_embeddings=True)
        else:
            query_embedding = model.encode(query)
        timing['encode_query'] = time.time() - timing['encode_query_start']
        
        # Search using pgvector cosine similarity in the embedding_categories table
        # OPTIMIZATION: Split into 2 steps so the index can work more efficiently
        # Step 1: Find chunk_id and similarity (use only the index, no need to read content)
        # Step 2: Retrieve full data using the chunk_id values found
        timing['db_search_start'] = time.time()
        
        # Optimization: Set work_mem and ef_search so the query planner can use the index more efficiently
        # IMPORTANT: SET LOCAL only works inside a transaction block
        ef_search = max(16, top_k * 2)  # Minimum 16, or top_k * 2
        logger.info(f"🔧 Attempting to set ef_search={ef_search} for HNSW query (top_k={top_k})")
        
        try:
            # Ensure there is a transaction: SQLAlchemy with autocommit=False automatically creates one
            # However, we need to execute a statement to start the transaction
            # SET LOCAL must be executed within the same transaction as the query
            db.execute(text("BEGIN"))
            db.execute(text("SET LOCAL work_mem = '256MB'"))
            db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
            logger.info(f"✅ Successfully set ef_search={ef_search} for HNSW query (top_k={top_k})")
        except Exception as e:
            logger.warning(f"⚠️  Unable to set work_mem or ef_search: {e}")
            logger.warning(f"⚠️  Error type: {type(e).__name__}, Error: {str(e)}")
            # If these settings cannot be applied, continue execution but the query may be slower
        
        query_embedding_str = str(query_embedding.tolist())
        
        # Step 1: Find top_k chunk_ids with similarity (FAST - uses only the index)
        # OPTIMIZATION: Use a parameterized query to avoid string interpolation overhead
        timing['find_chunk_ids_start'] = time.time()

        # Note: pgvector requires the embedding to be cast to the vector type
        # Therefore string interpolation is still needed for the vector, but it is optimized by
        # selecting only chunk_id and similarity_score (not selecting content)
        find_ids_query = text(f"""
            SELECT 
                ec.chunk_id,
                1 - (ec.embedding <=> '{query_embedding_str}'::vector) as similarity_score
            FROM embedding_categories ec
            WHERE ec.embedding IS NOT NULL
            ORDER BY ec.embedding <=> '{query_embedding_str}'::vector
            LIMIT :top_k
        """)
        
        chunk_ids_result = db.execute(find_ids_query, {"top_k": top_k}).fetchall()
        timing['find_chunk_ids'] = time.time() - timing['find_chunk_ids_start']
        
        if not chunk_ids_result:
            timing['db_search'] = time.time() - timing['db_search_start']
            logger.info(f"⏱️  Category search: find_chunk_ids={timing.get('find_chunk_ids', 0):.3f}s, total={timing['db_search']:.3f}s")
            return []
        
        # Step 2: Retrieve full data from chunk_ids (QUICKLY - use primary key index)
        timing['fetch_data_start'] = time.time()
        chunk_ids = [row.chunk_id for row in chunk_ids_result]
        similarity_scores = {row.chunk_id: float(row.similarity_score) for row in chunk_ids_result}
        
        fetch_data_query = text("""
            SELECT 
                ec.chunk_id,
                ec.content,
                ec.title,
                ec.doc_type,
                ec.source_url,
                ec.metadata
            FROM embedding_categories ec
            WHERE ec.chunk_id = ANY(:chunk_ids)
        """)
        
        results = db.execute(fetch_data_query, {"chunk_ids": chunk_ids}).fetchall()
        timing['fetch_data'] = time.time() - timing['fetch_data_start']
        
        timing['db_search'] = time.time() - timing['db_search_start']
        
        # Log breakdown timing
        logger.info(f"⏱️  Category search breakdown: find_chunk_ids={timing.get('find_chunk_ids', 0):.3f}s, "
                   f"fetch_data={timing.get('fetch_data', 0):.3f}s, "
                   f"total={timing['db_search']:.3f}s")
        
        # Log query plan if Category search step operate slowly (debug) - REDUCE THRESHOLD TO 1s
        if timing['find_chunk_ids'] > 1.0:  
            logger.warning(f"Category search query is slow ({timing['find_chunk_ids']:.2f}s), checking query plan...")
            try:
                # Set ef_search and work_mem again to testing
                db.execute(text("SET LOCAL work_mem = '256MB'"))
                ef_search = max(16, top_k * 2)
                db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
                
                explain_query = text(f"""
                    EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
                    SELECT ec.chunk_id
                    FROM embedding_categories ec
                    WHERE ec.embedding IS NOT NULL
                    ORDER BY ec.embedding <=> '{query_embedding_str}'::vector
                    LIMIT 1
                """)
                explain_result = db.execute(explain_query).fetchall()
                
                logger.warning("=" * 80)
                logger.warning("QUERY PLAN ANALYSIS:")
                logger.warning("=" * 80)
                for row in explain_result[:10]:  # Log the first 10 lines
                    plan_line = str(row[0]) if hasattr(row, '__getitem__') else str(row)
                    logger.warning(plan_line)

                    if 'Seq Scan' in plan_line:
                        logger.error("Query is using Sequential Scan - INDEX IS NOT BEING USED!")
                        logger.error("   → Run: ANALYZE embedding_categories;")

                    elif 'Index Scan' in plan_line and 'hnsw' in plan_line.lower():
                        logger.info(f"Query is using HNSW index: {plan_line[:150]}")

                    elif 'Index Scan' in plan_line:
                        logger.info(f"Query is using an index: {plan_line[:150]}")

                logger.warning("=" * 80)
            except Exception as e:
                logger.error(f"Unable to log query plan: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Format results and extract category_id from metadata
        # Retrieve similarity_score from the similarity_scores dictionary (do not set it on the Row object)
        similar_categories = []
        for result in results:
            metadata = result.metadata or {}
            category_id = metadata.get('category_id')
            
            # Get similarity_score from the dictionary created in step 1
            similarity_score = similarity_scores.get(result.chunk_id, 0.0)
            
            similar_categories.append({
                "chunk_id": result.chunk_id,
                "content": result.content,
                "title": result.title,
                "doc_type": result.doc_type,
                "source_url": result.source_url,
                "metadata": result.metadata,
                "category_id": category_id,  # Extract category_id
                "similarity_score": float(similarity_score)  # Retrieved from dict, not set on Row
            })
        
        total_time = time.time() - start_time
        timing['total'] = total_time
        
        logger.info(f"Found {len(similar_categories)} similar categories")
        if similar_categories:
            logger.info(f"Top category ID: {similar_categories[0].get('category_id')}, similarity: {similar_categories[0].get('similarity_score'):.3f}")
        
        # Log detailed timing
        logger.info(f"⏱️  Category search breakdown: load_model={timing.get('load_model', 0):.3f}s, "
                   f"encode_query={timing.get('encode_query', 0):.3f}s, "
                   f"db_search={timing.get('db_search', 0):.3f}s, "
                   f"total={total_time:.3f}s")
        
        return similar_categories
    
    def get_documents_by_category_ids(self, db: Session, category_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get documents that belong to the given category_ids (Layer 1 - RAG 3 Layer)
        Uses document_category_map to find documents
        """
        start_time = time.time()
        if not category_ids:
            return []
        
        query = text("""
            SELECT DISTINCT 
                d.id,
                d.title,
                d.text_content,
                d.doc_type,
                d.effective_date,
                d.source_url,
                dcm.category_id
            FROM documents d
            JOIN document_category_map dcm ON d.id = dcm.document_id
            WHERE dcm.category_id = ANY(:category_ids)
            AND d.text_content IS NOT NULL
            AND LENGTH(TRIM(d.text_content)) > 0
            ORDER BY d.id ASC
        """)
        
        db_start = time.time()
        results = db.execute(query, {"category_ids": category_ids}).fetchall()
        db_time = time.time() - db_start
        
        documents = []
        for result in results:
            documents.append({
                "id": result.id,
                "title": result.title,
                "text_content": result.text_content,
                "doc_type": result.doc_type,
                "effective_date": result.effective_date,
                "source_url": result.source_url,
                "category_id": result.category_id
            })
        
        total_time = time.time() - start_time
        logger.info(f"Found {len(documents)} documents for category_ids: {category_ids}")
        logger.info(f"⏱️  Get documents by category: db_query={db_time:.3f}s, total={total_time:.3f}s")
        return documents
    
    def search_document_chunks_by_documents(self, query: str, db: Session, document_ids: List[int], top_k: int = 5, use_reranker: bool = True, conversation_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks within specific documents (Layer 1 - RAG 3 Layer)
        Only searches in embedding_documents table for chunks belonging to the given document_ids
        Now with query rewrite and hybrid retrieval support
        """
        start_time = time.time()
        timing = {}
        if not document_ids:
            return []
        
        # Query enhancement with conversation context (using Gemini API or simple enhancement)
        timing['query_enhance_start'] = time.time()
        original_query = query
        if conversation_context:
            try:
                from utils.query_enhancer import enhance_query
                query = enhance_query(query, conversation_context, use_gemini=True)
                if query != original_query:
                    logger.info(f"Query enhanced: '{original_query}' → '{query}'")
            except Exception as e:
                logger.debug(f"Query enhancement failed: {e}, using original query")
                query = original_query
        timing['query_enhance'] = time.time() - timing['query_enhance_start']
        
        logger.info(f"Searching for document chunks in {len(document_ids)} documents: {query[:50]}...")
        
        timing['load_model_start'] = time.time()
        model = self.load_embedding_model()
        timing['load_model'] = time.time() - timing['load_model_start']
        
        # Create query embedding
        timing['encode_query_start'] = time.time()
        if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
            query_with_prefix = f"Bạn đang tìm kiếm: {query}"
            query_embedding = model.encode(query_with_prefix, normalize_embeddings=True)
        else:
            query_embedding = model.encode(query)
        timing['encode_query'] = time.time() - timing['encode_query_start']
        
        # Retrieve more chunks initially if using reranker
        retrieval_k = self.rerank_top_k if (use_reranker and self.use_reranker) else top_k
        
        # Search using pgvector cosine similarity in embedding_documents table
        # Filter by document_id from metadata
        timing['db_search_start'] = time.time()
        
        # Optimization: Set work_mem and ef_search so that the query planner can use the index efficiently.
        try:
            db.execute(text("SET LOCAL work_mem = '256MB'"))
            
            # ef_search: Number of candidates to examine during HNSW search
            # Should be = retrieval_k * 2–3 to ensure good recall
            ef_search = max(16, retrieval_k * 2)  # Minimum 16, or retrieval_k * 2
            
            db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
            logger.debug(f"Set ef_search={ef_search} for HNSW chunk search (retrieval_k={retrieval_k})")

        except Exception as e:
            logger.debug(f"Unable to set work_mem or ef_search: {e}")

        query_embedding_str = str(query_embedding.tolist())
        
        # Step 1: Find chunk_ids with similarity (only use index)
        timing['find_chunk_ids_start'] = time.time()
        find_ids_query = text(f"""
            SELECT 
                ed.chunk_id,
                1 - (ed.embedding <=> '{query_embedding_str}'::vector) as similarity_score
            FROM embedding_documents ed
            WHERE ed.embedding IS NOT NULL
            AND (ed.metadata->>'document_id')::integer = ANY(:document_ids)
            ORDER BY ed.embedding <=> '{query_embedding_str}'::vector
            LIMIT :retrieval_k
        """)
        
        chunk_ids_result = db.execute(find_ids_query, {"document_ids": document_ids, "retrieval_k": retrieval_k}).fetchall()
        timing['find_chunk_ids'] = time.time() - timing['find_chunk_ids_start']
        
        if not chunk_ids_result:
            timing['db_search'] = time.time() - timing['db_search_start']
            logger.info(f"⏱️  Chunk search: find_chunk_ids={timing.get('find_chunk_ids', 0):.3f}s, total={timing['db_search']:.3f}s")
            return []
        
        # Step 2: Get full data from chunk_ids (using primary key index)
        timing['fetch_data_start'] = time.time()
        chunk_ids = [row.chunk_id for row in chunk_ids_result]
        similarity_scores = {row.chunk_id: float(row.similarity_score) for row in chunk_ids_result}
        
        fetch_data_query = text("""
            SELECT 
                ed.chunk_id,
                ed.content,
                ed.title,
                ed.doc_type,
                ed.source_url,
                ed.metadata
            FROM embedding_documents ed
            WHERE ed.chunk_id = ANY(:chunk_ids)
        """)
        
        results = db.execute(fetch_data_query, {"chunk_ids": chunk_ids}).fetchall()
        timing['fetch_data'] = time.time() - timing['fetch_data_start']
        
        # Log breakdown timing
        logger.info(f"Chunk search breakdown: find_chunk_ids={timing.get('find_chunk_ids', 0):.3f}s, "
                   f"fetch_data={timing.get('fetch_data', 0):.3f}s")
        
        timing['db_search'] = time.time() - timing['db_search_start']
        
        # Format results - Get similarity_score from similarity_scores dict
        timing['format_results_start'] = time.time()
        similar_chunks = []
        for result in results:
            # Get similarity_score from the dict has been created at step 1
            similarity_score = similarity_scores.get(result.chunk_id, 0.0)
            similar_chunks.append({
                "chunk_id": result.chunk_id,
                "content": result.content,
                "title": result.title,
                "doc_type": result.doc_type,
                "source_url": result.source_url,
                "metadata": result.metadata,
                "similarity_score": float(similarity_score)
            })
        timing['format_results'] = time.time() - timing['format_results_start']
        
        # Hybrid retrieval if available
        timing['hybrid_retrieve_start'] = time.time()
        if self.new_services_available and hasattr(self, 'hybrid_retrieve_service'):
            try:
                # Use hybrid search (BM25 + Vector)
                similar_chunks = self.hybrid_retrieve_service.hybrid_search(
                    original_query,  # Use original query for BM25
                    similar_chunks,
                    db,
                    top_k=retrieval_k
                )
                logger.info(f"Hybrid retrieval completed: {len(similar_chunks)} results")
            except Exception as e:
                logger.warning(f"Hybrid retrieval failed, using vector only: {e}")
        timing['hybrid_retrieve'] = time.time() - timing['hybrid_retrieve_start']
        
        # Rerank if enabled
        timing['rerank_start'] = time.time()
        if use_reranker and self.use_reranker and len(similar_chunks) > 1:
            similar_chunks = self.rerank_documents(query, similar_chunks)
            # Take top k after reranking
            similar_chunks = similar_chunks[:top_k]
        else:
            # Just take top k
            similar_chunks = similar_chunks[:top_k]
        timing['rerank'] = time.time() - timing['rerank_start']
        
        total_time = time.time() - start_time
        logger.info(f"Found {len(similar_chunks)} similar document chunks")
        logger.info(f"Chunk search breakdown: query_enhance={timing.get('query_enhance', 0):.3f}s, "
                   f"load_model={timing.get('load_model', 0):.3f}s, "
                   f"encode_query={timing.get('encode_query', 0):.3f}s, "
                   f"db_search={timing.get('db_search', 0):.3f}s, "
                   f"format_results={timing.get('format_results', 0):.3f}s, "
                   f"hybrid_retrieve={timing.get('hybrid_retrieve', 0):.3f}s, "
                   f"rerank={timing.get('rerank', 0):.3f}s, "
                   f"total={total_time:.3f}s")
        return similar_chunks
    
    def check_citations(self, response: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if citations in response match the retrieved documents
        Returns validation results
        """
        # Import citation_manager to use excluded citations
        try:
            from utils.citation_manager import get_citation_manager
            citation_manager = get_citation_manager()
        except ImportError:
            citation_manager = None
        
        citation_patterns = [
            r'Điều\s+\d+',  # Article X
            r'Khoản\s+\d+',  # Paragraph X
            r'Luật\s+[^,\s]+',  # Law name
            r'Nghị\s+định\s+\d+',  # Decree X
            r'Thông\s+tư\s+\d+',  # Circular X
        ]
        
        found_citations = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            found_citations.extend(matches)
        
        # Check if citations appear in retrieved documents
        validated_citations = []
        invalid_citations = []
        excluded_citations = []
        
        doc_titles = [doc.get('title', '') for doc in docs]
        doc_content = ' '.join([doc.get('content', '') for doc in docs])
        
        for citation in found_citations:
            # Check if that citation is excluded (from the configuration)
            if citation_manager and citation_manager.is_excluded(citation):
                excluded_citations.append(citation)
                continue
            
            # Check if citation appears in documents
            if citation.lower() in ' '.join(doc_titles).lower() or citation.lower() in doc_content.lower():
                validated_citations.append(citation)
            else:
                invalid_citations.append(citation)
        
        return {
            "found_citations": found_citations,
            "validated_citations": validated_citations,
            "invalid_citations": invalid_citations,
            "excluded_citations": excluded_citations,  # Citations have been marked excluded.
            "citation_accuracy": len(validated_citations) / len(found_citations) if found_citations else 1.0
        }
    
    def get_document_context(
        self, 
        query: str, 
        db: Session, 
        top_k: int = 3, 
        conversation_id: str = None, 
        documents: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[int] = None
    ) -> str:
        """
        Get relevant document context for RAG with conversation history
        NOTE: Synthesizer service have been remove - Currently, only documents are formatted as context.
        
        Args:
            query: The search query
            db: Database session
            top_k: Number of documents to retrieve (only used if documents is None)
            conversation_id: Optional conversation ID for context (buffer memory)
            documents: Optional pre-retrieved documents to use instead of searching again
            session_id: Optional session ID for database memory
        """
        # Use provided documents if available, otherwise search
        if documents is not None:
            # Validate documents is a list of dicts
            if not isinstance(documents, list):
                logger.warning(f"documents parameter is not a list: {type(documents)}")
                documents = []
            # Filter to ensure all are dicts
            similar_docs = [doc for doc in documents[:top_k] if isinstance(doc, dict)]
        else:
            # Get conversation context for query rewrite and enhancement
            conversation_context = None
            if conversation_id or session_id:
                conversation_context = self.get_conversation_context(
                    conversation_id or "", 
                    db=db,
                    session_id=session_id
                )
            
            # Enhance query with conversation context (using Gemini API or simple enhancement)
            enhanced_query = query
            if conversation_context:
                try:
                    from utils.query_enhancer import enhance_query
                    enhanced_query = enhance_query(query, conversation_context, use_gemini=True)
                    if enhanced_query != query:
                        logger.info(f"Query enhanced with conversation context: '{query}' -> '{enhanced_query}'")
                except Exception as e:
                    logger.debug(f"Query enhancement failed: {e}, using original query")
                    enhanced_query = query
            
            # Use reranker by default for better results, with enhanced query
            similar_docs = self.search_similar_documents(
                enhanced_query,  # using enhanced query
                db, 
                top_k=top_k, 
                use_reranker=True,
                conversation_context=conversation_context
            )
        
        context_parts = []
        
        # Add conversation context if available (summary-based memory + buffer)
        if conversation_id or session_id:
            conversation_context = self.get_conversation_context(
                conversation_id or "", 
                db=db,
                session_id=session_id
            )
            if conversation_context:
                context_parts.append(f"**Conversation History:**\n{conversation_context}\n---")
        
        # Add topic context if exist (need session_id)
        if self.new_services_available and hasattr(self, 'topic_service') and session_id:
            try:
                topic_context = self.topic_service.get_topic_context(session_id, db)
                if topic_context:
                    context_parts.append(f"{topic_context}\n---")
            except Exception as e:
                logger.debug(f"Topic context failed: {e}")
        
        # Add document context - format directly (the legal can not be summarize)
        if similar_docs:
            for doc in similar_docs:
                # Validate doc is a dict
                if not isinstance(doc, dict):
                    logger.warning(f"Skipping invalid doc in get_document_context (not a dict): {type(doc)}")
                    continue
                
                try:
                    content = doc.get('content', '')
                    content_full = content
                    
                    similarity_score = doc.get('similarity_score', 0.0)
                    score_info = f"Độ tương đồng: {similarity_score:.2f}"
                    if 'reranker_score' in doc:
                        score_info += f", Reranker: {doc['reranker_score']:.2f}"
                    if 'combined_score' in doc:
                        score_info += f", Tổng hợp: {doc['combined_score']:.2f}"
                    
                    context_parts.append(f"""
**Tài liệu: {doc.get('title', 'N/A')}**
Loại: {doc.get('doc_type', 'N/A')}
Nội dung: {content_full}
Nguồn: {doc.get('source_url', 'N/A')}
{score_info}
---
                    """)
                except Exception as e:
                    logger.warning(f"Error processing doc in get_document_context: {e}")
                    continue
        
        return "\n".join(context_parts)
    
    def get_stats(self, db: Session) -> Dict[str, Any]:
        """Get RAG system statistics"""
        total_docs = db.query(Document).count()
        total_embeddings = db.query(Embedding).count()
        
        # Get documents with embeddings
        docs_with_embeddings = db.execute(text("""
            SELECT COUNT(DISTINCT e.metadata->>'document_id') as count
            FROM embeddings e
            WHERE e.metadata->>'document_id' IS NOT NULL
        """)).fetchone()
        
        return {
            "total_documents": total_docs,
            "total_embeddings": total_embeddings,
            "documents_with_embeddings": docs_with_embeddings.count if docs_with_embeddings else 0,
            "embedding_coverage": f"{(docs_with_embeddings.count / total_docs * 100):.1f}%" if total_docs > 0 else "0%",
            "embedding_model": os.getenv('EMBEDDING_MODEL', 'unknown'),
            "embedding_dimension": self.embedding_dimension,
            "reranker_enabled": self.use_reranker,
            "reranker_model": os.getenv('RERANKER_MODEL', 'none') if self.use_reranker else 'none'
        }

# Global RAG service instance
rag_service = LegalRAGService()

if __name__ == "__main__":
    # Test RAG service
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from models.database import get_db, Document, Embedding
    
    db = next(get_db())
    try:
        stats = rag_service.get_stats(db)
        logger.info("RAG System Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        # Test search
        test_query = "tranh chấp đất đai"  
        results = rag_service.search_similar_documents(test_query, db, top_k=3)
        logger.info(f"\nTest search for '{test_query}':")
        for i, result in enumerate(results, 1):
            score_info = f"similarity: {result['similarity_score']:.3f}"
            if 'reranker_score' in result:
                score_info += f", reranker: {result['reranker_score']:.3f}"
            logger.info(f"  {i}. {result['title'][:50]}... ({score_info})")
            
    finally:
        db.close()
