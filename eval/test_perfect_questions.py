#!/usr/bin/env python3
"""
Test optimized prompt on PERFECT questions (where Ministral already scored 1.0/1.0).
Ensure optimization doesn't degrade good performance.

Usage:
    python -m eval.test_perfect_questions
"""

import json
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from eval.metrics import RAGASMetrics

# Questions where Ministral scored 1.0/1.0 on BOTH faith and relevance
# From the analysis: Q1, Q7, Q12, Q15, Q17, Q29, Q34, Q35, Q36, Q39, Q40, Q41, Q43, Q45, Q47, Q48
PERFECT_QUESTIONS = [1, 7, 12, 15, 17, 29, 34, 35, 36, 39, 40, 41, 43, 45, 47, 48]

def get_baseline_prompt(question: str, content: str) -> str:
    return f"Contexte:\n{content}\n\nQuestion: {question}"

def get_optimized_prompt(question: str, content: str) -> str:
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
    path = Path(__file__).parent / "eval_dataset.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_prompt(model: str, question: str, content: str, prompt: str, config: Config) -> Dict[str, Any]:
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

def judge_response(metrics: RAGASMetrics, question: str, expected: str, generated: str, source: str) -> Dict[str, Any]:
    faith_data = metrics.compute_faithfulness_with_explanation(
        question=question,
        expected_answer=expected,
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
    }

def run_comparison():
    config = Config()
    judge_model = config.llm_model

    print("="*100)
    print("TESTING OPTIMIZED PROMPT ON PERFECT QUESTIONS (Ministral 1.0/1.0)")
    print("="*100)
    print(f"\nModel: ministral-3:8b")
    print(f"Perfect questions (1.0/1.0): {PERFECT_QUESTIONS}")
    print(f"Count: {len(PERFECT_QUESTIONS)}\n")

    # Load data
    dataset = load_qa_dataset(config)
    if not dataset:
        print("Error: Dataset not found")
        return

    qa_pairs = dataset['qa_pairs']
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    chunks_map = {c.chunk_id: c for c in chunks}
    judge_metrics = RAGASMetrics(config)
    judge_metrics.config.llm_model = judge_model

    results = {
        "baseline": {"scores": []},
        "optimized": {"scores": []}
    }

    print(f"{'Q':>3} | {'Question':50} | Baseline Faith | Opt Faith | Δ | Baseline Relev | Opt Relev | Δ | Status")
    print("-" * 130)

    regressions = []
    improvements = []

    for q_num in PERFECT_QUESTIONS:
        qa = qa_pairs[q_num - 1]
        chunk = chunks_map.get(qa['source_chunk_id'])
        content = chunk.content if chunk else ""

        # Baseline
        baseline_prompt = get_baseline_prompt(qa['question'], content)
        baseline_result = test_prompt("ministral-3:8b", qa['question'], content, baseline_prompt, config)

        if baseline_result["error"]:
            print(f"{q_num:3} | Error")
            continue

        baseline_judgment = judge_response(judge_metrics, qa['question'], qa['expected_answer'], baseline_result['answer'], content)

        # Optimized
        optimized_prompt = get_optimized_prompt(qa['question'], content)
        optimized_result = test_prompt("ministral-3:8b", qa['question'], content, optimized_prompt, config)

        if optimized_result["error"]:
            print(f"{q_num:3} | Error")
            continue

        optimized_judgment = judge_response(judge_metrics, qa['question'], qa['expected_answer'], optimized_result['answer'], content)

        baseline_avg = (baseline_judgment['faithfulness'] + baseline_judgment['relevance']) / 2
        optimized_avg = (optimized_judgment['faithfulness'] + optimized_judgment['relevance']) / 2

        results["baseline"]["scores"].append(baseline_avg)
        results["optimized"]["scores"].append(optimized_avg)

        faith_delta = optimized_judgment['faithfulness'] - baseline_judgment['faithfulness']
        relev_delta = optimized_judgment['relevance'] - baseline_judgment['relevance']
        avg_delta = optimized_avg - baseline_avg

        status = "✅" if avg_delta >= 0 else "❌"
        if avg_delta < -0.1:
            regressions.append((q_num, avg_delta))
            status = "❌ REGRESSION"
        elif avg_delta > 0.1:
            improvements.append((q_num, avg_delta))
            status = "✅ IMPROVED"
        else:
            status = "→ STABLE"

        print(
            f"{q_num:3} | {qa['question'][:50]:50} | "
            f"{baseline_judgment['faithfulness']:.2f}         | "
            f"{optimized_judgment['faithfulness']:.2f}      | "
            f"{faith_delta:+.2f} | "
            f"{baseline_judgment['relevance']:.2f}           | "
            f"{optimized_judgment['relevance']:.2f}      | "
            f"{relev_delta:+.2f} | {status}"
        )

    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)

    baseline_avg = sum(results["baseline"]["scores"]) / len(results["baseline"]["scores"]) if results["baseline"]["scores"] else 0
    optimized_avg = sum(results["optimized"]["scores"]) / len(results["optimized"]["scores"]) if results["optimized"]["scores"] else 0
    change = ((optimized_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

    print(f"\nBaseline avg score:  {baseline_avg:.4f}")
    print(f"Optimized avg score: {optimized_avg:.4f}")
    print(f"Change:              {change:+.2f}%")
    print(f"\nImprovements:        {len(improvements)}")
    print(f"Regressions:         {len(regressions)}")
    print(f"Stable:              {len(PERFECT_QUESTIONS) - len(improvements) - len(regressions)}")

    if regressions:
        print(f"\n⚠️  REGRESSIONS DETECTED on {len(regressions)} questions:")
        for q_num, delta in regressions:
            print(f"   Q{q_num}: {delta:+.2f}")

    if change >= -2:
        print(f"\n✅ ACCEPTABLE: No significant degradation ({change:+.2f}%)")
        return True
    else:
        print(f"\n❌ SIGNIFICANT DEGRADATION: {change:.2f}% - Optimization is too aggressive")
        return False

if __name__ == "__main__":
    success = run_comparison()
    sys.exit(0 if success else 1)
