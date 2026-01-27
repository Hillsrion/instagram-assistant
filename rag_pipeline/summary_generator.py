"""
Générateur de résumés hiérarchiques via LLM.
Génère des ConversationSummary et PeriodSummary à partir des chunks enrichis.
"""
import json
import requests
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from .config import Config, default_config
from .chunker import Chunk
from .summary_models import ConversationSummary, PeriodSummary


CONVERSATION_SUMMARY_PROMPT = """Tu es un assistant qui résume des conversations Instagram.

Voici les résumés de tous les échanges avec {participants} :

{narrative_summaries}

Génère un JSON avec :
- "summary": Résumé global de la relation/conversation (2-3 phrases max)
- "main_topics": Liste de 3-5 sujets récurrents
- "relationship_dynamic": Type de relation (amis proches, collègues, famille, connaissance, relation amoureuse, etc.)
- "notable_events": Liste d'événements marquants mentionnés (max 5)

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après."""


PERIOD_SUMMARY_PROMPT = """Tu es un assistant qui résume des conversations Instagram.

Voici les échanges avec {participants} pendant {period} :

{narrative_summaries}

Génère un JSON avec :
- "summary": Résumé de cette période (1-2 phrases max)
- "topics": Liste de 2-3 sujets abordés
- "mood": Ambiance générale (léger, sérieux, tendu, joyeux, intime, amical, etc.)

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après."""


class SummaryGenerator:
    """Génère des résumés hiérarchiques à partir des chunks."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = self.config.llm_model
        self._chunks_by_conversation: Dict[str, List[Chunk]] = {}

    def _group_chunks_by_conversation(self, chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
        """Groupe les chunks par conversation_id."""
        grouped = defaultdict(list)
        for chunk in chunks:
            grouped[chunk.conversation_id].append(chunk)

        # Trier par date au sein de chaque conversation
        for conv_id in grouped:
            grouped[conv_id].sort(key=lambda c: c.date_start)

        return dict(grouped)

    def _group_chunks_by_period(self, chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
        """Groupe les chunks par mois (YYYY-MM)."""
        grouped = defaultdict(list)
        for chunk in chunks:
            # Extraire le mois depuis date_start
            period = chunk.date_start[:7]  # "YYYY-MM"
            grouped[period].append(chunk)

        return dict(grouped)

    def _call_llm(self, prompt: str) -> Optional[dict]:
        """Appelle le LLM et retourne le JSON parsé."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 1024,
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()["message"]["content"]
            return json.loads(result)
        except Exception as e:
            print(f"⚠️ Erreur LLM: {e}")
            return None

    def generate_conversation_summary(
        self,
        conversation_id: str,
        chunks: List[Chunk]
    ) -> Optional[ConversationSummary]:
        """Génère un résumé global pour une conversation."""
        if not chunks:
            return None

        # Collecter les narrative_summary de chaque chunk
        summaries = []
        for chunk in chunks:
            if chunk.narrative_summary:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.narrative_summary}")

        if not summaries:
            # Fallback sur les résumés statistiques
            for chunk in chunks:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.summary}")

        # Participants
        participants = chunks[0].participants if chunks else []
        participants_str = ", ".join(participants)

        # Limiter le nombre de résumés pour ne pas dépasser le context window
        # Prendre les plus récents si trop nombreux
        max_summaries = 50
        if len(summaries) > max_summaries:
            # Garder un échantillon représentatif
            step = len(summaries) // max_summaries
            summaries = summaries[::step][:max_summaries]

        prompt = CONVERSATION_SUMMARY_PROMPT.format(
            participants=participants_str,
            narrative_summaries="\n".join(summaries)
        )

        result = self._call_llm(prompt)
        if not result:
            return None

        # Calculer les statistiques
        total_messages = sum(c.message_count for c in chunks)
        date_start = min(c.date_start for c in chunks)
        date_end = max(c.date_end for c in chunks)
        chunk_ids = [c.chunk_id for c in chunks]

        return ConversationSummary(
            summary_id=f"{conversation_id}_summary",
            conversation_id=conversation_id,
            participants=participants,
            date_start=date_start,
            date_end=date_end,
            total_messages=total_messages,
            total_chunks=len(chunks),
            summary=result.get("summary", ""),
            main_topics=result.get("main_topics", []),
            relationship_dynamic=result.get("relationship_dynamic", ""),
            notable_events=result.get("notable_events", []),
            chunk_ids=chunk_ids
        )

    def generate_period_summary(
        self,
        conversation_id: str,
        period: str,
        chunks: List[Chunk]
    ) -> Optional[PeriodSummary]:
        """Génère un résumé pour une période (mois) d'une conversation."""
        if not chunks:
            return None

        # Collecter les narrative_summary
        summaries = []
        for chunk in chunks:
            if chunk.narrative_summary:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.narrative_summary}")

        if not summaries:
            for chunk in chunks:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.summary}")

        participants = chunks[0].participants if chunks else []
        participants_str = ", ".join(participants)

        # Formater la période pour l'affichage
        try:
            period_date = datetime.strptime(period, "%Y-%m")
            period_display = period_date.strftime("%B %Y")
        except ValueError:
            period_display = period

        prompt = PERIOD_SUMMARY_PROMPT.format(
            participants=participants_str,
            period=period_display,
            narrative_summaries="\n".join(summaries)
        )

        result = self._call_llm(prompt)
        if not result:
            return None

        message_count = sum(c.message_count for c in chunks)
        date_start = min(c.date_start for c in chunks)
        date_end = max(c.date_end for c in chunks)
        chunk_ids = [c.chunk_id for c in chunks]

        return PeriodSummary(
            summary_id=f"{conversation_id}_period_{period}",
            conversation_id=conversation_id,
            participants=participants,
            period=period,
            date_start=date_start,
            date_end=date_end,
            message_count=message_count,
            summary=result.get("summary", ""),
            topics=result.get("topics", []),
            mood=result.get("mood", ""),
            chunk_ids=chunk_ids
        )

    def generate_period_summaries(
        self,
        conversation_id: str,
        chunks: List[Chunk],
        progress_callback=None
    ) -> List[PeriodSummary]:
        """Génère des résumés par mois pour une conversation."""
        chunks_by_period = self._group_chunks_by_period(chunks)

        summaries = []
        periods = sorted(chunks_by_period.keys())

        for i, period in enumerate(periods):
            period_chunks = chunks_by_period[period]
            summary = self.generate_period_summary(conversation_id, period, period_chunks)
            if summary:
                summaries.append(summary)

            if progress_callback:
                progress_callback(i + 1, len(periods))

        return summaries

    def generate_all_summaries(
        self,
        chunks: List[Chunk],
        progress_callback=None,
        save_callback=None
    ) -> Tuple[List[ConversationSummary], List[PeriodSummary]]:
        """
        Génère tous les résumés (conversation + période) pour tous les chunks.

        Returns:
            (conversation_summaries, period_summaries)
        """
        chunks_by_conversation = self._group_chunks_by_conversation(chunks)

        conversation_summaries = []
        period_summaries = []

        conversations = list(chunks_by_conversation.keys())
        total_steps = len(conversations) * 2  # 1 pour conv summary, 1 pour period summaries
        current_step = 0

        for conv_id in conversations:
            conv_chunks = chunks_by_conversation[conv_id]

            # 1. Générer le résumé de conversation
            conv_summary = self.generate_conversation_summary(conv_id, conv_chunks)
            if conv_summary:
                conversation_summaries.append(conv_summary)

            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, f"Conv: {conv_id[:30]}")

            # 2. Générer les résumés par période
            period_sums = self.generate_period_summaries(conv_id, conv_chunks)
            period_summaries.extend(period_sums)

            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, f"Periods: {conv_id[:30]}")

            # Sauvegarde périodique
            if save_callback:
                save_callback(conversation_summaries, period_summaries)

        return conversation_summaries, period_summaries
