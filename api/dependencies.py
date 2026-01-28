"""
Application dependencies and global state management.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI

from rag_pipeline.config import Config
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot
from rag_pipeline.analytics import ConversationAnalytics
from rag_pipeline.query_analyzer import QueryAnalyzer
from rag_pipeline.logger import get_logger

logger = get_logger()


# Global state
class AppState:
    """Container for application state."""
    retriever = None
    chatbot = None
    config = None
    components = None
    analytics = None
    query_analyzer = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG components on startup."""
    print("=" * 60)
    print("Instagram Conversations Assistant")
    print("=" * 60)
    print()

    state.config = Config()

    # Initialize analytics module
    state.analytics = ConversationAnalytics(state.config)

    # Check if index exists
    if not (state.config.vector_store_path / "index.faiss").exists():
        print("Index FAISS non trouvé.")
        print("Lancez d'abord: python3 setup_rag_batch.py")
        print()
        print("L'application démarre en mode limité...")
        yield
        return

    print("Chargement des composants RAG...")
    try:
        state.retriever, state.components = create_advanced_retriever(
            state.config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True,
            enable_summaries=True
        )
        state.chatbot = ChatBot(state.retriever, state.config)
        state.query_analyzer = QueryAnalyzer(state.config)
        print(f"Index chargé: {state.components['vector_store'].size} chunks")
        print()
        print(f"Application prête sur http://localhost:8000")
        print()
    except Exception as e:
        print(f"Erreur lors du chargement: {e}")

    yield

    # Cleanup
    if state.components and 'metadata_store' in state.components:
        state.components['metadata_store'].close()
    if state.analytics:
        state.analytics.close()


def get_retriever():
    """Get the retriever instance."""
    return state.retriever


def get_chatbot():
    """Get the chatbot instance."""
    return state.chatbot


def get_config():
    """Get the config instance."""
    return state.config


def get_components():
    """Get the components dict."""
    return state.components


def get_analytics():
    """Get the analytics instance."""
    return state.analytics


def get_query_analyzer():
    """Get the query analyzer instance."""
    return state.query_analyzer
