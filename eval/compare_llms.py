"""
Script to compare Generation Quality of different LLMs on the evaluation dataset.
This bypasses retrieval and provides the exact source chunk as context.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from eval.metrics import RAGASMetrics

def load_qa_dataset(config: Config):
    path = config.index_dir / "eval_dataset.json"
    if not path.exists():
        print(f"Error: {path} not found. Run run_eval --generate first.")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_chunk_content(chunk_id: str, chunks: List[Chunk]) -> str:
    for c in chunks:
        if c.chunk_id == chunk_id:
            return c.content
    return ""

def compare_models(model_names: List[str], n_trials: int = 3):
    config = Config()
    metrics = RAGASMetrics(config)
    
    # Load data
    print("📂 Loading data...")
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    
    dataset = load_qa_dataset(config)
    if not dataset: return
    
    qa_pairs = dataset['qa_pairs'][:n_trials]
    
    results = {model: {"faithfulness": [], "relevance": []} for model in model_names}
    
    from rag_pipeline.chat import ChatBot
    
    for i, qa in enumerate(qa_pairs):
        print(f"\n[{i+1}/{len(qa_pairs)}] Question: {qa['question']}")
        
        context_content = get_chunk_content(qa['source_chunk_id'], chunks)
        if not context_content:
            print(f"  ⚠️ Chunk {qa['source_chunk_id']} not found!")
            continue
            
        formatted_context = f"=== DOCUMENT SOURCE ===\n{context_content}"
        
        for model in model_names:
            print(f"  🤖 Querying {model}...", end="", flush=True)
            
            # Temporary override config model
            config.llm_model = model
            chatbot = ChatBot(None, config) # No retriever needed for raw_chat
            
            try:
                # Use a simple prompt with the context
                prompt = f"Utilise les documents suivants pour répondre à la question.\n\n{formatted_context}\n\nQuestion: {qa['question']}"
                
                # Mock a response object or use chatbot._call_llm if it exists
                # Actually ChatBot has a system prompt. Let's use a simpler way.
                import requests
                
                response = requests.post(
                    f"{config.ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.1}
                    },
                    timeout=60
                )
                response.raise_for_status()
                answer = response.json()["message"]["content"]
                
                # Evaluate
                # Use qwen3:latest as the judge (hardcoded for reliability)
                judge_config = Config()
                judge_config.llm_model = "qwen3:latest"
                judge_metrics = RAGASMetrics(judge_config)
                
                # We need to get the score AND explanation if possible, 
                # but metrics.py returns float. Let's just print the answer for now.
                faith = judge_metrics.compute_faithfulness(
                    qa['question'], qa['expected_answer'], answer, context_content
                )
                relev = judge_metrics.compute_answer_relevance(
                    qa['question'], qa['expected_answer'], answer
                )
                
                results[model]["faithfulness"].append(faith)
                results[model]["relevance"].append(relev)
                
                print(f" Done")
                print(f"    📝 Réponse: {answer.strip()}")
                print(f"    📊 Scores: Faith={faith:.2f}, Rel={relev:.2f}")
                
            except Exception as e:
                print(f" Error: {e}")

    # Print Summary
    print("\n" + "="*40)
    print("SUMMARY COMPARISON (Generation only)")
    print("="*40)
    for model in model_names:
        f_avg = sum(results[model]["faithfulness"]) / len(results[model]["faithfulness"]) if results[model]["faithfulness"] else 0
        r_avg = sum(results[model]["relevance"]) / len(results[model]["relevance"]) if results[model]["relevance"] else 0
        print(f"{model:<15} | Faith: {f_avg*100:>5.1f}% | Relev: {r_avg*100:>5.1f}%")
    print("="*40)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compare_llms.py model1 model2 ...")
    else:
        compare_models(sys.argv[1:])
