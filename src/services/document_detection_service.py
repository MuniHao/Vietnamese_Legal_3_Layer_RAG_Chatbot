"""
Document Detection Service
Extract and match exact document numbers from queries
 (ex: Thông tư 47/2014/TT-BTNMT / Circular 47/2014/TT-BTNMT)
"""
import re
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DocumentDetectionService:
    """Service to detect and search exact document numbers"""
    
    def __init__(self):
        # Patterns để extract document numbers
        self.patterns = [
            # Thông tư patterns
            r'Thông\s+tư\s+(\d+/\d+/TT-[A-Z]+)',  # "Thông tư 47/2014/TT-BTNMT"
            r'Thông\s+tư\s+số\s+(\d+/\d+/TT-[A-Z]+)',  # "Thông tư số 47/2014/TT-BTNMT"
            r'TT\s+(\d+/\d+/TT-[A-Z]+)',  # "TT 47/2014/TT-BTNMT"
            r'(\d+/\d+/TT-[A-Z]+)',  # Chỉ số "47/2014/TT-BTNMT"
            
            # Nghị định patterns
            r'Nghị\s+định\s+(\d+/\d+/NĐ-CP)',  # "Nghị định 170/2016/NĐ-CP"
            r'Nghị\s+định\s+số\s+(\d+/\d+/NĐ-CP)',  # "Nghị định số 170/2016/NĐ-CP"
            r'NĐ\s+(\d+/\d+/NĐ-CP)',  # "NĐ 170/2016/NĐ-CP"
            r'(\d+/\d+/NĐ-CP)',  # Chỉ số
            
            # Luật patterns
            r'Luật\s+(\d+/\d+/QH\d+)',  # "Luật 12/2017/QH14"
            r'Luật\s+số\s+(\d+/\d+/QH\d+)',  # "Luật số 12/2017/QH14"
            r'(\d+/\d+/QH\d+)',  # Chỉ số
            
            # Quyết định patterns
            r'Quyết\s+định\s+(\d+/\d+/QĐ-[A-Z]+)',  # "Quyết định 123/2020/QĐ-TTg"
            r'Quyết\s+định\s+số\s+(\d+/\d+/QĐ-[A-Z]+)',
            r'QĐ\s+(\d+/\d+/QĐ-[A-Z]+)',
            r'(\d+/\d+/QĐ-[A-Z]+)',
        ]
    
    def extract_document_info(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract the document number from the query
        
        Returns:
            Dict with keys: doc_number, doc_type, or None if not found
        """
        query_lower = query.lower()
        
        for pattern in self.patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                doc_number = match.group(1)
                
                """
                    Thông tư : Circular
                    Nghị định : Decree
                    Luật : Law
                    Quyết định : Decision
                """
                # Determine doc_type from pattern
                doc_type = None
                if 'TT-' in doc_number: 
                    doc_type = 'Thông tư' 
                elif 'NĐ-CP' in doc_number:
                    doc_type = 'Nghị định'
                elif 'QH' in doc_number:
                    doc_type = 'Luật'
                elif 'QĐ-' in doc_number:
                    doc_type = 'Quyết định'
                
                logger.info(f"Extracted document info: doc_number={doc_number}, doc_type={doc_type}")
                return {
                    'doc_number': doc_number,
                    'doc_type': doc_type,
                    'original_match': match.group(0)
                }
        
        return None
    
    def search_exact_document(
        self, 
        doc_number: str, 
        db: Session,
        category_ids: Optional[List[int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for an exact document using doc_number in the database
        
        Args:
            doc_number: Document number (e.g., "47/2014/TT-BTNMT")
            db: Database session
            category_ids: Optional list of category IDs for filtering
            
        Returns:
            Document dict or None if not found
        """
        try:
            # Search in the documents table using doc_number
            query = text("""
                SELECT 
                    d.id,
                    d.title,
                    d.text_content,
                    d.doc_type,
                    d.effective_date,
                    d.source_url,
                    d.doc_number
                FROM documents d
                WHERE d.doc_number = :doc_number
                OR d.title ILIKE :doc_number_pattern
                OR d.title ILIKE :doc_number_pattern2
                LIMIT 1
            """)
            
            # Create patterns for searching
            doc_number_pattern = f"%{doc_number}%"
            # Pattern with "Circular" prefix
            doc_number_pattern2 = f"%Thông tư%{doc_number}%"
            
            result = db.execute(query, {
                "doc_number": doc_number,
                "doc_number_pattern": doc_number_pattern,
                "doc_number_pattern2": doc_number_pattern2
            }).fetchone()
            
            if result:
                logger.info(f"Found exact document: {result.title} (ID: {result.id})")
                return {
                    "id": result.id,
                    "title": result.title,
                    "text_content": result.text_content,
                    "doc_type": result.doc_type,
                    "effective_date": result.effective_date,
                    "source_url": result.source_url,
                    "doc_number": result.doc_number
                }
            else:
                logger.debug(f"No exact document found for doc_number: {doc_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching exact document: {e}")
            return None
    
    def search_document_chunks_by_doc_number(
        self,
        doc_number: str,
        db: Session,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search chunks of a specific document using doc_number
        
        Args:
            doc_number: Document number
            db: Database session
            top_k: Number of chunks to return
            
        Returns:
            List of chunks
        """
        try:
            # Find document ID from doc_number
            doc = self.search_exact_document(doc_number, db)
            if not doc:
                return []
            
            document_id = doc['id']
            
            # Search chunks in embedding_documents
            query = text("""
                SELECT 
                    ed.chunk_id,
                    ed.content,
                    ed.title,
                    ed.doc_type,
                    ed.source_url,
                    ed.metadata
                FROM embedding_documents ed
                WHERE (ed.metadata->>'document_id')::integer = :document_id
                ORDER BY (ed.metadata->>'chunk_index')::integer ASC
                LIMIT :top_k
            """)
            
            results = db.execute(query, {
                "document_id": document_id,
                "top_k": top_k
            }).fetchall()
            
            chunks = []
            for result in results:
                chunks.append({
                    "chunk_id": result.chunk_id,
                    "content": result.content,
                    "title": result.title,
                    "doc_type": result.doc_type,
                    "source_url": result.source_url,
                    "metadata": result.metadata,
                    "similarity_score": 1.0,  # Exact match = 1.0
                    "combined_score": 1.0
                })
            
            logger.info(f"Found {len(chunks)} chunks for document {doc_number} (ID: {document_id})")
            return chunks
            
        except Exception as e:
            logger.error(f"Error searching chunks by doc_number: {e}")
            return []


# Singleton instance
_document_detection_service = None

def get_document_detection_service() -> DocumentDetectionService:
    """Get singleton instance of DocumentDetectionService"""
    global _document_detection_service
    if _document_detection_service is None:
        _document_detection_service = DocumentDetectionService()
    return _document_detection_service

