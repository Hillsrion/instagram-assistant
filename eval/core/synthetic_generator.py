"""
Synthetic data generation for RAG evaluation.
Generates QA pairs from chunks using LLM.
"""

import json
import random
import requests
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
from enum import Enum

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.chunker import Chunk
from rag_pipeline.json_utils import repair_and_load_json


class QuestionType(str, Enum):
    FACTUAL = "factual"      # Direct fact extraction
    SUMMARY = "summary"      # Summarization questions
    IMPLICIT = "implicit"    # Inference/implicit info
    TEMPORAL = "temporal"    # Date/time related


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class QAPair:
    """A question-answer pair for evaluation."""
    question: str
    expected_answer: str
    source_chunk_ids: List[str]
    question_type: QuestionType
    difficulty: Difficulty
    metadata: dict = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> dict:
        d = asdict(self)
        d['question_type'] = self.question_type.value
        d['difficulty'] = self.difficulty.value
        # Write both keys for backward compatibility
        d['source_chunk_id'] = self.source_chunk_ids[0] if self.source_chunk_ids else ""
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "QAPair":
        data['question_type'] = QuestionType(data['question_type'])
        data['difficulty'] = Difficulty(data['difficulty'])
        if 'tags' not in data:
            data['tags'] = []
        # Backward compat: wrap singular source_chunk_id into list
        if 'source_chunk_ids' not in data and 'source_chunk_id' in data:
            data['source_chunk_ids'] = [data.pop('source_chunk_id')]
        elif 'source_chunk_id' in data and 'source_chunk_ids' in data:
            data.pop('source_chunk_id')
        return cls(**data)


@dataclass
class MultiChunkQAPair(QAPair):
    """QA pair requiring multiple chunks for evaluation.

    Used for testing LLM's ability to synthesize information
    from multiple conversation chunks, reflecting real-world usage
    where 5-25 chunks are typically provided as context.
    """
    intent: str = "broad_summary"  # "specific_fact", "complex_reasoning", "broad_summary"
    expected_chunk_attribution: List[str] = None  # Chunks that should be cited in answer
    cross_chunk_required: bool = True  # Whether synthesis across chunks is needed

    def __post_init__(self):
        super().__post_init__()
        if self.expected_chunk_attribution is None:
            self.expected_chunk_attribution = []

    def to_dict(self) -> dict:
        d = super().to_dict()
        d['intent'] = self.intent
        d['expected_chunk_attribution'] = self.expected_chunk_attribution
        d['cross_chunk_required'] = self.cross_chunk_required
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MultiChunkQAPair":
        # Convert enums first
        data['question_type'] = QuestionType(data['question_type'])
        data['difficulty'] = Difficulty(data['difficulty'])
        if 'tags' not in data:
            data['tags'] = []
        # Backward compat for source_chunk_ids
        if 'source_chunk_ids' not in data and 'source_chunk_id' in data:
            data['source_chunk_ids'] = [data.pop('source_chunk_id')]
        elif 'source_chunk_id' in data and 'source_chunk_ids' in data:
            data.pop('source_chunk_id')
        # Set defaults for multichunk fields
        if 'intent' not in data:
            data['intent'] = "broad_summary"
        if 'expected_chunk_attribution' not in data:
            data['expected_chunk_attribution'] = []
        if 'cross_chunk_required' not in data:
            data['cross_chunk_required'] = True
        return cls(**data)


GENERATION_PROMPT = """Tu es un expert dans la création de jeux de données pour l'évaluation de systèmes RAG.

À partir du contenu de la conversation Instagram suivante, génère exactement 3 paires questions-réponses variées.

CONTENU DE LA CONVERSATION :
{content}

RÉSUMÉ :
{summary}

PARTICIPANTS : {participants}
PÉRIODE : {date_start} - {date_end}

RÈGLES :
1. Génère 3 questions de types différents :
   - 1 question FACTUELLE (réponse directement dans le texte)
   - 1 question de SYNTHÈSE (demandant un résumé)
   - 1 question IMPLICITE (nécessitant une légère inférence)

2. Les réponses doivent être :
   - Basées UNIQUEMENT sur le contenu fourni
   - Concises mais complètes
   - En Français

3. Les questions doivent être naturelles, comme si un utilisateur les posait.

FORMAT DE SORTIE (JSON Strict) :
[
  {{
    "question": "...",
    "answer": "...",
    "type": "factual|summary|implicit",
    "difficulty": "easy|medium|hard"
  }},
  ...
]

Réponds UNIQUEMENT avec le JSON, sans explication."""


MULTICHUNK_GENERATION_PROMPT = """Tu es un expert dans la création de jeux de données d'évaluation RAG multi-chunks.

Tu vas recevoir {num_chunks} extraits (chunks) de conversation. Génère une question qui NÉCESSITE la lecture de plusieurs extraits pour y répondre correctement.

EXTRAITS :
{chunks_content}

RÈGLES :
1. La question DOIT impérativement nécessiter des informations provenant d'au moins {min_chunks} extraits différents.
2. Types à générer (basé sur l'intention "{intent}") :
   - "specific_fact" : Question de recoupement nécessitant 3-5 extraits (ex: "Comment l'opinion de X sur Y a-t-elle évolué ?")
   - "complex_reasoning" : Raisonnement en plusieurs étapes nécessitant 5-10 extraits (ex: "Quels étaient les thèmes principaux des discussions sur Z ?")
   - "broad_summary" : Synthèse complète nécessitant 10-15 extraits (ex: "Résume toutes les discussions sur le sujet X")

3. La réponse attendue doit :
   - Synthétiser les informations des extraits fournis
   - Être factuelle et basée UNIQUEMENT sur le contenu fourni
   - Être en Français

4. Indique quels extraits contiennent les informations critiques pour la réponse.

FORMAT DE SORTIE (JSON Strict) :
{{
  "question": "Une question nécessitant une synthèse multi-extraits...",
  "expected_answer": "Réponse synthétisant les informations de plusieurs extraits...",
  "source_chunk_ids": ["chunk_1", "chunk_3", "chunk_7", ...],
  "expected_chunk_attribution": ["chunk_1", "chunk_3"],
  "cross_chunk_required": true,
  "intent": "{intent}",
  "difficulty": "easy|medium|hard"
}}

Réponds UNIQUEMENT avec le JSON, sans explication."""


class SyntheticDataGenerator:
    """Generate synthetic QA pairs from chunks for evaluation."""

    def __init__(self, config: Config = None):
        self.config = config or default_config

    def _get_length_bucket(self, chunk: Chunk) -> str:
        """Categorize chunk by content length."""
        length = len(chunk.content)
        if length < 800:
            return "short"
        elif length < 2000:
            return "medium"
        else:
            return "long"

    def sample_chunks(
        self,
        chunks: List[Chunk],
        n_samples: int = 20,
        ensure_diversity: bool = True
    ) -> List[Chunk]:
        """
        Sample chunks with diversity constraints.

        Args:
            chunks: All available chunks
            n_samples: Number of chunks to sample
            ensure_diversity: If True, ensure variety in participants AND lengths
        """
        if len(chunks) <= n_samples:
            return chunks

        if not ensure_diversity:
            return random.sample(chunks, n_samples)

        # Filter chunks with minimum content (at least 300 chars for meaningful QA)
        valid_chunks = [c for c in chunks if len(c.content) >= 300]
        if len(valid_chunks) < n_samples:
            valid_chunks = chunks

        # Group by participant combination
        by_participants = {}
        for chunk in valid_chunks:
            key = tuple(sorted(chunk.participants))
            if key not in by_participants:
                by_participants[key] = []
            by_participants[key].append(chunk)

        # Calculate target distribution for lengths (roughly equal)
        target_per_length = n_samples // 3
        length_counts = {"short": 0, "medium": 0, "long": 0}

        # Sample evenly from each participant group, balancing lengths
        sampled = []
        groups = list(by_participants.values())
        random.shuffle(groups)

        idx = 0
        max_iterations = n_samples * 10  # Prevent infinite loop
        iterations = 0

        while len(sampled) < n_samples and any(groups) and iterations < max_iterations:
            iterations += 1
            group = groups[idx % len(groups)]

            if group:
                # Try to pick a chunk that balances length distribution
                random.shuffle(group)
                selected = None

                for chunk in group:
                    bucket = self._get_length_bucket(chunk)
                    # Prefer under-represented length buckets
                    if length_counts[bucket] < target_per_length:
                        selected = chunk
                        break

                # If all buckets are full, just pick any
                if selected is None and group:
                    selected = group[0]

                if selected:
                    bucket = self._get_length_bucket(selected)
                    length_counts[bucket] += 1
                    sampled.append(selected)
                    group.remove(selected)

            # Remove empty groups
            groups = [g for g in groups if g]
            if not groups:
                break
            idx += 1

        return sampled

    def generate_qa_for_chunk(self, chunk: Chunk) -> List[QAPair]:
        """Generate QA pairs for a single chunk using LLM."""

        prompt = GENERATION_PROMPT.format(
            content=chunk.content[:3000],  # Truncate for context limit
            summary=chunk.narrative_summary or "Not available",
            participants=", ".join(chunk.participants),
            date_start=chunk.date_start[:10],
            date_end=chunk.date_end[:10]
        )

        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 1024,
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            content = response.json()["message"]["content"].strip()

            qa_data = repair_and_load_json(content)

            qa_pairs = []
            for item in qa_data:
                qtype = QuestionType.FACTUAL
                if item.get('type') == 'summary':
                    qtype = QuestionType.SUMMARY
                elif item.get('type') == 'implicit':
                    qtype = QuestionType.IMPLICIT
                elif item.get('type') == 'temporal':
                    qtype = QuestionType.TEMPORAL

                diff = Difficulty.MEDIUM
                if item.get('difficulty') == 'easy':
                    diff = Difficulty.EASY
                elif item.get('difficulty') == 'hard':
                    diff = Difficulty.HARD

                qa_pairs.append(QAPair(
                    question=item['question'],
                    expected_answer=item['answer'],
                    source_chunk_ids=[chunk.chunk_id],
                    question_type=qtype,
                    difficulty=diff,
                    metadata={
                        'participants': chunk.participants,
                        'date_range': f"{chunk.date_start[:10]} - {chunk.date_end[:10]}"
                    }
                ))

            return qa_pairs

        except Exception as e:
            print(f"Error generating QA for chunk {chunk.chunk_id}: {e}")
            return []

    def generate_dataset(
        self,
        chunks: List[Chunk],
        target_size: int = 50,
        progress_callback=None
    ) -> List[QAPair]:
        """
        Generate a complete evaluation dataset.

        Args:
            chunks: Available chunks
            target_size: Target number of QA pairs
            progress_callback: Function(current, total, message)
        """
        # Sample chunks (each generates ~3 QAs)
        n_chunks = max(10, target_size // 3)
        sampled_chunks = self.sample_chunks(chunks, n_chunks)

        all_qa_pairs = []

        for i, chunk in enumerate(sampled_chunks):
            if progress_callback:
                progress_callback(i + 1, len(sampled_chunks), f"Processing {chunk.chunk_id}")

            qa_pairs = self.generate_qa_for_chunk(chunk)
            all_qa_pairs.extend(qa_pairs)

            if len(all_qa_pairs) >= target_size:
                break

        # Trim to target size if needed
        if len(all_qa_pairs) > target_size:
            all_qa_pairs = random.sample(all_qa_pairs, target_size)

        return all_qa_pairs

    def save_dataset(self, qa_pairs: List[QAPair], path: Path = None):
        """Save QA dataset to JSON file in eval/ folder."""
        path = path or (Path(__file__).parent / "eval_dataset.json")

        data = {
            'metadata': {
                'total_pairs': len(qa_pairs),
                'by_type': {},
                'by_difficulty': {}
            },
            'qa_pairs': [qa.to_dict() for qa in qa_pairs]
        }

        # Count by type
        for qa in qa_pairs:
            t = qa.question_type.value
            data['metadata']['by_type'][t] = data['metadata']['by_type'].get(t, 0) + 1

            d = qa.difficulty.value
            data['metadata']['by_difficulty'][d] = data['metadata']['by_difficulty'].get(d, 0) + 1

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(qa_pairs)} QA pairs to {path}")

    def load_dataset(self, path: Path = None) -> List[QAPair]:
        """Load QA dataset from JSON file in eval/ folder."""
        path = path or (Path(__file__).parent / "eval_dataset.json")

        if not path.exists():
            return []

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return [QAPair.from_dict(qa) for qa in data['qa_pairs']]

    def _group_chunks_by_similarity(
        self,
        chunks: List[Chunk],
        max_groups: int = 10
    ) -> List[List[Chunk]]:
        """
        Group chunks by similarity (participant, timeframe, etc.).

        Args:
            chunks: All available chunks
            max_groups: Maximum number of groups to create

        Returns:
            List of chunk groups
        """
        # Group by participant combination first
        by_participants = {}
        for chunk in chunks:
            key = tuple(sorted(chunk.participants))
            if key not in by_participants:
                by_participants[key] = []
            by_participants[key].append(chunk)

        # For each participant group, further group by time proximity
        groups = []
        for participant_key, participant_chunks in by_participants.items():
            # Sort by date
            sorted_chunks = sorted(participant_chunks, key=lambda c: c.date_start)

            # Create temporal groups (chunks within ~30 days of each other)
            current_group = []
            for chunk in sorted_chunks:
                if not current_group:
                    current_group.append(chunk)
                else:
                    # Simple heuristic: if chunks are from same conversation file, group them
                    if chunk.file_source == current_group[0].file_source:
                        current_group.append(chunk)
                    else:
                        if len(current_group) >= 3:  # Only keep groups with 3+ chunks
                            groups.append(current_group)
                        current_group = [chunk]

            # Add final group
            if len(current_group) >= 3:
                groups.append(current_group)

        # Sort groups by size (prefer larger groups) and limit
        groups.sort(key=len, reverse=True)
        return groups[:max_groups]

    def generate_multichunk_qa_pairs(
        self,
        chunks: List[Chunk],
        num_pairs: int = 30,
        chunk_counts: List[int] = None,
        progress_callback=None
    ) -> List[MultiChunkQAPair]:
        """
        Generate QA pairs requiring multiple chunks.

        Args:
            chunks: All available chunks
            num_pairs: Target number of QA pairs to generate
            chunk_counts: List of chunk counts to use (default: [5, 10, 15])
            progress_callback: Function(current, total, message)

        Returns:
            List of MultiChunkQAPair instances
        """
        if chunk_counts is None:
            chunk_counts = [5, 10, 15]

        # Group chunks by similarity
        chunk_groups = self._group_chunks_by_similarity(chunks)

        if not chunk_groups:
            print("No suitable chunk groups found for multi-chunk generation")
            return []

        print(f"Found {len(chunk_groups)} chunk groups for multi-chunk QA generation")

        all_qa_pairs = []
        pairs_per_count = num_pairs // len(chunk_counts)

        # Intent mapping based on chunk count
        intent_map = {
            5: "specific_fact",
            10: "complex_reasoning",
            15: "broad_summary"
        }

        for chunk_count in chunk_counts:
            intent = intent_map.get(chunk_count, "broad_summary")
            min_chunks = max(2, chunk_count // 2)  # At least half the chunks should be needed

            for i in range(pairs_per_count):
                if progress_callback:
                    current = len(all_qa_pairs) + 1
                    progress_callback(current, num_pairs, f"Generating {intent} question (need {chunk_count} chunks)")

                # Select a group with enough chunks
                suitable_groups = [g for g in chunk_groups if len(g) >= chunk_count]
                if not suitable_groups:
                    print(f"Not enough chunks in groups for count={chunk_count}, skipping")
                    continue

                group = random.choice(suitable_groups)
                selected_chunks = random.sample(group, min(chunk_count, len(group)))

                # Format chunks for LLM
                chunks_content = []
                for idx, chunk in enumerate(selected_chunks):
                    chunk_preview = chunk.content[:800]  # Truncate for context
                    chunks_content.append(
                        f"=== CHUNK {idx+1} (ID: {chunk.chunk_id}) ===\n"
                        f"Participants: {', '.join(chunk.participants)}\n"
                        f"Period: {chunk.date_start[:10]} to {chunk.date_end[:10]}\n"
                        f"---\n{chunk_preview}\n"
                    )

                chunks_str = "\n\n".join(chunks_content)

                # Generate QA pair with LLM
                prompt = MULTICHUNK_GENERATION_PROMPT.format(
                    num_chunks=len(selected_chunks),
                    chunks_content=chunks_str,
                    min_chunks=min_chunks,
                    intent=intent
                )

                try:
                    payload = {
                        "model": self.config.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {
                            "temperature": 0.4,
                            "top_p": 0.9,
                            "num_predict": 2048,
                        }
                    }

                    response = requests.post(
                        f"{self.config.ollama_url}/api/chat",
                        json=payload,
                        timeout=120
                    )
                    response.raise_for_status()

                    content = response.json()["message"]["content"].strip()

                    qa_data = repair_and_load_json(content)

                    # Create MultiChunkQAPair
                    qa_pair = MultiChunkQAPair(
                        question=qa_data["question"],
                        expected_answer=qa_data["expected_answer"],
                        source_chunk_ids=[c.chunk_id for c in selected_chunks],
                        question_type=QuestionType.SUMMARY,  # Most multi-chunk are summary-type
                        difficulty=Difficulty(qa_data.get("difficulty", "medium")),
                        intent=intent,
                        expected_chunk_attribution=qa_data.get("expected_chunk_attribution", []),
                        cross_chunk_required=qa_data.get("cross_chunk_required", True),
                        metadata={
                            'num_chunks': len(selected_chunks),
                            'participants': list(set(p for c in selected_chunks for p in c.participants))
                        }
                    )

                    all_qa_pairs.append(qa_pair)

                except Exception as e:
                    print(f"Error generating multi-chunk QA pair: {e}")
                    continue

                if len(all_qa_pairs) >= num_pairs:
                    break

            if len(all_qa_pairs) >= num_pairs:
                break

        return all_qa_pairs[:num_pairs]

    def save_multichunk_dataset(self, qa_pairs: List[MultiChunkQAPair], path: Path = None):
        """Save multi-chunk QA dataset to JSON file in eval/ folder."""
        path = path or (Path(__file__).parent / "eval_dataset_multichunk.json")

        data = {
            'metadata': {
                'total_pairs': len(qa_pairs),
                'by_intent': {},
                'by_chunk_count': {},
                'avg_chunks_per_question': sum(len(qa.source_chunk_ids) for qa in qa_pairs) / len(qa_pairs) if qa_pairs else 0
            },
            'qa_pairs': [qa.to_dict() for qa in qa_pairs]
        }

        # Count by intent
        for qa in qa_pairs:
            intent = qa.intent
            data['metadata']['by_intent'][intent] = data['metadata']['by_intent'].get(intent, 0) + 1

            num_chunks = len(qa.source_chunk_ids)
            data['metadata']['by_chunk_count'][num_chunks] = data['metadata']['by_chunk_count'].get(num_chunks, 0) + 1

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(qa_pairs)} multi-chunk QA pairs to {path}")

    def load_multichunk_dataset(self, path: Path = None) -> List[MultiChunkQAPair]:
        """Load multi-chunk QA dataset from JSON file in eval/ folder."""
        path = path or (Path(__file__).parent / "eval_dataset_multichunk.json")

        if not path.exists():
            return []

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return [MultiChunkQAPair.from_dict(qa) for qa in data['qa_pairs']]


class QuestionFilter:
    """Filter QA pairs by various criteria."""

    @staticmethod
    def filter_by_type(qa_pairs: List[QAPair], question_types: List[str]) -> List[QAPair]:
        """Filter by question type(s)."""
        types = [QuestionType(t) for t in question_types]
        return [qa for qa in qa_pairs if qa.question_type in types]

    @staticmethod
    def filter_by_difficulty(qa_pairs: List[QAPair], difficulties: List[str]) -> List[QAPair]:
        """Filter by difficulty level(s)."""
        diffs = [Difficulty(d) for d in difficulties]
        return [qa for qa in qa_pairs if qa.difficulty in diffs]

    @staticmethod
    def filter_by_participant(qa_pairs: List[QAPair], participant: str) -> List[QAPair]:
        """Filter by participant name (case-insensitive, partial match)."""
        participant_lower = participant.lower()
        return [
            qa for qa in qa_pairs
            if qa.metadata and any(
                participant_lower in p.lower()
                for p in qa.metadata.get('participants', [])
            )
        ]

    @staticmethod
    def filter_by_date_range(qa_pairs: List[QAPair], start_date: str, end_date: str) -> List[QAPair]:
        """Filter by date range (ISO format: YYYY-MM-DD)."""
        return [
            qa for qa in qa_pairs
            if qa.metadata and start_date <= qa.metadata.get('date_range', '').split(' - ')[0] <= end_date
        ]

    @staticmethod
    def filter_by_tags(qa_pairs: List[QAPair], tags: List[str]) -> List[QAPair]:
        """Filter by tags (all specified tags must be present)."""
        tag_set = set(tags)
        return [qa for qa in qa_pairs if tag_set.issubset(set(qa.tags or []))]

    @staticmethod
    def apply_filters(
        qa_pairs: List[QAPair],
        question_types: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None,
        participant: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[QAPair]:
        """Apply multiple filters to QA pairs."""
        result = qa_pairs

        if question_types:
            result = QuestionFilter.filter_by_type(result, question_types)

        if difficulties:
            result = QuestionFilter.filter_by_difficulty(result, difficulties)

        if participant:
            result = QuestionFilter.filter_by_participant(result, participant)

        if start_date and end_date:
            result = QuestionFilter.filter_by_date_range(result, start_date, end_date)

        if tags:
            result = QuestionFilter.filter_by_tags(result, tags)

        return result