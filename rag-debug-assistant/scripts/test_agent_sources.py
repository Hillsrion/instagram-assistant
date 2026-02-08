import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from rag_pipeline.core.config import Config
from rag_pipeline.query.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat.agent import AgentRunner
from rag_pipeline.utils.analytics import ConversationAnalytics
from rag_pipeline.query.query_analyzer import QueryAnalyzer
from rag_pipeline.core.logger import initialize_logging

def test_agent_sources():
    initialize_logging(verbose=True)
    config = Config()
    
    print("⏳ Loading RAG system...")
    retriever, components = create_advanced_retriever(
        config,
        enable_reranking=True,
        enable_bm25=True,
        enable_metadata=True,
        enable_summaries=True
    )
    
    analytics = ConversationAnalytics(config)
    analyzer = QueryAnalyzer(config)
    
    agent = AgentRunner(
        config=config,
        retriever=retriever,
        analytics=analytics
    )
    
    # Query that should trigger multiple tools
    query = "Qu'est-ce que j'ai dit à propos de mon déménagement ?"
    
    print(f"\n🚀 Running agent for: '{query}'")
    
    analysis = analyzer.analyze(query, [])
    
    # We use run_stream to see steps
    response_text = ""
    for event in agent.run_stream(query, history=[], analysis=analysis):
        if event["type"] == "thought":
            print(f"\n🤔 Thought: {event['content']}")
        elif event["type"] == "action":
            print(f"🛠️ Action: {event['tool']}({event['input']})")
        elif event["type"] == "observation":
            print(f"👁️ Observation: (received {len(event['content'])} chars)")
        elif event["type"] == "final":
            response_text = event["answer"]
            print(f"\n✅ Final Answer: {response_text}")
            
            print(f"\n📚 ACCUMULATED SOURCES ({len(event['sources'])} chunks, {len(event['summary_sources'])} summaries):")
            for i, s in enumerate(event['sources'], 1):
                print(f"  [{i}] {s['chunk_id']} ({s['date_start']}) - score: {s['score']}")
            
            for i, s in enumerate(event['summary_sources'], 1):
                print(f"  [SUM {i}] {s['summary_id']} ({s['period']}) - score: {s['score']}")

if __name__ == "__main__":
    test_agent_sources()