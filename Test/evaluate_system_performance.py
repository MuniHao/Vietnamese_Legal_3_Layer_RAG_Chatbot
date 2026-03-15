#!/usr/bin/env python3
"""
The script evaluates system performance based on test results.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict
import statistics

# Đường dẫn thư mục results
RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_DIR = Path(__file__).parent

def load_all_test_results() -> List[Dict[str, Any]]:
    """Load all test results from the results folder"""
    all_results = []
    
    if not RESULTS_DIR.exists():
        print(f"The folder results doesn't exist: {RESULTS_DIR}")
        return all_results
    
    # Tìm tất cả file JSON trong thư mục results
    result_files = sorted(RESULTS_DIR.glob("test_results_*.json"))
    
    if not result_files:
        print(f"Don't find any file test results in folder {RESULTS_DIR}")
        return all_results
    
    print(f"Found {len(result_files)} file test results")
    
    for result_file in result_files:
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_results.append({
                    'file': result_file.name,
                    'test_date': data.get('test_date'),
                    'questions_file': data.get('questions_file_used'),
                    'data': data
                })
        except Exception as e:
            print(f"Lỗi đọc file {result_file.name}: {e}")
    
    return all_results

def calculate_metrics(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculating metrics from test results"""
    
    # Tổng hợp tất cả results từ các file
    all_question_results = []
    for result_data in all_results:
        results = result_data['data'].get('results', [])
        for r in results:
            r['source_file'] = result_data['file']
            r['test_date'] = result_data['test_date']
        all_question_results.extend(results)
    
    total_questions = len(all_question_results)
    if total_questions == 0:
        return {"error": "Don't have data to evaluate"}
    
    # Phân loại theo difficulty
    by_difficulty = defaultdict(list)
    for r in all_question_results:
        difficulty = r.get('difficulty', 'unknown')
        by_difficulty[difficulty].append(r)
    
    # 1. System-Level Metrics
    successful = [r for r in all_question_results if r.get('success', False)]
    failed = [r for r in all_question_results if not r.get('success', False)]
    
    success_rate = len(successful) / total_questions if total_questions > 0 else 0
    
    # Response times
    response_times = [r.get('response_time', 0) for r in successful if 'response_time' in r]
    avg_response_time = statistics.mean(response_times) if response_times else 0
    median_response_time = statistics.median(response_times) if response_times else 0
    p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times) if response_times else 0
    
    # Timeout rate (response_time > 60s hoặc có error)
    timeouts = [r for r in all_question_results if r.get('response_time', 0) > 60 or 'error' in r]
    timeout_rate = len(timeouts) / total_questions if total_questions > 0 else 0
    
    # 2. Retrieval Metrics (từ sources)
    all_sources = []
    similarity_scores = []
    combined_scores = []
    reranker_scores = []
    sources_counts = []
    has_chunk_id_count = 0
    has_category_id_count = 0
    
    for r in successful:
        sources = r.get('full_response', {}).get('sources', [])
        sources_count = len(sources)
        sources_counts.append(sources_count)
        
        for source in sources:
            all_sources.append(source)
            if 'similarity_score' in source:
                similarity_scores.append(source['similarity_score'])
            if 'combined_score' in source:
                combined_scores.append(source['combined_score'])
            if 'reranker_score' in source:
                reranker_scores.append(source['reranker_score'])
            if 'chunk_id' in source:
                has_chunk_id_count += 1
            if 'category_id' in source:
                has_category_id_count += 1
    
    avg_similarity = statistics.mean(similarity_scores) if similarity_scores else 0
    avg_combined_score = statistics.mean(combined_scores) if combined_scores else 0
    avg_reranker_score = statistics.mean(reranker_scores) if reranker_scores else 0
    avg_sources_count = statistics.mean(sources_counts) if sources_counts else 0
    has_sources_rate = len([r for r in successful if r.get('has_sources', False)]) / len(successful) if successful else 0
    
    # Source breakdown by category_id
    category_breakdown = defaultdict(int)
    for source in all_sources:
        if 'category_id' in source:
            cat_id = source['category_id']
            category_breakdown[cat_id] += 1
    
    # 3. Generation Metrics
    confidences = [r.get('confidence', 0) for r in successful if 'confidence' in r]
    avg_confidence = statistics.mean(confidences) if confidences else 0
    
    response_lengths = [r.get('response_length', 0) for r in successful if 'response_length' in r]
    avg_response_length = statistics.mean(response_lengths) if response_lengths else 0
    
    # 4. Performance by Difficulty
    difficulty_stats = {}
    for difficulty in ['easy', 'medium', 'hard']:
        diff_results = by_difficulty.get(difficulty, [])
        if not diff_results:
            continue
        
        diff_successful = [r for r in diff_results if r.get('success', False)]
        diff_failed = [r for r in diff_results if not r.get('success', False)]
        
        diff_response_times = [r.get('response_time', 0) for r in diff_successful if 'response_time' in r]
        diff_confidences = [r.get('confidence', 0) for r in diff_successful if 'confidence' in r]
        diff_sources_counts = [r.get('sources_count', 0) for r in diff_successful]
        
        difficulty_stats[difficulty] = {
            'total': len(diff_results),
            'successful': len(diff_successful),
            'failed': len(diff_failed),
            'success_rate': len(diff_successful) / len(diff_results) if diff_results else 0,
            'avg_response_time': statistics.mean(diff_response_times) if diff_response_times else 0,
            'median_response_time': statistics.median(diff_response_times) if diff_response_times else 0,
            'avg_confidence': statistics.mean(diff_confidences) if diff_confidences else 0,
            'avg_sources_count': statistics.mean(diff_sources_counts) if diff_sources_counts else 0,
            'avg_response_length': statistics.mean([r.get('response_length', 0) for r in diff_successful]) if diff_successful else 0
        }
    
    # 5. Source Quality Metrics
    unique_documents = len(set(s.get('document_id') for s in all_sources if 'document_id' in s))
    unique_chunks = len(set(s.get('chunk_id') for s in all_sources if 'chunk_id' in s))
    unique_categories = len(set(s.get('category_id') for s in all_sources if 'category_id' in s))
    
    # 6. Response Quality Indicators
    no_source_responses = len([r for r in successful if not r.get('has_sources', False)])
    no_source_rate = no_source_responses / len(successful) if successful else 0
    
    # 7. Test Coverage
    test_files = set(r['source_file'] for r in all_question_results)
    questions_files = set(r.get('data', {}).get('questions_file_used', 'unknown') for r in all_results)
    
    return {
        'evaluation_date': datetime.now().isoformat(),
        'test_summary': {
            'total_questions': total_questions,
            'total_test_files': len(test_files),
            'test_files': list(test_files),
            'questions_files': list(questions_files)
        },
        'system_level_metrics': {
            'success_rate': success_rate,
            'failed_rate': 1 - success_rate,
            'total_successful': len(successful),
            'total_failed': len(failed),
            'timeout_rate': timeout_rate
        },
        'performance_metrics': {
            'response_time': {
                'average': avg_response_time,
                'median': median_response_time,
                'p95': p95_response_time,
                'min': min(response_times) if response_times else 0,
                'max': max(response_times) if response_times else 0
            },
            'target_met': {
                'easy_under_5s': len([r for r in by_difficulty.get('easy', []) if r.get('response_time', 0) < 5]) / len(by_difficulty.get('easy', [])) if by_difficulty.get('easy') else 0,
                'medium_under_15s': len([r for r in by_difficulty.get('medium', []) if r.get('response_time', 0) < 15]) / len(by_difficulty.get('medium', [])) if by_difficulty.get('medium') else 0,
                'hard_under_30s': len([r for r in by_difficulty.get('hard', []) if r.get('response_time', 0) < 30]) / len(by_difficulty.get('hard', [])) if by_difficulty.get('hard') else 0
            }
        },
        'retrieval_metrics': {
            'average_similarity_score': avg_similarity,
            'average_combined_score': avg_combined_score,
            'average_reranker_score': avg_reranker_score,
            'average_sources_per_question': avg_sources_count,
            'has_sources_rate': has_sources_rate,
            'no_source_rate': no_source_rate,
            'source_quality': {
                'total_sources': len(all_sources),
                'unique_documents': unique_documents,
                'unique_chunks': unique_chunks,
                'unique_categories': unique_categories,
                'sources_with_chunk_id': has_chunk_id_count,
                'sources_with_category_id': has_category_id_count,
                'chunk_id_coverage': has_chunk_id_count / len(all_sources) if all_sources else 0,
                'category_id_coverage': has_category_id_count / len(all_sources) if all_sources else 0
            },
            'category_distribution': dict(sorted(category_breakdown.items(), key=lambda x: x[1], reverse=True)[:10])  # Top 10 categories
        },
        'generation_metrics': {
            'average_confidence': avg_confidence,
            'average_response_length': avg_response_length,
            'confidence_distribution': {
                'high_confidence_above_3': len([c for c in confidences if c >= 3.0]) / len(confidences) if confidences else 0,
                'medium_confidence_1_3': len([c for c in confidences if 1.0 <= c < 3.0]) / len(confidences) if confidences else 0,
                'low_confidence_below_1': len([c for c in confidences if c < 1.0]) / len(confidences) if confidences else 0
            }
        },
        'performance_by_difficulty': difficulty_stats,
        'overall_assessment': {
            'meets_targets': {
                'success_rate_above_95pct': success_rate >= 0.95,
                'avg_response_time_under_10s': avg_response_time < 10,
                'p95_response_time_under_15s': p95_response_time < 15,
                'timeout_rate_below_1pct': timeout_rate < 0.01,
                'has_sources_rate_above_80pct': has_sources_rate >= 0.80,
                'avg_confidence_above_2': avg_confidence >= 2.0
            },
            'system_health': {
                'status': 'healthy' if success_rate >= 0.95 and timeout_rate < 0.01 else 'needs_attention',
                'recommendations': []
            }
        }
    }

def generate_report(metrics: Dict[str, Any]) -> str:
    report = []
    report.append("THREE-LAYER RAG SYSTEM PERFORMANCE EVALUATION")
    report.append(f"\nEvaluation Date: {metrics.get('evaluation_date', 'N/A')}")
    
    # Test Summary
    test_summary = metrics.get('test_summary', {})
    report.append(f"\nTEST SUMMARY:")
    report.append(f"  - Total questions: {test_summary.get('total_questions', 0)}")
    report.append(f"  - Number of test files: {test_summary.get('total_test_files', 0)}")
    
    # System Level Metrics
    sys_metrics = metrics.get('system_level_metrics', {})
    report.append(f"\nSYSTEM METRICS:")
    report.append(f"  - Success rate: {sys_metrics.get('success_rate', 0):.2%}")
    report.append(f"  - Failure rate: {sys_metrics.get('failed_rate', 0):.2%}")
    report.append(f"  - Timeout rate: {sys_metrics.get('timeout_rate', 0):.2%}")
    
    # Performance Metrics
    perf = metrics.get('performance_metrics', {})
    rt = perf.get('response_time', {})
    report.append(f"\n⏱ RESPONSE TIME PERFORMANCE:")
    report.append(f"  - Average response time: {rt.get('average', 0):.2f}s")
    report.append(f"  - Median response time: {rt.get('median', 0):.2f}s")
    report.append(f"  - P95 (95th percentile): {rt.get('p95', 0):.2f}s")
    
    targets = perf.get('target_met', {})
    report.append(f"\nTime Targets Achieved:")
    report.append(f"    - Easy (< 5s): {targets.get('easy_under_5s', 0):.2%}")
    report.append(f"    - Medium (< 15s): {targets.get('medium_under_15s', 0):.2%}")
    report.append(f"    - Hard (< 30s): {targets.get('hard_under_30s', 0):.2%}")
    
    # Retrieval Metrics
    retrieval = metrics.get('retrieval_metrics', {})
    report.append(f"\nRETRIEVAL METRICS:")
    report.append(f"  - Average similarity score: {retrieval.get('average_similarity_score', 0):.4f}")
    report.append(f"  - Average combined score: {retrieval.get('average_combined_score', 0):.4f}")
    report.append(f"  - Average reranker score: {retrieval.get('average_reranker_score', 0):.4f}")
    report.append(f"  - Average sources per question: {retrieval.get('average_sources_per_question', 0):.2f}")
    report.append(f"  - Has sources rate: {retrieval.get('has_sources_rate', 0):.2%}")
    
    sq = retrieval.get('source_quality', {})
    report.append(f"\nSource Quality:")
    report.append(f"    - Total sources: {sq.get('total_sources', 0)}")
    report.append(f"    - Unique documents: {sq.get('unique_documents', 0)}")
    report.append(f"    - Unique chunks: {sq.get('unique_chunks', 0)}")
    report.append(f"    - Unique categories: {sq.get('unique_categories', 0)}")
    report.append(f"    - Chunk ID coverage: {sq.get('chunk_id_coverage', 0):.2%}")
    report.append(f"    - Category ID coverage: {sq.get('category_id_coverage', 0):.2%}")
    
    # Generation Metrics
    gen = metrics.get('generation_metrics', {})
    report.append(f"\nGENERATION METRICS:")
    report.append(f"  - Average confidence: {gen.get('average_confidence', 0):.4f}")
    report.append(f"  - Average response length: {gen.get('average_response_length', 0):.0f} characters")
    
    conf_dist = gen.get('confidence_distribution', {})
    report.append(f"\nConfidence Distribution:")
    report.append(f"    - High (≥ 3.0): {conf_dist.get('high_confidence_above_3', 0):.2%}")
    report.append(f"    - Medium (1.0–3.0): {conf_dist.get('medium_confidence_1_3', 0):.2%}")
    report.append(f"    - Low (< 1.0): {conf_dist.get('low_confidence_below_1', 0):.2%}")
    
    # Performance by Difficulty
    by_diff = metrics.get('performance_by_difficulty', {})
    report.append(f"\nPERFORMANCE BY DIFFICULTY:")
    for difficulty in ['easy', 'medium', 'hard']:
        if difficulty in by_diff:
            diff = by_diff[difficulty]
            report.append(f"\n  {difficulty.upper()}:")
            report.append(f"    - Total: {diff.get('total', 0)}")
            report.append(f"    - Successful: {diff.get('successful', 0)} ({diff.get('success_rate', 0):.2%})")
            report.append(f"    - Average response time: {diff.get('avg_response_time', 0):.2f}s")
            report.append(f"    - Average confidence: {diff.get('avg_confidence', 0):.4f}")
            report.append(f"    - Average sources: {diff.get('avg_sources_count', 0):.2f}")
    
    # Overall Assessment
    assessment = metrics.get('overall_assessment', {})
    meets = assessment.get('meets_targets', {})
    report.append(f"\nOVERALL ASSESSMENT:")
    report.append(f"  - Success rate ≥ 95%: {'✅' if meets.get('success_rate_above_95pct') else '❌'}")
    report.append(f"  - Avg response time < 10s: {'✅' if meets.get('avg_response_time_under_10s') else '❌'}")
    report.append(f"  - P95 response time < 15s: {'✅' if meets.get('p95_response_time_under_15s') else '❌'}")
    report.append(f"  - Timeout rate < 1%: {'✅' if meets.get('timeout_rate_below_1pct') else '❌'}")
    report.append(f"  - Has sources rate ≥ 80%: {'✅' if meets.get('has_sources_rate_above_80pct') else '❌'}")
    report.append(f"  - Avg confidence ≥ 2.0: {'✅' if meets.get('avg_confidence_above_2') else '❌'}")
    
    health = assessment.get('system_health', {})
    report.append(f"\n  System status: {health.get('status', 'unknown').upper()}")
    
    report.append("\n" + "=" * 80)
    
    return "\n".join(report)

def main():
    """Main function"""
    print("=" * 80)
    print("🔍 THREE-LAYER RAG SYSTEM PERFORMANCE EVALUATION")
    print("=" * 80)
    
    # Load all test results
    all_results = load_all_test_results()
    
    if not all_results:
        print("No data available for evaluation")
        return
    
    # Calculate metrics
    print(f"\nCalculating metrics from {len(all_results)} test result files...")
    metrics = calculate_metrics(all_results)
    
    if 'error' in metrics:
        print(f"Error: {metrics['error']}")
        return
    
    # Generate report
    report = generate_report(metrics)
    print("\n" + report)
    
    # Save results
    output_file = OUTPUT_DIR / f"system_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults have been saved to: {output_file}")
    
    # Save text report
    report_file = OUTPUT_DIR / f"system_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Text report has been saved to: {report_file}")

if __name__ == "__main__":
    main()
