"""
Validation and evaluation of chunk enrichment quality.

This module provides comprehensive validation of enrichment outputs including:
- Questions hypothéitiques: answerability, relevance, coverage
- Entity extraction: precision, recall, completeness
- Emotion & social dynamics: coherence, appropriate classification
- Narrative summary: length, content accuracy
- Temporal context & speaker intents: validity checks
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple, Set
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.config import Config, default_config
from rag_pipeline.llm_provider import create_provider

# Optional ROUGE scoring for summary validation
try:
    from rouge_score import rouge_scorer
    HAS_ROUGE = True
except ImportError:
    HAS_ROUGE = False


class EnrichmentFieldType(Enum):
    """Types of enrichment fields for categorized validation."""
    NARRATIVE_SUMMARY = "narrative_summary"
    QUESTIONS = "questions"
    SPEAKER_INTENTS = "speaker_intents"
    TEMPORAL_CONTEXT = "temporal_context"
    ENTITIES = "entities"
    EMOTIONS = "emotions"
    INTERACTION_PATTERN = "interaction_pattern"
    INITIATIVE = "initiative"
    EMOTIONAL_SHIFT = "emotional_shift"
    OPEN_LOOPS = "open_loops"


@dataclass
class FieldValidationResult:
    """Validation result for a single enrichment field."""
    field_type: EnrichmentFieldType
    field_value: Any
    is_valid: bool
    score: float = 0.0  # 0-1, where 1 is perfect
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "field_type": self.field_type.value,
            "is_valid": self.is_valid,
            "score": round(self.score, 3),
            "issues": self.issues,
            "warnings": self.warnings,
            "metadata": self.metadata
        }


@dataclass
class ChunkEnrichmentValidationReport:
    """Complete validation report for a single enriched chunk."""
    chunk_id: str
    conversation_id: str
    content_preview: str = ""

    # Field-level results
    field_results: Dict[str, FieldValidationResult] = field(default_factory=dict)

    # Overall metrics
    overall_validity: bool = True
    overall_score: float = 0.0  # Weighted average of field scores
    completeness: float = 0.0  # % of enrichment fields that are non-empty
    critical_issues: int = 0
    warnings_count: int = 0

    # Summary
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "conversation_id": self.conversation_id,
            "overall_validity": self.overall_validity,
            "overall_score": round(self.overall_score, 3),
            "completeness": round(self.completeness, 3),
            "critical_issues": self.critical_issues,
            "warnings": self.warnings_count,
            "field_results": {k: v.to_dict() for k, v in self.field_results.items()},
            "summary": self.summary
        }


@dataclass
class EnrichmentBenchmarkReport:
    """Aggregated validation report for multiple chunks."""
    total_chunks: int
    valid_chunks: int = 0
    avg_overall_score: float = 0.0
    avg_completeness: float = 0.0
    total_critical_issues: int = 0
    total_warnings: int = 0

    # Per-field statistics
    field_scores: Dict[str, float] = field(default_factory=dict)
    field_validity_rates: Dict[str, float] = field(default_factory=dict)

    # Issue distribution
    issue_frequency: Dict[str, int] = field(default_factory=dict)

    # Chunk-level reports
    chunk_reports: List[ChunkEnrichmentValidationReport] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_chunks": self.total_chunks,
            "valid_chunks": self.valid_chunks,
            "validity_rate": round(self.valid_chunks / self.total_chunks if self.total_chunks > 0 else 0, 3),
            "avg_overall_score": round(self.avg_overall_score, 3),
            "avg_completeness": round(self.avg_completeness, 3),
            "total_critical_issues": self.total_critical_issues,
            "total_warnings": self.total_warnings,
            "field_scores": {k: round(v, 3) for k, v in self.field_scores.items()},
            "field_validity_rates": {k: round(v, 3) for k, v in self.field_validity_rates.items()},
            "issue_frequency": self.issue_frequency
        }


class EnrichmentValidator:
    """Validates enrichment quality across all fields."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.rouge_scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True) if HAS_ROUGE else None

    @staticmethod
    def calculate_rouge_l(reference: str, candidate: str) -> float:
        """
        Calculate ROUGE-L score between two texts.
        ROUGE-L measures Longest Common Subsequence (LCS) similarity.

        Args:
            reference: Ground truth text
            candidate: Generated/predicted text

        Returns:
            ROUGE-L f-measure score (0.0-1.0), or None if ROUGE not available
        """
        if not HAS_ROUGE:
            return None

        if not reference or not candidate:
            return 0.0

        try:
            scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
            scores = scorer.score(reference, candidate)
            return scores['rougeL'].fmeasure
        except Exception:
            return None

    @staticmethod
    def calculate_word_overlap(reference: str, candidate: str) -> float:
        """
        Fallback metric: Simple word overlap when ROUGE not available.
        Calculates Jaccard similarity of word sets.

        Returns:
            Overlap score (0.0-1.0)
        """
        if not reference or not candidate:
            return 0.0

        ref_words = set(reference.lower().split())
        cand_words = set(candidate.lower().split())

        intersection = len(ref_words & cand_words)
        union = len(ref_words | cand_words)

        return intersection / union if union > 0 else 0.0

    def validate_chunk(self, chunk: Chunk) -> ChunkEnrichmentValidationReport:
        """Validate all enrichment fields in a chunk.

        Returns a detailed validation report with per-field scores and issues.
        """
        report = ChunkEnrichmentValidationReport(
            chunk_id=chunk.chunk_id,
            conversation_id=chunk.conversation_id,
            content_preview=chunk.content[:200] + "..." if chunk.content else ""
        )

        # Validate each enrichment field
        field_validators = {
            EnrichmentFieldType.NARRATIVE_SUMMARY: self._validate_narrative_summary,
            EnrichmentFieldType.QUESTIONS: self._validate_questions,
            EnrichmentFieldType.SPEAKER_INTENTS: self._validate_speaker_intents,
            EnrichmentFieldType.TEMPORAL_CONTEXT: self._validate_temporal_context,
            EnrichmentFieldType.ENTITIES: self._validate_entities,
            EnrichmentFieldType.EMOTIONS: self._validate_emotions,
            EnrichmentFieldType.INTERACTION_PATTERN: self._validate_interaction_pattern,
            EnrichmentFieldType.INITIATIVE: self._validate_initiative,
            EnrichmentFieldType.EMOTIONAL_SHIFT: self._validate_emotional_shift,
            EnrichmentFieldType.OPEN_LOOPS: self._validate_open_loops,
        }

        for field_type, validator in field_validators.items():
            field_value = getattr(chunk, field_type.value, None)
            result = validator(field_value, chunk)
            report.field_results[field_type.value] = result

        # Calculate overall metrics
        self._calculate_overall_metrics(report)

        return report

    def _validate_narrative_summary(
        self, summary: Optional[str], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate narrative summary field.

        If chunk has a reference_summary, uses ROUGE-L to compare.
        Otherwise validates based on format and length.
        """
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.NARRATIVE_SUMMARY,
            field_value=summary,
            is_valid=True,
            score=1.0
        )

        # Check presence
        if not summary or len(summary.strip()) == 0:
            result.is_valid = False
            result.score = 0.0
            result.issues.append("Summary is empty")
            return result

        # Check length (should be concise, ideally 1 sentence)
        word_count = len(summary.split())
        if word_count > 30:
            result.warnings.append(
                f"Summary is quite long ({word_count} words), should be max ~25 words"
            )
            result.score = max(0.7, result.score)

        if word_count < 5:
            result.warnings.append(f"Summary is very short ({word_count} words)")
            result.score = max(0.8, result.score)

        # ROUGE-L comparison if reference summary available
        rouge_score = None
        if hasattr(chunk, 'reference_summary') and chunk.reference_summary:
            rouge_score = self.calculate_rouge_l(chunk.reference_summary, summary)
            if rouge_score is not None:
                result.metadata["rouge_l"] = round(rouge_score, 3)
                if rouge_score < 0.3:
                    result.warnings.append(
                        f"Low ROUGE-L vs reference ({rouge_score:.2%}), may differ significantly"
                    )
                    result.score = min(result.score, 0.7)
                elif rouge_score < 0.5:
                    result.warnings.append(
                        f"Moderate ROUGE-L vs reference ({rouge_score:.2%})"
                    )
                    result.score = min(result.score, 0.85)

        result.metadata.update({
            "word_count": word_count,
            "sentence_count": len([s for s in summary.split(".") if s.strip()])
        })

        return result

    def _validate_questions(
        self, questions: Optional[List[str]], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate hypothetical questions field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.QUESTIONS,
            field_value=questions or [],
            is_valid=True,
            score=1.0
        )

        # Check presence
        if not questions:
            result.warnings.append("No hypothetical questions generated")
            result.score = 0.5
            return result

        # Validate it's a list
        if not isinstance(questions, list):
            result.is_valid = False
            result.issues.append(f"Questions should be list, got {type(questions)}")
            result.score = 0.0
            return result

        # Check number of questions
        if len(questions) < 1:
            result.warnings.append("Only 0 questions - should have at least 1")
            result.score = 0.3
        elif len(questions) > 5:
            result.warnings.append(f"Many questions ({len(questions)}), consider reducing to 3-5")
            result.score = max(0.8, result.score)

        # Check individual question quality
        invalid_questions = []
        short_questions = []
        long_questions = []

        for q in questions:
            if not isinstance(q, str):
                invalid_questions.append(str(q))
            elif len(q.split()) < 3:
                short_questions.append(q)
            elif len(q.split()) > 30:
                long_questions.append(q)

        if invalid_questions:
            result.issues.append(
                f"Non-string questions found: {len(invalid_questions)}"
            )
            result.score = max(0.5, result.score)

        if short_questions:
            result.warnings.append(
                f"Short questions ({len(short_questions)}): might be too vague"
            )
            result.score = max(0.8, result.score)

        if long_questions:
            result.warnings.append(
                f"Long questions ({len(long_questions)}): might be complex"
            )
            result.score = max(0.8, result.score)

        result.metadata = {
            "question_count": len(questions),
            "avg_question_length": sum(len(q.split()) for q in questions if isinstance(q, str)) // len(questions) if questions else 0,
            "question_list": questions[:3] if len(questions) <= 3 else questions[:3] + ["..."]
        }

        return result

    def _validate_speaker_intents(
        self, intents: Optional[Dict[str, str]], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate speaker intents field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.SPEAKER_INTENTS,
            field_value=intents or {},
            is_valid=True,
            score=1.0
        )

        # Check presence
        if not intents:
            result.warnings.append("No speaker intents identified")
            result.score = 0.5
            return result

        # Validate it's a dict
        if not isinstance(intents, dict):
            result.is_valid = False
            result.issues.append(f"Intents should be dict, got {type(intents)}")
            result.score = 0.0
            return result

        # Check alignment with chunk participants
        if chunk.participants:
            identified_speakers = set(intents.keys())
            chunk_speakers = set(chunk.participants)
            missing_speakers = chunk_speakers - identified_speakers
            extra_speakers = identified_speakers - chunk_speakers

            if missing_speakers:
                result.warnings.append(
                    f"Missing intents for participants: {missing_speakers}"
                )
                result.score = max(0.7, result.score)

            if extra_speakers:
                result.warnings.append(
                    f"Intents for non-participants: {extra_speakers}"
                )
                result.score = max(0.8, result.score)

        # Check individual intent quality
        invalid_intents = [
            speaker for speaker, intent in intents.items()
            if not isinstance(intent, str)
        ]
        short_intents = [
            speaker for speaker, intent in intents.items()
            if isinstance(intent, str) and len(intent.split()) < 3
        ]
        long_intents = [
            speaker for speaker, intent in intents.items()
            if isinstance(intent, str) and len(intent.split()) > 15
        ]

        if invalid_intents:
            result.issues.append(
                f"Non-string intents found for speakers: {invalid_intents}"
            )
            result.score = max(0.5, result.score)

        if short_intents:
            result.warnings.append(
                f"Very short intents for {short_intents} - might be vague"
            )
            result.score = max(0.8, result.score)

        if long_intents:
            result.warnings.append(
                f"Long intents for {long_intents} - should be one sentence max"
            )
            result.score = max(0.8, result.score)

        result.metadata = {
            "speaker_count": len(intents),
            "speakers": list(intents.keys())[:5]
        }

        return result

    def _validate_temporal_context(
        self, temporal: Optional[str], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate temporal context field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.TEMPORAL_CONTEXT,
            field_value=temporal,
            is_valid=True,
            score=1.0
        )

        if not temporal or len(temporal.strip()) == 0:
            result.warnings.append("Temporal context is empty")
            result.score = 0.3
            return result

        # Check format
        if not isinstance(temporal, str):
            result.is_valid = False
            result.issues.append(f"Temporal context should be string, got {type(temporal)}")
            result.score = 0.0
            return result

        word_count = len(temporal.split())
        if word_count < 2:
            result.warnings.append("Temporal context is too short to be meaningful")
            result.score = 0.5
        elif word_count > 20:
            result.warnings.append("Temporal context is verbose, should be concise")
            result.score = 0.8

        result.metadata = {"word_count": word_count}
        return result

    def _validate_entities(
        self, entities: Optional[Dict[str, List[str]]], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate entity extraction field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.ENTITIES,
            field_value=entities or {},
            is_valid=True,
            score=1.0
        )

        if not entities:
            result.warnings.append("No entities extracted")
            result.score = 0.5
            return result

        if not isinstance(entities, dict):
            result.is_valid = False
            result.issues.append(f"Entities should be dict, got {type(entities)}")
            result.score = 0.0
            return result

        # Check required keys
        required_keys = {"locations", "people", "media", "events"}
        found_keys = set(entities.keys())
        missing_keys = required_keys - found_keys

        if missing_keys:
            result.warnings.append(f"Missing entity categories: {missing_keys}")
            result.score = max(0.7, result.score)

        # Validate each category
        total_entities = 0
        invalid_categories = []

        for category, values in entities.items():
            if not isinstance(values, list):
                invalid_categories.append((category, type(values).__name__))
                result.score = max(0.5, result.score)
            else:
                # Ensure all values are strings
                invalid_values = [
                    v for v in values if not isinstance(v, str)
                ]
                if invalid_values:
                    result.warnings.append(
                        f"Non-string values in {category}: {len(invalid_values)}"
                    )
                    result.score = max(0.8, result.score)
                total_entities += len([v for v in values if isinstance(v, str)])

        if invalid_categories:
            result.issues.append(
                f"Invalid category types: {invalid_categories}"
            )

        result.metadata = {
            "total_entities": total_entities,
            "categories": {k: len(v) if isinstance(v, list) else 0 for k, v in entities.items()},
            "populated_categories": sum(
                1 for v in entities.values()
                if isinstance(v, list) and len(v) > 0
            )
        }

        return result

    def _validate_emotions(
        self, emotions: Optional[Dict[str, Any]], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate emotion/ambiance field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.EMOTIONS,
            field_value=emotions or {},
            is_valid=True,
            score=1.0
        )

        if not emotions:
            result.warnings.append("No emotion analysis performed")
            result.score = 0.3
            return result

        if not isinstance(emotions, dict):
            result.is_valid = False
            result.issues.append(f"Emotions should be dict, got {type(emotions)}")
            result.score = 0.0
            return result

        # Required fields
        required = {"dominant", "tone", "tension_level"}
        found = set(emotions.keys())
        missing = required - found

        if missing:
            result.warnings.append(f"Missing emotion fields: {missing}")
            result.score = max(0.6, result.score)

        # Validate tension_level
        if "tension_level" in emotions:
            tension = emotions["tension_level"]
            valid_tensions = {"low", "medium", "high"}
            if tension not in valid_tensions:
                result.warnings.append(
                    f"Invalid tension_level '{tension}', should be one of {valid_tensions}"
                )
                result.score = max(0.7, result.score)

        result.metadata = {
            "fields_found": list(found),
            "dominant_emotion": emotions.get("dominant"),
            "tension_level": emotions.get("tension_level")
        }

        return result

    def _validate_interaction_pattern(
        self, pattern: Optional[str], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate interaction pattern field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.INTERACTION_PATTERN,
            field_value=pattern,
            is_valid=True,
            score=1.0
        )

        if not pattern or len(str(pattern).strip()) == 0:
            result.warnings.append("No interaction pattern identified (null is acceptable)")
            result.score = 0.6
            return result

        valid_patterns = {
            "planification", "planning", "débat", "debate",
            "soutien", "support", "conflit", "conflict",
            "récit", "story-telling", "catch-up", "information",
            "consultation", "question-réponse", "q&a"
        }

        pattern_lower = str(pattern).lower()
        if pattern_lower not in valid_patterns:
            result.warnings.append(
                f"Pattern '{pattern}' not in expected list. "
                f"Expected one of: {sorted(valid_patterns)}"
            )
            result.score = 0.7

        result.metadata = {"pattern": pattern}
        return result

    def _validate_initiative(
        self, initiative: Optional[str], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate conversation initiative field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.INITIATIVE,
            field_value=initiative,
            is_valid=True,
            score=1.0
        )

        if not initiative or len(str(initiative).strip()) == 0:
            result.warnings.append("No initiative identified")
            result.score = 0.5
            return result

        # Should reference participants or use "Balanced"
        initiative_str = str(initiative).lower()
        if "balanced" not in initiative_str:
            # Should mention a participant
            if chunk.participants:
                mentioned = any(
                    p.lower() in initiative_str
                    for p in chunk.participants
                )
                if not mentioned:
                    result.warnings.append(
                        f"Initiative '{initiative}' doesn't mention any participants: {chunk.participants}"
                    )
                    result.score = 0.7

        result.metadata = {"initiative": initiative}
        return result

    def _validate_emotional_shift(
        self, shift: Optional[str], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate emotional shift field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.EMOTIONAL_SHIFT,
            field_value=shift,
            is_valid=True,
            score=1.0
        )

        if not shift or len(str(shift).strip()) == 0:
            result.warnings.append("No emotional shift identified (Stable is acceptable)")
            result.score = 0.6
            return result

        # Should describe a transition or "Stable"
        shift_str = str(shift)
        if "→" in shift_str or "->" in shift_str or "stable" in shift_str.lower():
            # Good format
            pass
        else:
            result.warnings.append(
                f"Shift '{shift}' should use format 'State1 → State2' or be 'Stable'"
            )
            result.score = 0.7

        result.metadata = {"shift": shift}
        return result

    def _validate_open_loops(
        self, loops: Optional[List[str]], chunk: Chunk
    ) -> FieldValidationResult:
        """Validate open loops/unresolved topics field."""
        result = FieldValidationResult(
            field_type=EnrichmentFieldType.OPEN_LOOPS,
            field_value=loops or [],
            is_valid=True,
            score=1.0
        )

        if not loops:
            result.warnings.append("No open loops identified (empty list is acceptable)")
            result.score = 0.7
            return result

        if not isinstance(loops, list):
            result.is_valid = False
            result.issues.append(f"Open loops should be list, got {type(loops)}")
            result.score = 0.0
            return result

        # Check individual loops
        invalid_loops = [l for l in loops if not isinstance(l, str)]
        if invalid_loops:
            result.issues.append(f"Non-string items in open_loops: {len(invalid_loops)}")
            result.score = 0.5

        short_loops = [l for l in loops if isinstance(l, str) and len(l.split()) < 3]
        if short_loops:
            result.warnings.append(
                f"Very short open loops ({len(short_loops)}), might be too vague"
            )
            result.score = max(0.8, result.score)

        result.metadata = {
            "loop_count": len([l for l in loops if isinstance(l, str)]),
            "loops": loops[:3] if loops else []
        }

        return result

    def _calculate_overall_metrics(self, report: ChunkEnrichmentValidationReport):
        """Calculate overall metrics from field results."""
        if not report.field_results:
            report.overall_score = 0.0
            report.completeness = 0.0
            return

        # Calculate weighted average score
        scores = [r.score for r in report.field_results.values()]
        report.overall_score = sum(scores) / len(scores) if scores else 0.0

        # Calculate completeness (% of non-empty fields)
        non_empty = sum(
            1 for r in report.field_results.values()
            if r.field_value is not None and (
                isinstance(r.field_value, (str, list, dict))
                and (r.field_value if isinstance(r.field_value, (str, list)) else len(r.field_value) > 0)
            )
        )
        total_fields = len(report.field_results)
        report.completeness = non_empty / total_fields if total_fields > 0 else 0.0

        # Count issues
        report.critical_issues = sum(len(r.issues) for r in report.field_results.values())
        report.warnings_count = sum(len(r.warnings) for r in report.field_results.values())

        # Overall validity: must have no critical issues and score >= 0.5
        report.overall_validity = (
            report.critical_issues == 0
            and report.overall_score >= 0.5
        )

        # Generate summary
        if report.overall_validity:
            report.summary = f"Valid enrichment (score: {report.overall_score:.2f}, completeness: {report.completeness:.2%})"
        else:
            issues_str = f"{report.critical_issues} critical issues" if report.critical_issues > 0 else ""
            score_str = f"low score ({report.overall_score:.2f})" if report.overall_score < 0.5 else ""
            parts = [p for p in [issues_str, score_str] if p]
            report.summary = f"Invalid enrichment: {', '.join(parts)}"

    def validate_chunks(
        self, 
        chunks: List[Chunk], 
        verbose: bool = False,
        judge_model: str = None,
        provider_type: str = "ollama"
    ) -> EnrichmentBenchmarkReport:
        """Validate multiple chunks and generate aggregated report."""
        report = EnrichmentBenchmarkReport(total_chunks=len(chunks))

        chunk_scores = {field.value: [] for field in EnrichmentFieldType}

        for i, chunk in enumerate(chunks):
            if verbose:
                print(f"[{i+1}/{len(chunks)}] Validating {chunk.chunk_id}...", end="", flush=True)

            if judge_model:
                chunk_report = self.validate_chunk_with_llm(chunk, judge_model, provider_type)
            else:
                chunk_report = self.validate_chunk(chunk)
            
            report.chunk_reports.append(chunk_report)
            
            if verbose:
                print(f" Score: {chunk_report.overall_score:.2f}")
            if chunk_report.overall_validity:
                report.valid_chunks += 1

            for field_name, field_result in chunk_report.field_results.items():
                chunk_scores[field_name].append(field_result.score)

                # Track issues
                for issue in field_result.issues:
                    key = f"{field_name}: {issue[:50]}"
                    report.issue_frequency[key] = report.issue_frequency.get(key, 0) + 1

            if verbose:
                print(f"✓ {chunk.chunk_id}: {chunk_report.summary}")

        # Calculate aggregated field statistics
        for field_name, scores in chunk_scores.items():
            if scores:
                report.field_scores[field_name] = sum(scores) / len(scores)
                valid_count = sum(1 for s in scores if s >= 0.7)
                report.field_validity_rates[field_name] = valid_count / len(scores)

        # Calculate overall average
        all_scores = [r.overall_score for r in report.chunk_reports]
        report.avg_overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        all_completeness = [r.completeness for r in report.chunk_reports]
        report.avg_completeness = sum(all_completeness) / len(all_completeness) if all_completeness else 0.0

        report.total_critical_issues = sum(r.critical_issues for r in report.chunk_reports)
        report.total_warnings = sum(r.warnings_count for r in report.chunk_reports)

        return report

    def validate_chunk_with_llm(
        self, 
        chunk: Chunk, 
        judge_model: str, 
        provider_type: str = "ollama"
    ) -> ChunkEnrichmentValidationReport:
        """
        Validate enrichment quality using an LLM judge.
        
        This method sends the chunk content and its enrichment to an LLM
        to evaluate the quality, accuracy, and relevance of the enriched metadata.
        """
        # 1. Run Heuristic Validation first (Base Layer)
        # This catches schema errors, missing fields, invalid enums, etc.
        heuristic_report = self.validate_chunk(chunk)
        
        # If heuristics completely failed (critical issues), maybe skip LLM to save cost?
        # For now, let's proceed but weight the heuristic failure heavily.
        
        try:
            provider = create_provider(self.config, judge_model, provider_type)
        except Exception as e:
            print(f"⚠️ Failed to create judge provider: {e}")
            return heuristic_report
        
        # ... (rest of prompt construction stays similar) ...
        
        # Prepare the context for the judge
        enrichment_data = {
            "narrative_summary": chunk.narrative_summary,
            "hypothetical_questions": chunk.hypothetical_questions,
            "speaker_intents": chunk.speaker_intents,
            "temporal_context": chunk.temporal_context,
            "entities": chunk.entities,
            "emotions": chunk.emotions,
            "social_dynamics": {
                "interaction_pattern": chunk.interaction_pattern,
                "initiative": chunk.initiative,
                "emotional_shift": chunk.emotional_shift,
                "open_loops": chunk.open_loops
            }
        }
        
        prompt = f"""You are an expert AI judge evaluating the quality of metadata extraction from conversation chunks.
        
TASK:
Evaluate how well the extracted metadata (Enrichment) reflects the original Conversation Chunk.

ORIGINAL CONVERSATION CHUNK:
---
{chunk.content}
---

EXTRACTED ENRICHMENT METADATA:
---
{json.dumps(enrichment_data, indent=2, ensure_ascii=False)}
---

EVALUATION CRITERIA:
1. Accuracy: Does the summary and metadata factually reflect the conversation?
2. Completeness: Are all key entities, emotions, and intents captured?
3. Relevance: Are the hypothetical questions relevant and answerable from the text?
4. Hallucination: Are there any invented details not present in the text?

OUTPUT FORMAT:
Return a JSON object with evaluation for each major category. format:
{{
    "narrative_summary": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "questions": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "speaker_intents": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "entities": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "emotions": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "temporal_context": {{ "score": 0.0-1.0, "reason": "concise explanation" }},
    "social_dynamics": {{ "score": 0.0-1.0, "reason": "concise explanation" }}
}}

Ensure strictly valid JSON output. Do not include markdown formatting ```json ... ```.
"""
        
        try:
            response = provider.generate([{"role": "user", "content": prompt}], temperature=0.1)
            
            # Clean response
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            eval_json = json.loads(cleaned_response)
                
            # Update heuristic report with LLM scores
            # We treat the LLM score as the "Quality Score" and Heuristic as "Schema Score"
            # Final Score = (LLM Score * 0.7) + (Heuristic Score * 0.3) ? 
            # Or simplified: Use LLM score but penalize if heuristic failed.
            
            def update_field(field_type, json_key):
                if json_key not in eval_json: return
                
                data = eval_json[json_key]
                llm_score = float(data.get("score", 0.0))
                reason = data.get("reason", "")
                
                # Get existing heuristic result
                if field_type.value in heuristic_report.field_results:
                    res = heuristic_report.field_results[field_type.value]
                    
                    # Combine scores: LLM is dominant for quality, but heuristic penalties apply
                    # If heuristic found critical issue (score=0), keep it low.
                    # If heuristic was perfect (1.0), let LLM decide quality.
                    
                    if res.is_valid: # Heuristics passed
                        res.score = llm_score
                    else: # Heuristics failed (schema error)
                        res.score = min(res.score, llm_score)
                    
                    res.metadata["judge_score"] = llm_score
                    res.metadata["judge_reason"] = reason
                    
                    if llm_score < 0.7:
                         res.warnings.append(f"Judge Warning: {reason}")
                    if llm_score < 0.4:
                         res.issues.append(f"Judge Critical: {reason}")

            # Map fields
            update_field(EnrichmentFieldType.NARRATIVE_SUMMARY, "narrative_summary")
            update_field(EnrichmentFieldType.QUESTIONS, "questions")
            update_field(EnrichmentFieldType.SPEAKER_INTENTS, "speaker_intents")
            update_field(EnrichmentFieldType.ENTITIES, "entities")
            update_field(EnrichmentFieldType.EMOTIONS, "emotions")
            update_field(EnrichmentFieldType.TEMPORAL_CONTEXT, "temporal_context")
            
            # Social dynamics fields
            social_data = eval_json.get("social_dynamics", {})
            if social_data:
                social_score = float(social_data.get("score", 0.0))
                social_reason = social_data.get("reason", "")
                
                for field_type in [EnrichmentFieldType.INTERACTION_PATTERN, EnrichmentFieldType.INITIATIVE, EnrichmentFieldType.EMOTIONAL_SHIFT, EnrichmentFieldType.OPEN_LOOPS]:
                    if field_type.value in heuristic_report.field_results:
                        res = heuristic_report.field_results[field_type.value]
                        if res.is_valid:
                            res.score = social_score
                        else:
                            res.score = min(res.score, social_score)
                        
                        res.metadata["judge_score"] = social_score
                        res.metadata["judge_reason"] = social_reason
                        if social_score < 0.7: res.warnings.append(f"Judge: {social_reason}")

            # Recalculate overall metrics for the report
            self._calculate_overall_metrics(heuristic_report)
            return heuristic_report

        except Exception as e:
            print(f"⚠️ LLM Judge failed for chunk {chunk.chunk_id}: {e}")
            # Fallback to heuristic validation
            return heuristic_report

def print_validation_report(report: ChunkEnrichmentValidationReport):
    """Pretty print a chunk validation report."""
    print(f"\n{'='*60}")
    print(f"ENRICHMENT VALIDATION: {report.chunk_id}")
    print(f"{'='*60}")
    print(f"Conversation: {report.conversation_id}")
    print(f"Overall Score: {report.overall_score:.2%} | Completeness: {report.completeness:.2%}")
    print(f"Status: {'✓ VALID' if report.overall_validity else '✗ INVALID'}")
    print(f"Issues: {report.critical_issues} | Warnings: {report.warnings_count}")
    print()

    for field_name, field_result in report.field_results.items():
        status = "✓" if field_result.is_valid else "✗"
        print(f"{status} {field_name.upper()} ({field_result.score:.2%})")
        if field_result.issues:
            for issue in field_result.issues:
                print(f"  ❌ {issue}")
        if field_result.warnings:
            for warning in field_result.warnings:
                print(f"  ⚠️  {warning}")
        if field_result.metadata:
            print(f"  📊 {field_result.metadata}")
        print()


def print_benchmark_report(report: EnrichmentBenchmarkReport):
    """Pretty print aggregated benchmark report."""
    print(f"\n{'='*60}")
    print(f"ENRICHMENT BENCHMARK REPORT")
    print(f"{'='*60}")
    print(f"Chunks Evaluated: {report.total_chunks}")
    print(f"Valid Chunks: {report.valid_chunks} ({report.valid_chunks/report.total_chunks:.1%})")
    print(f"Average Score: {report.avg_overall_score:.2%}")
    print(f"Average Completeness: {report.avg_completeness:.2%}")
    print(f"Total Critical Issues: {report.total_critical_issues}")
    print(f"Total Warnings: {report.total_warnings}")
    print()

    print("FIELD PERFORMANCE:")
    print(f"{'Field':<25} {'Score':<10} {'Validity Rate':<15}")
    print("-" * 50)
    for field in sorted(report.field_scores.keys()):
        score = report.field_scores.get(field, 0.0)
        rate = report.field_validity_rates.get(field, 0.0)
        print(f"{field:<25} {score:>6.2%}     {rate:>6.1%}")
    print()

    if report.issue_frequency:
        print("TOP ISSUES:")
        sorted_issues = sorted(
            report.issue_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for issue, count in sorted_issues[:10]:
            print(f"  - {issue}: {count} occurrences")


if __name__ == "__main__":
    print("Enrichment Validation Module")
    print("Use: validator = EnrichmentValidator(); report = validator.validate_chunk(chunk)")
