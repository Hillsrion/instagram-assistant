"""
RAGAS-inspired metrics for RAG evaluation.
Implements Retrieval Accuracy, MRR, and Faithfulness metrics.
"""

import json
import requests
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Union, Tuple
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.advanced_retriever import AdvancedSearchResult
from rag_pipeline.chunker import Chunk
from rag_pipeline.json_utils import repair_and_load_json


@dataclass
class EvalResult:
    """Result of evaluating a single question."""
    question: str
    expected_answer: str
    generated_answer: str
    source_chunk_ids: List[str]
    retrieved_chunk_ids: List[str]

    # Retrieval metrics
    retrieval_hit: bool  # Was correct chunk in top-k?
    retrieval_rank: Optional[int]  # Rank of correct chunk (1-indexed)
    retrieval_score: Optional[float]  # Score of correct chunk
    recall_at_k: float = 0.0  # Fraction of source chunks found in top-k
    precision_at_k: float = 0.0  # Fraction of top-k results that are source chunks

    # Generation metrics
    faithfulness_score: float = 0.0  # 0-1, LLM-judged answer fidelity
    answer_relevance: float = 0.0  # 0-1, how relevant is the answer
    conciseness_score: float = 0.0  # 0-1, LLM-judged conciseness

    # Metadata
    config_used: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MultiChunkEvalResult:
    """Result of evaluating a single multi-chunk question.

    Extends basic evaluation with multi-chunk specific metrics:
    - Chunk attribution: Did the LLM use the correct source chunks?
    - Cross-chunk coherence: Quality of synthesis across multiple chunks
    """
    question: str
    expected_answer: str
    generated_answer: str
    source_chunk_ids: List[str]
    intent: str  # "specific_fact", "complex_reasoning", "broad_summary"

    # Core metrics (compatible with single-chunk eval)
    faithfulness: Dict[str, Any]  # {score: float, explanation: str}
    relevance: Dict[str, Any]  # {score: float, explanation: str}

    # Multi-chunk specific metrics
    chunk_attribution_score: float = 0.0  # 0-1: Did LLM cite correct chunks?
    chunk_attribution_explanation: str = ""
    cross_chunk_coherence: float = 0.0  # 0-1: Quality of multi-chunk synthesis
    cross_chunk_explanation: str = ""

    # Performance metrics
    num_chunks_provided: int = 0
    num_chunks_used: int = 0  # Estimated from answer
    generation_time: float = 0.0
    words_per_sec: float = 0.0

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
    avg_recall_at_k: float = 0.0
    avg_precision_at_k: float = 0.0

    # Generation metrics
    avg_faithfulness: float = 0.0
    avg_relevance: float = 0.0
    avg_conciseness: float = 0.0

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


CONCISENESS_PROMPT = """Tu es un évaluateur expert pour les systèmes de question-réponse.

QUESTION: {question}

RÉPONSE GÉNÉRÉE: {generated_answer}

Évalue la CONCISION de la réponse générée.
La concision mesure si la réponse:
1. Va droit au but sans détours inutiles
2. Ne contient pas de répétitions ou de remplissage
3. Est proportionnelle à la complexité de la question

Réponds avec un JSON strict:
{{"score": 0.0 à 1.0, "explanation": "..."}}

0.0 = Extrêmement verbose / hors sujet
0.5 = Contient du remplissage mais reste lisible
1.0 = Parfaitement concise et directe"""


CHUNK_ATTRIBUTION_PROMPT = """You are an expert evaluator for RAG systems.

QUESTION: {question}

GENERATED ANSWER: {generated_answer}

CHUNKS PROVIDED (total: {num_chunks}):
{chunks_info}

EXPECTED CHUNKS TO BE USED: {expected_chunk_ids}

Evaluate CHUNK ATTRIBUTION: Did the LLM correctly use the expected source chunks?

Consider:
1. Does the answer reference information from the expected chunks?
2. Are citations or information traceable to the correct chunks?
3. Did the LLM avoid hallucinating information not in the expected chunks?
4. Did the LLM use chunks that weren't expected (potential error)?

Respond with strict JSON:
{{"score": 0.0 to 1.0, "explanation": "which chunks were used and if correct"}}

0.0 = Wrong chunks used or heavy hallucination
0.5 = Partially correct attribution
1.0 = Perfect attribution to expected chunks"""


CROSS_CHUNK_COHERENCE_PROMPT = """You are an expert evaluator for RAG systems.

QUESTION: {question}

GENERATED ANSWER: {generated_answer}

NUMBER OF CHUNKS PROVIDED: {num_chunks}

Evaluate CROSS-CHUNK COHERENCE: Quality of synthesis across multiple chunks.

Consider:
1. Does the answer combine information from multiple chunks logically?
2. Are there contradictions or inconsistencies in the synthesis?
3. Is the multi-chunk synthesis fluent and coherent?
CHUNKS ATTENDUS : {expected_chunk_ids}

Évalue l'ATTRIBUTION DES CHUNKS : l'IA a-t-elle correctement utilisé les chunks sources attendus ?

Considère :
1. La réponse contient-elle des informations provenant des chunks attendus ?
2. Les citations ou informations sont-elles traçables vers les bons chunks ?
3. L'IA a-t-elle évité d'halluciner des informations non présentes dans les chunks attendus ?
4. L'IA a-t-elle utilisé des chunks non attendus (erreur potentielle) ?

Réponds avec un JSON strict :
{{"score" : 0.0 à 1.0, "explanation" : "quels chunks ont été utilisés et si c'est correct"}}

0.0 = Mauvais chunks utilisés ou forte hallucination
0.5 = Attribution partiellement correcte
1.0 = Attribution parfaite aux chunks attendus"""


CROSS_CHUNK_COHERENCE_PROMPT = """Tu es un évaluateur expert pour les systèmes RAG.

QUESTION : {question}

RÉPONSE GÉNÉRÉE : {generated_answer}

NOMBRE DE CHUNKS FOURNIS : {num_chunks}

Évalue la COHÉRENCE MULTI-CHUNKS : qualité de la synthèse à travers plusieurs chunks.

Considère :
1. La réponse combine-t-elle les informations de plusieurs chunks de manière logique ?
2. Y a-t-il des contradictions ou des incohérences dans la synthèse ?
3. La synthèse multi-chunks est-elle fluide et cohérente ?
4. La réponse démontre-t-elle une compréhension globale au-delà des limites de chaque chunk ?

Réponds avec un JSON strict :
{{"score" : 0.0 à 1.0, "explanation" : "évaluation de la qualité de la synthèse"}}

0.0 = Synthèse incohérente ou contradictoire
0.5 = Synthèse adéquate avec des problèmes mineurs
1.0 = Excellente synthèse multi-chunks"""


class RAGASMetrics:
    """Compute RAGAS-style metrics for RAG evaluation."""

    def __init__(self, config: Config = None, provider_type: str = "ollama"):
        self.config = config or default_config
        self.provider_type = provider_type
        self.provider = None  # Lazy init

    def compute_retrieval_hit(
        self,
        source_chunk_ids: List[str],
        retrieved_results: List[AdvancedSearchResult],
        top_k: int = 5
    ) -> tuple:
        """
        Check if any correct source chunk is in the top-k results.

        Args:
            source_chunk_ids: List of correct source chunk IDs
            retrieved_results: Retrieved results
            top_k: Number of top results to consider

        Returns:
            (hit: bool, rank: Optional[int], score: Optional[float])
        """
        source_set = set(source_chunk_ids)
        for i, result in enumerate(retrieved_results[:top_k]):
            if result.chunk.chunk_id in source_set:
                return True, i + 1, result.final_score

        return False, None, None

    # Backward-compatible alias
    def compute_retrieval_accuracy(
        self,
        source_chunk_id: str,
        retrieved_results: List[AdvancedSearchResult],
        top_k: int = 5
    ) -> tuple:
        """Deprecated: use compute_retrieval_hit instead."""
        return self.compute_retrieval_hit([source_chunk_id], retrieved_results, top_k)

    def compute_recall_at_k(
        self,
        source_chunk_ids: List[str],
        retrieved_results: List[AdvancedSearchResult],
        top_k: int = 5
    ) -> float:
        """
        Compute recall@k: fraction of source chunks found in top-k results.

        Returns:
            Float between 0 and 1.
        """
        if not source_chunk_ids:
            return 0.0
        source_set = set(source_chunk_ids)
        retrieved_ids = {r.chunk.chunk_id for r in retrieved_results[:top_k]}
        found = source_set & retrieved_ids
        return len(found) / len(source_set)

    def compute_precision_at_k(
        self,
        source_chunk_ids: List[str],
        retrieved_results: List[AdvancedSearchResult],
        top_k: int = 5
    ) -> float:
        """
        Compute precision@k: fraction of top-k results that are source chunks.

        Returns:
            Float between 0 and 1.
        """
        top_results = retrieved_results[:top_k]
        if not top_results:
            return 0.0
        source_set = set(source_chunk_ids)
        relevant = sum(1 for r in top_results if r.chunk.chunk_id in source_set)
        return relevant / len(top_results)

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

    def _llm_judge(self, prompt: str, return_explanation: bool = False) -> Union[float, Dict[str, Any]]:
        """
        Call LLM and extract score from response.

        Args:
            prompt: The evaluation prompt
            return_explanation: If True, return dict with score and explanation

        Returns:
            Score (float) if return_explanation=False, else dict with score and explanation
        """
        # Lazy init provider
        if self.provider is None:
            from rag_pipeline.llm_provider import create_provider
            self.provider = create_provider(self.config, self.config.llm_model, self.provider_type)

        try:
            content = self.provider.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                top_p=0.9,
                max_tokens=1024,
                timeout=120
            ).strip()

            data = repair_and_load_json(content)
            score = float(data.get('score', 0.5))
            score = max(0.0, min(1.0, score))
            
            if return_explanation:
                return {"score": score, "explanation": data.get('explanation', '')}
            return score

        except Exception as e:
            print(f"[JUDGE LOG] LLM judge error: {e}")
            if return_explanation:
                return {"score": 0.5, "explanation": f"Error: {e}"}
            return 0.5

    def compute_faithfulness_with_explanation(
        self,
        question: str,
        generated_answer: str,
        source_content: str,
        expected_answer: str = None  # kept for backward compat, ignored
    ) -> Dict[str, Any]:
        """
        Use LLM-as-judge to evaluate answer faithfulness to sources.
        Returns score and explanation.
        """
        prompt = FAITHFULNESS_PROMPT.format(
            question=question,
            generated_answer=generated_answer,
            sources=source_content[:2000]
        )
        return self._llm_judge(prompt, return_explanation=True)

    def compute_relevance_with_explanation(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str
    ) -> Dict[str, Any]:
        """
        Use LLM-as-judge to evaluate answer relevance.
        Returns score and explanation.
        """
        prompt = RELEVANCE_PROMPT.format(
            question=question,
            expected_answer=expected_answer,
            generated_answer=generated_answer
        )
        return self._llm_judge(prompt, return_explanation=True)

    def compute_conciseness(
        self,
        question: str,
        generated_answer: str
    ) -> float:
        """
        Use LLM-as-judge to evaluate answer conciseness.

        Returns:
            Score between 0 and 1.
        """
        prompt = CONCISENESS_PROMPT.format(
            question=question,
            generated_answer=generated_answer
        )
        return self._llm_judge(prompt)

    def compute_chunk_attribution(
        self,
        question: str,
        generated_answer: str,
        expected_chunk_ids: List[str],
        all_chunks: List[Chunk]
    ) -> Tuple[float, str]:
        """
        Use LLM-as-judge to evaluate chunk attribution.

        Checks if the LLM correctly used the expected source chunks
        in generating its answer.

        Args:
            question: The question asked
            generated_answer: The LLM's answer
            expected_chunk_ids: IDs of chunks that should be cited
            all_chunks: All chunks provided to the LLM

        Returns:
            (score: 0-1, explanation: str)
        """
        # Build chunks info (truncated for context limit)
        chunks_info_parts = []
        for i, chunk in enumerate(all_chunks[:15]):  # Limit to 15 chunks
            chunk_preview = chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content
            chunks_info_parts.append(
                f"CHUNK {i+1} (ID: {chunk.chunk_id}):\n{chunk_preview}"
            )
        chunks_info = "\n\n".join(chunks_info_parts)

        # Extract chunk IDs if they are dicts (from some dataset formats)
        clean_expected_ids = []
        for item in expected_chunk_ids:
            if isinstance(item, dict):
                clean_expected_ids.append(item.get('chunk_id', str(item)))
            else:
                clean_expected_ids.append(str(item))

        prompt = CHUNK_ATTRIBUTION_PROMPT.format(
            question=question,
            generated_answer=generated_answer,
            num_chunks=len(all_chunks),
            chunks_info=chunks_info,
            expected_chunk_ids=", ".join(clean_expected_ids)
        )

        result = self._llm_judge(prompt, return_explanation=True)
        return result["score"], result["explanation"]

    def compute_cross_chunk_coherence(
        self,
        question: str,
        generated_answer: str,
        num_chunks: int
    ) -> Tuple[float, str]:
        """
        Use LLM-as-judge to evaluate cross-chunk coherence.

        Checks if the LLM synthesized information across multiple
        chunks logically and coherently.

        Args:
            question: The question asked
            generated_answer: The LLM's answer
            num_chunks: Number of chunks provided to the LLM

        Returns:
            (score: 0-1, explanation: str)
        """
        prompt = CROSS_CHUNK_COHERENCE_PROMPT.format(
            question=question,
            generated_answer=generated_answer,
            num_chunks=num_chunks
        )

        result = self._llm_judge(prompt, return_explanation=True)
        return result["score"], result["explanation"]

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
        avg_conciseness = sum(r.conciseness_score for r in results) / len(results)

        # Compute recall/precision averages
        avg_recall_at_k = sum(r.recall_at_k for r in results) / len(results)
        avg_precision_at_k = sum(r.precision_at_k for r in results) / len(results)

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
            avg_recall_at_k=avg_recall_at_k,
            avg_precision_at_k=avg_precision_at_k,
            avg_faithfulness=avg_faithfulness,
            avg_relevance=avg_relevance,
            avg_conciseness=avg_conciseness,
            by_type=by_type,
            by_difficulty=by_difficulty,
            results=results
        )