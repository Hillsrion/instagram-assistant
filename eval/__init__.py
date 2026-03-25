"""
Evaluation module for the Sira RAG pipeline.
Includes synthetic data generation, RAGAS metrics, and benchmarking.

Submodules:
- core: Shared metrics, benchmarking, and dataset generation
- retrieval: Retrieval quality evaluation
- generation: LLM generation quality evaluation
- enrichment: Chunk enrichment validation
- summaries: Summary evaluation
- routing: Routing evaluation
- config_comparison: Configuration comparison
- dataset: Dataset generation utilities
"""

# Core utilities
from .core import (
    SyntheticDataGenerator,
    QAPair,
    MultiChunkQAPair,
    RAGASMetrics,
    EvalResult,
    BenchmarkReport,
    MultiChunkEvalResult,
    BenchmarkRunner,
    BenchmarkConfig,
)

# Enrichment validation
from .enrichment import EnrichmentValidator

__all__ = [
    # Core
    "SyntheticDataGenerator",
    "QAPair",
    "MultiChunkQAPair",
    "RAGASMetrics",
    "EvalResult",
    "BenchmarkReport",
    "MultiChunkEvalResult",
    "BenchmarkRunner",
    "BenchmarkConfig",
    # Enrichment
    "EnrichmentValidator",
]
