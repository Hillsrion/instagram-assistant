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
        
        # Source accumulation for multi-step reasoning
        self._sources_registry = {}  # chunk_id -> dict
        self._summaries_registry = {} # summary_id -> dict
        
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

    def _register_chunks(self, results, expanded=False):
        """Helper to accumulate chunks from different tools."""
        for r in results:
            # Handle both AdvancedSearchResult and raw Chunk objects
            chunk = getattr(r, 'chunk', r)
            score = getattr(r, 'final_score', 1.0)
            
            if chunk.chunk_id not in self._sources_registry:
                self._sources_registry[chunk.chunk_id] = {
                    "chunk_id": chunk.chunk_id,
                    "file": chunk.file_source,
                    "participants": chunk.participants,
                    "date_start": chunk.date_start[:10],
                    "date_end": chunk.date_end[:10],
                    "score": round(score, 2),
                    "expanded": expanded or getattr(r, 'is_expanded', False),
                    "preview": (chunk.narrative_summary or chunk.summary or chunk.content[:200])[:200]
                }

    def _register_summaries(self, results):
        """Helper to accumulate summaries from different tools."""
        for r in results:
            # Handle both SummarySearchResult and raw Summary objects
            # CRITICAL: models have a .summary attribute which is a string (the text)
            # wrappers have a .summary attribute which is the model object
            summary_attr = getattr(r, 'summary', None)
            
            if summary_attr is not None and not isinstance(summary_attr, str):
                summary = summary_attr
                score = getattr(r, 'score', 1.0)
                level = getattr(r, 'level', 'unknown')
            else:
                summary = r
                score = 1.0
                level = getattr(r, 'level', 'unknown') if hasattr(r, 'level') else 'unknown'
            
            summary_id = getattr(summary, 'summary_id', f"sum_{getattr(summary, 'date_start', 'unknown')}_{getattr(summary, 'date_end', 'unknown')}")
            
            if summary_id not in self._summaries_registry:
                self._summaries_registry[summary_id] = {
                    "type": "summary",
                    "level": level,
                    "summary_id": summary_id,
                    "participants": summary.participants,
                    "period": getattr(summary, 'period', None) or f"{summary.date_start[:10]} - {summary.date_end[:10]}",
                    "score": round(score, 2),
                    "preview": summary.summary[:200]
                }

    def set_analysis(self, analysis):
        """Inject QueryAnalyzer results so tools can use them."""
        self._analysis = analysis

    def set_original_query(self, query: str):
        """Store original user query for smart fallback."""
        self._original_query = query

    def get_sources(self) -> list:
        """Extract all accumulated sources."""
        return list(self._sources_registry.values())

    def get_summary_sources(self) -> list:
        """Extract all accumulated summary sources."""
        return list(self._summaries_registry.values())

    def get_last_context(self):
        """Return the last retrieval context (for chat.py to access confidence, etc.)."""
        return self._last_context

    # Per-tool descriptions for filtering
    TOOL_DESCRIPTIONS = {
        "search_conversations": "search_conversations(query: str, participant: str = None, about_person: str = None, date_range: str = None): Recherche sémantique.\n   - 'participant': UNIQUEMENT pour restreindre aux conversations où la personne est présente (ex: \"Qu'a dit X?\").\n   - 'about_person': Pour chercher TOUT ce qui concerne une personne (elle est présente OU mentionnée). Préférable pour des sujets comme des anniversaires ou cadeaux.\n   - 'date_range': format \"YYYY-MM-DD to YYYY-MM-DD\".",
        "get_contact_stats": "get_contact_stats(contact_name: str): Statistiques (messages, conversations, dates) pour un contact précis.",
        "get_participants": "get_participants(): Liste tous les participants connus avec leurs statistiques globales.",
        "get_todays_date": "get_todays_date(): Date actuelle pour aider aux calculs temporels.",
        "explore_topic_timeline": "explore_topic_timeline(query: str): Chronologie détaillée d'un sujet avec volume mensuel et épisodes clés.",
        "get_thread_context": "get_thread_context(chunk_id: str, window: int = 5): Récupère les messages entourant un extrait précis (ID de chunk) pour comprendre le flux de la conversation.",
        "check_entity_presence": "check_entity_presence(keyword: str, participant: str = None): Vérifie de manière stricte (mot-clé) la présence d'un terme. Très fiable pour confirmer ou infirmer une mention.",
        "get_summaries_for_contact": "get_summaries_for_contact(contact: str, limit: int = 5): Récupère les résumés de haut niveau des dernières conversations avec ce contact.",
    }

    def get_tools_description(self, allowed_tools: list = None) -> str:
        """Returns description of available tools for the agent prompt, optionally filtered."""
        descs = self.TOOL_DESCRIPTIONS
        if allowed_tools:
            descs = {k: v for k, v in descs.items() if k in allowed_tools}
        return "\n".join(f"{i+1}. {desc}" for i, desc in enumerate(descs.values()))

    def get_tool_names(self, allowed_tools: list = None) -> List[str]:
        """Returns list of tool names, optionally filtered."""
        names = list(self._tools_registry.keys())
        if allowed_tools:
            names = [n for n in names if n in allowed_tools]
        return names

    def execute(self, tool_name: str, tool_input: str, allowed_tools: list = None) -> ToolResult:
        """
        Execute a tool by name with the given input.
        Supports both simple strings and JSON-formatted multi-argument strings.
        """
        tool_name = tool_name.strip().lower()

        available = self.get_tool_names(allowed_tools)

        if tool_name not in available:
            return ToolResult(
                success=False,
                output=f"Erreur: Outil '{tool_name}' non disponible. Outils disponibles: {', '.join(available)}",
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

    def search_conversations(self, query: str, participant: str = None, about_person: str = None, date_range: str = None) -> str:
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
            participant_filter=participant_filter,
            about_person=about_person
        )

        # Smart Fallback
        if (context.low_confidence or not context.has_results) and self._original_query and query != self._original_query:
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

        # Accumuler les sources
        self._last_context = context
        self._register_chunks(context.results)
        if context.used_summary_fallback:
            self._register_summaries(context.summary_results)

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

        stats = self.analytics.get_participant_stats()

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

        return f"Statistiques pour '{contact_name}':\n- Nombre de messages: environ {count}"

    def get_participants(self, _: str = None) -> str:
        """Liste tous les participants avec leurs statistiques."""
        if not self.analytics:
            return "Erreur: Module analytics non initialisé."

        stats = self.analytics.get_participant_stats()

        if not stats:
            return "Aucun participant trouvé."

        lines = [f"**{len(stats)} participants trouvés:**\n"]
        for participant, info in list(stats.items())[:20]:
            lines.append(f"• {participant}: {info['message_count']} messages")

        return "\n".join(lines)

    def get_todays_date(self, _: str = None) -> str:
        """Returns today's date."""
        now = datetime.now()
        return f"Date actuelle: {now.strftime('%A %d %B %Y')} (ISO: {now.strftime('%Y-%m-%d')})"

    def explore_topic_timeline(self, query: str) -> str:
        """Analyse chronologique d'un sujet."""
        if not self.retriever:
            return "Erreur: Retriever non initialisé."

        query = query.strip().strip('"\'')
        
        # 1. Search summaries
        summary_results = []
        if self.retriever.summary_store:
            summary_results = self.retriever.summary_store.search(query, level="all", top_k=5)
            self._register_summaries(summary_results)

        # 2. Search chunks
        context = self.retriever.retrieve(query, top_k=15, use_reranking=True)
        self._register_chunks(context.results)

        if not summary_results and not context.has_results:
            return f"Aucun épisode trouvé pour: '{query}'"

        timeline = [f"Chronologie pour '{query}':\n"]

        if summary_results:
            timeline.append("**Épisodes clés:**")
            for r in summary_results:
                timeline.append(f"- [{r.summary.date_start[:10]}]: {r.summary.summary[:150]}...")
            timeline.append("")

        if context.has_results:
            timeline.append("**Mentions détaillées:**")
            for r in sorted(context.results, key=lambda x: x.chunk.date_start):
                timeline.append(f"- {r.chunk.date_start[:10]}: {r.chunk.content[:100]}...")

        return "\n".join(timeline)

    def get_thread_context(self, chunk_id: str, window: int = 5) -> str:
        """Récupère les messages entourant un extrait précis."""
        if not self.retriever or not self.retriever.metadata_store:
            return "Erreur: MetadataStore non disponible."

        chunk_id = chunk_id.strip().strip('"\'')
        adj_indices = self.retriever.metadata_store.get_adjacent_chunks(chunk_id, window=window)
        
        if not adj_indices:
            return f"Impossible de trouver le contexte pour {chunk_id}"

        chunks = [self.retriever.vector_store.chunks[idx] for idx in sorted(adj_indices)]
        
        # Accumuler ces nouveaux chunks comme sources
        self._register_chunks(chunks, expanded=True)
        
        output = [f"Contexte étendu pour {chunk_id}:\n"]
        for c in chunks:
            marker = ">>> " if c.chunk_id == chunk_id else "    "
            output.append(f"{marker}[{c.date_start[11:16]}] {', '.join(c.participants)}: {c.content}")
            
        return "\n---\n".join(output)

    def check_entity_presence(self, keyword: str, participant: str = None) -> str:
        """
        Vérification stricte et comptage par mot-clé (Anti-hallucination + Stats).
        """
        if not self.retriever or not self.retriever.bm25_index:
            return "Erreur: Le moteur de recherche textuelle n'est pas prêt."

        keyword = keyword.strip().strip('"\'')
        
        # 1. Récupérer TOUS les matches potentiels via BM25 (plus que 50 pour le compte)
        results = self.retriever.bm25_index.search(keyword, top_k=500)
        
        if not results:
            return f"Confirmation: Le terme '{keyword}' n'apparaît dans aucune conversation."

        # 2. Filtrage et validation exacte
        matches = []
        for idx, _ in results:
            chunk = self.retriever.vector_store.chunks[idx]
            
            # Filtre participant
            if participant:
                if not any(participant.lower() in p.lower() for p in chunk.participants):
                    continue
            
            # Vérification exacte (case insensitive)
            count_in_chunk = chunk.content.lower().count(keyword.lower())
            if count_in_chunk > 0:
                matches.append((chunk, count_in_chunk))

        if not matches:
            return f"Le terme '{keyword}' n'a pas été trouvé avec les filtres demandés."

        # 3. Calcul des statistiques
        total_mentions = sum(count for _, count in matches)
        unique_chunks = len(matches)
        dates = sorted(list(set(c.date_start[:10] for c, _ in matches)))
        
        # Distribution par année pour le contexte
        years = {}
        for c, _ in matches:
            yr = c.date_start[:4]
            years[yr] = years.get(yr, 0) + 1

        stats_str = ", ".join([f"{y} ({count} segments)" for y, count in sorted(years.items())])

        # Accumuler les top matches comme sources (limité à 10 pour ne pas saturer)
        self._register_chunks([c for c, _ in matches[:10]])
        
        res = [
            f"Résultats pour '{keyword}':",
            f"- Total d'occurrences trouvées: {total_mentions}",
            f"- Nombre de segments de conversation impactés: {unique_chunks}",
            f"- Répartition temporelle: {stats_str}",
            f"- Première mention: {dates[0]}",
            f"- Dernière mention: {dates[-1]}",
            f"\nExtrait représentatif: \"...{matches[0][0].content[:200]}...\""
        ]
        
        return "\n".join(res)

    def get_summaries_for_contact(self, contact: str, limit: int = 5) -> str:
        """Récupère les résumés globaux pour un contact."""
        if not self.retriever or not self.retriever.summary_store:
            return "Erreur: Service de résumés non disponible."

        convs, periods = self.retriever.summary_store.get_summaries_for_participant(contact)
        
        # Accumuler les résumés comme sources
        self._register_summaries(convs[:limit])
        self._register_summaries(periods[:limit])
        
        output = [f"Résumés pour {contact}:\n"]
        for s in (convs + periods)[:limit]:
            output.append(f"- [{s.date_start[:10]}] {s.summary[:200]}...")
                
        return "\n\n".join(output)

