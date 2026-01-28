"""
Benchmark runner for RAG evaluation.
Runs evaluations with different configurations and compares results.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.advanced_retriever import AdvancedRetriever, create_advanced_retriever
from rag_pipeline.chat import ChatBot

from .synthetic_generator import QAPair, QuestionType
from .metrics import RAGASMetrics, EvalResult, BenchmarkReport
from ._output_paths import get_retrieval_report_path, get_comparison_report_path


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    name: str
    use_query_rewriting: bool = True
    use_hypothetical_questions: bool = True  # In chunk embeddings
    use_reranking: bool = True
    use_hybrid: bool = True
    use_context_expansion: bool = True
    top_k: int = 5

    def to_dict(self) -> dict:
        return asdict(self)


class BenchmarkRunner:
    """Run benchmarks with different configurations."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.metrics = RAGASMetrics(config)

        # Lazy-loaded components
        self._retriever = None
        self._components = None
        self._chatbot = None

    @property
    def retriever(self) -> AdvancedRetriever:
        if self._retriever is None:
            self._retriever, self._components = create_advanced_retriever(
                self.config,
                enable_reranking=True,
                enable_bm25=True,
                enable_metadata=True
            )
        return self._retriever

    @property
    def chatbot(self) -> ChatBot:
        if self._chatbot is None:
            self._chatbot = ChatBot(self.retriever, self.config)
        return self._chatbot

    def run_benchmark(
        self,
        qa_pairs: List[QAPair],
        bench_config: BenchmarkConfig,
        progress_callback=None
    ) -> BenchmarkReport:
        """
        Run a full benchmark with the given configuration.

        Args:
            qa_pairs: List of QA pairs to evaluate
            bench_config: Configuration for this benchmark run
            progress_callback: Function(current, total, message)

        Returns:
            BenchmarkReport with aggregated results
        """
        results = []

        for i, qa in enumerate(qa_pairs):
            if progress_callback:
                progress_callback(i + 1, len(qa_pairs), f"Evaluating: {qa.question[:50]}...")

            result = self._evaluate_single(qa, bench_config)
            results.append(result)

        return self.metrics.aggregate_results(results, bench_config.name)

    def _evaluate_single(
        self,
        qa: QAPair,
        bench_config: BenchmarkConfig
    ) -> EvalResult:
        """Evaluate a single QA pair."""

        # 1. Optionally rewrite query
        search_query = qa.question
        if bench_config.use_query_rewriting and hasattr(self.chatbot, '_rewrite_query'):
            search_query = self.chatbot._rewrite_query(qa.question)

        # 2. Retrieve documents
        context = self.retriever.retrieve(
            query=search_query,
            top_k=bench_config.top_k,
            use_reranking=bench_config.use_reranking,
            use_hybrid=bench_config.use_hybrid,
            expand_context=bench_config.use_context_expansion
        )

        # 3. Check retrieval accuracy
        hit, rank, score = self.metrics.compute_retrieval_hit(
            qa.source_chunk_ids,
            context.results,
            bench_config.top_k
        )

        # 3b. Compute recall and precision at k
        recall_at_k = self.metrics.compute_recall_at_k(
            qa.source_chunk_ids,
            context.results,
            bench_config.top_k
        )
        precision_at_k = self.metrics.compute_precision_at_k(
            qa.source_chunk_ids,
            context.results,
            bench_config.top_k
        )

        # 4. Generate answer
        generated_answer = ""
        if context.has_results:
            try:
                response = self.chatbot.chat(
                    qa.question,
                    stream=False,
                    use_rewriting=False  # Already did rewriting
                )
                generated_answer = response.answer
            except Exception as e:
                generated_answer = f"[Error: {e}]"

        # 5. Evaluate faithfulness, relevance, and conciseness
        source_content = context.formatted_context if context.has_results else ""

        faithfulness = self.metrics.compute_faithfulness(
            qa.question,
            generated_answer,
            source_content
        )

        relevance = self.metrics.compute_answer_relevance(
            qa.question,
            qa.expected_answer,
            generated_answer
        )

        conciseness = self.metrics.compute_conciseness(
            qa.question,
            generated_answer
        )

        return EvalResult(
            question=qa.question,
            expected_answer=qa.expected_answer,
            generated_answer=generated_answer,
            source_chunk_ids=qa.source_chunk_ids,
            retrieved_chunk_ids=[r.chunk.chunk_id for r in context.results],
            retrieval_hit=hit,
            retrieval_rank=rank,
            retrieval_score=score,
            recall_at_k=recall_at_k,
            precision_at_k=precision_at_k,
            faithfulness_score=faithfulness,
            answer_relevance=relevance,
            conciseness_score=conciseness,
            config_used={
                'question_type': qa.question_type.value,
                'difficulty': qa.difficulty.value,
                'benchmark_config': bench_config.name
            }
        )

    def compare_configs(
        self,
        qa_pairs: List[QAPair],
        configs: List[BenchmarkConfig] = None,
        progress_callback=None
    ) -> Dict[str, BenchmarkReport]:
        """
        Compare multiple configurations on the same dataset.

        Args:
            qa_pairs: List of QA pairs
            configs: Configurations to compare (defaults to standard comparison)
            progress_callback: Progress callback

        Returns:
            Dict mapping config name to BenchmarkReport
        """
        if configs is None:
            # Default comparison: with vs without key features
            configs = [
                BenchmarkConfig(
                    name="full",
                    use_query_rewriting=True,
                    use_reranking=True,
                    use_hybrid=True,
                    use_context_expansion=True
                ),
                BenchmarkConfig(
                    name="no_reranking",
                    use_query_rewriting=True,
                    use_reranking=False,
                    use_hybrid=True,
                    use_context_expansion=True
                ),
                BenchmarkConfig(
                    name="no_hybrid",
                    use_query_rewriting=True,
                    use_reranking=True,
                    use_hybrid=False,
                    use_context_expansion=True
                ),
                BenchmarkConfig(
                    name="minimal",
                    use_query_rewriting=False,
                    use_reranking=False,
                    use_hybrid=False,
                    use_context_expansion=False
                ),
            ]

        reports = {}

        for i, cfg in enumerate(configs):
            if progress_callback:
                progress_callback(0, len(qa_pairs), f"Running config: {cfg.name}")

            report = self.run_benchmark(
                qa_pairs,
                cfg,
                progress_callback=lambda curr, total, msg: progress_callback(
                    curr, total, f"[{cfg.name}] {msg}"
                ) if progress_callback else None
            )
            reports[cfg.name] = report

        return reports

    def save_report(self, report: BenchmarkReport, path: Path = None):
        """Save benchmark report to JSON."""
        path = path or get_retrieval_report_path(report.config_name)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"Report saved to {path}")

    def save_comparison(self, reports: Dict[str, BenchmarkReport], path: Path = None):
        """Save comparison results to JSON."""
        path = path or get_comparison_report_path()

        comparison = {
            'timestamp': datetime.now().isoformat(),
            'configs': {name: report.to_dict() for name, report in reports.items()},
            'summary': self._generate_comparison_summary(reports)
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)

        print(f"Comparison saved to {path}")

    def _generate_comparison_summary(self, reports: Dict[str, BenchmarkReport]) -> dict:
        """Generate a summary comparing all configurations."""
        summary = {
            'best_retrieval_accuracy': None,
            'best_mrr': None,
            'best_faithfulness': None,
            'ranking': []
        }

        # Find best for each metric
        best_acc = (None, 0.0)
        best_mrr = (None, 0.0)
        best_faith = (None, 0.0)

        for name, report in reports.items():
            if report.retrieval_accuracy > best_acc[1]:
                best_acc = (name, report.retrieval_accuracy)
            if report.mrr > best_mrr[1]:
                best_mrr = (name, report.mrr)
            if report.avg_faithfulness > best_faith[1]:
                best_faith = (name, report.avg_faithfulness)

        summary['best_retrieval_accuracy'] = {'config': best_acc[0], 'value': best_acc[1]}
        summary['best_mrr'] = {'config': best_mrr[0], 'value': best_mrr[1]}
        summary['best_faithfulness'] = {'config': best_faith[0], 'value': best_faith[1]}

        # Overall ranking (weighted score)
        scores = []
        for name, report in reports.items():
            score = (
                0.4 * report.retrieval_accuracy +
                0.3 * report.mrr +
                0.3 * report.avg_faithfulness
            )
            scores.append((name, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        summary['ranking'] = [{'config': name, 'score': score} for name, score in scores]

        return summary

    def print_comparison(self, reports: Dict[str, BenchmarkReport]):
        """Print a formatted comparison of results."""
        print("\n" + "=" * 70)
        print("BENCHMARK COMPARISON")
        print("=" * 70)

        # Header
        print(f"{'Config':<20} {'Acc%':>8} {'MRR':>8} {'Faith%':>8} {'Relev%':>8}")
        print("-" * 70)

        # Results
        for name, report in sorted(reports.items()):
            print(f"{name:<20} {report.retrieval_accuracy*100:>7.1f}% {report.mrr:>8.3f} {report.avg_faithfulness*100:>7.1f}% {report.avg_relevance*100:>7.1f}%")

        print("=" * 70)

        # Summary
        summary = self._generate_comparison_summary(reports)
        print(f"\nBest Retrieval Accuracy: {summary['best_retrieval_accuracy']['config']} ({summary['best_retrieval_accuracy']['value']:.1%})")
        print(f"Best MRR: {summary['best_mrr']['config']} ({summary['best_mrr']['value']:.3f})")
        print(f"Best Faithfulness: {summary['best_faithfulness']['config']} ({summary['best_faithfulness']['value']:.1%})")

        print("\nOverall Ranking:")
        for i, r in enumerate(summary['ranking']):
            print(f"  {i+1}. {r['config']}: {r['score']:.3f}")
