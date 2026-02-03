"""
Evaluate GENERATION quality with MULTIPLE CHUNKS as context.

This script tests LLM's ability to synthesize information from multiple
conversation chunks, reflecting real-world usage where 5-25 chunks are
typically provided based on query intent.

Differences from eval_generation.py:
- Uses ALL chunks from source_chunk_ids (not just the first)
- Replicates production context formatting with headers/metadata
- Adds attribution and cross-chunk coherence metrics
- Tests scenarios: 5 chunks (factual), 10 (complex), 15 (summary)

Usage:
    python -m eval.eval_generation_multichunk model1 model2
    python -m eval.eval_generation_multichunk qwen3:latest --trials 10 --html
    python -m eval.eval_generation_multichunk --generate-dataset --size 30
"""

import json
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from eval.core import RAGASMetrics, MultiChunkEvalResult, SyntheticDataGenerator, MultiChunkQAPair
from eval.core._output_paths import get_multichunk_report_path
from rag_pipeline.llm_provider import create_provider

# Reuse helper functions from eval_generation.py
from eval.generation.eval_generation import (
    escape_html,
    markdown_to_html,
    format_chunk_as_chat,
    check_ollama_models_available,
    display_missing_models_help
)


def format_multichunk_context(
    chunks: List[Chunk],
    intent: str = "broad_summary",
    max_chars_per_chunk: int = 2500
) -> str:
    """
    Format multiple chunks for LLM context.

    Replicates EXACTLY the production formatting from
    advanced_retriever._format_context() (L491-530).

    Args:
        chunks: List of chunks to format
        intent: Query intent (affects truncation)
        max_chars_per_chunk: Max characters per chunk

    Returns:
        Formatted context string
    """
    if not chunks:
        return "No relevant documents found."

    context_parts = []

    for i, chunk in enumerate(chunks):
        # Replicate production header format exactly
        header = (
            f"=== DOCUMENT {i+1} ===\n"
            f"Source: {chunk.file_source}\n"
            f"Participants: {', '.join(chunk.participants)}\n"
            f"Period: {chunk.date_start[:10]} → {chunk.date_end[:10]}\n"
            f"Score: 0.85\n"  # Simulated relevance score
            f"---\n"
        )

        content = chunk.content
        if len(content) > max_chars_per_chunk:
            content = content[:max_chars_per_chunk] + "\n[... truncated ...]"

        context_parts.append(header + content)

    return "\n\n".join(context_parts)


def get_eval_prompt(question: str, context: str) -> str:
    """
    Build the evaluation prompt for any model in French.
    """
    return f"""Réponds à la question ci-dessous en te basant UNIQUEMENT sur le contexte fourni.

Règles :
- Réponds directement et de manière concise
- N'ajoute pas d'interprétations ou de suppositions au-delà du texte
- Si l'information n'est pas dans le contexte, dis-le
- TA RÉPONSE DOIT ÊTRE EN FRANÇAIS

Contexte :
{context}

Question : {question}

Réponse :"""


class MultiChunkEvaluator:
    """Evaluator for multi-chunk generation quality."""

    def __init__(self, config: Config, provider_type: str = "ollama"):
        self.config = config
        self.provider_type = provider_type
        self.metrics = RAGASMetrics(config, provider_type)

    def evaluate_single_qa(
        self,
        model: str,
        qa: MultiChunkQAPair,
        chunks_map: Dict[str, Chunk],
        provider
    ) -> MultiChunkEvalResult:
        """
        Evaluate a single model answer for a multi-chunk QA pair.
        """
        # 1. Retrieve all chunks
        chunks = [chunks_map[cid] for cid in qa.source_chunk_ids
                 if cid in chunks_map]

        if not chunks:
            return MultiChunkEvalResult(
                question=qa.question,
                expected_answer=qa.expected_answer,
                generated_answer="Error: No chunks found",
                source_chunk_ids=qa.source_chunk_ids,
                intent=qa.intent,
                faithfulness={"score": 0.0, "explanation": "No chunks found"},
                relevance={"score": 0.0, "explanation": "No chunks found"},
                num_chunks_provided=0,
                generation_time=0.0,
                words_per_sec=0.0
            )

        # 2. Format context (production-style)
        context = format_multichunk_context(chunks, qa.intent)

        # 3. Generate answer
        prompt = get_eval_prompt(qa.question, context)
        start = time.time()

        try:
            answer = provider.generate(
                [{"role": "user", "content": prompt}],
                timeout=180
            )
        except Exception as e:
            return MultiChunkEvalResult(
                question=qa.question,
                expected_answer=qa.expected_answer,
                generated_answer=f"Error: {e}",
                source_chunk_ids=qa.source_chunk_ids,
                intent=qa.intent,
                faithfulness={"score": 0.0, "explanation": "Generation failed"},
                relevance={"score": 0.0, "explanation": "Generation failed"},
                num_chunks_provided=len(chunks),
                generation_time=0.0,
                words_per_sec=0.0
            )

        duration = time.time() - start
        word_count = len(answer.split())
        wps = word_count / duration if duration > 0 else 0

        # 4. Compute metrics
        faith_data = self.metrics.compute_faithfulness_with_explanation(
            qa.question, answer, context
        )
        relev_data = self.metrics.compute_relevance_with_explanation(
            qa.question, qa.expected_answer, answer
        )
        attr_score, attr_explanation = self.metrics.compute_chunk_attribution(
            qa.question, answer, qa.expected_chunk_attribution or qa.source_chunk_ids[:3], chunks
        )
        coherence_score, coherence_explanation = self.metrics.compute_cross_chunk_coherence(
            qa.question, answer, len(chunks)
        )

        return MultiChunkEvalResult(
            question=qa.question,
            expected_answer=qa.expected_answer,
            generated_answer=answer,
            source_chunk_ids=qa.source_chunk_ids,
            intent=qa.intent,
            faithfulness=faith_data,
            relevance=relev_data,
            chunk_attribution_score=attr_score,
            chunk_attribution_explanation=attr_explanation,
            cross_chunk_coherence=coherence_score,
            cross_chunk_explanation=coherence_explanation,
            num_chunks_provided=len(chunks),
            num_chunks_used=len(chunks),
            generation_time=duration,
            words_per_sec=wps
        )


    def evaluate_model(
        self,
        model: str,
        qa_pairs: List[MultiChunkQAPair],
        chunks_map: Dict[str, Chunk],
        provider
    ) -> List[MultiChunkEvalResult]:
        """
        Evaluate a model on multi-chunk QA pairs.

        Args:
            model: Model name
            qa_pairs: List of multi-chunk QA pairs
            chunks_map: Map of chunk_id -> Chunk
            provider: LLM provider instance

        Returns:
            List of evaluation results
        """
        results = []

        for i, qa in enumerate(qa_pairs):
            print(f"  [{i+1}/{len(qa_pairs)}] Processing: {qa.question[:60]}...")
            result = self.evaluate_single_qa(model, qa, chunks_map, provider)
            results.append(result)

            if "Error" in result.generated_answer:
                print(f"  ❌ Generation failed for question {i+1}: {result.generated_answer}")
            else:
                print(f"    ✓ Faith: {result.faithfulness['score']:.2f}, Relev: {result.relevance['score']:.2f}, "
                      f"Attr: {result.chunk_attribution_score:.2f}, Coherence: {result.cross_chunk_coherence:.2f} ({result.words_per_sec:.1f} w/s)")

        return results


def load_multichunk_dataset(config: Config) -> List[MultiChunkQAPair]:
    """Load multi-chunk QA dataset from eval/ folder."""
    path = Path(__file__).parent / "eval_dataset_multichunk.json"
    if not path.exists():
        return None

    generator = SyntheticDataGenerator(config)
    return generator.load_multichunk_dataset(path)


def generate_dataset(size: int = 30, chunk_counts: List[int] = None):
    """Generate multi-chunk dataset."""
    if chunk_counts is None:
        chunk_counts = [5, 10, 15]

    print("=" * 60)
    print("Multi-Chunk Dataset Generation")
    print("=" * 60)
    print(f"Target size: {size} QA pairs")
    print(f"Chunk counts: {chunk_counts}")
    print()

    config = Config()
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()

    print(f"Loaded {len(chunks)} chunks")

    generator = SyntheticDataGenerator(config)

    def progress(current, total, message):
        print(f"[{current}/{total}] {message}")

    qa_pairs = generator.generate_multichunk_qa_pairs(
        chunks,
        num_pairs=size,
        chunk_counts=chunk_counts,
        progress_callback=progress
    )

    generator.save_multichunk_dataset(qa_pairs)

    print(f"\n✅ Generated {len(qa_pairs)} multi-chunk QA pairs")
    print("\nDistribution:")
    by_intent = {}
    for qa in qa_pairs:
        by_intent[qa.intent] = by_intent.get(qa.intent, 0) + 1
    for intent, count in by_intent.items():
        print(f"  {intent}: {count}")


def generate_multichunk_comparison_json(
    all_results: Dict[str, List[MultiChunkEvalResult]],
    qa_pairs: List[MultiChunkQAPair],
    judge_model: str,
    provider: str,
    num_questions: int,
    summary_synthesis: str = "",
    run_timestamp: datetime = None
) -> Path:
    """Generate a single consolidated JSON report for all models (Multi-Chunk)."""
    models = list(all_results.keys())
    
    report_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "models": models,
            "provider": provider,
            "judge_model": judge_model,
            "num_questions": num_questions
        },
        "synthesis": summary_synthesis,
        "results": []
    }

    for i, qa in enumerate(qa_pairs):
        q_entry = {
            "question": qa.question,
            "expected_answer": qa.expected_answer,
            "source_chunk_ids": qa.source_chunk_ids,
            "intent": qa.intent,
            "model_responses": {}
        }
        
        for model in models:
            if i < len(all_results[model]):
                res = all_results[model][i]
                q_entry["model_responses"][model] = {
                    "answer": res.generated_answer,
                    "time": res.generation_time,
                    "wps": res.words_per_sec,
                    "faithfulness": res.faithfulness,
                    "relevance": res.relevance,
                    "attribution": {
                        "score": res.chunk_attribution_score,
                        "explanation": res.chunk_attribution_explanation
                    },
                    "coherence": {
                        "score": res.cross_chunk_coherence,
                        "explanation": res.cross_chunk_explanation
                    }
                }
        
        report_data["results"].append(q_entry)

    # Save consolidated JSON
    report_path = get_multichunk_report_path(models, num_questions, timestamp=run_timestamp, format="json")

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return report_path


def generate_json_report(
    model: str,
    results: List[MultiChunkEvalResult],
    qa_pairs: List[MultiChunkQAPair],
    judge_model: str,
    provider: str,
    trials: int,
    run_timestamp: datetime = None
) -> Path:
    """Generate JSON report for a single model."""
    report_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "provider": provider,
            "judge_model": judge_model,
            "num_trials": trials,
            "num_questions": len(qa_pairs)
        },
        "summary": {
            "avg_faithfulness": round(
                sum(r.faithfulness["score"] for r in results) / len(results), 3
            ) if results else 0,
            "avg_relevance": round(
                sum(r.relevance["score"] for r in results) / len(results), 3
            ) if results else 0,
            "avg_attribution": round(
                sum(r.chunk_attribution_score for r in results) / len(results), 3
            ) if results else 0,
            "avg_coherence": round(
                sum(r.cross_chunk_coherence for r in results) / len(results), 3
            ) if results else 0,
            "avg_speed_wps": round(
                sum(r.words_per_sec for r in results) / len(results), 2
            ) if results else 0
        },
        "results": [r.to_dict() for r in results]
    }

    # Save per-model JSON
    report_path = get_multichunk_report_path([model], trials, timestamp=run_timestamp, format="json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return report_path


def generate_html_report(
    all_results: Dict[str, List[MultiChunkEvalResult]],
    qa_pairs: List[MultiChunkQAPair],
    judge_model: str,
    chunks_map: Dict[str, Chunk],
    models: List[str],
    num_questions: int,
    synthesis: str = "",
    run_timestamp: datetime = None
) -> Path:
    """Generate comprehensive HTML report with multi-chunk visualizations."""
    timestamp_str = run_timestamp.strftime("%Y-%m-%d %H:%M:%S") if run_timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Compute statistics
    stats_by_model = {}
    for model, results in all_results.items():
        if not results:
            continue

        stats_by_model[model] = {
            "faithfulness": sum(r.faithfulness["score"] for r in results) / len(results),
            "relevance": sum(r.relevance["score"] for r in results) / len(results),
            "attribution": sum(r.chunk_attribution_score for r in results) / len(results),
            "coherence": sum(r.cross_chunk_coherence for r in results) / len(results),
            "speed": sum(r.words_per_sec for r in results) / len(results)
        }

    html = f"""
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Chunk LLM Evaluation Report</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        .prose-content {{ line-height: 1.6; }}
        .chat-messages {{ display: flex; flex-direction: column; }}
    </style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                    📊 Multi-Chunk LLM Evaluation
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Generated on <span class="font-semibold text-indigo-600">{timestamp_str}</span> •
                    <span class="font-semibold text-indigo-600">{num_questions}</span> multi-chunk questions •
                    Judge: <span class="font-semibold text-indigo-600">{escape_html(judge_model)}</span>
                </p>
            </div>

            <!-- Synthesis Section -->
            <div class="bg-indigo-900 rounded-2xl shadow-xl overflow-hidden mb-12 border border-indigo-800">
                <div class="px-8 py-6 border-b border-indigo-800/50 flex items-center justify-between">
                    <h2 class="text-xl font-bold text-white flex items-center gap-2">
                        <span>📝 Synthèse du Juge (Multi-Chunk)</span>
                    </h2>
                </div>
                <div class="px-8 py-8 bg-indigo-950/40 text-indigo-50 prose-content">
                    {markdown_to_html(synthesis) if synthesis else "<p class='italic opacity-70'>No synthesis generated.</p>"}
                </div>
            </div>

            <!-- Summary Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
"""

    # Add metric cards for each model
    for model, stats in stats_by_model.items():
        html += f"""
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">{escape_html(model)}</h3>
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-600">Faithfulness</span>
                            <span class="font-bold text-indigo-600">{stats['faithfulness']:.1%}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-600">Relevance</span>
                            <span class="font-bold text-green-600">{stats['relevance']:.1%}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-600">Attribution</span>
                            <span class="font-bold text-purple-600">{stats['attribution']:.1%}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-600">Coherence</span>
                            <span class="font-bold text-cyan-600">{stats['coherence']:.1%}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-600">Speed</span>
                            <span class="font-bold text-amber-600">{stats['speed']:.1f} w/s</span>
                        </div>
                    </div>
                </div>
"""

    html += """
            </div>

            <!-- Charts -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6">🎯 Core Metrics Comparison</h3>
                    <div class="h-80"><canvas id="coreMetricsChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6">🔗 Multi-Chunk Specific Metrics</h3>
                    <div class="h-80"><canvas id="multiChunkMetricsChart"></canvas></div>
                </div>
            </div>

            <!-- Performance by Chunk Count -->
            <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 mb-12">
                <h2 class="text-2xl font-bold text-slate-900 mb-6">📈 Performance by Chunk Count</h2>
                <div class="h-96"><canvas id="chunkCountChart"></canvas></div>
            </div>

            <!-- Question Details -->
            <div class="space-y-12">
                <div class="flex items-center justify-between border-b border-slate-200 pb-4">
                    <h2 class="text-3xl font-bold text-slate-900">🔍 Question Details</h2>
                    <span class="bg-slate-200 text-slate-700 px-3 py-1 rounded-full text-sm font-medium">
                        {len(qa_pairs)} questions
                    </span>
                </div>

                <div class="space-y-12">
"""

    # Add details for each question
    for i, qa in enumerate(qa_pairs):
        # Get results for this question from all models
        model_results_for_q = {}
        for model_name, results in all_results.items():
            if i < len(results):
                model_results_for_q[model_name] = results[i]

        # Get chunks for this question
        chunks = [chunks_map[cid] for cid in qa.source_chunk_ids if cid in chunks_map]

        html += f"""
                    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div class="bg-slate-50 px-8 py-6 border-b border-slate-100">
                            <div class="flex items-start justify-between">
                                <div class="flex-1">
                                    <div class="flex items-center gap-3 mb-2">
                                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                                            Question {i+1}
                                        </span>
                                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                            {qa.intent}
                                        </span>
                                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-100 text-cyan-800">
                                            {len(chunks)} chunks
                                        </span>
                                    </div>
                                    <h3 class="text-xl font-bold text-slate-900 mb-2">{escape_html(qa.question)}</h3>
                                    <div class="flex items-start text-sm text-slate-600">
                                        <span class="font-bold text-slate-900 mr-2">Expected:</span>
                                        <span>{escape_html(qa.expected_answer[:200])}{'...' if len(qa.expected_answer) > 200 else ''}</span>
                                    </div>
                                </div>
                            </div>
                            <button class="mt-4 px-3 py-1 text-xs font-medium bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg transition"
                                    onclick="toggleElement('chunks-{i}', this)">
                                📌 Show {len(chunks)} source chunks
                            </button>
                        </div>

                        <!-- Hidden chunks section -->
                        <div id="chunks-{i}" class="hidden px-8 py-6 bg-slate-50 border-b border-slate-200">
                            <p class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-4">
                                💬 Source Chunks ({len(chunks)} provided as context)
                            </p>
                            <div class="space-y-4 max-h-96 overflow-y-auto">
"""

        # Show all chunks for this question
        for chunk_idx, chunk in enumerate(chunks[:10]):  # Limit to first 10 for display
            html += f"""
                                <div class="bg-white p-4 rounded-lg border border-slate-200">
                                    <div class="text-xs text-slate-600 mb-2">
                                        <strong>Chunk {chunk_idx + 1}/{len(chunks)}</strong> •
                                        {', '.join(chunk.participants)} •
                                        {chunk.date_start[:10]} to {chunk.date_end[:10]}
                                    </div>
                                    <div class="text-sm text-slate-700">
                                        {escape_html(chunk.content[:300])}{'...' if len(chunk.content) > 300 else ''}
                                    </div>
                                </div>
"""

        if len(chunks) > 10:
            html += f"""
                                <div class="text-center text-sm text-slate-500 italic">
                                    ... and {len(chunks) - 10} more chunks
                                </div>
"""

        html += """
                            </div>
                        </div>

                        <!-- Model responses -->
                        <div class="p-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
"""

        # Show results from each model
        for model_name, result in model_results_for_q.items():
            faith_score = result.faithfulness["score"]
            faith_expl = result.faithfulness.get("explanation", "")
            relev_score = result.relevance["score"]
            relev_expl = result.relevance.get("explanation", "")
            attr_score = result.chunk_attribution_score
            attr_expl = result.chunk_attribution_explanation
            coherence_score = result.cross_chunk_coherence
            coherence_expl = result.cross_chunk_explanation

            # Badge colors
            bg_f = "bg-green-100 text-green-800" if faith_score > 0.8 else ("bg-yellow-100 text-yellow-800" if faith_score > 0.4 else "bg-red-100 text-red-800")
            bg_r = "bg-green-100 text-green-800" if relev_score > 0.8 else ("bg-yellow-100 text-yellow-800" if relev_score > 0.4 else "bg-red-100 text-red-800")
            bg_a = "bg-green-100 text-green-800" if attr_score > 0.8 else ("bg-yellow-100 text-yellow-800" if attr_score > 0.4 else "bg-red-100 text-red-800")
            bg_c = "bg-green-100 text-green-800" if coherence_score > 0.8 else ("bg-yellow-100 text-yellow-800" if coherence_score > 0.4 else "bg-red-100 text-red-800")

            html += f"""
                            <div class="flex flex-col h-full bg-slate-50/50 rounded-xl p-6 border border-slate-100">
                                <div class="mb-4">
                                    <div class="flex items-center mb-3">
                                        <div class="h-10 w-10 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg mr-3">
                                            🤖
                                        </div>
                                        <div>
                                            <h4 class="font-bold text-slate-900">{escape_html(model_name)}</h4>
                                            <span class="text-xs text-slate-500">
                                                {result.generation_time:.2f}s • {result.words_per_sec:.1f} words/s
                                            </span>
                                        </div>
                                    </div>
                                    <div class="grid grid-cols-2 gap-2">
                                        <span class="px-2 py-1 rounded text-xs font-bold {bg_f}">Faith: {faith_score*100:.0f}%</span>
                                        <span class="px-2 py-1 rounded text-xs font-bold {bg_r}">Relev: {relev_score*100:.0f}%</span>
                                        <span class="px-2 py-1 rounded text-xs font-bold {bg_a}">Attr: {attr_score*100:.0f}%</span>
                                        <span class="px-2 py-1 rounded text-xs font-bold {bg_c}">Coheren: {coherence_score*100:.0f}%</span>
                                    </div>
                                </div>

                                <div class="flex-grow bg-white p-4 rounded-lg border border-slate-100 mb-4 prose-content">
                                    {markdown_to_html(result.generated_answer)}
                                </div>

                                <div class="space-y-2 mt-auto">
                                    <div class="bg-indigo-50/50 p-3 rounded-lg">
                                        <p class="text-xs font-bold text-indigo-900 uppercase mb-1">Faithfulness Judge</p>
                                        <p class="text-xs text-indigo-800 italic">"{escape_html(faith_expl[:150])}..."</p>
                                    </div>
                                    <div class="bg-green-50/50 p-3 rounded-lg">
                                        <p class="text-xs font-bold text-green-900 uppercase mb-1">Relevance Judge</p>
                                        <p class="text-xs text-green-800 italic">"{escape_html(relev_expl[:150])}..."</p>
                                    </div>
                                    <div class="bg-purple-50/50 p-3 rounded-lg">
                                        <p class="text-xs font-bold text-purple-900 uppercase mb-1">Attribution Judge</p>
                                        <p class="text-xs text-purple-800 italic">"{escape_html(attr_expl[:150])}..."</p>
                                    </div>
                                    <div class="bg-cyan-50/50 p-3 rounded-lg">
                                        <p class="text-xs font-bold text-cyan-900 uppercase mb-1">Coherence Judge</p>
                                        <p class="text-xs text-cyan-800 italic">"{escape_html(coherence_expl[:150])}..."</p>
                                    </div>
                                </div>
                            </div>
"""

        html += """
                        </div>
                    </div>
"""

    # Prepare chart data
    models_list = list(models)

    # Core metrics
    faiths = [stats_by_model[m]["faithfulness"] for m in models_list]
    relevs = [stats_by_model[m]["relevance"] for m in models_list]

    # Multi-chunk metrics
    attrs = [stats_by_model[m]["attribution"] for m in models_list]
    coherences = [stats_by_model[m]["coherence"] for m in models_list]

    # Performance by chunk count
    chunk_count_data = {}
    for model_name, results in all_results.items():
        chunk_count_data[model_name] = {}
        for result in results:
            count = result.num_chunks_provided
            if count not in chunk_count_data[model_name]:
                chunk_count_data[model_name][count] = []
            chunk_count_data[model_name][count].append(result.faithfulness["score"])

    # Average by chunk count
    chunk_counts = sorted(set(r.num_chunks_provided for results in all_results.values() for r in results))
    chunk_count_datasets = []
    colors = ["#4f46e5", "#10b981", "#f59e0b", "#ef4444", "#a855f7"]
    for idx, model_name in enumerate(models_list):
        data = []
        for count in chunk_counts:
            if count in chunk_count_data.get(model_name, {}):
                avg = sum(chunk_count_data[model_name][count]) / len(chunk_count_data[model_name][count])
                data.append(avg)
            else:
                data.append(None)
        chunk_count_datasets.append({
            "label": model_name,
            "data": data,
            "backgroundColor": colors[idx % len(colors)],
            "borderColor": colors[idx % len(colors)],
            "borderWidth": 2,
            "tension": 0.2
        })

    html += f"""
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleElement(elementId, button) {{
            const element = document.getElementById(elementId);
            const isHidden = element.classList.contains('hidden');

            if (isHidden) {{
                element.classList.remove('hidden');
                button.textContent = button.textContent.replace('Show', 'Hide');
            }} else {{
                element.classList.add('hidden');
                button.textContent = button.textContent.replace('Hide', 'Show');
            }}
        }}

        const models_list = {json.dumps(models_list)};

        // Core metrics chart
        new Chart(document.getElementById('coreMetricsChart'), {{
            type: 'bar',
            data: {{
                labels: models_list,
                datasets: [
                    {{
                        label: 'Faithfulness',
                        data: {json.dumps(faiths)},
                        backgroundColor: '#4f46e5',
                    }},
                    {{
                        label: 'Relevance',
                        data: {json.dumps(relevs)},
                        backgroundColor: '#10b981',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true, max: 1 }}
                }}
            }}
        }});

        // Multi-chunk metrics chart
        new Chart(document.getElementById('multiChunkMetricsChart'), {{
            type: 'bar',
            data: {{
                labels: models_list,
                datasets: [
                    {{
                        label: 'Attribution',
                        data: {json.dumps(attrs)},
                        backgroundColor: '#a855f7',
                    }},
                    {{
                        label: 'Coherence',
                        data: {json.dumps(coherences)},
                        backgroundColor: '#06b6d4',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true, max: 1 }}
                }}
            }}
        }});

        // Performance by chunk count
        new Chart(document.getElementById('chunkCountChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(chunk_counts)},
                datasets: {json.dumps(chunk_count_datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 1,
                        title: {{ display: true, text: 'Faithfulness Score' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Number of Chunks' }}
                    }}
                }},
                plugins: {{
                    title: {{
                        display: true,
                        text: 'How does performance change with more chunks?'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    # Save report
    report_path = get_multichunk_report_path(models, num_questions, timestamp=run_timestamp, format="html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return report_path


def run_comparison():
    """Main comparison entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate multi-chunk generation quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This evaluates LLM response quality with multiple chunks as context,
reflecting real-world usage where 5-25 chunks are provided.

Metrics:
  - Faithfulness: Answer fidelity to sources
  - Relevance: How well the answer addresses the question
  - Attribution: Correct chunk usage
  - Cross-Chunk Coherence: Quality of multi-chunk synthesis
  - Speed: Words per second generation rate

Examples:
    python -m eval.eval_generation_multichunk mistral neural-chat
    python -m eval.eval_generation_multichunk qwen3:latest --trials 10 --html
    python -m eval.eval_generation_multichunk --generate-dataset --size 30
        """
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="Model names to compare (space-separated)"
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=10,
        help="Number of questions to evaluate (default: 10)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report with visualizations"
    )
    parser.add_argument(
        "--judge",
        type=str,
        help="Model to use as judge (default: from config)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "mlx"],
        default="ollama",
        help="LLM provider for run models (default: ollama)"
    )
    parser.add_argument(
        "--judge-provider",
        type=str,
        choices=["ollama", "mlx"],
        default=None,
        dest="judge_provider",
        help="LLM provider for judge model (default: same as --provider)"
    )
    parser.add_argument(
        "--generate-dataset",
        action="store_true",
        help="Generate multi-chunk dataset instead of running evaluation"
    )
    parser.add_argument(
        "--size",
        type=int,
        default=30,
        help="Dataset size when using --generate-dataset (default: 30)"
    )
    parser.add_argument(
        "--chunks",
        type=str,
        default="5,10,15",
        help="Comma-separated chunk counts for dataset generation (default: 5,10,15)"
    )
    args = parser.parse_args()

    # Dataset generation mode
    if args.generate_dataset:
        chunk_counts = [int(x.strip()) for x in args.chunks.split(",")]
        generate_dataset(args.size, chunk_counts)
        return

    # Evaluation mode
    models = args.models if args.models else []

    # Default models if none provided
    if not models:
        models = ["qwen3:latest", "qwen2.5:3b"]
        print("ℹ️  No models specified. Using defaults: qwen3:latest, qwen2.5:3b")
        print()

    # Clean up model names
    models = [m.strip() for m in models if m.strip()]

    if len(models) < 1:
        parser.print_help()
        print("\n❌ Error: Must specify at least 1 model")
        return

    print("=" * 60)
    print("RAG Evaluation - Multi-Chunk Generation Quality")
    print("=" * 60)
    print()

    config = Config()
    judge_model = args.judge if args.judge else config.llm_model
    judge_provider_type = args.judge_provider if args.judge_provider else args.provider

    # Check Ollama availability for run models
    if args.provider == "ollama":
        print(f"Checking Ollama run models at {config.ollama_url}...")
        available, missing = check_ollama_models_available(config, models)

        if missing:
            display_missing_models_help(missing)
            available_test_models = [m for m in models if m in available]
            if not available_test_models:
                print("❌ Error: No test models available.")
                return
            print(f"Continuing with available models: {', '.join(available_test_models)}\n")
            models = available_test_models

    # Check Ollama availability for judge model
    if judge_provider_type == "ollama":
        _, judge_missing = check_ollama_models_available(config, [judge_model])
        if judge_missing:
            display_missing_models_help(judge_missing)
            print(f"❌ Error: Judge model '{judge_model}' is not available on Ollama.")
            return

    print(f"Models: {', '.join(models)}")
    print(f"Judge: {judge_model}")
    print(f"Run provider: {args.provider} | Judge provider: {judge_provider_type}")
    print()

    # Load dataset
    dataset = load_multichunk_dataset(config)
    if not dataset:
        print("❌ Error: Multi-chunk dataset not found.")
        print("   Run: python -m eval.eval_generation_multichunk --generate-dataset --size 30")
        return

    print(f"Loaded {len(dataset)} multi-chunk QA pairs")

    # Load chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    chunks_map = {c.chunk_id: c for c in chunks}

    # Limit to trials
    qa_pairs = dataset[:args.trials]
    print(f"Evaluating on {len(qa_pairs)} questions\n")

    # Create evaluator (uses judge_provider_type for metrics/judging)
    evaluator = MultiChunkEvaluator(config, judge_provider_type)

    # Create providers: run models use args.provider
    providers = {m: create_provider(config, m, args.provider) for m in models}
    judge_provider = create_provider(config, judge_model, judge_provider_type)

    # Use a single timestamp for all reports in this run
    run_timestamp = datetime.now()

    # Phase 1: Generation
    print("\n" + "="*60)
    print("🚀 PHASE 1: GENERATION (Batch per model)")
    print("="*60)

    # Initialize structure
    all_results = {m: [] for m in models}
    
    # Pre-structure results with empty placeholders to maintain order
    for model in models:
        all_results[model] = [None] * len(qa_pairs)

    for model in models:
        print(f"\n🤖 Running Generation for model: {model}")
        provider_instance = providers[model]
        
        for i, qa in enumerate(qa_pairs):
            print(f"  Question [{i+1}/{len(qa_pairs)}]...", end="", flush=True)
            
            # 1. Retrieve chunks
            chunks = [chunks_map[cid] for cid in qa.source_chunk_ids if cid in chunks_map]
            
            # 2. Format context
            context = format_multichunk_context(chunks, qa.intent)
            
            start = time.time()
            try:
                # 3. Generate answer
                prompt = get_eval_prompt(qa.question, context)
                answer = provider_instance.generate(
                    [{"role": "user", "content": prompt}],
                    timeout=180
                )
                duration = time.time() - start
                word_count = len(answer.split())
                wps = word_count / duration if duration > 0 else 0
                
                # Store intermediate result with generation stats (metrics will be 0 for now)
                all_results[model][i] = MultiChunkEvalResult(
                    question=qa.question,
                    expected_answer=qa.expected_answer,
                    generated_answer=answer,
                    source_chunk_ids=qa.source_chunk_ids,
                    intent=qa.intent,
                    faithfulness={"score": 0.0, "explanation": "Pending"},
                    relevance={"score": 0.0, "explanation": "Pending"},
                    chunk_attribution_score=0.0, 
                    chunk_attribution_explanation="Pending",
                    cross_chunk_coherence=0.0, 
                    cross_chunk_explanation="Pending",
                    num_chunks_provided=len(chunks),
                    num_chunks_used=len(chunks), 
                    generation_time=duration,
                    words_per_sec=wps
                )
                print(f" Done ({duration:.2f}s)")

            except Exception as e:
                print(f" Failed ({e})")
                all_results[model][i] = MultiChunkEvalResult(
                    question=qa.question,
                    expected_answer=qa.expected_answer,
                    generated_answer=f"Error: {e}",
                    source_chunk_ids=qa.source_chunk_ids,
                    intent=qa.intent,
                    faithfulness={"score": 0.0, "explanation": f"Error: {e}"},
                    relevance={"score": 0.0, "explanation": f"Error: {e}"},
                    chunk_attribution_score=0.0, chunk_attribution_explanation="Error",
                    cross_chunk_coherence=0.0, cross_chunk_explanation="Error",
                    num_chunks_provided=len(chunks), num_chunks_used=0,
                    generation_time=0.0, words_per_sec=0.0
                )

    # Phase 2: Judging
    print("\n" + "="*60)
    print("⚖️  PHASE 2: JUDGING (Batch)")
    print("="*60)

    for i, qa in enumerate(qa_pairs):
        print(f"\n[{i+1}/{len(qa_pairs)}] Judging Question: {qa.question[:60]}...")
        
        # 1. Retrieve chunks
        chunks = [chunks_map[cid] for cid in qa.source_chunk_ids if cid in chunks_map]
        context = format_multichunk_context(chunks, qa.intent)

        for model in models:
            res = all_results[model][i]
            if not res or res.generated_answer.startswith("Error"):
                continue

            print(f"  👨‍⚖️  Judging {model}...", end="", flush=True)
            
            try:
                # 4. Compute metrics using evaluator (which holds the RAGASMetrics instance)
                faith_data = evaluator.metrics.compute_faithfulness_with_explanation(
                    qa.question, res.generated_answer, context
                )
                relev_data = evaluator.metrics.compute_relevance_with_explanation(
                    qa.question, qa.expected_answer, res.generated_answer
                )
                attr_score, attr_expl = evaluator.metrics.compute_chunk_attribution(
                    qa.question, res.generated_answer, qa.expected_chunk_attribution or qa.source_chunk_ids[:3], chunks
                )
                coh_score, coh_expl = evaluator.metrics.compute_cross_chunk_coherence(
                    qa.question, res.generated_answer, len(chunks)
                )

                # Update the result object in place
                # (Can't directly set attributes of dataclass if frozen, but MultiChunkEvalResult isn't frozen)
                res.faithfulness = faith_data
                res.relevance = relev_data
                res.chunk_attribution_score = attr_score
                res.chunk_attribution_explanation = attr_expl
                res.cross_chunk_coherence = coh_score
                res.cross_chunk_explanation = coh_expl
                
                print(f" Faith: {faith_data['score']:.2f} | Relev: {relev_data['score']:.2f}")

            except Exception as e:
                print(f" Failed ({e})")
                res.faithfulness = {"score": 0.0, "explanation": f"Judge error: {e}"}
                res.relevance = {"score": 0.0, "explanation": f"Judge error: {e}"}

    # Final Synthesis in French
    print("\n✍️ Génération de la synthèse finale...")
    synth_prompt = f"Tu es un juge expert. Compare ces résultats pour les modèles {models} et fournis une conclusion humaine détaillée sur leurs forces et faiblesses respectives basées sur ces tests de génération RAG MULTI-CHUNK.\n\nDonnées : " + json.dumps({m: [r.to_dict() for r in all_results[m]] for m in models})
    
    try:
        synth_resp = judge_provider.generate(
            [{"role": "user", "content": synth_prompt}],
            timeout=180
        )
    except Exception as e:
        synth_resp = f"Erreur lors de la génération de la synthèse : {e}"

    # Generate consolidated JSON report
    print("\n📊 Génération du rapport JSON consolidé...")
    json_path = generate_multichunk_comparison_json(
        all_results, qa_pairs, judge_model, args.provider, len(qa_pairs), synth_resp, run_timestamp=run_timestamp
    )
    print(f"  ✅ Rapport JSON enregistré : {json_path}")

    if args.html:
        print("\n📊 Generating HTML report...")
        html_path = generate_html_report(
            all_results, qa_pairs, judge_model, chunks_map, models, len(qa_pairs), synth_resp, run_timestamp=run_timestamp
        )
        print(f"✅ HTML report saved: {html_path}")

    print("\n" + synth_resp)
    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    run_comparison()
