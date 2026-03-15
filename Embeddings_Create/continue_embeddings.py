#!/usr/bin/env python3
"""
Script to create embeddings starting from topic 1:
- Create embeddings for all topics from topic 1 onwards.
- Save checkpoints after each topic so you can resume.
- Automatically skip categories and documents that already have embeddings.
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from models.database import get_db, Embedding, EmbeddingDocument, EmbeddingCategory, Document, Category, Topic
from services.rag_service import rag_service
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Checkpoint file path
CHECKPOINT_FILE = Path(__file__).parent / 'embedding_checkpoint.json'
# Error log file path
ERROR_LOG_FILE = Path(__file__).parent / 'embedding_errors.json'

def load_checkpoint():
    """Load checkpoint from file"""
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
                logger.info(f"Loaded checkpoint: last completed topic_id = {checkpoint.get('last_completed_topic_id', 'none')}")
                return checkpoint
        except Exception as e:
            logger.warning(f"Could not load checkpoint: {e}")
            return None
    return None

def save_checkpoint(topic_id: int, topic_title: str, stats: dict):
    """Save checkpoint to file"""
    checkpoint = {
        'last_completed_topic_id': topic_id,
        'last_completed_topic_title': topic_title,
        'last_updated': datetime.now().isoformat(),
        'stats': stats
    }
    try:
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)
        logger.info(f"Checkpoint saved: topic_id = {topic_id}")
    except Exception as e:
        logger.error(f"Could not save checkpoint: {e}")

def get_all_topics_from_id(db, start_from_topic_id: int = 1):
    """Get all topics starting from a specific topic ID"""
    query = text("""
        SELECT id, title, code
        FROM topics
        WHERE id >= :start_from_topic_id
        ORDER BY id ASC
    """)
    topics = db.execute(query, {"start_from_topic_id": start_from_topic_id}).fetchall()
    return topics

def get_categories_for_topic(db, topic_id: int):
    """Get all categories that belong to a specific topic"""
    query = text("""
        SELECT id, title, topic_id, content
        FROM categories
        WHERE topic_id = :topic_id
        AND content IS NOT NULL
        AND LENGTH(TRIM(content)) > 0
        ORDER BY id ASC
    """)
    categories = db.execute(query, {"topic_id": topic_id}).fetchall()
    return categories

def get_documents_for_categories(db, category_ids: list):
    """Get all documents that belong to the given categories"""
    if not category_ids:
        return []
    
    query = text("""
        SELECT DISTINCT d.id, d.title, d.text_content, d.doc_type, d.effective_date, d.source_url
        FROM documents d
        JOIN document_category_map dcm ON d.id = dcm.document_id
        WHERE dcm.category_id = ANY(:category_ids)
        AND d.text_content IS NOT NULL
        AND LENGTH(TRIM(d.text_content)) > 0
        ORDER BY d.id ASC
    """)
    documents = db.execute(query, {"category_ids": category_ids}).fetchall()
    return documents

def get_document_metadata(db, document_id: int):
    """Get full metadata for a document including category_id and topic_id"""
    query = text("""
        SELECT 
            d.id,
            d.title,
            d.doc_type,
            d.effective_date,
            d.source_url,
            d.doc_number,
            d.issuing_agency,
            d.signing_date,
            -- Get category_id from document_category_map
            (SELECT category_id 
             FROM document_category_map 
             WHERE document_id = d.id 
             LIMIT 1) as category_id,
            -- Get topic_id from category
            (SELECT c.topic_id 
             FROM document_category_map dcm
             JOIN categories c ON c.id = dcm.category_id
             WHERE dcm.document_id = d.id 
             LIMIT 1) as topic_id
        FROM documents d
        WHERE d.id = :doc_id
    """)
    result = db.execute(query, {"doc_id": document_id}).fetchone()
    return result

def check_category_has_embeddings(db, category_id: int):
    """Check if a category already has embeddings"""
    query = text("""
        SELECT COUNT(*) 
        FROM embedding_categories 
        WHERE (metadata->>'category_id')::integer = :cat_id
    """)
    result = db.execute(query, {"cat_id": category_id}).scalar()
    return result > 0

def check_document_has_embeddings(db, document_id: int):
    """Check if a document already has embeddings"""
    query = text("""
        SELECT COUNT(*) 
        FROM embedding_documents 
        WHERE (metadata->>'document_id')::integer = :doc_id
    """)
    result = db.execute(query, {"doc_id": document_id}).scalar()
    return result > 0

def create_category_embeddings(db, categories, model, failed_list=None):
    """Create embeddings for categories - skip if already exists"""
    created = 0
    skipped = 0
    total = len(categories)
    if failed_list is None:
        failed_list = []
    
    for cat_idx, cat in enumerate(categories, 1):
        try:
            # Check if category already has embeddings
            if check_category_has_embeddings(db, cat.id):
                skipped += 1
                print(f"Category {cat.id}: Embeddings already exist, skipping... ({cat_idx}/{total})")
                continue
            
            # Split category content into semantic chunks (chunk by sentences for categories)
            chunks = rag_service._semantic_chunk_text(cat.content, chunk_by_article=False)
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
                existing = db.query(EmbeddingCategory).filter(EmbeddingCategory.chunk_id == chunk_id).first()
                if existing:
                    continue

                # Insert embedding record into embedding_categories
                new_embedding = EmbeddingCategory(
                    chunk_id=chunk_id,
                    content=chunk,
                    embedding=embedding.tolist(),
                    metadata_json={
                        "category_id": cat.id,
                        "topic_id": cat.topic_id,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "source": "categories"
                    },
                    title=cat.title,
                    doc_type="category",
                    source_url=None
                )

                db.add(new_embedding)
                created += 1

            db.commit()
            print(f"Category {cat.id}: {cat.title[:60]}... - {len(chunks)} chunks ({cat_idx}/{total})")

        except Exception as e:
            logger.error(f"Error creating embeddings for category {cat.id}: {e}")
            db.rollback()
            import traceback
            error_trace = traceback.format_exc()
            
            # Track failed category
            failed_list.append({
                'type': 'category',
                'id': cat.id,
                'title': cat.title,
                'topic_id': cat.topic_id,
                'error': str(e),
                'error_type': type(e).__name__,
                'traceback': error_trace
            })
            traceback.print_exc()
            continue
    
    return created, skipped

def create_document_embeddings(db, documents, model, failed_list=None):
    """Create embeddings for documents with full metadata - skip if already exists"""
    created = 0
    skipped = 0
    total = len(documents)
    if failed_list is None:
        failed_list = []
    
    for doc_idx, doc in enumerate(documents, 1):
        try:
            # Check if document already has embeddings
            if check_document_has_embeddings(db, doc.id):
                skipped += 1
                print(f"Document {doc.id}: Embeddings already exist, skipping... ({doc_idx}/{total})")
                continue
            
            # Get full metadata for this document
            metadata = get_document_metadata(db, doc.id)
            
            if not metadata:
                logger.warning(f"Could not get metadata for document {doc.id}, skipping...")
                continue
            
            # Split document into semantic chunks (chunk by Điều/Khoản)
            chunks = rag_service._semantic_chunk_text(doc.text_content, chunk_by_article=True)
            logger.info(f"Document {doc.id}: Created {len(chunks)} semantic chunks")
            
            # Count tokens for each chunk (for logging)
            chunk_token_counts = [rag_service._count_tokens(chunk) for chunk in chunks]
            avg_tokens = sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0

            for i, chunk in enumerate(chunks):
                # Encode chunk
                if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
                    embedding = model.encode(chunk, normalize_embeddings=True)
                else:
                    embedding = model.encode(chunk)

                # Create chunk ID
                chunk_id = f"doc_{doc.id}_chunk_{i}"

                # Skip if exists
                existing = db.query(EmbeddingDocument).filter(EmbeddingDocument.chunk_id == chunk_id).first()
                if existing:
                    continue

                # Format effective_date for metadata
                effective_date_str = None
                if metadata.effective_date:
                    if isinstance(metadata.effective_date, datetime):
                        effective_date_str = metadata.effective_date.strftime('%Y-%m-%d')
                    else:
                        effective_date_str = str(metadata.effective_date)

                # Create metadata with all required fields
                metadata_json = {
                    "document_id": doc.id,
                    "doc_id": f"vb_{doc.id}",
                    "doc_title": doc.title,
                    "category_id": f"cat_{metadata.category_id}" if metadata.category_id else None,
                    "topic_id": f"topic_{metadata.topic_id}" if metadata.topic_id else None,
                    "doc_type": doc.doc_type or metadata.doc_type,
                    "effective_date": effective_date_str,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": "documents"
                }

                # Insert embedding record into embedding_documents
                new_embedding = EmbeddingDocument(
                    chunk_id=chunk_id,
                    content=chunk,
                    embedding=embedding.tolist(),
                    metadata_json=metadata_json,
                    title=doc.title,
                    doc_type=doc.doc_type or metadata.doc_type,
                    source_url=doc.source_url
                )

                db.add(new_embedding)
                created += 1

            db.commit()
            print(f"Document {doc.id}: {doc.title[:60]}... - {len(chunks)} chunks (avg {avg_tokens:.0f} tokens) ({doc_idx}/{total})")

        except Exception as e:
            logger.error(f"Error creating embeddings for document {doc.id}: {e}")
            db.rollback()
            import traceback
            error_trace = traceback.format_exc()
            
            # Track failed document
            failed_list.append({
                'type': 'document',
                'id': doc.id,
                'title': doc.title,
                'error': str(e),
                'error_type': type(e).__name__,
                'traceback': error_trace
            })
            traceback.print_exc()
            continue
    
    return created, skipped

def process_topic(db, topic, model, failed_list=None):
    """Process a single topic: create embeddings for its categories and documents"""
    topic_id = topic.id
    topic_title = topic.title
    if failed_list is None:
        failed_list = []
    
    print(f"Processing Topic {topic_id}: {topic_title[:60]}...")
    
    # Get categories for this topic
    categories = get_categories_for_topic(db, topic_id)
    
    if not categories:
        print(f"Topic {topic_id}: Doesn't have any categories!")
        return {
            'topic_id': topic_id,
            'categories_created': 0,
            'categories_skipped': 0,
            'documents_created': 0,
            'documents_skipped': 0
        }
    
    category_ids = [c.id for c in categories]
    print(f"\nTopic {topic_id}: Found {len(categories)} categories")
    
    # Get documents for these categories
    documents = get_documents_for_categories(db, category_ids)
    
    if not documents:
        print(f"Topic {topic_id}: Doesn;t have any documents !")
        doc_created, doc_skipped = 0, 0
    else:
        print(f"Topic {topic_id}: Found {len(documents)} documents")
        doc_created, doc_skipped = 0, 0
    
    # Create category embeddings (Tầng 2)
    print(f"\nTopic {topic_id}: CREATE EMBEDDINGS FOR CATEGORIES (Layer 2)...")
    cat_created, cat_skipped = create_category_embeddings(db, categories, model, failed_list)
    print(f"Topic {topic_id}: Categories - Đã tạo: {cat_created}, Đã bỏ qua: {cat_skipped}")
    
    # Create document embeddings (Tầng 1)
    if documents:
        print(f"\nTopic {topic_id}: CREATE EMBEDDINGS FOR DOCUMENTS (Layer 1)...")
        doc_created, doc_skipped = create_document_embeddings(db, documents, model, failed_list)
        print(f"Topic {topic_id}: Documents - created: {doc_created}, skipped: {doc_skipped}")
    
    return {
        'topic_id': topic_id,
        'categories_created': cat_created,
        'categories_skipped': cat_skipped,
        'documents_created': doc_created,
        'documents_skipped': doc_skipped
    }

def main():
print("\n📋 This script will:")
print("   1. Retrieve all topics starting from Topic 1")
print("   2. Process topics sequentially")
print("   3. Generate embeddings for categories (level 2) and documents (level 1)")
print("   4. Save a checkpoint after each topic to allow resuming")

print("\n💡 Features:")
print("   - Automatically skip categories and documents that already have embeddings")
print("   - Save a checkpoint after each completed topic")
print("   - Resume from the last checkpoint if the process is interrupted\n")
    
    # Load checkpoint
    checkpoint = load_checkpoint()
    start_from_topic_id = 1
    
if checkpoint:
    last_topic_id = checkpoint.get('last_completed_topic_id')
    if last_topic_id:
        print(f"Found checkpoint: Topic {last_topic_id} has already been completed")
        resume = input(f"Do you want to continue from topic {last_topic_id + 1}? (yes/no, default: yes): ").strip().lower()
        if resume in ["", "yes", "y"]:
            start_from_topic_id = last_topic_id + 1
            print(f"Will continue from topic {start_from_topic_id}\n")
        else:
            print(f"Will start from topic {start_from_topic_id}\n")
    else:
        print(f"Will start from topic {start_from_topic_id}\n")
else:
    print(f"Will start from topic {start_from_topic_id}\n")
    
    db = next(get_db())
    try:
        # Get all topics from topic 1 onwards
        print("STEP 1: GET ALL TOPICS FROM TOPICS 1 ONWARDS")
        topics = get_all_topics_from_id(db, start_from_topic_id)
        
        if not topics:
            print(f"No topics found starting from topic {start_from_topic_id}!")
            return
        
        print(f"\nFound {len(topics)} topics:")
        for topic in topics[:10]:  # Show first 10
            print(f"   - Topic {topic.id}: {topic.title[:60]}...")
        if len(topics) > 10:
            print(f"   ... and {len(topics) - 10} more topics")

        # Load model
        print("\STEP 2: LOAD MODEL")
        print(f"   Model: {os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')}")
        print(f"   Chunk size: {os.getenv('MAX_CHUNK_SIZE', '500')} tokens")
        print(f"   Overlap: {os.getenv('CHUNK_OVERLAP', '100')} tokens\n")
        
        model = rag_service.load_embedding_model()
        
        # Process each topic
        print("\STEP 3: PROCESSING EACH TOPIC")
        
        total_topics = len(topics)
        total_cat_created = 0
        total_cat_skipped = 0
        total_doc_created = 0
        total_doc_skipped = 0
        
        # Track failed documents and categories
        failed_items = []
        
        for topic_idx, topic in enumerate(topics, 1):
            try:
                print(f"\n{'='*70}")
                print(f"TOPIC {topic_idx}/{total_topics}: Topic {topic.id}")
                print(f"{'='*70}")
                
                # Process this topic
                result = process_topic(db, topic, model, failed_items)
                
                # Update totals
                total_cat_created += result['categories_created']
                total_cat_skipped += result['categories_skipped']
                total_doc_created += result['documents_created']
                total_doc_skipped += result['documents_skipped']
                
                # Save checkpoint after each topic
                from services.rag_service import rag_service as rs
                stats = rs.get_stats(db)
                save_checkpoint(topic.id, topic.title, stats)
                
                print(f"\nCompleted Topic {topic.id} ({topic_idx}/{total_topics})")
                print(f"   - Categories: {result['categories_created']} created, {result['categories_skipped']} skipped (already exist)")
                print(f"   - Documents: {result['documents_created']} created, {result['documents_skipped']} skipped (already exist)")
                                
            except Exception as e:
                logger.error(f"Error processing topic {topic.id}: {e}")
                import traceback
                traceback.print_exc()
                print(f"\n❌ Error while processing Topic {topic.id}. A checkpoint has been saved for the previous topic.")
                print(f"   You can rerun the script to resume from Topic {topic.id}.")
                break
        
        # Final summary
        print("\n" + "="*70)
        print("SUMMARY")
        print(f"Topics processed: {topic_idx}/{total_topics}")
        print(f"Categories -> created: {total_cat_created}, skipped: {total_cat_skipped}")
        print(f"Documents  -> created: {total_doc_created}, skipped: {total_doc_skipped}")
        
        # Final stats
        from services.rag_service import rag_service as rs
        stats = rs.get_stats(db)
        print(f"\n- Total embeddings: {stats['total_embeddings']}")
        print(f"- Model: {stats.get('embedding_model', 'unknown')} ({stats.get('embedding_dimension', 'unknown')})")
        
        # Save and display failed items
        if failed_items:
            error_log = {
                'total_failed': len(failed_items),
                'failed_documents': [item for item in failed_items if item['type'] == 'document'],
                'failed_categories': [item for item in failed_items if item['type'] == 'category'],
                'generated_at': datetime.now().isoformat()
            }
            
            # Save to JSON file
            try:
                with open(ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(error_log, f, indent=2, ensure_ascii=False)
                print(f"\n⚠️  {len(failed_items)} ITEMS FAILED")
                print("="*70)
                print(f"Saved in: {ERROR_LOG_FILE}")
                
                # Display summary
                failed_docs = [item for item in failed_items if item['type'] == 'document']
                failed_cats = [item for item in failed_items if item['type'] == 'category']
                
                print(f"\nFailed documents: {len(failed_docs)}")
                print(f"Failed categories: {len(failed_cats)}")
                
                # Display error types
                error_types = {}
                for item in failed_items:
                    error_type = item['error_type']
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                
                print(f"\nError classification:")
                for err_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"      - {err_type}: {count}")
                
                # Display first 10 failed items
                print(f"\nList of the first {min(10, len(failed_items))} failed items:")
                for i, item in enumerate(failed_items[:10], 1):
                    item_type = "Document" if item['type'] == 'document' else "Category"
                    print(f"      {i}. {item_type} {item['id']}: {item['title'][:50]}...")
                    print(f"         Error: {item['error_type']} - {item['error'][:80]}...")
                
                if len(failed_items) > 10:
                    print(f"      ... and {len(failed_items) - 10} more items (see JSON for details)")
                
            except Exception as e:
                logger.error(f"Could not save error log: {e}")
        else:
            print("\nDon't have any error items!")
            # Delete error log if exists and no errors
            if ERROR_LOG_FILE.exists():
                ERROR_LOG_FILE.unlink()
        
        if topic_idx == total_topics:
            print("\Complete all topics!")
            # Delete checkpoint if completed
            if CHECKPOINT_FILE.exists():
                CHECKPOINT_FILE.unlink()
                print("have deleted checkpoint (Completed)")
        else:
            print(f"\n⚠️  Stopped at topic {topics[topic_idx-1].id}")
            print(f"   Checkpoint have already saved, you can run the script again to continue")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()

