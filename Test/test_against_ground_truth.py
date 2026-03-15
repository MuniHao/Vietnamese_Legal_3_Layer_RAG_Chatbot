#!/usr/bin/env python3
"""
System test script and comparison with ground truth: 
Read questions from the questions folder, send them to the API, and compare them with ground_truth.json.
"""

import json
import os
import requests
import time
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
from collections import defaultdict

# Cấu hình
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')
API_ENDPOINT = f"{API_BASE_URL}/api/chat/gemini"

# Đường dẫn
QUESTIONS_DIR = Path(__file__).parent / "questions"
GROUND_TRUTH_FILE = Path(__file__).parent / "ground_truth.json"
OUTPUT_DIR = Path(__file__).parent / "results"

def load_ground_truth() -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Load ground truth from file
    Returns: Dict with key as (source_file, original_question_id)
    """

    if not GROUND_TRUTH_FILE.exists():
        print(f"Ground truth file does not exist: {GROUND_TRUTH_FILE}")
        print(f"Please run generate_ground_truth.py first")
        return {}

    try:
        with open(GROUND_TRUTH_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            ground_truth_list = data.get('ground_truth', [])

            # Convert to dict using (source_file, original_question_id) as key
            ground_truth_dict = {}

            for entry in ground_truth_list:
                source_file = entry.get('source_file', 'unknown')
                original_question_id = entry.get('original_question_id')

                if original_question_id is not None:
                    key = (source_file, original_question_id)
                    ground_truth_dict[key] = entry

            print(f"Loaded {len(ground_truth_dict)} ground truth entries")

            return ground_truth_dict

    except Exception as e:
        print(f"Error reading ground truth file: {e}")

        import traceback
        traceback.print_exc()

        return {}

def load_questions(questions_file: Path) -> List[Dict[str, Any]]:
    """Load question from file JSON"""
    if not questions_file.exists():
        print(f"File doesn't exist: {questions_file}")
        return []
    
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            questions = data.get('questions', [])
            return questions
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

def test_question(question_data: Dict[str, Any], auth_token: str = None) -> Dict[str, Any]:
    """Test a single question and return the result"""

    question = question_data['question']
    question_id = question_data['id']
    
    headers = {"Content-Type": "application/json"}
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    payload = {
        "message": question,
        "conversation_id": None  # Each question starts a new conversation
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
        elapsed_time = time.time() - start_time
        
        result = {
            "question_id": question_id,
            "question": question,
            "status_code": response.status_code,
            "response_time": elapsed_time,
            "success": response.status_code == 200,
            "timestamp": datetime.now().isoformat()
        }
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                result.update({
                    "response": data.get('response', ''),
                    "sources": data.get('sources', []),
                    "confidence": data.get('confidence', 0.0)
                })
                
            except json.JSONDecodeError:
                result["error"] = "Response is not valid JSON"
        
        else:
            result["error"] = response.text[:200]
        
        return result
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        
        return {
            "question_id": question_id,
            "question": question,
            "success": False,
            "error": str(e),
            "response_time": elapsed_time,
            "timestamp": datetime.now().isoformat()
        }

def compare_with_ground_truth(
    test_result: Dict[str, Any],
    ground_truth: Dict[str, Any]
) -> Dict[str, Any]:
    """So sánh kết quả test với ground truth"""
    comparison = {
        "question_id": test_result.get('question_id'),
        "question": test_result.get('question'),
        "match": {}
    }
    
    if not ground_truth:
        comparison["match"]["error"] = "No ground truth found"
        return comparison
    
    # Extract IDs từ test result (chỉ lấy top 5 sources)
    test_sources = test_result.get('sources', [])[:5]  # Top 5 cho Recall@5
    test_chunk_ids = []
    test_document_ids = []
    test_category_ids = set()
    
    for source in test_sources:
        if 'chunk_id' in source:
            test_chunk_ids.append(source['chunk_id'])
        if 'document_id' in source:
            test_document_ids.append(int(source['document_id']))
        if 'category_id' in source:
            cat_id = source['category_id']
            if isinstance(cat_id, str) and cat_id.startswith('cat_'):
                try:
                    test_category_ids.add(int(cat_id.replace('cat_', '')))
                except:
                    pass
            elif isinstance(cat_id, (int, float)):
                test_category_ids.add(int(cat_id))
    
    # Convert to sets for matching
    test_chunk_ids_set = set(test_chunk_ids)
    test_document_ids_set = set(test_document_ids)
    
    # So sánh với ground truth
    expected_chunk_ids = set(ground_truth.get('expected_chunk_ids', []))
    expected_document_ids = set(ground_truth.get('expected_document_ids', []))
    expected_category_id = ground_truth.get('expected_category_id')
    
    # Chunk IDs matching - Recall@5
    if expected_chunk_ids:
        expected_chunk_ids_set = set(expected_chunk_ids)
        
        # Recall@5 - Exact match
        matched_chunks_exact = test_chunk_ids_set & expected_chunk_ids_set
        chunk_recall_at_5_exact = len(matched_chunks_exact) / len(expected_chunk_ids_set) if expected_chunk_ids_set else 0.0
        
        # Recall@5 - Document-based match
        # Nếu có expected_document_ids, kiểm tra xem retrieved chunks có từ expected documents không
        chunk_recall_at_5_document = 0.0
        if expected_document_ids:
            # Extract document_id từ chunk_ids (format: doc_XXX_chunk_Y)
            import re
            retrieved_doc_ids_from_chunks = set()
            for chunk_id in test_chunk_ids:
                match = re.match(r'doc_(\d+)_chunk_', chunk_id)
                if match:
                    retrieved_doc_ids_from_chunks.add(int(match.group(1)))
            
            expected_doc_set = set(expected_document_ids)
            if retrieved_doc_ids_from_chunks & expected_doc_set:
                chunk_recall_at_5_document = 1.0  # Có ít nhất 1 chunk từ expected document
        
        # Recall@5 - Use exact if > 0, else use document-based
        chunk_recall_at_5 = chunk_recall_at_5_exact if chunk_recall_at_5_exact > 0 else chunk_recall_at_5_document
        
        chunk_precision = len(matched_chunks_exact) / len(test_chunk_ids_set) if test_chunk_ids_set else 0
        chunk_f1 = 2 * chunk_precision * chunk_recall_at_5 / (chunk_precision + chunk_recall_at_5) if (chunk_precision + chunk_recall_at_5) > 0 else 0
        
        comparison["match"]["chunk_ids"] = {
            "expected": list(expected_chunk_ids_set),
            "actual": list(test_chunk_ids_set),
            "matched": list(matched_chunks_exact),
            "precision": chunk_precision,
            "recall": chunk_recall_at_5,
            "recall_at_5": chunk_recall_at_5,
            "recall_at_5_exact": chunk_recall_at_5_exact,
            "recall_at_5_document": chunk_recall_at_5_document,
            "f1_score": chunk_f1,
            "match_rate": chunk_recall_at_5
        }
    else:
        comparison["match"]["chunk_ids"] = {
            "expected": [],
            "actual": list(test_chunk_ids_set),
            "matched": [],
            "precision": 0,
            "recall": 0,
            "recall_at_5": 0,
            "recall_at_5_exact": 0,
            "recall_at_5_document": 0,
            "f1_score": 0,
            "match_rate": 0
        }
    
    # Document IDs matching - Recall@5
    if expected_document_ids:
        expected_document_ids_set = set(expected_document_ids)
        matched_docs = test_document_ids_set & expected_document_ids_set
        
        # Document Recall@5
        doc_recall_at_5 = len(matched_docs) / len(expected_document_ids_set) if expected_document_ids_set else 0.0
        doc_precision = len(matched_docs) / len(test_document_ids_set) if test_document_ids_set else 0
        doc_f1 = 2 * doc_precision * doc_recall_at_5 / (doc_precision + doc_recall_at_5) if (doc_precision + doc_recall_at_5) > 0 else 0
        
        comparison["match"]["document_ids"] = {
            "expected": list(expected_document_ids_set),
            "actual": list(test_document_ids_set),
            "matched": list(matched_docs),
            "precision": doc_precision,
            "recall": doc_recall_at_5,
            "recall_at_5": doc_recall_at_5,
            "f1_score": doc_f1,
            "match_rate": doc_recall_at_5
        }
    else:
        comparison["match"]["document_ids"] = {
            "expected": [],
            "actual": list(test_document_ids_set),
            "matched": [],
            "precision": 0,
            "recall": 0,
            "recall_at_5": 0,
            "f1_score": 0,
            "match_rate": 0
        }
    
    # Category ID matching - Category Accuracy
    if expected_category_id:
        category_match = expected_category_id in test_category_ids
        comparison["match"]["category_id"] = {
            "expected": expected_category_id,
            "actual": list(test_category_ids),
            "matched": category_match,
            "correct": category_match,  # For category_accuracy calculation
            "match_rate": 1.0 if category_match else 0.0
        }
    else:
        comparison["match"]["category_id"] = {
            "expected": None,
            "actual": list(test_category_ids),
            "matched": False,
            "correct": False,
            "match_rate": 0.0
        }
    
    # Overall match score (weighted average)
    weights = {
        'chunk_ids': 0.5,
        'document_ids': 0.3,
        'category_id': 0.2
    }
    
    overall_score = (
        comparison["match"]["chunk_ids"]["f1_score"] * weights['chunk_ids'] +
        comparison["match"]["document_ids"]["f1_score"] * weights['document_ids'] +
        comparison["match"]["category_id"]["match_rate"] * weights['category_id']
    )
    
    comparison["match"]["overall_score"] = overall_score
    comparison["match"]["is_match"] = overall_score >= 0.5  # Threshold 50%
    
    return comparison

def run_tests(questions_file: Path, ground_truth: Dict[Tuple[str, int], Dict[str, Any]], auth_token: str = None):
    """Run tests and compare with ground truth"""
    print("=" * 80)
    print("TEST SYSTEM WITH GROUND TRUTH")
    
    # Load questions
    questions = load_questions(questions_file)
    if not questions:
        print("No questions available for testing")
        return
    
    print(f"\nTotal questions: {len(questions)}")
    print(f"API Endpoint: {API_ENDPOINT}")
    
    results = []
    comparisons = []
    
    # Get questions file name to match with ground truth
    questions_filename = questions_file.name
    print(f"Questions file: {questions_filename}")
    print(f"Ground truth keys available for this file:")
    available_for_file = [k for k in ground_truth.keys() if k[0] == questions_filename]
    print(f"   Found {len(available_for_file)} ground truth entries for {questions_filename}")
    if available_for_file:
        print(f"   Sample keys: {available_for_file[:3]}")
    print()
    
    for i, question_data in enumerate(questions, 1):
        question_id = question_data.get('id')
        question = question_data.get('question')
        
        print(f"\n[{i}/{len(questions)}] Testing question {question_id}: {question[:60]}...")
        
        # Test question
        test_result = test_question(question_data, auth_token)
        results.append(test_result)
        
        # Compare with ground truth - match by (source_file, original_question_id)
        key = (questions_filename, question_id)
        if key in ground_truth:
            comparison = compare_with_ground_truth(test_result, ground_truth[key])
            comparisons.append(comparison)
            
            overall_score = comparison["match"].get("overall_score", 0)
            is_match = comparison["match"].get("is_match", False)
            status = "✅" if is_match else "❌"
            print(f"   {status} Match score: {overall_score:.2%} (Threshold: 50%)")
        else:
            print(f"No ground truth for question {question_id} (file: {questions_filename})")
            # Debug: print available keys
            available_keys = [k for k in ground_truth.keys() if k[1] == question_id]
            if available_keys:
                print(f"(Found {len(available_keys)} entries with question_id={question_id} but from different file)")
        
        # Delay between requests
        if i < len(questions):
            time.sleep(1)
    
    # Aggregate calculations
    successful = [r for r in results if r.get('success', False)]
    matched = [c for c in comparisons if c["match"].get("is_match", False)]
    
    # Aggregate metrics - same format as evaluation_*.json
    if comparisons:
        # Category Accuracy
        category_correct = sum(1 for c in comparisons if c["match"].get("category_id", {}).get("correct", False))
        category_accuracy = category_correct / len(comparisons) if comparisons else 0.0
        
        # Document Recall@5 (average)
        document_recalls_at_5 = [c["match"].get("document_ids", {}).get("recall_at_5", 0.0) for c in comparisons]
        document_recall_at_5 = sum(document_recalls_at_5) / len(document_recalls_at_5) if document_recalls_at_5 else 0.0
        
        # Chunk Recall@5 (average)
        chunk_recalls_at_5 = [c["match"].get("chunk_ids", {}).get("recall_at_5", 0.0) for c in comparisons]
        chunk_recall_at_5 = sum(chunk_recalls_at_5) / len(chunk_recalls_at_5) if chunk_recalls_at_5 else 0.0
        
        # Chunk Recall@5 - Exact (average)
        chunk_recalls_at_5_exact = [c["match"].get("chunk_ids", {}).get("recall_at_5_exact", 0.0) for c in comparisons]
        chunk_recall_at_5_exact = sum(chunk_recalls_at_5_exact) / len(chunk_recalls_at_5_exact) if chunk_recalls_at_5_exact else 0.0
        
        # Chunk Recall@5 - Document-based (average)
        chunk_recalls_at_5_document = [c["match"].get("chunk_ids", {}).get("recall_at_5_document", 0.0) for c in comparisons]
        chunk_recall_at_5_document = sum(chunk_recalls_at_5_document) / len(chunk_recalls_at_5_document) if chunk_recalls_at_5_document else 0.0
        
        # Average Latency
        latencies = [r.get("response_time", 0.0) for r in successful]
        average_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        # Legacy metrics
        avg_chunk_f1 = sum(c["match"].get("chunk_ids", {}).get("f1_score", 0) for c in comparisons) / len(comparisons)
        avg_doc_f1 = sum(c["match"].get("document_ids", {}).get("f1_score", 0) for c in comparisons) / len(comparisons)
        avg_category_match = sum(c["match"].get("category_id", {}).get("match_rate", 0) for c in comparisons) / len(comparisons)
        avg_overall_score = sum(c["match"].get("overall_score", 0) for c in comparisons) / len(comparisons)
    else:
        category_accuracy = document_recall_at_5 = chunk_recall_at_5 = 0.0
        chunk_recall_at_5_exact = chunk_recall_at_5_document = 0.0
        average_latency = 0.0
        avg_chunk_f1 = avg_doc_f1 = avg_category_match = avg_overall_score = 0
    
# Summary
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print(f"Successful tests: {len(successful)}/{len(results)}")
    print(f"Matched with ground truth: {len(matched)}/{len(comparisons)} ({len(matched)/len(comparisons)*100:.1f}%)" if comparisons else "⚠️  No comparisons")
    
    print(f"\nSUMMARY METRICS (same as evaluation_*.json):")
    print(f"  - Category Accuracy: {category_accuracy:.2%}")
    print(f"  - Document Recall@5: {document_recall_at_5:.2%}")
    print(f"  - Chunk Recall@5: {chunk_recall_at_5:.2%}")
    print(f"  - Chunk Recall@5 (Exact): {chunk_recall_at_5_exact:.2%}")
    print(f"  - Chunk Recall@5 (Document-based): {chunk_recall_at_5_document:.2%}")
    print(f"  - Average Latency: {average_latency:.2f}s")
    print(f"  - Total Questions: {len(questions)}")
    print(f"  - Successful API Calls: {len(successful)}")
    
    print(f"\nAdditional Metrics:")
    print(f"  - Chunk IDs F1: {avg_chunk_f1:.2%}")
    print(f"  - Document IDs F1: {avg_doc_f1:.2%}")
    print(f"  - Category ID Match: {avg_category_match:.2%}")
    print(f"  - Overall Score: {avg_overall_score:.2%}")
    
    # Save results
    OUTPUT_DIR.mkdir(exist_ok=True)
    questions_name = questions_file.stem
    output_file = OUTPUT_DIR / f"test_ground_truth_{questions_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    output_data = {
        "test_date": datetime.now().isoformat(),
        "questions_file": str(questions_file),
        "ground_truth_file": str(GROUND_TRUTH_FILE),
        "summary": {
            "total_questions": len(questions),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "with_ground_truth": len(comparisons),
            "matched": len(matched),
            "match_rate": len(matched) / len(comparisons) if comparisons else 0
        },
        "summary_metrics": {
            "category_accuracy": category_accuracy,
            "document_recall_at_5": document_recall_at_5,
            "chunk_recall_at_5": chunk_recall_at_5,
            "chunk_recall_at_5_exact": chunk_recall_at_5_exact,
            "chunk_recall_at_5_document": chunk_recall_at_5_document,
            "average_latency": average_latency,
            "total_questions": len(questions),
            "successful_api_calls": len(successful)
        },
        "metrics": {
            "average_chunk_f1": avg_chunk_f1,
            "average_document_f1": avg_doc_f1,
            "average_category_match": avg_category_match,
            "average_overall_score": avg_overall_score
        },
        "results": results,
        "comparisons": comparisons
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults have been saved to: {output_file}")
    
    return output_data

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test the system and compare with ground truth')
    parser.add_argument('--questions', type=str, default=None,
                        help='Path to questions JSON file (if not provided, all files in questions/ will be tested)')
    parser.add_argument('--token', type=str, default=None,
                        help='Authentication token (optional)')
    parser.add_argument('--url', type=str, default='http://localhost:8000',
                        help='API base URL')
    
    args = parser.parse_args()
    
    global API_BASE_URL, API_ENDPOINT
    API_BASE_URL = args.url
    API_ENDPOINT = f"{API_BASE_URL}/api/chat/gemini"
    
    # Load ground truth
    ground_truth = load_ground_truth()
    if not ground_truth:
        print("Failed to load ground truth. Please run generate_ground_truth.py first.")
        return
    
    # Determine which questions file(s) to test
    if args.questions:
        questions_files = [Path(args.questions)]
    else:
        # Test all files in questions/
        questions_files = sorted(QUESTIONS_DIR.glob("test_questions_*.json"))
    
    if not questions_files:
        print(f"No questions files found in {QUESTIONS_DIR}")
        return
    
    # Test each file
    for questions_file in questions_files:
        print(f"\n{'='*80}")
        print(f"Testing with file: {questions_file.name}")
        run_tests(questions_file, ground_truth, args.token)
if __name__ == "__main__":
    main()
