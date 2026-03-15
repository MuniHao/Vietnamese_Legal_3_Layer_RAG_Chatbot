"""
Hybrid Retrieve Service
Combine BM25 (keyword search) + Vector Search to improve recall
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from dotenv import load_dotenv
import numpy as np

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

class HybridRetrieveService:
    """Service for combining BM25 and vector search"""
    
    def __init__(self):
        self.enabled = os.getenv('USE_HYBRID_RETRIEVE', 'True').lower() == 'true'
        self.bm25_weight = float(os.getenv('BM25_WEIGHT', '0.3'))  # Weight for BM25
        self.vector_weight = float(os.getenv('VECTOR_WEIGHT', '0.7'))  # Weight for vector search
        self.alpha = float(os.getenv('HYBRID_ALPHA', '0.5'))  # Alpha for reciprocal rank fusion
        
        if not self.enabled:
            logger.info("Hybrid retrieve is disabled")
    
    def extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from the query for BM25 search"""
        import re
        
        # First, extract document numbers (e.g., 47/2014/TT-BTNMT)
        doc_number_patterns = [
            r'\d+/\d+/TT-[A-Z]+',  # Thông tư
            r'\d+/\d+/NĐ-CP',  # Nghị định
            r'\d+/\d+/QH\d+',  # Luật
            r'\d+/\d+/QĐ-[A-Z]+',  # Quyết định
        ]
        
        keywords = []
        remaining_query = query
        
        # Extract document numbers first
        for pattern in doc_number_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                keywords.append(match)  # Keep exact format
                # Also add parts separately for better matching
                parts = match.split('/')
                keywords.extend([p for p in parts if len(p) > 0])
                # Remove from remaining query
                remaining_query = re.sub(re.escape(match), '', remaining_query, flags=re.IGNORECASE)
        
        # Extract other keywords from remaining query
        words = remaining_query.lower().split()
        # Remove simple stop words
        stop_words = {'của', 'và', 'với', 'cho', 'từ', 'về', 'là', 'có', 'được', 'sẽ', 'đã', 'đang'}
        keywords.extend([w for w in words if len(w) > 2 and w not in stop_words])
        
        return keywords
    
    def bm25_search(self, query: str, db: Session, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        BM25 keyword search using PostgreSQL full-text search
        
        Args:
            query: Search query
            db: Database session
            top_k: Number of results
            
        Returns:
            List of documents with BM25 scores
        """
        start_time = time.time()
        if not self.enabled:
            return []
        
        try:
            timing = {}
            timing['extract_keywords_start'] = time.time()
            keywords = self.extract_keywords(query)
            timing['extract_keywords'] = time.time() - timing['extract_keywords_start']
            if not keywords:
                return []
            
            # Create search query using PostgreSQL full-text search
            # Use ts_rank to compute a BM25-like score
            # Improvement: add exact matching for document numbers
            search_terms = ' | '.join(keywords)
            
            # Extract document numbers from keywords
            doc_numbers = [k for k in keywords if '/' in k and any(x in k.upper() for x in ['TT-', 'NĐ-CP', 'QH', 'QĐ-'])]
            
            # Search in embedding_documents (primary table)
            timing['db_search_start'] = time.time()
            
            # Build query with exact matching for document numbers
            if doc_numbers:
                # If there are document numbers, add exact match conditions.
                doc_number_conditions = ' OR '.join([f"ed.title ILIKE :doc_num_{i}" for i in range(len(doc_numbers))])
                doc_number_params = {f"doc_num_{i}": f"%{doc_num}%" for i, doc_num in enumerate(doc_numbers)}
                
                search_query = text(f"""
                    SELECT 
                        ed.chunk_id,
                        ed.content,
                        ed.title,
                        ed.doc_type,
                        ed.source_url,
                        ed.metadata,
                        CASE 
                            WHEN {' OR '.join([f"ed.title ILIKE :doc_num_{i}" for i in range(len(doc_numbers))])} THEN 10.0
                            ELSE ts_rank(
                                to_tsvector('simple', COALESCE(ed.title, '') || ' ' || COALESCE(ed.content, '')),
                                plainto_tsquery('simple', :search_terms)
                            )
                        END as bm25_score
                    FROM embedding_documents ed
                    WHERE (
                        to_tsvector('simple', COALESCE(ed.title, '') || ' ' || COALESCE(ed.content, '')) 
                        @@ plainto_tsquery('simple', :search_terms)
                        OR {' OR '.join([f"ed.title ILIKE :doc_num_{i}" for i in range(len(doc_numbers))])}
                    )
                    ORDER BY bm25_score DESC
                    LIMIT :top_k
                """)
                
                params = {
                    "search_terms": search_terms,
                    "top_k": top_k,
                    **doc_number_params
                }
            else:
                # No document numbers, use the standard query
                search_query = text(f"""
                    SELECT 
                        ed.chunk_id,
                        ed.content,
                        ed.title,
                        ed.doc_type,
                        ed.source_url,
                        ed.metadata,
                        ts_rank(
                            to_tsvector('simple', COALESCE(ed.title, '') || ' ' || COALESCE(ed.content, '')),
                            plainto_tsquery('simple', :search_terms)
                        ) as bm25_score
                    FROM embedding_documents ed
                    WHERE to_tsvector('simple', COALESCE(ed.title, '') || ' ' || COALESCE(ed.content, '')) 
                          @@ plainto_tsquery('simple', :search_terms)
                    ORDER BY bm25_score DESC
                    LIMIT :top_k
                """)
                
                params = {
                    "search_terms": search_terms,
                    "top_k": top_k
                }
            
            results = db.execute(search_query, params).fetchall()
            timing['db_search'] = time.time() - timing['db_search_start']
            
            timing['format_results_start'] = time.time()
            bm25_docs = []
            for result in results:
                bm25_docs.append({
                    "chunk_id": result.chunk_id,
                    "content": result.content,
                    "title": result.title,
                    "doc_type": result.doc_type,
                    "source_url": result.source_url,
                    "metadata": result.metadata,
                    "bm25_score": float(result.bm25_score) if result.bm25_score else 0.0
                })
            timing['format_results'] = time.time() - timing['format_results_start']
            
            total_time = time.time() - start_time
            logger.info(f"BM25 search found {len(bm25_docs)} documents")
            logger.info(f"⏱️  BM25 search: extract_keywords={timing.get('extract_keywords', 0):.3f}s, "
                       f"db_search={timing.get('db_search', 0):.3f}s, "
                       f"format_results={timing.get('format_results', 0):.3f}s, "
                       f"total={total_time:.3f}s")
            return bm25_docs
            
        except Exception as e:
            logger.warning(f"Error in BM25 search: {e}")
            return []
    
    def combine_results(
        self, 
        vector_results: List[Dict[str, Any]], 
        bm25_results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and BM25 results using Reciprocal Rank Fusion (RRF)
        
        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            top_k: Final number of results
            
        Returns:
            Combined and reranked results
        """
        if not self.enabled:
            return vector_results[:top_k]
        
        # Create a dictionary to track scores
        doc_scores = {}
        
        # Add vector results with RRF score
        for rank, doc in enumerate(vector_results, 1):
            chunk_id = doc.get('chunk_id')
            if chunk_id not in doc_scores:
                doc_scores[chunk_id] = {
                    **doc,
                    "vector_score": doc.get('similarity_score', 0.0),
                    "bm25_score": 0.0,
                    "vector_rank": rank
                }
            else:
                doc_scores[chunk_id]["vector_score"] = doc.get('similarity_score', 0.0)
                doc_scores[chunk_id]["vector_rank"] = rank
        
        # Add BM25 results with RRF score
        for rank, doc in enumerate(bm25_results, 1):
            chunk_id = doc.get('chunk_id')
            if chunk_id not in doc_scores:
                doc_scores[chunk_id] = {
                    **doc,
                    "vector_score": 0.0,
                    "bm25_score": doc.get('bm25_score', 0.0),
                    "bm25_rank": rank
                }
            else:
                doc_scores[chunk_id]["bm25_score"] = doc.get('bm25_score', 0.0)
                doc_scores[chunk_id]["bm25_rank"] = rank
        
        # Calculate RRF scores
        k = 60  # RRF constant
        combined_results = []
        
        for chunk_id, doc in doc_scores.items():
            # RRF formula: score = 1/(k + rank)
            rrf_score = 0.0
            
            if "vector_rank" in doc:
                rrf_score += 1.0 / (k + doc["vector_rank"])
            
            if "bm25_rank" in doc:
                rrf_score += 1.0 / (k + doc["bm25_rank"])
            
            # Also combine normalized scores
            vector_norm = doc.get("vector_score", 0.0)
            bm25_norm = doc.get("bm25_score", 0.0)
            
            # Normalize scores to 0-1 range (rough estimate)
            if vector_norm > 0:
                vector_norm = min(1.0, vector_norm)
            if bm25_norm > 0:
                # PostgreSQL BM25 scores are usually small → scale them
                bm25_norm = min(1.0, bm25_norm * 10)  # Scale up BM25 scores
            
            # Weighted combination
            combined_score = (
                self.vector_weight * vector_norm + 
                self.bm25_weight * bm25_norm +
                (1 - self.vector_weight - self.bm25_weight) * rrf_score
            )
            
            doc["combined_score"] = combined_score
            doc["hybrid_score"] = combined_score
            combined_results.append(doc)
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)
        
        logger.info(f"Hybrid retrieve combined {len(vector_results)} vector + {len(bm25_results)} BM25 = {len(combined_results)} results")
        
        return combined_results[:top_k]
    
    def hybrid_search(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        db: Session,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and BM25
        
        Args:
            query: Search query
            vector_results: Results from vector search
            db: Database session
            top_k: Final number of results
            
        Returns:
            Combined results
        """
        start_time = time.time()
        if not self.enabled:
            return vector_results[:top_k]
        
        timing = {}
        # Get BM25 results
        timing['bm25_start'] = time.time()
        bm25_results = self.bm25_search(query, db, top_k=top_k * 2)  # Get more BM25 results
        timing['bm25'] = time.time() - timing['bm25_start']
        
        # Combine results
        timing['combine_start'] = time.time()
        combined = self.combine_results(vector_results, bm25_results, top_k=top_k)
        timing['combine'] = time.time() - timing['combine_start']
        
        total_time = time.time() - start_time
        logger.info(f"⏱️  Hybrid search: bm25={timing.get('bm25', 0):.3f}s, "
                   f"combine={timing.get('combine', 0):.3f}s, "
                   f"total={total_time:.3f}s")
        
        return combined

# Singleton instance
_hybrid_retrieve_service = None

def get_hybrid_retrieve_service() -> HybridRetrieveService:
    """Get singleton instance of HybridRetrieveService"""
    global _hybrid_retrieve_service
    if _hybrid_retrieve_service is None:
        _hybrid_retrieve_service = HybridRetrieveService()
    return _hybrid_retrieve_service
