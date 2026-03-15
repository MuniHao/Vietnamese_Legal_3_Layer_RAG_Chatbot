#!/usr/bin/env python3
"""
Script for analyzing and measuring the optimal chunk size for documents:
- Measure the actual token count of the regulations
- Analyze the chunk size distribution
- Suggest the optimal chunk size
"""
import sys
import os
from pathlib import Path
from collections import Counter
import statistics
from models.database import get_db, Document
from services.rag_service import rag_service
from sqlalchemy import text
import re

src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))


def count_tokens(text: str) -> int:
    """Count tokens using tokenizer or estimation"""
    return rag_service._count_tokens(text)

def extract_articles(text: str) -> list:
    """Extract individual articles (Điều) from document text"""
    if not text:
        return []
    
    # Split by Điều markers
    article_pattern = r'(?=Điều\s+\d+)'
    articles = re.split(article_pattern, text)
    
    # Clean and filter
    articles = [a.strip() for a in articles if a.strip()]
    return articles

def analyze_document_chunks(db, sample_size: int = 50):
    """Analyze chunk size distribution from sample documents"""
    print("PHÂN TÍCH CHUNK SIZE CHO DOCUMENTS")
    
    query = text("""
        SELECT id, title, text_content, doc_type
        FROM documents
        WHERE text_content IS NOT NULL
        AND LENGTH(TRIM(text_content)) > 100
        ORDER BY id
        LIMIT :limit
    """)
    
    documents = db.execute(query, {"limit": sample_size}).fetchall()
    
    if not documents:
        print("Không tìm thấy documents nào!")
        return
    
    print(f"\nPhân tích {len(documents)} documents\n")
    
    # Statistics
    article_token_counts = []
    chunk_token_counts = []
    article_lengths = []
    chunk_lengths = []
    
    # Process each document
    for i, doc in enumerate(documents[:10], 1):
        print(f"Document {i}/{min(10, len(documents))}: {doc.title[:60]}...")
        
        # Extract articles
        articles = extract_articles(doc.text_content)
        print(f"Số Điều: {len(articles)}")
        
        # Analyze each article
        for j, article in enumerate(articles[:5], 1):
            article_tokens = count_tokens(article)
            article_token_counts.append(article_tokens)
            article_lengths.append(len(article))
            
            chunks = rag_service._semantic_chunk_text(article, chunk_by_article=True)
            
            for chunk in chunks:
                chunk_tokens = count_tokens(chunk)
                chunk_token_counts.append(chunk_tokens)
                chunk_lengths.append(len(chunk))
        
        print(f"Phân tích {min(5, len(articles))} Điều đầu tiên\n")
    
    # Process remaining documents for statistics
    for doc in documents[10:]:
        articles = extract_articles(doc.text_content)
        for article in articles[:3]:
            article_tokens = count_tokens(article)
            article_token_counts.append(article_tokens)
            
            chunks = rag_service._semantic_chunk_text(article, chunk_by_article=True)
            for chunk in chunks:
                chunk_token_counts.append(count_tokens(chunk))
    
    # Calculate statistics
    print("THỐNG KÊ CHUNK SIZE")
    
    if article_token_counts:
        print(f"\nThống kê Điều luật (Articles):")
        print(f"Tổng số Điều phân tích: {len(article_token_counts)}")
        print(f"Token count - Min: {min(article_token_counts)}, Max: {max(article_token_counts)}")
        print(f"Token count - Trung bình: {statistics.mean(article_token_counts):.1f}")
        print(f"Token count - Median: {statistics.median(article_token_counts):.1f}")
        print(f"Token count - Std Dev: {statistics.stdev(article_token_counts):.1f if len(article_token_counts) > 1 else 0:.1f}")
        
        # Percentiles
        sorted_articles = sorted(article_token_counts)
        p25 = sorted_articles[len(sorted_articles) // 4]
        p75 = sorted_articles[3 * len(sorted_articles) // 4]
        print(f"   Token count - P25: {p25}, P75: {p75}")
    
    if chunk_token_counts:
        print(f"\nThống kê Chunks (sau khi chunking):")
        print(f"Tổng số chunks: {len(chunk_token_counts)}")
        print(f"Token count - Min: {min(chunk_token_counts)}, Max: {max(chunk_token_counts)}")
        print(f"Token count - Trung bình: {statistics.mean(chunk_token_counts):.1f}")
        print(f"Token count - Median: {statistics.median(chunk_token_counts):.1f}")
        print(f"Token count - Std Dev: {statistics.stdev(chunk_token_counts):.1f if len(chunk_token_counts) > 1 else 0:.1f}")
        
        # Percentiles
        sorted_chunks = sorted(chunk_token_counts)
        p25 = sorted_chunks[len(sorted_chunks) // 4]
        p75 = sorted_chunks[3 * len(sorted_chunks) // 4]
        print(f"   Token count - P25: {p25}, P75: {p75}")
        
        print(f"\nPhân bố chunk size:")
        size_ranges = [
            (0, 200, "Rất nhỏ (<200)"),
            (200, 400, "Nhỏ (200-400)"),
            (400, 600, "Trung bình (400-600)"),
            (600, 800, "Lớn (600-800)"),
            (800, 1000, "Rất lớn (800-1000)"),
            (1000, float('inf'), "Quá lớn (>1000)")
        ]
        
        for min_size, max_size, label in size_ranges:
            count = sum(1 for c in chunk_token_counts if min_size <= c < max_size)
            percentage = (count / len(chunk_token_counts)) * 100 if chunk_token_counts else 0
            print(f"   {label}: {count} chunks ({percentage:.1f}%)")
    
    # Recommendations
    print("ĐỀ XUẤT CHUNK SIZE TỐI ƯU")
    
    if chunk_token_counts:
        median_chunk = statistics.median(chunk_token_counts)
        mean_chunk = statistics.mean(chunk_token_counts)
        max_chunk = max(chunk_token_counts)
        
        # Recommended chunk size: 1.2-1.5x median, but not exceeding 700
        recommended_min = int(median_chunk * 1.2)
        recommended_max = min(int(median_chunk * 1.5), 700)
        
        print(f"\nPhân tích:")
        print(f"   - Median chunk size: {median_chunk:.0f} tokens")
        print(f"   - Mean chunk size: {mean_chunk:.0f} tokens")
        print(f"   - Max chunk size: {max_chunk:.0f} tokens")
        print(f"\nĐề xuất MAX_CHUNK_SIZE: {recommended_max} tokens")
        print(f"\nĐề xuất CHUNK_OVERLAP: {int(recommended_max * 0.2)} tokens")
        
        # Check current config
        current_max = int(os.getenv('MAX_CHUNK_SIZE', '500'))
        current_overlap = int(os.getenv('CHUNK_OVERLAP', '100'))
        
        print(f"\nCấu hình hiện tại:")
        print(f"MAX_CHUNK_SIZE: {current_max} tokens")
        print(f"CHUNK_OVERLAP: {current_overlap} tokens")
        
        if current_max < recommended_min:
            print(f"\n⚠️  Cảnh báo: MAX_CHUNK_SIZE hiện tại ({current_max}) có thể quá nhỏ!")
            print(f"   Nên tăng lên ít nhất {recommended_min} tokens")
        elif current_max > recommended_max * 1.2:
            print(f"\n⚠️  Cảnh báo: MAX_CHUNK_SIZE hiện tại ({current_max}) có thể quá lớn!")
            print(f"   Nên giảm xuống khoảng {recommended_max} tokens")
        else:
            print(f"\nCấu hình hiện tại hợp lý!")

def main():
    print("\nChạy script này trước khi tạo embeddings để tối ưu chunk size\n")
    
    db = next(get_db())
    try:
        # Ask for sample size
        sample_size_input = input("Nhập số documents mẫu để phân tích (Enter để dùng mặc định 50): ").strip()
        sample_size = int(sample_size_input) if sample_size_input else 50
        
        analyze_document_chunks(db, sample_size=sample_size)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()


