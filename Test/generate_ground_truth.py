#!/usr/bin/env python3
"""
Script to generate ground truth from test results
Extract chunk_ids, category_ids, and document_ids from sources to use as ground truth.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
from collections import defaultdict

# Đường dẫn thư mục
RESULTS_DIR = Path(__file__).parent / "results"
QUESTIONS_DIR = Path(__file__).parent / "questions"
OUTPUT_DIR = Path(__file__).parent

def load_all_questions() -> List[Dict[str, Any]]:
    """Load all questions from the questions/ directory"""
    all_questions = []
    
    if not QUESTIONS_DIR.exists():
        print(f"⚠️  Questions directory does not exist: {QUESTIONS_DIR}")
        return all_questions
    
    question_files = sorted(QUESTIONS_DIR.glob("test_questions_*.json"))
    
    if not question_files:
        print(f"⚠️  No question files found in {QUESTIONS_DIR}")
        return all_questions
    
    print(f"📂 Found {len(question_files)} question files")
    
    for question_file in question_files:
        try:
            with open(question_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = data.get('questions', [])
                
                for q in questions:
                    # Add source file information
                    q_with_source = q.copy()
                    q_with_source['source_file'] = question_file.name
                    all_questions.append(q_with_source)
        except Exception as e:
            print(f"Error reading file {question_file.name}: {e}")
    
    return all_questions

def extract_ground_truth_from_results() -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Extract ground truth from all test results
    Returns: Dict with key as (questions_file, question_id)
    """
    ground_truth_dict = {}  # Dict với (questions_file, question_id) làm key
    
    if not RESULTS_DIR.exists():
        print(f"Results directory does not exist: {RESULTS_DIR}")
        return []
    
    # Find all JSON files in the results directory
    result_files = sorted(RESULTS_DIR.glob("test_results_*.json"))
    
    if not result_files:
        print(f"No test result files found in {RESULTS_DIR}")
        return []
    
    print(f"Tìm thấy {len(result_files)} file test results")
    
    for result_file in result_files:
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results = data.get('results', [])
                questions_file_used = data.get('questions_file_used') or data.get('test_config', {}).get('questions_filename', 'unknown')
                
                for result in results:
                    question_id = result.get('question_id')
                    question = result.get('question')
                    difficulty = result.get('difficulty', 'unknown')
                    
                    # Create key from questions_file and question_id
                    key = (questions_file_used, question_id)
                    
                    if not question_id or not question:
                        continue
                    
                    # Only keep successful results that contain sources
                    if not result.get('success', False):
                        continue
                    
                    sources = result.get('full_response', {}).get('sources', [])
                    if not sources:
                        continue
                    
                    # Extract chunk_ids, document_ids, category_ids from sources
                    chunk_ids = []
                    document_ids = []
                    category_ids = []
                    
                    for source in sources:
                        if 'chunk_id' in source:
                            chunk_id = source['chunk_id']
                            if chunk_id not in chunk_ids:
                                chunk_ids.append(chunk_id)
                        
                        if 'document_id' in source:
                            doc_id = source['document_id']
                            if doc_id not in document_ids:
                                document_ids.append(doc_id)
                        
                        if 'category_id' in source:
                            cat_id = source['category_id']
                            # Handle category_id which may be a string like "cat_212" or a number
                            if isinstance(cat_id, str) and cat_id.startswith('cat_'):
                                try:
                                    cat_id_num = int(cat_id.replace('cat_', ''))
                                    if cat_id_num not in category_ids:
                                        category_ids.append(cat_id_num)
                                except:
                                    pass
                            elif isinstance(cat_id, (int, float)):
                                cat_id_num = int(cat_id)
                                if cat_id_num not in category_ids:
                                    category_ids.append(cat_id_num)
                    
                    # Use the response as expected_answer
                    response = result.get('full_response', {}).get('response', '')
                    
                    # Extract citations từ response (tìm các document links)
                    citations = []
                    if response:
                        # Find links like lawchat://document/ID
                        import re
                        doc_links = re.findall(r'lawchat://document/(\d+)', response)
                        citations.extend([int(doc_id) for doc_id in doc_links])
                        
                        # Find legal document numbers (e.g., 95/2015/QH13, Article 3)
                        doc_numbers = re.findall(r'(\d+/\d+/\w+-\w+)', response)
                        citations.extend(doc_numbers)
                        article_refs = re.findall(r'Điều\s+(\d+)', response)
                        citations.extend([f"Điều {art}" for art in article_refs])
                    
                    # Create ground truth entry
                    ground_truth_entry = {
                        "question_id": question_id,
                        "question": question,
                        "difficulty": difficulty
                    }
                    
                    # Only add if at least one ID exists
                    if chunk_ids or document_ids or category_ids:
                        if category_ids:
                            ground_truth_entry["expected_category_id"] = category_ids[0]  # Lấy category đầu tiên
                        if document_ids:
                            ground_truth_entry["expected_document_ids"] = document_ids
                        if chunk_ids:
                            ground_truth_entry["expected_chunk_ids"] = chunk_ids
                        if response:
                            ground_truth_entry["expected_answer"] = response[:500]  # Giới hạn 500 ký tự
                        if citations:
                            ground_truth_entry["expected_citations"] = list(set(citations))[:10]  # Top 10 unique
                        
                        # Notes
                        notes_parts = []
                        if category_ids:
                            notes_parts.append(f"Category IDs: {category_ids}")
                        if document_ids:
                            notes_parts.append(f"Document IDs: {document_ids}")
                        notes_parts.append(f"Difficulty: {difficulty}")
                        ground_truth_entry["notes"] = ", ".join(notes_parts)
                        
                        # Save or update (prioritize entries with more sources)
                        if key not in ground_truth_dict:
                            ground_truth_dict[key] = ground_truth_entry
                        else:
                            # Update if the new result has more sources
                            existing = ground_truth_dict[key]
                            if len(chunk_ids) > len(existing.get('expected_chunk_ids', [])):
                                ground_truth_dict[key] = ground_truth_entry
        
        except Exception as e:
            print(f"Error reading file {result_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    return ground_truth_dict

def main():
    """Main function"""
    print("=" * 80)
    print("GENERATING GROUND TRUTH FROM TEST RESULTS AND QUESTIONS")
    
    # Load all questions from questions/
    print("\n📚 Loading all questions from the questions/ directory...")
    all_questions = load_all_questions()
    print(f" Loaded {len(all_questions)} questions from {len(sorted(QUESTIONS_DIR.glob('test_questions_*.json')))} files")
   
    # Extract ground truth from test results
    print("\nExtracting ground truth from test results...")
    ground_truth_from_results = extract_ground_truth_from_results()
    print(f" Extracted {len(ground_truth_from_results)} ground truth entries from test results")
 
    # Generate ground truth for all questions
    print("\nGenerating ground truth for all questions...")
    ground_truth_list = []
    
    # Create a unique question_id by combining source_file and original id
    for question_data in all_questions:
        original_id = question_data.get('id')
        source_file = question_data.get('source_file', 'unknown')

        # Create unique question_id: "file_number-question_id" (e.g., "1-1", "2-1")
        # Extract number from file name (test_questions_1.json -> 1)
        import re
        file_match = re.search(r'test_questions_(\d+)', source_file)
        file_number = file_match.group(1) if file_match else '0'
        unique_question_id = f"{file_number}-{original_id}"

        # Find corresponding test result using (source_file, original_id)
        key = (source_file, original_id)

        if key in ground_truth_from_results:
            ground_truth_entry = ground_truth_from_results[key].copy()
            ground_truth_entry["question_id"] = unique_question_id
            ground_truth_entry["original_question_id"] = original_id
            ground_truth_entry["source_file"] = source_file
        else:
            # Create a new entry using only question information (no test results yet)
            ground_truth_entry = {
                "question_id": unique_question_id,
                "original_question_id": original_id,
                "question": question_data.get('question', ''),
                "difficulty": question_data.get('difficulty', 'unknown'),
                "source_file": source_file,
                "notes": f"No test results yet. Source: {source_file}, Difficulty: {question_data.get('difficulty', 'unknown')}"
            }

        ground_truth_list.append(ground_truth_entry)
    
    # Sort by question_id
    ground_truth_list.sort(key=lambda x: (x.get('source_file', ''), x.get('original_question_id', 0)))

    if not ground_truth_list:
        print("No data found to generate ground truth")
        return

    print(f" Generated {len(ground_truth_list)} ground truth entries (including questions without test results)")

    # Create structure similar to ground_truth.json
    ground_truth_data = {
        "description": "Ground truth for test questions - Automatically generated from test results",
        "version": "2.0",
        "created_date": datetime.now().isoformat(),
        "source": "Z_Test_After_Update/results",
        "total_questions": len(ground_truth_list),
        "ground_truth": ground_truth_list
    }

    
    # Statistics
    by_difficulty = defaultdict(int)
    with_chunk_ids = 0
    with_category_ids = 0
    with_document_ids = 0
    
    for entry in ground_truth_list:
        by_difficulty[entry.get('difficulty', 'unknown')] += 1
        if 'expected_chunk_ids' in entry:
            with_chunk_ids += 1
        if 'expected_category_id' in entry:
            with_category_ids += 1
        if 'expected_document_ids' in entry:
            with_document_ids += 1
    
    print(f"\nStatistics:")
    print(f"  - Total questions: {len(ground_truth_list)}")
    print(f"  - With chunk_ids: {with_chunk_ids} ({with_chunk_ids/len(ground_truth_list)*100:.1f}%)")
    print(f"  - With category_ids: {with_category_ids} ({with_category_ids/len(ground_truth_list)*100:.1f}%)")
    print(f"  - With document_ids: {with_document_ids} ({with_document_ids/len(ground_truth_list)*100:.1f}%)")

   print(f"\n  Distribution by difficulty:")
    for diff, count in sorted(by_difficulty.items()):
        print(f"    - {diff}: {count}")
    
    # Save file
    output_file = OUTPUT_DIR / "ground_truth.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ground_truth_data, f, ensure_ascii=False, indent=2)
    
    # Count how many questions have test results
    questions_with_results = sum(1 for entry in ground_truth_list 
                                 if 'expected_chunk_ids' in entry or 'expected_document_ids' in entry)
    
    print(f"\nGround truth has been saved to: {output_file}")
    print(f"   Total entries: {len(ground_truth_list)}")
    print(f"   - With test results: {questions_with_results}")
    print(f"   - Without test results: {len(ground_truth_list) - questions_with_results}")
    
if __name__ == "__main__":
    main()
