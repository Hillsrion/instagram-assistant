"""
Embeddings module for RAG Pipeline.
Uses sentence-transformers with bge-m3 model (multilingual).
"""
import numpy as np
import time
from typing import List, Optional, Union, Dict, Any
from pathlib import Path

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.indexing.embedding_log import EmbeddingLogger
from rag_pipeline.core.models import Chunk
from rag_pipeline.indexing.chunk_utils import repeat_with_budget


class EmbeddingModel:
    """Generates high-quality embeddings with bge-m3."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = None
        self._device = None
        self.logger = EmbeddingLogger()
    
    def _load_model(self):
        """Loads the embedding model (lazy loading)."""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            import torch
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        # Determine device
        if self.config.use_gpu and torch.cuda.is_available():
            self._device = "cuda"
        elif self.config.use_gpu and torch.backends.mps.is_available():
            self._device = "mps"  # Apple Silicon
        else:
            self._device = "cpu"
        
        print(f"📦 Loading embedding model {self.config.embedding_model} (local cache)...")
        print(f"🖥️  Device: {self._device}")
        
        try:
            # Try to load from local cache first to avoid 307 pings
            self.model = SentenceTransformer(
                self.config.embedding_model,
                device=self._device,
                local_files_only=True
            )
        except Exception:
            # Fallback to standard loading if not in cache (first time)
            print(f"ℹ️  Model not found in local cache, downloading from Hugging Face...")
            self.model = SentenceTransformer(
                self.config.embedding_model,
                device=self._device,
                local_files_only=False
            )
        
        print("✅ Model loaded")
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Encodes a list of texts into embeddings.
        
        Args:
            texts: List of texts to encode
            show_progress: Show progress bar
            
        Returns:
            Numpy matrix of shape (n_texts, embedding_dim)
        """
        self._load_model()
        
        start_time = time.time()
        batch_size = 32
        
        embeddings = self.model.encode(
            texts,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # Normalization for cosine similarity
            batch_size=batch_size,
        )
        
        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_batch(
            batch_size=batch_size,
            total_texts=len(texts),
            model_name=self.config.embedding_model,
            device=str(self._device),
            duration_ms=duration_ms
        )
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encodes a single text."""
        return self.encode([text], show_progress=False)[0]
    
    @property
    def dimension(self) -> int:
        """Returns the embedding dimension."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()


class OllamaEmbeddings:
    """
    Alternative: uses Ollama for embeddings (nomic-embed-text).
    Slower but does not require sentence-transformers.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model_name = "nomic-embed-text"
        self.logger = EmbeddingLogger()
    
    def _call_ollama(self, text: str) -> List[float]:
        """Calls Ollama API to get an embedding."""
        import requests
        
        response = requests.post(
            f"{self.config.ollama_url}/api/embeddings",
            json={
                "model": self.model_name,
                "prompt": text
            }
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """Encodes a list of texts via Ollama."""
        embeddings = []
        
        start_time = time.time()
        iterator = texts
        if show_progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(texts, desc="Embedding")
            except ImportError:
                pass
        
        for text in iterator:
            emb = self._call_ollama(text)
            embeddings.append(emb)
        
        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_batch(
            batch_size=1,  # Ollama is usually sequential in this implementation
            total_texts=len(texts),
            model_name=self.model_name,
            device="ollama_api",
            duration_ms=duration_ms
        )
        
        return np.array(embeddings, dtype=np.float32)
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encodes a single text."""
        return np.array(self._call_ollama(text), dtype=np.float32)
    
    @property
    def dimension(self) -> int:
        """Returns the embedding dimension (768 for nomic-embed-text)."""
        return 768


def get_compact_content(chunk: Chunk) -> str:
    """
    Returns a compact version of content for embeddings and LLM analysis.
    Removes timestamps and shortens names.
    Handles name collisions (Lucie D. / Lucie M.) and special characters.
    """
    # 1. Parse lines first to find all unique authors
    parsed_lines = [] # List of (author|None, content_text)
    authors = set()
    
    for line in chunk.content.split('\n'):
        # Only process lines that look like messages with our timestamp format
        if line.startswith('[') and '] ' in line:
            try:
                # [2024-...] Author: Message
                timestamp_end = line.find('] ')
                rest = line[timestamp_end + 2:]
                if ': ' in rest:
                     # Split on first colon only
                    author, msg = rest.split(': ', 1)
                    parsed_lines.append((author, msg))
                    authors.add(author)
                else:
                    parsed_lines.append((None, line))
            except Exception:
                parsed_lines.append((None, line))
        else:
            parsed_lines.append((None, line))

    # 2. Build Disambiguated Name Map
    # Step A: Count First Names
    first_name_counts = {}
    for author in authors:
        parts = author.split() if author else []
        first = parts[0] if parts else author
        first_name_counts[first] = first_name_counts.get(first, 0) + 1
        
    # Step B: Generate Initial Candidates
    temp_map = {}
    for author in authors:
        parts = author.split() if author else []
        first = parts[0] if parts else author
        
        if first_name_counts.get(first, 0) <= 1:
            temp_map[author] = first
        else:
            # Collision detected -> Try First + Last Initial
            if len(parts) > 1:
                # "Lucie Dupont" -> "Lucie D."
                # Use last part as surname (simple heuristic)
                last_initial = parts[-1][0]
                temp_map[author] = f"{first} {last_initial}."
            else:
                # "Lucie" -> "Lucie" (if unique string, handled above, else keep as is)
                temp_map[author] = first

    # Step C: Resolve Candidate Collisions (e.g. Lucie D. vs Lucie D.)
    final_map = {}
    # Group by candidate name
    candidate_groups = {}
    for original, candidate in temp_map.items():
        if candidate not in candidate_groups:
            candidate_groups[candidate] = []
        candidate_groups[candidate].append(original)
    
    # Assign final names
    for candidate, original_list in candidate_groups.items():
        if len(original_list) == 1:
            final_map[original_list[0]] = candidate
        else:
            # Still collision? Revert to full name for these specific users
            for original in original_list:
                final_map[original] = original

    # 3. Reconstruct Content
    output_lines = []
    for author, content in parsed_lines:
        if author:
            short_name = final_map.get(author, author)
            output_lines.append(f"{short_name}: {content}")
        else:
            # Non-message lines (continuations, system messages)
            output_lines.append(content)
    
    return "\n".join(output_lines)

def get_chunk_embedding_text(chunk: Chunk) -> str:
    """
    Texte pondéré pour embeddings (dense + BM25 hybride).
    Hiérarchie : voir docs/EMBEDDING_STRATEGY.md
    """

    parts = []

    # 1. Questions hypothétiques — signal dominant, aligne query ↔ document
    #    Budget normalisé pour éviter la domination par volume
    QUESTION_BUDGET = default_config.max_questions
    if chunk.hypothetical_questions:
        weighted_questions = repeat_with_budget(
            chunk.hypothetical_questions,
            QUESTION_BUDGET
        )
        for q in weighted_questions:
            parts.append(f"[QUESTION] {q}")

    # 2. Résumé narratif — condensé sémantique dense (1 phrase)
    #    Aide le dense retriever sur les requêtes larges/vagues
    if chunk.narrative_summary:
        parts.append(f"[SUMMARY] {chunk.narrative_summary}")

    # 3. Entités — ancres factuelles (x1, BM25 couvre les termes exacts via le contenu brut)
    if chunk.entities and isinstance(chunk.entities, dict):
        for category, items in chunk.entities.items():
            if isinstance(items, list):
                for item in items:
                    if item:
                        parts.append(f"[ENTITY:{category}] {item}")
            elif isinstance(items, dict):
                # Handle nested dicts (sometimes LLM groups by subcategory)
                for subcat, subitems in items.items():
                    if isinstance(subitems, list):
                        for item in subitems:
                            parts.append(f"[ENTITY:{category}:{subcat}] {item}")
                    elif isinstance(subitems, str):
                        parts.append(f"[ENTITY:{category}:{subcat}] {subitems}")
            elif isinstance(items, str):
                parts.append(f"[ENTITY:{category}] {items}")

    # 4. Contexte temporel — temps relationnel ("pendant les vacances")
    if chunk.temporal_context:
        parts.append(f"[TIME] {chunk.temporal_context}")

    # 5. Intentions — pont entre factuel et social
    if chunk.speaker_intents:
        for participant, intent in chunk.speaker_intents.items():
            parts.append(f"[INTENT] {participant}: {intent}")

    # 6. Dynamique structurelle — initiative, boucles ouvertes
    if chunk.initiative:
        parts.append(f"[INITIATIVE] {chunk.initiative}")

    if chunk.open_loops:
        for loop in chunk.open_loops:
            parts.append(f"[OPEN_LOOP] {loop}")

    # 7. Émotionnel / social — signal faible mais ciblé
    if chunk.emotions:
        emo = []
        if chunk.emotions.get("dominant"):
            emo.append(chunk.emotions["dominant"])
        if chunk.emotions.get("tone"):
            emo.append(chunk.emotions["tone"])
        if chunk.emotions.get("tension_level"):
            emo.append(f"tension:{chunk.emotions['tension_level']}")
        if emo:
            parts.append(f"[EMOTION] {' | '.join(emo)}")

    if chunk.interaction_pattern:
        parts.append(f"[INTERACTION] {chunk.interaction_pattern}")

    if chunk.emotional_shift:
        parts.append(f"[EMOTIONAL_SHIFT] {chunk.emotional_shift}")

    # 8. Contenu brut — signal primaire pour BM25 (alpha=0.5), contexte reranker
    parts.append("[CONTENT]")
    parts.append(get_compact_content(chunk))

    return "\n".join(parts)

def get_summary_embedding_text(summary: Any) -> str:
    """Returns text to encode for vector search for summaries."""
    parts = []

    # Using duck typing or checking class name to avoid circular imports
    class_name = summary.__class__.__name__

    if class_name == 'ConversationSummary':
        # Participants
        parts.append(f"Conversation with {', '.join(summary.participants)}")
        # Period
        parts.append(f"Period: {summary.date_start[:10]} to {summary.date_end[:10]}")
        # Summary
        parts.append(f"Summary: {summary.summary}")
        # Topics
        if summary.main_topics:
            parts.append(f"Main topics: {', '.join(summary.main_topics)}")
        # Relationship dynamic
        if summary.relationship_dynamic:
            parts.append(f"Relationship type: {summary.relationship_dynamic}")
        # Events
        if summary.notable_events:
            parts.append(f"Notable events: {', '.join(summary.notable_events)}")
    
    elif class_name == 'PeriodSummary':
        # Participants and period
        parts.append(f"Conversation with {', '.join(summary.participants)} in {summary.period}")
        # Precise period
        parts.append(f"From {summary.date_start[:10]} to {summary.date_end[:10]}")
        # Summary
        parts.append(f"Summary: {summary.summary}")
        # Topics
        if summary.topics:
            parts.append(f"Topics discussed: {', '.join(summary.topics)}")
        # Mood
        if summary.mood:
            parts.append(f"Mood: {summary.mood}")

    return "\n".join(parts)