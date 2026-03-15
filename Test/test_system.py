#!/usr/bin/env python3
"""
Script to test the legal advisory system using a set of questions from test_questions.json
"""

import json
import requests
import time
import sys
import os
from typing import Dict, List, Any
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change if necessary
API_ENDPOINT = f"{API_BASE_URL}/api/chat/gemini"

# Default paths to question files (can be modified here)
QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), "questions")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
DEFAULT_QUESTIONS_FILE = os.path.join(QUESTIONS_DIR, "test_questions_6.json")


def load_questions(file_path: str) -> Dict[str, Any]:
    """Load questions from a JSON file"""
    
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def test_question(question_data: Dict[str, Any], auth_token: str = None) -> Dict[str, Any]:
    """Test a single question and return the result"""

    question = question_data['question']
    question_id = question_data['id']
    difficulty = question_data['difficulty']

    print(f"\n{'='*80}")
    print(f"Question {question_id} ({difficulty.upper()}): {question}")

    # Prepare request
    headers = {
        "Content-Type": "application/json"
    }

    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {
        "message": question,
        "conversation_id": None  # Each question starts a new conversation
    }

    # Measure response time
    start_time = time.time()

    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
        elapsed_time = time.time() - start_time

        result = {
            "question_id": question_id,
            "question": question,
            "difficulty": difficulty,
            "status_code": response.status_code,
            "response_time": elapsed_time,
            "success": response.status_code == 200,
            "timestamp": datetime.now().isoformat()
        }

        if response.status_code == 200:

            try:
                data = response.json()

                # Save the entire response data
                # chunk_id and category_id will appear inside the sources in full_response
                result.update({
                    "response_length": len(data.get('response', '')),
                    "sources_count": len(data.get('sources', [])),
                    "confidence": data.get('confidence', 0.0),
                    "has_sources": len(data.get('sources', [])) > 0,

                    # Store full API response (response, sources, chunk_id, category_id, confidence, conversation_id)
                    "full_response": data
                })

                print(f"SUCCESS - Time: {elapsed_time:.2f}s, Confidence: {data.get('confidence', 0.0):.2f}")
                print(f"   Sources: {len(data.get('sources', []))}, Response length: {len(data.get('response', ''))} chars")

            except json.JSONDecodeError:

                # If response is not JSON, store raw text
                result.update({
                    "full_response": {"raw_text": response.text},
                    "error": "Response is not valid JSON"
                })

                print(f"Warning - Response is not JSON")
                print(f"   Raw response length: {len(response.text)} chars")

        else:

            # Save the full error response
            result.update({
                "error_response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "text": response.text,
                    "url": str(response.url)
                }
            })

            print(f"FAILED - Status: {response.status_code}")
            print(f"   Error: {response.text[:200]}")

        return result

    except requests.exceptions.Timeout:

        elapsed_time = time.time() - start_time

        print(f"Timeout after {elapsed_time:.2f}s")

        return {
            "question_id": question_id,
            "question": question,
            "difficulty": difficulty,
            "success": False,
            "error": "Timeout",
            "error_type": "Timeout",
            "response_time": elapsed_time,
            "timestamp": datetime.now().isoformat(),
            "full_response": None
        }

    except Exception as e:

        elapsed_time = time.time() - start_time

        import traceback
        error_traceback = traceback.format_exc()

        print(f"Error: {str(e)}")

        return {
            "question_id": question_id,
            "question": question,
            "difficulty": difficulty,
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "error_traceback": error_traceback,
            "response_time": elapsed_time,
            "timestamp": datetime.now().isoformat(),
            "full_response": None
        }


def run_tests(questions_file: str, auth_token: str = None, filter_difficulty: str = None):
    """Run tests for all questions"""

    # Load questions
    data = load_questions(questions_file)
    questions = data['questions']

    # Filter by difficulty if specified
    if filter_difficulty:
        questions = [q for q in questions if q['difficulty'] == filter_difficulty]
        print(f"Filtering by difficulty: {filter_difficulty}")

    print(f"Total questions: {len(questions)}")
    print(f"API Endpoint: {API_ENDPOINT}")

    results = []
    total_start = time.time()

    for i, question_data in enumerate(questions, 1):

        print(f"\n[{i}/{len(questions)}] Testing question {question_data['id']}...")

        result = test_question(question_data, auth_token)
        results.append(result)

        # Small delay between requests
        if i < len(questions):
            time.sleep(1)

    total_time = time.time() - total_start

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', False)]

    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Failed: {len(failed)}/{len(results)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per question: {total_time/len(results):.2f}s")

    if successful:

        avg_response_time = sum(r['response_time'] for r in successful) / len(successful)
        avg_confidence = sum(r.get('confidence', 0) for r in successful) / len(successful)
        avg_sources = sum(r.get('sources_count', 0) for r in successful) / len(successful)

        print(f"\nStatistics (successful only):")
        print(f"   Average response time: {avg_response_time:.2f}s")
        print(f"   Average confidence: {avg_confidence:.2f}")
        print(f"   Average sources: {avg_sources:.1f}")

    # Group by difficulty
    print(f"\nBy Difficulty:")

    for difficulty in ['easy', 'medium', 'hard']:

        diff_results = [r for r in results if r['difficulty'] == difficulty]

        if diff_results:

            diff_successful = [r for r in diff_results if r.get('success', False)]

            diff_avg_time = (
                sum(r['response_time'] for r in diff_successful) / len(diff_successful)
                if diff_successful else 0
            )

            print(f"   {difficulty.upper()}: {len(diff_successful)}/{len(diff_results)} successful, avg time: {diff_avg_time:.2f}s")

    # Save results with full data
    os.makedirs(RESULTS_DIR, exist_ok=True)

    questions_filename = os.path.basename(questions_file)
    questions_name = os.path.splitext(questions_filename)[0]

    output_filename = f"test_results_{questions_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file = os.path.join(RESULTS_DIR, output_filename)

    with open(output_file, 'w', encoding='utf-8') as f:

        json.dump({
            "test_date": datetime.now().isoformat(),
            "questions_file_used": questions_filename,

            "test_config": {
                "questions_file": questions_file,
                "questions_filename": questions_filename,
                "api_endpoint": API_ENDPOINT,
                "filter_difficulty": filter_difficulty
            },

            "summary": {
                "questions_file": questions_filename,
                "total_questions": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "total_time": total_time,
                "average_time": total_time / len(results) if results else 0
            },

            "results": results

        }, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_file}")

    return results

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Testing the Legal Consultant System')
    parser.add_argument('--questions', type=str, default=DEFAULT_QUESTIONS_FILE,
                        help=f'Path to questions JSON file (default: {DEFAULT_QUESTIONS_FILE})')
    parser.add_argument('--token', type=str, default=None,
                        help='Authentication token (optional)')
    parser.add_argument('--difficulty', type=str, choices=['easy', 'medium', 'hard'],
                        help='Filter by difficulty level')
    parser.add_argument('--url', type=str, default='http://localhost:8000',
                        help='API base URL')
    
    args = parser.parse_args()
    
    global API_BASE_URL, API_ENDPOINT
    API_BASE_URL = args.url
    API_ENDPOINT = f"{API_BASE_URL}/api/chat/gemini"
    
    try:
        run_tests(args.questions, args.token, args.difficulty)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

