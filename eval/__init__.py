"""
Evaluation module for the Instagram Assistant RAG pipeline.
Includes synthetic data generation, RAGAS metrics, and benchmarking.
"""

from .synthetic_generator import SyntheticDataGenerator, QAPair
from .metrics import RAGASMetrics, EvalResult, BenchmarkReport
from .benchmark import BenchmarkRunner, BenchmarkConfig

__all__ = [
    'SyntheticDataGenerator',
    'QAPair',
    'RAGASMetrics',
    'EvalResult',
    'BenchmarkReport',
    'BenchmarkRunner',
    'BenchmarkConfig',
]
