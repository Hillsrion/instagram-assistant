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
    Each tool wraps existing RAG capabilities.
    """

    def __init__(self, config: Config = None, retriever: Retriever = None):
        self.config = config or default_config
        self.retriever = retriever
        self._tools_registry = {
            "search_conversations": self.search_conversations,
            "count_messages": self.count_messages,
            "get_todays_date": self.get_todays_date,
        }

    def get_tools_description(self) -> str:
        """Returns description of available tools for the agent prompt."""
        return """1. search_conversations(query: str): Recherche sémantique dans l'historique des discussions. Renvoie les passages les plus pertinents.
2. count_messages(contact_name: str): Compte le nombre de messages échangés avec un contact spécifique.
3. get_todays_date(): Renvoie la date d'aujourd'hui au format YYYY-MM-DD."""

    def get_tool_names(self) -> List[str]:
        """Returns list of tool names."""
        return list(self._tools_registry.keys())

    def execute(self, tool_name: str, tool_input: str) -> ToolResult:
        """
        Execute a tool by name with the given input.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input argument for the tool
            
        Returns:
            ToolResult with success status and output
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
        Semantic search in conversation history.
        Returns formatted search results.
        """
        if not self.retriever:
            return "Erreur: Retriever non initialisé."
        
        query = query.strip().strip('"\'')
        
        # Perform retrieval
        context: RetrievalContext = self.retriever.retrieve(query, top_k=5)
        
        if not context.has_results:
            return f"Aucun résultat trouvé pour: '{query}'"
        
        # Format results for the agent
        results = []
        for r in context.results:
            chunk = r.chunk
            # Truncate content for readability
            content_preview = chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content
            
            result_str = (
                f"[Score: {r.score:.2f}] "
                f"Participants: {', '.join(chunk.participants)} | "
                f"Date: {chunk.date_start[:10]} à {chunk.date_end[:10]}\n"
                f"{content_preview}"
            )
            results.append(result_str)
        
        return f"Trouvé {len(context.results)} résultats pour '{query}':\n\n" + "\n---\n".join(results)

    def count_messages(self, contact_name: str) -> str:
        """
        Count messages with a specific contact.
        Uses chunk data for approximate counting.
        """
        if not self.retriever:
            return "Erreur: Retriever non initialisé."
        
        contact_name = contact_name.strip().strip('"\'')
        
        # Access chunks from vector store
        vector_store: VectorStore = self.retriever.vector_store
        
        total_messages = 0
        matching_chunks = 0
        
        for chunk in vector_store.chunks:
            # Check if contact is a participant
            participants_lower = [p.lower() for p in chunk.participants]
            if any(contact_name.lower() in p for p in participants_lower):
                matching_chunks += 1
                total_messages += chunk.message_count
        
        if matching_chunks == 0:
            return f"Aucun message trouvé avec '{contact_name}'."
        
        return (
            f"Statistiques pour '{contact_name}':\n"
            f"- Nombre de messages: environ {total_messages}\n"
            f"- Nombre de chunks de conversation: {matching_chunks}"
        )

    def get_todays_date(self, _: str = None) -> str:
        """Returns today's date."""
        now = datetime.now()
        return (
            f"Date actuelle: {now.strftime('%A %d %B %Y')} "
            f"(ISO: {now.strftime('%Y-%m-%d')})"
        )
