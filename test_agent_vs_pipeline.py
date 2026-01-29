#!/usr/bin/env python3
"""
Standalone test for ReAct Agent vs Pipeline comparison.
Does not depend on the eval module to avoid broken dependencies.
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List
from dataclasses import dataclass

# Add root to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.agent import AgentRunner, AgentResult
from rag_pipeline.chat import ChatBot
from rag_pipeline.retriever import Retriever
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore


# Test queries
TEST_QUERIES = [
    ("De quoi on a parlé récemment ?", "simple"),
    ("Combien de messages j'ai échangés ?", "analytical"),
    ("Bonjour, comment ça va ?", "direct"),
]


@dataclass
class Result:
    query: str
    query_type: str
    pipeline_answer: str
    pipeline_time: float
    agent_answer: str
    agent_time: float
    agent_steps: int
    agent_tools: List[str]


def main():
    print("=" * 60)
    print("Pipeline vs ReAct Agent - Quick Test")
    print("=" * 60)
    print()
    
    config = Config()
    
    # Load components
    print("📦 Loading components...")
    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)
    
    if not vector_store.load():
        print("❌ Vector store not found. Run setup_rag.py first.")
        return
    
    retriever = Retriever(embedding_model, vector_store, config)
    chatbot = ChatBot(retriever, config)
    agent = AgentRunner(config, retriever)
    
    print(f"✅ Loaded {vector_store.size} vectors")
    print()
    
    results: List[Result] = []
    
    for i, (query, qtype) in enumerate(TEST_QUERIES):
        print(f"[{i+1}/{len(TEST_QUERIES)}] {qtype.upper()}: {query}")
        
        # Pipeline
        print("  📦 Pipeline...", end="", flush=True)
        start = time.time()
        try:
            resp = chatbot.chat(query, stream=False)
            pipeline_answer = resp.answer if hasattr(resp, 'answer') else str(resp)
        except Exception as e:
            pipeline_answer = f"Error: {e}"
        pipeline_time = time.time() - start
        print(f" {pipeline_time:.2f}s")
        
        # Agent
        print("  🤖 Agent...", end="", flush=True)
        try:
            agent_result = agent.run(query)
            agent_answer = agent_result.answer
            agent_steps = len(agent_result.steps)
            agent_tools = [s.action for s in agent_result.steps if s.action]
            agent_time = agent_result.total_time
        except Exception as e:
            agent_answer = f"Error: {e}"
            agent_steps = 0
            agent_tools = []
            agent_time = 0
        print(f" {agent_time:.2f}s ({agent_steps} steps)")
        
        results.append(Result(
            query=query,
            query_type=qtype,
            pipeline_answer=pipeline_answer,
            pipeline_time=pipeline_time,
            agent_answer=agent_answer,
            agent_time=agent_time,
            agent_steps=agent_steps,
            agent_tools=agent_tools
        ))
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    pipeline_avg = sum(r.pipeline_time for r in results) / len(results)
    agent_avg = sum(r.agent_time for r in results) / len(results)
    
    print(f"\n📦 Pipeline avg latency: {pipeline_avg:.2f}s")
    print(f"🤖 Agent avg latency: {agent_avg:.2f}s")
    print(f"⚡ Difference: {((agent_avg - pipeline_avg) / pipeline_avg) * 100:+.1f}%")
    
    print("\n" + "-" * 60)
    print("DETAILS")
    print("-" * 60)
    
    for r in results:
        print(f"\n🔹 {r.query}")
        print(f"   Pipeline ({r.pipeline_time:.2f}s): {r.pipeline_answer[:100]}...")
        print(f"   Agent ({r.agent_time:.2f}s, {r.agent_steps} steps, tools: {r.agent_tools}): {r.agent_answer[:100]}...")


if __name__ == "__main__":
    main()
