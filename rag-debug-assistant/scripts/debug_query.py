#!/usr/bin/env python3
import sys
import argparse
import json
from pathlib import Path

# Add project root to path to import rag_pipeline
sys.path.append(str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.query_analyzer import QueryAnalyzer
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot

def debug_query(query, history=None):
    if history is None:
        history = []
    
    config = Config()
    print(f"--- DEBUGGING QUERY: {query} ---")
    
    # 1. Analyze
    analyzer = QueryAnalyzer(config)
    print("\n[STEP 1] Query Analysis...")
    analysis = analyzer.analyze(query, history)
    print(f"  Mode: {analysis.mode}")
    print(f"  Intent: {analysis.intent}")
    print(f"  Rewritten: {analysis.rewritten_query}")
    print(f"  Top-K: {analysis.top_k}")
    print(f"  Dates: {analysis.date_start} -> {analysis.date_end}")
    
    # 2. Retrieve
    print("\n[STEP 2] Retrieval...")
    retriever, _ = create_advanced_retriever(config)
    context = retriever.retrieve(
        analysis.rewritten_query,
        top_k=analysis.top_k,
        date_start=analysis.date_start,
        date_end=analysis.date_end,
        use_reranking=analysis.use_reranking,
        expand_context=analysis.expand_context
    )
    
    print(f"  Found {len(context.results)} results.")
    print(f"  Max score: {context.max_confidence_score:.4f}")
    print(f"  Low confidence: {context.low_confidence}")
    
    for i, res in enumerate(context.results[:3]):
        print(f"\n  Result {i+1} [Score {res.final_score:.4f}]:")
        print(f"    Source: {res.chunk.file_source}")
        print(f"    Date: {res.chunk.date_start[:10]}")
        print(f"    Content (preview): {res.chunk.content[:200]}...")
    
    # 3. Chat (optional)
    print("\n[STEP 3] LLM Generation...")
    bot = ChatBot(retriever, config)
    bot.conversation_history = history
    
    # Non-streaming call
    response = bot.chat(query, stream=False, use_rewriting=False) # Already analyzed
    print(f"\n  Final Answer:\n{response.answer}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="The query to debug")
    parser.add_argument("--history", help="Optional JSON string of history", default="[]")
    args = parser.parse_args()
    
    try:
        history_data = json.loads(args.history)
        debug_query(args.query, history_data)
    except Exception as e:
        print(f"Error: {e}")