"""
ToolBox for ReAct Agent.
Wraps RAG capabilities as callable tools for the agent.
"""
import re
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .retriever import Retriever, RetrievalContext
from .vector_store import VectorStore, SearchResult
from .embeddings import EmbeddingModel
from .logger import get_logger

logger = get_logger()


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    tool_name: str
    input_args: str


class ToolBox:
    """
    Collection of tools available to the ReAct agent.
    Each tool wraps existing RAG capabilities with full pipeline access.
    """

    def __init__(self, config: Config = None, retriever: Retriever = None, analytics=None):
        self.config = config or default_config
        self.retriever = retriever
        self.analytics = analytics
        self._analysis = None
        self._original_query = None
        self._last_context = None
        self._tools_registry = {
            "search_conversations": self.search_conversations,
            "get_contact_stats": self.get_contact_stats,
            "get_participants": self.get_participants,
            "get_todays_date": self.get_todays_date,
        }

    def set_analysis(self, analysis):
        """Inject QueryAnalyzer results so tools can use them."""
        self._analysis = analysis

    def set_original_query(self, query: str):
        """Store original user query for smart fallback."""
        self._original_query = query

    def get_sources(self) -> list:
        """Extract sources from the last retrieval context."""
        if not self._last_context or not self._last_context.results:
            return []
        sources = []
        for r in self._last_context.results:
            sources.append({
                "rank": r.rank,
                "chunk_id": r.chunk.chunk_id,
                "file": r.chunk.file_source,
                "participants": r.chunk.participants,
                "date_start": r.chunk.date_start[:10],
                "date_end": r.chunk.date_end[:10],
                "score": round(r.final_score, 2),
                "expanded": r.is_expanded,
                "preview": (r.chunk.narrative_summary or r.chunk.summary or r.chunk.content[:200])[:200]
            })
        return sources

    def get_summary_sources(self) -> list:
        """Extract summary sources from the last retrieval context."""
        if not self._last_context:
            return []
        if not self._last_context.used_summary_fallback or not self._last_context.summary_results:
            return []
        summary_sources = []
        for sr in self._last_context.summary_results:
            summary = sr.summary
            summary_sources.append({
                "type": "summary",
                "level": sr.level,
                "summary_id": summary.summary_id,
                "participants": summary.participants,
                "period": getattr(summary, 'period', None) or f"{summary.date_start[:10]} - {summary.date_end[:10]}",
                "score": round(sr.score, 2),
                "preview": summary.summary[:200]
            })
        return summary_sources

    def get_last_context(self):
        """Return the last retrieval context (for chat.py to access confidence, etc.)."""
        return self._last_context

    def get_tools_description(self) -> str:
        """Returns description of available tools for the agent prompt."""
        return """1. search_conversations(query: str): Recherche sémantique dans l'historique des discussions. Utilise le pipeline complet (reranking, filtres, fallback). Renvoie les passages les plus pertinents.
2. get_contact_stats(contact_name: str): Statistiques détaillées pour un contact: nombre de messages, conversations, période d'activité.
3. get_participants(): Liste tous les participants avec leurs statistiques (messages, conversations).
4. get_todays_date(): Renvoie la date d'aujourd'hui au format YYYY-MM-DD."""

    def get_tool_names(self) -> List[str]:
        """Returns list of tool names."""
        return list(self._tools_registry.keys())

    def execute(self, tool_name: str, tool_input: str) -> ToolResult:
        """
        Execute a tool by name with the given input.
        """
        tool_name = tool_name.strip().lower()

        if tool_name not in self._tools_registry:
            return ToolResult(
                success=False,
                output=f"Erreur: Outil '{tool_name}' inconnu. Outils disponibles: {', '.join(self.get_tool_names())}",
                tool_name=tool_name,
                input_args=tool_input
            )

        try:
            tool_func = self._tools_registry[tool_name]
            output = tool_func(tool_input)
            return ToolResult(
                success=True,
                output=output,
                tool_name=tool_name,
                input_args=tool_input
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Erreur lors de l'exécution de {tool_name}: {str(e)}",
                tool_name=tool_name,
                input_args=tool_input
            )

    def search_conversations(self, query: str) -> str:
        """
        Recherche sémantique avec pipeline complet (reranking, filtres, fallback).
        """
        if not self.retriever:
            return "Erreur: Retriever non initialisé."

        query = query.strip().strip('"\'')

        # Paramètres issus de l'analyse si disponible
        a = self._analysis
        top_k = a.top_k if a else 5
        use_reranking = a.use_reranking if a else True
        expand_context = a.expand_context if a else True
        date_start = a.date_start if a else None
        date_end = a.date_end if a else None

        # Appel au pipeline complet
        context = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            use_reranking=use_reranking,
            use_hybrid=True,
            expand_context=expand_context,
            date_start=date_start,
            date_end=date_end,
        )

        # Smart Fallback: si la requête réécrite donne de mauvais résultats
        if (context.low_confidence or not context.has_results) and self._original_query and query != self._original_query:
            logger.info(f"⚠️ Agent smart fallback: score={context.max_confidence_score:.2f}, trying original query")
            fallback = self.retriever.retrieve(
                query=self._original_query,
                top_k=top_k,
                use_reranking=use_reranking,
                use_hybrid=True,
                expand_context=expand_context,
                date_start=date_start,
                date_end=date_end,
            )
            if fallback.max_confidence_score > context.max_confidence_score:
                context = fallback

        # Stocker le contexte pour extraction des sources
        self._last_context = context

        if not context.has_results:
            return f"Aucun résultat trouvé pour: '{query}'"

        # Formater les résultats pour l'agent
        results = []
        for r in context.results:
            chunk = r.chunk
            content_preview = chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content

            result_str = (
                f"[Score: {r.final_score:.2f}] "
                f"Participants: {', '.join(chunk.participants)} | "
                f"Date: {chunk.date_start[:10]} à {chunk.date_end[:10]}\n"
                f"{content_preview}"
            )
            results.append(result_str)

        confidence = "haute" if not context.low_confidence else "basse"
        return (
            f"Trouvé {len(context.results)} résultats pour '{query}' (confiance: {confidence}):\n\n"
            + "\n---\n".join(results)
        )

    def get_contact_stats(self, contact_name: str) -> str:
        """
        Statistiques détaillées pour un contact via le module analytics.
        """
        if not self.analytics:
            return "Erreur: Module analytics non initialisé."

        contact_name = contact_name.strip().strip('"\'')

        count = self.analytics.count_messages(participant=contact_name)

        if count == 0:
            return f"Aucun message trouvé avec '{contact_name}'."

        # Récupérer les stats détaillées
        stats = self.analytics.get_participant_stats()

        # Chercher le contact (correspondance partielle insensible à la casse)
        matched_stats = None
        matched_name = contact_name
        for name, info in stats.items():
            if contact_name.lower() in name.lower():
                matched_stats = info
                matched_name = name
                break

        if matched_stats:
            return (
                f"Statistiques pour '{matched_name}':\n"
                f"- Nombre de messages: {matched_stats['message_count']}\n"
                f"- Nombre de conversations: {matched_stats['conversations']}\n"
                f"- Période: {matched_stats.get('date_start', 'N/A')} à {matched_stats.get('date_end', 'N/A')}"
            )

        return (
            f"Statistiques pour '{contact_name}':\n"
            f"- Nombre de messages: environ {count}"
        )

    def get_participants(self, _: str = None) -> str:
        """
        Liste tous les participants avec leurs statistiques.
        """
        if not self.analytics:
            return "Erreur: Module analytics non initialisé."

        stats = self.analytics.get_participant_stats()

        if not stats:
            return "Aucun participant trouvé dans les conversations."

        lines = [f"**{len(stats)} participants trouvés:**\n"]
        for participant, info in list(stats.items())[:20]:
            lines.append(
                f"• {participant}: {info['message_count']} messages, "
                f"{info['conversations']} conversations"
            )

        if len(stats) > 20:
            lines.append(f"\n... et {len(stats) - 20} autres participants.")

        return "\n".join(lines)

    def get_todays_date(self, _: str = None) -> str:
        """Returns today's date."""
        now = datetime.now()
        return (
            f"Date actuelle: {now.strftime('%A %d %B %Y')} "
            f"(ISO: {now.strftime('%Y-%m-%d')})"
        )
