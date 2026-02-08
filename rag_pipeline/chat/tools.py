"""
ToolBox for ReAct Agent.
Wraps RAG capabilities as callable tools for the agent.
"""
import re
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.query.retriever import Retriever, RetrievalContext
from rag_pipeline.indexing.vector_store import VectorStore, SearchResult
from rag_pipeline.indexing.embeddings import EmbeddingModel
from rag_pipeline.core.logger import get_logger

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
            "explore_topic_timeline": self.explore_topic_timeline,
            "get_thread_context": self.get_thread_context,
            "check_entity_presence": self.check_entity_presence,
            "get_summaries_for_contact": self.get_summaries_for_contact,
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
        if not getattr(self._last_context, 'used_summary_fallback', False) or not getattr(self._last_context, 'summary_results', []):
            return []
        summary_sources = []
        for sr in self._last_context.summary_results:
            summary = sr.summary
            summary_sources.append({
                "type": "summary",
                "level": sr.level,
                "summary_id": getattr(summary, 'summary_id', 'N/A'),
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
        return """1. search_conversations(query: str, participant: str = None, date_range: str = None): Recherche sémantique. Paramètres optionnels pour forcer un participant ou une période (format "YYYY-MM-DD to YYYY-MM-DD").
2. get_contact_stats(contact_name: str): Statistiques (messages, conversations, dates) pour un contact précis.
3. get_participants(): Liste tous les participants connus avec leurs statistiques globales.
4. get_todays_date(): Date actuelle pour aider aux calculs temporels.
5. explore_topic_timeline(query: str): Chronologie détaillée d'un sujet avec volume mensuel et épisodes clés.
6. get_thread_context(chunk_id: str, window: int = 5): Récupère les messages entourant un extrait précis pour comprendre le flux de la conversation.
7. check_entity_presence(keyword: str, participant: str = None): Vérifie de manière stricte (mot-clé) la présence d'un terme. Très fiable pour confirmer ou infirmer une mention.
8. get_summaries_for_contact(contact: str, limit: int = 5): Récupère les résumés de haut niveau des dernières conversations avec ce contact."""

    def get_tool_names(self) -> List[str]:
        """Returns list of tool names."""
        return list(self._tools_registry.keys())

    def execute(self, tool_name: str, tool_input: str) -> ToolResult:
        """
        Execute a tool by name with the given input.
        Supports both simple strings and JSON-formatted multi-argument strings.
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
            # Try to parse input as JSON for multi-args support
            import json
            kwargs = {}
            if tool_input.strip().startswith('{'):
                try:
                    kwargs = json.loads(tool_input)
                except:
                    # Fallback to single string if JSON parsing fails
                    pass
            
            tool_func = self._tools_registry[tool_name]
            
            if kwargs:
                output = tool_func(**kwargs)
            else:
                output = tool_func(tool_input)
                
            return ToolResult(
                success=True,
                output=output,
                tool_name=tool_name,
                input_args=tool_input
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output=f"Erreur lors de l'exécution de {tool_name}: {str(e)}",
                tool_name=tool_name,
                input_args=tool_input
            )

    def search_conversations(self, query: str, participant: str = None, date_range: str = None) -> str:
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
        
        # Override analysis with forced parameters if provided
        date_start = a.date_start if a else None
        date_end = a.date_end if a else None
        participant_filter = participant or (a.participant_filter if hasattr(a, 'participant_filter') else None)

        if date_range:
            parts = date_range.lower().split(" to ")
            if len(parts) == 2:
                date_start = parts[0].strip()
                date_end = parts[1].strip()

        # Appel au pipeline complet
        context = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            use_reranking=use_reranking,
            use_hybrid=True,
            expand_context=expand_context,
            date_start=date_start,
            date_end=date_end,
            participant_filter=participant_filter
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
                participant_filter=participant_filter
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
                f"[ID: {chunk.chunk_id} | Score: {r.final_score:.2f}] "
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

    def explore_topic_timeline(self, query: str) -> str:
        """
        Analyse chronologique d'un sujet en croisant les résumés hiérarchiques et les chunks.
        Ajoute maintenant des statistiques de volume mensuel.
        """
        if not self.retriever:
            return "Erreur: Retriever non initialisé."

        query = query.strip().strip('"\'')
        logger.info(f"⏳ Exploring timeline for: '{query}'")

        # 1. Search in hierarchical summaries (Conversation and Period)
        summary_results = []
        if self.retriever.summary_store:
            summary_results = self.retriever.summary_store.search(
                query, level="all", top_k=5, min_score=0.3
            )

        # 2. Search in detailed chunks
        context = self.retriever.retrieve(
            query, top_k=15, use_reranking=True, expand_context=False
        )

        if not summary_results and not context.has_results:
            return f"Aucun épisode ou mention trouvé pour le sujet: '{query}'"

        timeline = [f"Chronologie pour '{query}':\n"]

        # 3. Monthly volume (via Analytics if possible, or sampling)
        if self.analytics:
            # We use a keyword search fallback for volume if it's a specific term
            # For simplicity, we report global monthly activity if the query is a participant
            stats = self.analytics.get_participant_stats()
            matched_participant = None
            for p in stats:
                if p.lower() in query.lower():
                    matched_participant = p
                    break
            
            if matched_participant:
                monthly = self.analytics.get_message_count_by_month(participant=matched_participant)
                if monthly:
                    timeline.append("**Volume d'activité mensuel (avec ce contact):**")
                    for m in monthly[-12:]: # Last 12 active months
                        timeline.append(f"- {m['month_name']} {m['year']}: {m['message_count']} messages")
                    timeline.append("")

        # 4. Format Summaries (Episodes)
        if summary_results:
            timeline.append("**Épisodes clés identifiés:**")
            for r in summary_results:
                s = r.summary
                period = getattr(s, 'period', f"{s.date_start[:10]} à {s.date_end[:10]}")
                line = f"- [{period}]: {s.summary[:200]}..."
                timeline.append(line)
            timeline.append("")

        # 5. Format detailed mentions
        if context.has_results:
            timeline.append("**Mentions détaillées chronologiques:**")
            for r in sorted(context.results, key=lambda x: x.chunk.date_start):
                date = r.chunk.date_start[:10]
                text = r.chunk.narrative_summary or r.chunk.content[:100]
                timeline.append(f"- {date}: {text[:120]}...")

        return "\n".join(timeline)

    def get_thread_context(self, chunk_id: str, window: int = 5) -> str:
        """
        Récupère les messages entourant un extrait précis.
        """
        if not self.retriever or not self.retriever.metadata_store:
            return "Erreur: MetadataStore non disponible pour l'expansion de contexte."

        chunk_id = chunk_id.strip().strip('"\'')
        logger.info(f"🧵 Expanding context for chunk: {chunk_id} (window={window})")

        # Get adjacent indices from metadata store
        adj_indices = self.retriever.metadata_store.get_adjacent_chunks(chunk_id, window=window)
        
        if not adj_indices:
            return f"Impossible de trouver le contexte pour l'ID: {chunk_id}"

        # Get chunks from vector store
        chunks = [self.retriever.vector_store.chunks[idx] for idx in sorted(adj_indices)]
        
        output = [f"Contexte étendu pour {chunk_id} (+/- {window} blocs):\n"]
        for c in chunks:
            marker = ">>> " if c.chunk_id == chunk_id else "    "
            output.append(f"{marker}[{c.date_start[11:16]}] {', '.join(c.participants)}:\n{c.content}\n")
            
        return "\n---\n".join(output)

    def check_entity_presence(self, keyword: str, participant: str = None) -> str:
        """
        Vérification stricte par mot-clé (BM25 ou Exact match).
        """
        if not self.retriever or not self.retriever.bm25_index:
            # Fallback to simple scan if BM25 is not ready
            return f"Vérification pour '{keyword}': Le moteur de recherche stricte n'est pas prêt."

        keyword = keyword.strip().strip('"\'')
        
        # We search specifically for the keyword
        # Use BM25 index directly
        results = self.retriever.bm25_index.search(keyword, top_k=50)
        
        if not results:
            return f"Confirmation: Le terme '{keyword}' n'apparaît nulle part dans les conversations."

        # Filter by participant if requested
        matches = []
        for idx, score in results:
            chunk = self.retriever.vector_store.chunks[idx]
            if participant:
                if not any(participant.lower() in p.lower() for p in chunk.participants):
                    continue
            
            # Verify exact presence in content (case insensitive)
            if keyword.lower() in chunk.content.lower():
                matches.append(chunk)

        if not matches:
            return f"Le terme '{keyword}' est absent (ou pas trouvé avec {participant if participant else 'ces critères'})."

        # Summarize findings
        dates = sorted(list(set(m.date_start[:10] for m in matches)))
        participants = list(set(p for m in matches for p in m.participants))
        
        return (
            f"Confirmation: '{keyword}' trouvé dans {len(matches)} segments.\n"
            f"- Dates: {', '.join(dates[:5])}{'...' if len(dates) > 5 else ''}\n"
            f"- Participants impliqués: {', '.join(participants[:5])}\n"
            f"- Premier extrait: \"...{matches[0].content[:150]}...\""
        )

    def get_summaries_for_contact(self, contact: str, limit: int = 5) -> str:
        """
        Récupère les résumés globaux des conversations avec un contact.
        """
        if not self.retriever or not self.retriever.summary_store:
            return "Erreur: Service de résumés non disponible."

        contact = contact.strip().strip('"\'')
        convs, periods = self.retriever.summary_store.get_summaries_for_participant(contact)
        
        if not convs and not periods:
            return f"Aucun résumé trouvé pour '{contact}'."

        output = [f"Résumés de haut niveau pour {contact}:\n"]
        
        # Mix and sort by date
        all_summaries = []
        for s in convs: all_summaries.append(("conversation", s))
        for s in periods: all_summaries.append(("period", s))
        
        all_summaries.sort(key=lambda x: x[1].date_start, reverse=True)
        
        for stype, s in all_summaries[:limit]:
            date = s.date_start[:10]
            if stype == "conversation":
                output.append(f"- [{date}] Conversation ({s.total_messages} msg): {s.summary[:300]}...")
            else:
                output.append(f"- [{date}] Période ({getattr(s, 'period', 'N/A')}): {s.summary[:300]}...")
                
        return "\n\n".join(output)

