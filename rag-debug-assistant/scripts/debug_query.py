#!/usr/bin/env python3
import sys
import argparse
import json
from pathlib import Path

# Add project root to path to import rag_pipeline
sys.path.append(str(Path(__file__).parent.parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.query.query_analyzer import QueryAnalyzer
from rag_pipeline.query.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat.chat import ChatBot
from rag_pipeline.chat.agent import AgentRunner
from api.routing import should_use_agent

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
    
    # 2. Routing Decision
    use_agent = should_use_agent(analysis)
    print(f"\n[STEP 2] Routing: {'AGENT PATH' if use_agent else 'FAST PATH'}")
    
    # 3. Execution
    retriever, _ = create_advanced_retriever(config)
    
    if use_agent:
        print("\n[STEP 3] Agent Execution...")
        agent = AgentRunner(config, retriever)
        result = agent.run(query, history=history, analysis=analysis)
        
        print("\n--- AGENT REASONING ---")
        for step in result.steps:
            print(f"\nStep {step.step_num}:")
            print(f"  Thought: {step.thought}")
            if step.action:
                print(f"  Action: {step.action}({step.action_input})")
                print(f"  Observation: {str(step.observation)[:200]}...")
        
        print(f"\n  Final Answer:\n{result.answer}")
    else:
        print("\n[STEP 3] Fast Path Execution...")
        bot = ChatBot(retriever, config)
        bot.conversation_history = history
        response = bot.chat(query, stream=False, use_rewriting=False)
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