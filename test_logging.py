#!/usr/bin/env python3
"""
Test script to verify RAG pipeline logging.
Sends test requests and displays corresponding logs.
"""
import json
import sys
import time
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.logger import RequestLogger, get_logger, initialize_logging
from rag_pipeline.query_analyzer import QueryAnalyzer
from rag_pipeline.config import default_config

logger = get_logger()


def test_query_analyzer():
    """Test the QueryAnalyzer with different queries."""
    print("\n" + "="*80)
    print("🧪 TESTING QUERY ANALYZER WITH LOGGING")
    print("="*80 + "\n")

    analyzer = QueryAnalyzer(default_config)

    # Test queries
    test_queries = [
        "who is ayoub ?",
        "how many messages have we exchanged",
        "is ayoub moroccan",
        "what are my contacts",
        "summarize my exchanges with Ayoub"
    ]

    print(f"Testing {len(test_queries)} queries...\n")

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{query}'")
        print("-" * 60)

        # Create request logger
        req_logger = RequestLogger(query)

        # Analyze
        logger.info(f"🔬 Testing query #{i}: '{query}'")
        analysis = analyzer.analyze(query, [])

        # Log the analysis
        req_logger.log_analysis({
            "mode": analysis.mode,
            "intent": analysis.intent,
            "rewritten_query": analysis.rewritten_query,
            "top_k": analysis.top_k,
            "date_start": analysis.date_start,
            "date_end": analysis.date_end
        })

        # Print result
        print(f"   MODE: {analysis.mode}")
        print(f"   INTENT: {analysis.intent}")
        print(f"   REWRITTEN: {analysis.rewritten_query}")
        print(f"   TOP_K: {analysis.top_k}")

        # Highlight analytics mode
        if analysis.mode == "analytics":
            print(f"   ⚠️  → ANALYTICS MODE DETECTED")
        else:
            print(f"   ✅ → RETRIEVAL MODE (Good)")

        # Save to debug log
        req_logger.save()
        time.sleep(0.5)  # Small delay between requests


def view_test_results():
    """View the test results from the log."""
    debug_log = Path("rag_data/logs/debug.jsonl")

    if not debug_log.exists():
        print("\n❌ No debug logs found yet")
        return

    print("\n" + "="*80)
    print("📊 TEST RESULTS FROM DEBUG LOG")
    print("="*80 + "\n")

    with open(debug_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Show last 5 test results
    print(f"Showing last {min(5, len(lines))} test requests:\n")

    for line in lines[-5:]:
        record = json.loads(line)
        query = record.get('query')
        events = record.get('events', [])

        # Find the analysis event
        for event in events:
            if event.get('type') == 'query_analysis':
                data = event.get('data', {})
                mode = data.get('mode')
                intent = data.get('intent')

                status = "✅ RETRIEVAL" if mode == "retrieval" else "⚠️  ANALYTICS"
                print(f"{status:15} | Query: '{query}'")
                print(f"                 | Intent: {intent}, Top_k: {data.get('top_k')}")
                break


def main():
    """Run the tests."""
    parser = argparse.ArgumentParser(description='Test logging system')
    parser.add_argument(
        '--log-verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    args = parser.parse_args()

    # Initialize logging according to flag
    initialize_logging(args.log_verbose)

    try:
        # Test the analyzer
        test_query_analyzer()

        # Give a moment for everything to flush
        time.sleep(1)

        # View results
        view_test_results()

        print("\n" + "="*80)
        print("✅ Test completed successfully!")
        print("\nTo view detailed logs:")
        print("  python view_logs.py debug")
        print("  python view_logs.py tail")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()