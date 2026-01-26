"""
RAGAS-inspired metrics for RAG evaluation.
Implements Retrieval Accuracy, MRR, and Faithfulness metrics.
"""

import json
import requests
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.advanced_retriever import AdvancedSearchResult


@dataclass
class EvalResult:
    """Result of evaluating a single question."""
    question: str
    expected_answer: str
    generated_answer: str
    source_chunk_id: str
    retrieved_chunk_ids: List[str]

    # Retrieval metrics
    retrieval_hit: bool  # Was correct chunk in top-k?
    retrieval_rank: Optional[int]  # Rank of correct chunk (1-indexed)
    retrieval_score: Optional[float]  # Score of correct chunk

    # Generation metrics
    faithfulness_score: float  # 0-1, LLM-judged answer fidelity
    answer_relevance: float  # 0-1, how relevant is the answer

    # Metadata
    config_used: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""
    config_name: str
    total_questions: int

    # Retrieval metrics
    retrieval_accuracy: float  # % questions where correct chunk in top-k
    mrr: float  # Mean Reciprocal Rank
    avg_retrieval_rank: float

    # Generation metrics
    avg_faithfulness: float
    avg_relevance: float

    # By type breakdown
    by_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_difficulty: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Individual results
    results: List[EvalResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['results'] = [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.results]
        return d

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"=== Benchmark Report: {self.config_name} ===",
            f"Total questions: {self.total_questions}",
            "",
            "Retrieval Metrics:",
            f"  Accuracy (Hit@k): {self.retrieval_accuracy:.1%}",
            f"  MRR: {self.mrr:.3f}",
            f"  Avg Rank: {self.avg_retrieval_rank:.2f}",
            "",
            "Generation Metrics:",
            f"  Faithfulness: {self.avg_faithfulness:.1%}",
            f"  Relevance: {self.avg_relevance:.1%}",
        ]

        if self.by_type:
            lines.append("")
            lines.append("By Question Type:")
            for qtype, metrics in self.by_type.items():
                lines.append(f"  {qtype}: Acc={metrics.get('accuracy', 0):.1%}, Faith={metrics.get('faithfulness', 0):.1%}")

        if self.by_difficulty:
            lines.append("")
            lines.append("By Difficulty:")
            for diff, metrics in self.by_difficulty.items():
                lines.append(f"  {diff}: Acc={metrics.get('accuracy', 0):.1%}, Faith={metrics.get('faithfulness', 0):.1%}")

        return "\n".join(lines)


FAITHFULNESS_PROMPT = """Tu es un évaluateur expert pour les systèmes de question-réponse.

QUESTION: {question}

RÉPONSE ATTENDUE: {expected_answer}

RÉPONSE GÉNÉRÉE: {generated_answer}

DOCUMENTS SOURCES:
{sources}

Évalue la FIDÉLITÉ de la réponse générée par rapport aux sources.
La fidélité mesure si la réponse:
1. Est factuelle et basée sur les sources
2. Ne contient pas d'hallucinations
3. Ne contredit pas les sources

Réponds avec un JSON strict:
{{"score": 0.0 à 1.0, "explanation": "..."}}

0.0 = Complètement faux/halluciné
0.5 = Partiellement correct
1.0 = Parfaitement fidèle aux sources"""


RELEVANCE_PROMPT = """Tu es un évaluateur expert pour les systèmes de question-réponse.

QUESTION: {question}

RÉPONSE ATTENDUE: {expected_answer}

RÉPONSE GÉNÉRÉE: {generated_answer}

Évalue la PERTINENCE de la réponse générée par rapport à la question.
La pertinence mesure si la réponse:
1. Répond directement à la question posée
2. Est complète et couvre les points importants
3. Est comparable à la réponse attendue

Réponds avec un JSON strict:
{{"score": 0.0 à 1.0, "explanation": "..."}}

0.0 = Hors sujet / Ne répond pas
0.5 = Répond partiellement
1.0 = Répond parfaitement"""


class RAGASMetrics:
    """Compute RAGAS-style metrics for RAG evaluation."""

    def __init__(self, config: Config = None):
        self.config = config or default_config

    def compute_retrieval_accuracy(
        self,
        source_chunk_id: str,
        retrieved_results: List[AdvancedSearchResult],
        top_k: int = 5
    ) -> tuple:
        """
        Check if the correct source chunk is in the top-k results.

        Returns:
            (hit: bool, rank: Optional[int], score: Optional[float])
        """
        for i, result in enumerate(retrieved_results[:top_k]):
            if result.chunk.chunk_id == source_chunk_id:
                return True, i + 1, result.final_score

        return False, None, None

    def compute_mrr(self, results: List[EvalResult]) -> float:
        """
        Compute Mean Reciprocal Rank.

        MRR = average of 1/rank for each query where correct doc was found.
        """
        reciprocal_ranks = []

        for result in results:
            if result.retrieval_hit and result.retrieval_rank:
                reciprocal_ranks.append(1.0 / result.retrieval_rank)
            else:
                reciprocal_ranks.append(0.0)

        if not reciprocal_ranks:
            return 0.0

        return sum(reciprocal_ranks) / len(reciprocal_ranks)

    def compute_faithfulness(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str,
        source_content: str
    ) -> float:
        """
        Use LLM-as-judge to evaluate answer faithfulness to sources.

        Returns:
            Score between 0 and 1.
        """
        prompt = FAITHFULNESS_PROMPT.format(
            question=question,
            expected_answer=expected_answer,
            generated_answer=generated_answer,
            sources=source_content[:2000]
        )

        return self._llm_judge(prompt)

    def compute_answer_relevance(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str
    ) -> float:
        """
        Use LLM-as-judge to evaluate answer relevance.

        Returns:
            Score between 0 and 1.
        """
        prompt = RELEVANCE_PROMPT.format(
            question=question,
            expected_answer=expected_answer,
            generated_answer=generated_answer
        )

        return self._llm_judge(prompt)

    def _llm_judge(self, prompt: str) -> float:
        """Call LLM and extract score from response."""
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 256,
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            content = response.json()["message"]["content"].strip()

            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            # Try to find JSON in response
            import re
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get('score', 0.5))
                return max(0.0, min(1.0, score))

            return 0.5

        except Exception as e:
            print(f"LLM judge error: {e}")
            return 0.5

    def aggregate_results(
        self,
        results: List[EvalResult],
        config_name: str = "default"
    ) -> BenchmarkReport:
        """Aggregate individual results into a benchmark report."""
        if not results:
            return BenchmarkReport(
                config_name=config_name,
                total_questions=0,
                retrieval_accuracy=0.0,
                mrr=0.0,
                avg_retrieval_rank=0.0,
                avg_faithfulness=0.0,
                avg_relevance=0.0
            )

        # Compute retrieval metrics
        hits = sum(1 for r in results if r.retrieval_hit)
        retrieval_accuracy = hits / len(results)

        mrr = self.compute_mrr(results)

        ranks = [r.retrieval_rank for r in results if r.retrieval_rank]
        avg_rank = sum(ranks) / len(ranks) if ranks else 0.0

        # Compute generation metrics
        avg_faithfulness = sum(r.faithfulness_score for r in results) / len(results)
        avg_relevance = sum(r.answer_relevance for r in results) / len(results)

        # Group by type and difficulty
        by_type = {}
        by_difficulty = {}

        for r in results:
            qtype = r.config_used.get('question_type', 'unknown')
            diff = r.config_used.get('difficulty', 'unknown')

            if qtype not in by_type:
                by_type[qtype] = {'count': 0, 'hits': 0, 'faithfulness': 0.0}
            by_type[qtype]['count'] += 1
            by_type[qtype]['hits'] += 1 if r.retrieval_hit else 0
            by_type[qtype]['faithfulness'] += r.faithfulness_score

            if diff not in by_difficulty:
                by_difficulty[diff] = {'count': 0, 'hits': 0, 'faithfulness': 0.0}
            by_difficulty[diff]['count'] += 1
            by_difficulty[diff]['hits'] += 1 if r.retrieval_hit else 0
            by_difficulty[diff]['faithfulness'] += r.faithfulness_score

        # Finalize by_type
        for t in by_type:
            c = by_type[t]['count']
            by_type[t] = {
                'accuracy': by_type[t]['hits'] / c if c else 0,
                'faithfulness': by_type[t]['faithfulness'] / c if c else 0
            }

        # Finalize by_difficulty
        for d in by_difficulty:
            c = by_difficulty[d]['count']
            by_difficulty[d] = {
                'accuracy': by_difficulty[d]['hits'] / c if c else 0,
                'faithfulness': by_difficulty[d]['faithfulness'] / c if c else 0
            }

        return BenchmarkReport(
            config_name=config_name,
            total_questions=len(results),
            retrieval_accuracy=retrieval_accuracy,
            mrr=mrr,
            avg_retrieval_rank=avg_rank,
            avg_faithfulness=avg_faithfulness,
            avg_relevance=avg_relevance,
            by_type=by_type,
            by_difficulty=by_difficulty,
            results=results
        )
