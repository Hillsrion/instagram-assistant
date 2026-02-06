#!/usr/bin/env python3
"""
Script to view RAG pipeline logs.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
DEBUG_LOG_FILE = LOG_DIR / "debug.jsonl"
RAG_LOG_FILE = LOG_DIR / "rag_pipeline.log"


def view_debug_logs(limit: int = 10, latest: bool = True):
    """Displays structured JSONL logs (request traces)."""
    if not DEBUG_LOG_FILE.exists():
        print(f"❌ No debug logs found at {DEBUG_LOG_FILE}")
        return

    print(f"\n{'='*80}")
    print(f"📊 STRUCTURED DEBUG LOGS (Request Traces)")
    print(f"File: {DEBUG_LOG_FILE}")
    print(f"{'='*80}\n")

    with open(DEBUG_LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Show latest N records
    records_to_show = lines[-limit:] if latest else lines[:limit]

    for i, line in enumerate(records_to_show):
        record = json.loads(line)
        request_id = record.get('request_id')
        query = record.get('query')
        duration = record.get('duration_seconds', 0)
        event_count = record.get('event_count', 0)

        print(f"\n🔹 Request #{i+1}")
        print(f"   ID: {request_id}")
        print(f"   Query: {query}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Events: {event_count}")

        # Show key events
        events = record.get('events', [])
        for event in events:
            event_type = event.get('type')
            data = event.get('data', {})

            if event_type == 'query_analysis':
                print(f"   ├─ [ANALYSIS] mode={data.get('mode')}, intent={data.get('intent')}")
                print(f"   │  └─ top_k={data.get('top_k')}, rewritten={data.get('rewritten_query')}")
            elif event_type == 'retrieval':
                print(f"   ├─ [RETRIEVAL] sources={data.get('source_count')}")
            elif event_type == 'llm_response':
                print(f"   ├─ [LLM] model={data.get('model')}, response_len={data.get('response_length')}")
            elif event_type == 'error':
                print(f"   ├─ [ERROR] {data.get('type')}: {data.get('message')}")


def tail_rag_logs(lines: int = 50):
    """Displays the last N lines of the main log."""
    if not RAG_LOG_FILE.exists():
        print(f"❌ No RAG logs found at {RAG_LOG_FILE}")
        return

    print(f"\n{'='*80}")
    print(f"📝 RAG PIPELINE LOGS (Last {lines} lines)")
    print(f"File: {RAG_LOG_FILE}")
    print(f"{'='*80}\n")

    with open(RAG_LOG_FILE, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    # Show last N lines
    for line in all_lines[-lines:]:
        print(line.rstrip())


def search_logs(query: str):
    """Searches for a specific query in the logs."""
    if not DEBUG_LOG_FILE.exists():
        print(f"❌ No debug logs found")
        return

    print(f"\n{'='*80}")
    print(f"🔍 SEARCHING FOR: '{query}'")
    print(f"{'='*80}\n")

    found = 0
    with open(DEBUG_LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if query.lower() in record.get('query', '').lower():
                request_id = record.get('request_id')
                duration = record.get('duration_seconds', 0)
                events = record.get('events', [])

                print(f"\n🎯 Found: {record.get('query')}")
                print(f"   ID: {request_id}")
                print(f"   Duration: {duration:.2f}s")

                # Show events
                for event in events:
                    event_type = event.get('type')
                    data = event.get('data', {})
                    if event_type == 'query_analysis':
                        print(f"   └─ MODE: {data.get('mode')} | INTENT: {data.get('intent')}")

                found += 1

    if found == 0:
        print(f"❌ No matches found for '{query}'")
    else:
        print(f"\n✅ Found {found} matching request(s)")


def main():
    """Main command handler."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python view_logs.py debug [limit=10]     - View latest debug logs")
        print("  python view_logs.py tail [lines=50]       - View RAG pipeline logs")
        print("  python view_logs.py search <query>        - Search for specific query")
        print("  python view_logs.py latest                - Show latest request details")
        return

    command = sys.argv[1]

    if command == "debug":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        view_debug_logs(limit)
    elif command == "tail":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        tail_rag_logs(lines)
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ Please provide a search query")
            return
        search_logs(sys.argv[2])
    elif command == "latest":
        view_debug_logs(limit=1)
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main()