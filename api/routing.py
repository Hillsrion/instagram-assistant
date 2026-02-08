"""
Binary router: fast-path (direct retrieval) vs agent.
Deterministic, no LLM call.
"""
from rag_pipeline.query.query_analyzer import AnalysisResult


def should_use_agent(analysis: AnalysisResult) -> bool:
    """
    Returns True if query should go through agent, False for fast-path.

    Fast-path criteria (ALL must be true):
    - mode is "retrieval"
    - intent is "specific_fact"

    Everything else -> agent (complex retrieval, analytics, discovery, broad_summary)
    """
    if analysis.mode != "retrieval":
        return True  # analytics/discovery always use agent

    if analysis.intent == "complex_reasoning":
        return True  # complex queries use agent

    # specific_fact and broad_summary -> fast-path
    return False
