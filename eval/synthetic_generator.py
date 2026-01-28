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
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.chunker import Chunk


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
    source_chunk_id: str
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
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "QAPair":
        data['question_type'] = QuestionType(data['question_type'])
        data['difficulty'] = Difficulty(data['difficulty'])
        if 'tags' not in data:
            data['tags'] = []
        return cls(**data)


GENERATION_PROMPT = """Tu es un expert en création de jeux de données pour l'évaluation de systèmes RAG.

À partir du contenu de conversation Instagram suivant, génère exactement 3 paires question-réponse variées.

CONTENU DE LA CONVERSATION:
{content}

RÉSUMÉ:
{summary}

PARTICIPANTS: {participants}
PÉRIODE: {date_start} - {date_end}

RÈGLES:
1. Génère 3 questions de types différents:
   - 1 question FACTUELLE (réponse directement dans le texte)
   - 1 question de RÉSUMÉ (demandant une synthèse)
   - 1 question IMPLICITE (nécessitant une inférence légère)

2. Les réponses doivent être:
   - Basées UNIQUEMENT sur le contenu fourni
   - Concises mais complètes
   - En français

3. Les questions doivent être naturelles, comme si un utilisateur les posait.

FORMAT DE SORTIE (JSON strict):
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


class SyntheticDataGenerator:
    """Generate synthetic QA pairs from chunks for evaluation."""

    def __init__(self, config: Config = None):
        self.config = config or default_config

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
            ensure_diversity: If True, ensure variety in participants and dates
        """
        if len(chunks) <= n_samples:
            return chunks

        if not ensure_diversity:
            return random.sample(chunks, n_samples)

        # Filter for "rich" chunks (more than 500 characters)
        rich_chunks = [c for c in chunks if len(c.content) > 1000]
        if len(rich_chunks) < n_samples:
            rich_chunks = [c for c in chunks if len(c.content) > 500]
        
        target_pool = rich_chunks if len(rich_chunks) >= n_samples else chunks

        # Group by participant combination and year
        by_participants = {}
        for chunk in target_pool:
            key = tuple(sorted(chunk.participants))
            if key not in by_participants:
                by_participants[key] = []
            by_participants[key].append(chunk)

        # Sample evenly from each group
        sampled = []
        groups = list(by_participants.values())
        random.shuffle(groups)

        idx = 0
        while len(sampled) < n_samples and any(groups):
            group = groups[idx % len(groups)]
            if group:
                chunk = random.choice(group)
                sampled.append(chunk)
                group.remove(chunk)

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
            summary=chunk.narrative_summary or chunk.summary,
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

            # Parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            qa_data = json.loads(content)

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
                    source_chunk_id=chunk.chunk_id,
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
