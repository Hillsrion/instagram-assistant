#!/usr/bin/env python3
"""
Test optimized prompt on specific weak questions (Q3, Q5, Q13, Q14, Q18, Q25, Q31, Q32).
Compare baseline vs optimized prompt performance.

Usage:
    python -m eval.test_optimized_prompts_weak
"""

import json
import sys
import time
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from eval.metrics import RAGASMetrics

# Weak questions where Ministral performs poorly
WEAK_QUESTIONS = [3, 5, 13, 14, 18, 25, 31, 32]

def get_baseline_prompt(question: str, content: str) -> str:
    """Original baseline prompt."""
    return f"Contexte:\n{content}\n\nQuestion: {question}"

def get_optimized_prompt(question: str, content: str) -> str:
    """Optimized prompt for Ministral (strict, concise, anti-hallucination)."""
    return f"""Tu es un assistant d'extraction d'information STRICTE et CONCISE.

RÈGLES ABSOLUES À SUIVRE:
1. Réponds UNIQUEMENT ce qui est explicitement demandé
2. Sois concis: 1-2 phrases maximum sauf si plus est clairement nécessaire
3. N'ajoute PAS d'interprétations, d'hypothèses ou de contexte externe
4. N'ajoute PAS de détails supplémentaires non demandés
5. Si tu dois inférer, cite la source qui le justifie

Contexte:
{content}

Question: {question}

Réponse (concise et directe):"""

def load_qa_dataset(config: Config):
    """Load QA dataset from eval/ folder."""
    path = Path(__file__).parent / "eval_dataset.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_prompt(
    model: str,
    question: str,
    content: str,
    prompt: str,
    config: Config
) -> Dict[str, Any]:
    """Test a single prompt on Ollama."""
    try:
        start = time.time()
        resp = requests.post(
            f"{config.ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=180
        ).json()

        duration = time.time() - start
        answer = resp["message"]["content"]
        word_count = len(answer.split())
        wps = word_count / duration if duration > 0 else 0

        return {
            "answer": answer,
            "time": duration,
            "wps": wps,
            "error": None
        }
    except Exception as e:
        return {
            "answer": f"Error: {e}",
            "time": 0,
            "wps": 0,
            "error": str(e)
        }

def judge_response(
    metrics: RAGASMetrics,
    question: str,
    expected: str,
    generated: str,
    source: str
) -> Dict[str, Any]:
    """Judge a response using RAGASMetrics."""
    faith_data = metrics.compute_faithfulness_with_explanation(
        question=question,
        generated_answer=generated,
        source_content=source
    )
    relev_data = metrics.compute_relevance_with_explanation(
        question=question,
        expected_answer=expected,
        generated_answer=generated
    )

    return {
        "faithfulness": faith_data["score"],
        "relevance": relev_data["score"],
        "faith_explanation": faith_data["explanation"][:100],
        "relev_explanation": relev_data["explanation"][:100]
    }

def run_comparison():
    parser = argparse.ArgumentParser(
        description="Test optimized prompt on weak questions"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="ministral-3:8b",
        help="Model to test (default: ministral-3:8b)"
    )
    parser.add_argument(
        "--judge",
        type=str,
        help="Judge model (default: from config)"
    )
    args = parser.parse_args()

    config = Config()
    judge_model = args.judge if args.judge else config.llm_model

    print("="*80)
    print("TESTING OPTIMIZED PROMPT ON WEAK QUESTIONS")
    print("="*80)
    print(f"\nModel: {args.model}")
    print(f"Judge: {judge_model}")
    print(f"Weak questions: {WEAK_QUESTIONS}\n")

    # Load dataset
    dataset = load_qa_dataset(config)
    if not dataset:
        print("Error: Dataset not found. Run: python -m eval.generate_dataset 10")
        return

    qa_pairs = dataset['qa_pairs']

    # Load chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    chunks_map = {c.chunk_id: c for c in chunks}

    # Create judge
    judge_metrics = RAGASMetrics(config)
    judge_metrics.config.llm_model = judge_model

    results = {
        "baseline": {"trials": [], "scores": []},
        "optimized": {"trials": [], "scores": []}
    }

    print(f"{'Q':>3} | {'Question':45} | Baseline Faith | Opt Faith | Δ | Baseline Relev | Opt Relev | Δ")
    print("-" * 120)

    for q_num in WEAK_QUESTIONS:
        qa = qa_pairs[q_num - 1]
        chunk_ids = qa.get('source_chunk_ids', [qa['source_chunk_id']] if 'source_chunk_id' in qa else [])
        chunk = next((chunks_map[cid] for cid in chunk_ids if cid in chunks_map), None)
        content = chunk.content if chunk else ""

        # Test BASELINE
        baseline_prompt = get_baseline_prompt(qa['question'], content)
        baseline_result = test_prompt(args.model, qa['question'], content, baseline_prompt, config)

        if baseline_result["error"]:
            print(f"{q_num:3} | Error in baseline: {baseline_result['error']}")
            continue

        baseline_judgment = judge_response(
            judge_metrics,
            qa['question'],
            qa['expected_answer'],
            baseline_result['answer'],
            content
        )

        # Test OPTIMIZED
        optimized_prompt = get_optimized_prompt(qa['question'], content)
        optimized_result = test_prompt(args.model, qa['question'], content, optimized_prompt, config)

        if optimized_result["error"]:
            print(f"{q_num:3} | Error in optimized: {optimized_result['error']}")
            continue

        optimized_judgment = judge_response(
            judge_metrics,
            qa['question'],
            qa['expected_answer'],
            optimized_result['answer'],
            content
        )

        # Store results
        baseline_avg = (baseline_judgment['faithfulness'] + baseline_judgment['relevance']) / 2
        optimized_avg = (optimized_judgment['faithfulness'] + optimized_judgment['relevance']) / 2

        results["baseline"]["scores"].append(baseline_avg)
        results["optimized"]["scores"].append(optimized_avg)

        results["baseline"]["trials"].append({
            "q_num": q_num,
            "faithfulness": baseline_judgment['faithfulness'],
            "relevance": baseline_judgment['relevance'],
            "avg": baseline_avg,
            "answer": baseline_result['answer'][:100]
        })

        results["optimized"]["trials"].append({
            "q_num": q_num,
            "faithfulness": optimized_judgment['faithfulness'],
            "relevance": optimized_judgment['relevance'],
            "avg": optimized_avg,
            "answer": optimized_result['answer'][:100]
        })

        # Display results
        faith_delta = optimized_judgment['faithfulness'] - baseline_judgment['faithfulness']
        relev_delta = optimized_judgment['relevance'] - baseline_judgment['relevance']

        print(
            f"{q_num:3} | {qa['question'][:45]:45} | "
            f"{baseline_judgment['faithfulness']:.2f}         | "
            f"{optimized_judgment['faithfulness']:.2f}      | "
            f"{faith_delta:+.2f} | "
            f"{baseline_judgment['relevance']:.2f}           | "
            f"{optimized_judgment['relevance']:.2f}      | "
            f"{relev_delta:+.2f}"
        )

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    baseline_avg = sum(results["baseline"]["scores"]) / len(results["baseline"]["scores"]) if results["baseline"]["scores"] else 0
    optimized_avg = sum(results["optimized"]["scores"]) / len(results["optimized"]["scores"]) if results["optimized"]["scores"] else 0
    improvement = ((optimized_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

    print(f"\nBaseline avg score:  {baseline_avg:.4f}")
    print(f"Optimized avg score: {optimized_avg:.4f}")
    print(f"Improvement:         {improvement:+.2f}%")

    if improvement > 5:
        print(f"\n✅ SIGNIFICANT IMPROVEMENT ({improvement:.2f}%)")
        print("   Optimized prompt is RECOMMENDED for production use")
        return True
    elif improvement > 0:
        print(f"\n⚠️  MODEST IMPROVEMENT ({improvement:.2f}%)")
        print("   Consider further refinement")
        return True
    else:
        print(f"\n❌ NO IMPROVEMENT or REGRESSION ({improvement:.2f}%)")
        print("   Keep baseline prompt")
        return False

if __name__ == "__main__":
    success = run_comparison()
    sys.exit(0 if success else 1)
