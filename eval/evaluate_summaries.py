"""
Evaluation system for hierarchical conversation summaries.
Tests ConversationSummary and PeriodSummary quality.
"""

import json
import sys
import time
import argparse
import requests
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.summary_store import SummaryStore
from rag_pipeline.summary_models import ConversationSummary, PeriodSummary
from eval._output_paths import get_summaries_report_path


@dataclass
class SummaryEvalResult:
    """Result of evaluating a single summary."""
    summary_id: str
    summary_type: str  # "conversation" or "period"
    summary_content: str
    test_question: str
    expected_answer: str
    generated_answer: str

    conciseness_score: float  # 0-1, is it concise?
    completeness_score: float  # 0-1, does it cover all key points?
    accuracy_score: float  # 0-1, is it factually correct?

    judge_explanation: str


class SummaryEvaluator:
    """Evaluate summary quality."""

    def __init__(self, config: Config):
        self.config = config
        self.summary_store = SummaryStore(config)

    def evaluate_conversation_summary(self, summary: ConversationSummary) -> List[SummaryEvalResult]:
        """Generate and evaluate questions about a conversation summary."""
        results = []

        # Generate 3 questions per summary
        questions = self._generate_summary_questions(
            summary.summary,
            summary.main_topics,
            summary.notable_events,
            summary.participants,
            summary.date_start
        )

        for question, expected_answer in questions:
            # Generate answer from summary
            answer_prompt = f"""Based on this summary:
"{summary.summary}"

Key topics: {', '.join(summary.main_topics)}
Notable events: {', '.join(summary.notable_events)}

Answer this question: {question}
Provide a concise answer."""

            generated_answer = self._call_llm(answer_prompt)

            # Judge the answer
            concise, complete, accurate, explanation = self._judge_answer(
                question, expected_answer, generated_answer, summary.summary
            )

            results.append(SummaryEvalResult(
                summary_id=summary.summary_id,
                summary_type="conversation",
                summary_content=summary.summary,
                test_question=question,
                expected_answer=expected_answer,
                generated_answer=generated_answer,
                conciseness_score=concise,
                completeness_score=complete,
                accuracy_score=accurate,
                judge_explanation=explanation
            ))

        return results

    def evaluate_period_summary(self, summary: PeriodSummary) -> List[SummaryEvalResult]:
        """Generate and evaluate questions about a period summary."""
        results = []

        # Generate 2 questions per period summary
        questions = self._generate_period_questions(
            summary.summary,
            summary.topics,
            summary.mood,
            summary.period
        )

        for question, expected_answer in questions:
            # Generate answer from summary
            answer_prompt = f"""Based on this period summary for {summary.period}:
"{summary.summary}"

Topics: {', '.join(summary.topics)}
Mood: {summary.mood}

Answer this question: {question}
Provide a concise answer."""

            generated_answer = self._call_llm(answer_prompt)

            # Judge the answer
            concise, complete, accurate, explanation = self._judge_answer(
                question, expected_answer, generated_answer, summary.summary
            )

            results.append(SummaryEvalResult(
                summary_id=summary.summary_id,
                summary_type="period",
                summary_content=summary.summary,
                test_question=question,
                expected_answer=expected_answer,
                generated_answer=generated_answer,
                conciseness_score=concise,
                completeness_score=complete,
                accuracy_score=accurate,
                judge_explanation=explanation
            ))

        return results

    def _generate_summary_questions(
        self,
        summary: str,
        topics: List[str],
        events: List[str],
        participants: List[str],
        date_start: str
    ) -> List[Tuple[str, str]]:
        """Generate test questions for a conversation summary."""
        prompt = f"""Generate 3 test questions to evaluate this conversation summary:

Summary: "{summary}"
Main topics: {', '.join(topics)}
Notable events: {', '.join(events)}
Participants: {', '.join(participants)}

Generate questions that test:
1. Understanding of main topics
2. Comprehension of key events
3. Inference about relationship/dynamics

Format as JSON:
[
  {{"question": "...", "expected_answer": "..."}},
  ...
]

Only return JSON, no explanation."""

        response = self._call_llm(prompt)

        try:
            # Extract JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response)
            return [(q['question'], q['expected_answer']) for q in data[:3]]
        except:
            # Fallback questions
            return [
                (f"What are the main topics discussed with {participants[0]}?", ", ".join(topics)),
                (f"What notable events happened in this conversation?", ", ".join(events)),
                (f"Summarize this conversation in one sentence.", summary)
            ]

    def _generate_period_questions(
        self,
        summary: str,
        topics: List[str],
        mood: str,
        period: str
    ) -> List[Tuple[str, str]]:
        """Generate test questions for a period summary."""
        prompt = f"""Generate 2 test questions to evaluate this monthly summary:

Period: {period}
Summary: "{summary}"
Topics: {', '.join(topics)}
Overall mood: {mood}

Generate questions that test:
1. Understanding of key topics in this period
2. Comprehension of the overall mood/atmosphere

Format as JSON:
[
  {{"question": "...", "expected_answer": "..."}},
  ...
]

Only return JSON, no explanation."""

        response = self._call_llm(prompt)

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response)
            return [(q['question'], q['expected_answer']) for q in data[:2]]
        except:
            return [
                (f"What were the main topics in {period}?", ", ".join(topics)),
                (f"What was the overall mood in {period}?", mood)
            ]

    def _judge_answer(
        self,
        question: str,
        expected: str,
        generated: str,
        source: str
    ) -> Tuple[float, float, float, str]:
        """Judge answer quality on three dimensions."""
        prompt = f"""Tu es un expert en évaluation de résumés. Évalue cette réponse.

QUESTION: {question}
RÉPONSE ATTENDUE: {expected}
RÉPONSE GÉNÉRÉE: {generated}
SOURCE: {source[:500]}

Évalue sur 3 dimensions (0-1 chacun):
1. CONCISENESS: Est-ce que la réponse est concise et directe?
2. COMPLETENESS: Est-ce que la réponse couvre tous les points importants?
3. ACCURACY: Est-ce que la réponse est factuellement correcte?

Réponds en JSON:
{{
  "conciseness": 0.0-1.0,
  "completeness": 0.0-1.0,
  "accuracy": 0.0-1.0,
  "explanation": "..."
}}"""

        try:
            response = self._call_llm(prompt)

            # Extract JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response)
            return (
                float(data.get('conciseness', 0.5)),
                float(data.get('completeness', 0.5)),
                float(data.get('accuracy', 0.5)),
                data.get('explanation', 'No explanation')
            )
        except:
            return 0.5, 0.5, 0.5, "Error in judgment"

    def _call_llm(self, prompt: str) -> str:
        """Call LLM for evaluation."""
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=60
            )
            return response.json()["message"]["content"].strip()
        except Exception as e:
            return f"Error: {e}"


def generate_json_report(
    results: List[SummaryEvalResult],
    conversations: int = 0,
    periods: int = 0
) -> Path:
    """Generate JSON report for summary evaluation."""
    # Calculate metrics
    avg_conciseness = sum(r.conciseness_score for r in results) / len(results) if results else 0
    avg_completeness = sum(r.completeness_score for r in results) / len(results) if results else 0
    avg_accuracy = sum(r.accuracy_score for r in results) / len(results) if results else 0

    # Group by summary type
    conv_results = [r for r in results if r.summary_type == "conversation"]
    period_results = [r for r in results if r.summary_type == "period"]

    report_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "conversations_evaluated": conversations,
            "periods_evaluated": periods,
            "total_evaluations": len(results)
        },
        "summary": {
            "avg_conciseness": round(avg_conciseness, 3),
            "avg_completeness": round(avg_completeness, 3),
            "avg_accuracy": round(avg_accuracy, 3),
            "by_type": {
                "conversation": {
                    "count": len(conv_results),
                    "avg_conciseness": round(sum(r.conciseness_score for r in conv_results) / len(conv_results), 3) if conv_results else 0,
                    "avg_completeness": round(sum(r.completeness_score for r in conv_results) / len(conv_results), 3) if conv_results else 0,
                    "avg_accuracy": round(sum(r.accuracy_score for r in conv_results) / len(conv_results), 3) if conv_results else 0
                },
                "period": {
                    "count": len(period_results),
                    "avg_conciseness": round(sum(r.conciseness_score for r in period_results) / len(period_results), 3) if period_results else 0,
                    "avg_completeness": round(sum(r.completeness_score for r in period_results) / len(period_results), 3) if period_results else 0,
                    "avg_accuracy": round(sum(r.accuracy_score for r in period_results) / len(period_results), 3) if period_results else 0
                }
            }
        },
        "results": [
            {
                "summary_id": r.summary_id,
                "summary_type": r.summary_type,
                "test_question": r.test_question,
                "expected_answer": r.expected_answer,
                "generated_answer": r.generated_answer,
                "scores": {
                    "conciseness": round(r.conciseness_score, 3),
                    "completeness": round(r.completeness_score, 3),
                    "accuracy": round(r.accuracy_score, 3)
                },
                "judge_explanation": r.judge_explanation
            }
            for r in results
        ]
    }

    report_path = get_summaries_report_path(conversations, periods, format="json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return report_path


def generate_html_report(
    results: List[SummaryEvalResult],
    conversations: int = 0,
    periods: int = 0
) -> Path:
    """Generate HTML report for summary evaluation."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate metrics
    avg_conciseness = sum(r.conciseness_score for r in results) / len(results) if results else 0
    avg_completeness = sum(r.completeness_score for r in results) / len(results) if results else 0
    avg_accuracy = sum(r.accuracy_score for r in results) / len(results) if results else 0

    # Group by summary type
    conv_results = [r for r in results if r.summary_type == "conversation"]
    period_results = [r for r in results if r.summary_type == "period"]

    html = f"""
<!DOCTYPE html>
<html lang="fr" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport d'Évaluation de Résumés</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
    </style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                    📋 Rapport d'Évaluation de Résumés
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Généré le <span class="font-semibold text-indigo-600">{timestamp}</span> •
                    <span class="font-semibold text-indigo-600">{len(results)}</span> évaluations
                </p>
            </div>

            <!-- Metrics Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
                <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-bold text-slate-600 uppercase tracking-wider mb-2">
                        📏 Conciseness
                    </h3>
                    <div class="text-4xl font-extrabold text-indigo-600 mb-2">
                        {avg_conciseness*100:.0f}%
                    </div>
                    <div class="w-full bg-slate-200 rounded-full h-2">
                        <div class="bg-indigo-600 h-2 rounded-full" style="width: {avg_conciseness*100}%"></div>
                    </div>
                </div>

                <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-bold text-slate-600 uppercase tracking-wider mb-2">
                        ✅ Completeness
                    </h3>
                    <div class="text-4xl font-extrabold text-green-600 mb-2">
                        {avg_completeness*100:.0f}%
                    </div>
                    <div class="w-full bg-slate-200 rounded-full h-2">
                        <div class="bg-green-600 h-2 rounded-full" style="width: {avg_completeness*100}%"></div>
                    </div>
                </div>

                <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-bold text-slate-600 uppercase tracking-wider mb-2">
                        🎯 Accuracy
                    </h3>
                    <div class="text-4xl font-extrabold text-purple-600 mb-2">
                        {avg_accuracy*100:.0f}%
                    </div>
                    <div class="w-full bg-slate-200 rounded-full h-2">
                        <div class="bg-purple-600 h-2 rounded-full" style="width: {avg_accuracy*100}%"></div>
                    </div>
                </div>
            </div>

            <!-- Details Section -->
            <div class="space-y-12">
    """

    # Conversation summaries section
    if conv_results:
        html += """
                <div class="border-b border-slate-200 pb-8">
                    <h2 class="text-3xl font-bold text-slate-900 mb-6">🗣️ Conversation Summaries</h2>
                    <div class="space-y-8">
        """
        for i, result in enumerate(conv_results):
            summary_preview = result.summary_content[:100] if result.summary_content else "..."
            html += f"""
                        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                            <div class="bg-indigo-50 px-8 py-4 border-b border-slate-100">
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 mb-2">
                                    Summary {i+1}
                                </span>
                                <h3 class="text-lg font-bold text-slate-900 mt-2">{summary_preview}...</h3>
                            </div>
                            <div class="px-8 py-6">
                                <div class="mb-6 p-4 bg-slate-50 rounded-lg">
                                    <p class="text-sm font-bold text-slate-600 uppercase tracking-wide mb-2">Question</p>
                                    <p class="text-slate-800">{result.test_question}</p>
                                </div>
                                <div class="grid grid-cols-3 gap-4 mb-6">
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Conciseness</p>
                                        <p class="text-2xl font-bold text-indigo-600">{result.conciseness_score*100:.0f}%</p>
                                    </div>
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Completeness</p>
                                        <p class="text-2xl font-bold text-green-600">{result.completeness_score*100:.0f}%</p>
                                    </div>
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Accuracy</p>
                                        <p class="text-2xl font-bold text-purple-600">{result.accuracy_score*100:.0f}%</p>
                                    </div>
                                </div>
                                <div class="p-4 bg-slate-50 rounded-lg">
                                    <p class="text-xs font-bold text-slate-600 uppercase mb-2">Judge Note</p>
                                    <p class="text-sm text-slate-700">{result.judge_explanation}</p>
                                </div>
                            </div>
                        </div>
            """
        html += """
                    </div>
                </div>
        """

    # Period summaries section
    if period_results:
        html += """
                <div>
                    <h2 class="text-3xl font-bold text-slate-900 mb-6">📅 Period Summaries</h2>
                    <div class="space-y-8">
        """
        for i, result in enumerate(period_results):
            period_preview = result.summary_content[:100] if result.summary_content else "..."
            html += f"""
                        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                            <div class="bg-green-50 px-8 py-4 border-b border-slate-100">
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 mb-2">
                                    Period {i+1}
                                </span>
                                <h3 class="text-lg font-bold text-slate-900 mt-2">{period_preview}...</h3>
                            </div>
                            <div class="px-8 py-6">
                                <div class="mb-6 p-4 bg-slate-50 rounded-lg">
                                    <p class="text-sm font-bold text-slate-600 uppercase tracking-wide mb-2">Question</p>
                                    <p class="text-slate-800">{result.test_question}</p>
                                </div>
                                <div class="grid grid-cols-3 gap-4 mb-6">
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Conciseness</p>
                                        <p class="text-2xl font-bold text-indigo-600">{result.conciseness_score*100:.0f}%</p>
                                    </div>
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Completeness</p>
                                        <p class="text-2xl font-bold text-green-600">{result.completeness_score*100:.0f}%</p>
                                    </div>
                                    <div>
                                        <p class="text-xs font-bold text-slate-600 uppercase">Accuracy</p>
                                        <p class="text-2xl font-bold text-purple-600">{result.accuracy_score*100:.0f}%</p>
                                    </div>
                                </div>
                                <div class="p-4 bg-slate-50 rounded-lg">
                                    <p class="text-xs font-bold text-slate-600 uppercase mb-2">Judge Note</p>
                                    <p class="text-sm text-slate-700">{result.judge_explanation}</p>
                                </div>
                            </div>
                        </div>
            """
        html += """
                    </div>
                </div>
        """

    html += """
            </div>
        </div>
    </div>
</body>
</html>
    """

    report_path = get_summaries_report_path(conversations, periods)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return report_path


def run_evaluation():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate hierarchical conversation summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python eval/evaluate_summaries.py
    python eval/evaluate_summaries.py --html
    python eval/evaluate_summaries.py --conversations 5
        """
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=3,
        help="Number of conversation summaries to evaluate (default: 3)"
    )
    parser.add_argument(
        "--periods",
        type=int,
        default=5,
        help="Number of period summaries to evaluate (default: 5)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Summary Evaluation Pipeline")
    print("=" * 60)
    print()

    config = Config()
    evaluator = SummaryEvaluator(config)

    # Load summary store
    if not evaluator.summary_store.load():
        print("No summaries found. Run the summary generation pipeline first.")
        return

    all_results = []
    conv_count = 0
    period_count = 0

    # Evaluate conversation summaries
    try:
        conv_summaries = evaluator.summary_store.conversation_summaries[:args.conversations]
        conv_count = len(conv_summaries)
        print(f"Evaluating {conv_count} conversation summaries...")

        for i, summary in enumerate(conv_summaries):
            print(f"  [{i+1}/{conv_count}] Evaluating {summary.summary_id}...", end="", flush=True)
            results = evaluator.evaluate_conversation_summary(summary)
            all_results.extend(results)
            print(" Done")

    except Exception as e:
        print(f"⚠️  Error loading conversation summaries: {e}")

    print()

    # Evaluate period summaries
    try:
        period_summaries = evaluator.summary_store.period_summaries[:args.periods]
        period_count = len(period_summaries)
        print(f"Evaluating {period_count} period summaries...")

        for i, summary in enumerate(period_summaries):
            print(f"  [{i+1}/{period_count}] Evaluating {summary.summary_id}...", end="", flush=True)
            results = evaluator.evaluate_period_summary(summary)
            all_results.extend(results)
            print(" Done")

    except Exception as e:
        print(f"⚠️  Error loading period summaries: {e}")

    print()

    if not all_results:
        print("No summaries evaluated.")
        return

    # Print summary
    avg_concise = sum(r.conciseness_score for r in all_results) / len(all_results)
    avg_complete = sum(r.completeness_score for r in all_results) / len(all_results)
    avg_accurate = sum(r.accuracy_score for r in all_results) / len(all_results)

    print(f"Evaluated {len(all_results)} summary questions")
    print()
    print("Results:")
    print(f"  📏 Conciseness:  {avg_concise*100:.1f}%")
    print(f"  ✅ Completeness: {avg_complete*100:.1f}%")
    print(f"  🎯 Accuracy:     {avg_accurate*100:.1f}%")
    print()

    # Always generate JSON report
    json_path = generate_json_report(all_results, conversations=conv_count, periods=period_count)
    print(f"✅ JSON report generated: {json_path}")

    # Optionally generate HTML report
    if args.html:
        html_path = generate_html_report(all_results, conversations=conv_count, periods=period_count)
        print(f"✅ HTML report generated: {html_path}")


if __name__ == "__main__":
    run_evaluation()
