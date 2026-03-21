"""
Binary router: fast-path (direct retrieval) vs agent.
Deterministic, no LLM call.
"""
from rag_pipeline.query.query_analyzer import AnalysisResult


def should_use_agent(analysis: AnalysisResult, mode: str = "fast") -> bool:
    """
    Returns True if query should go through agent, False for fast-path.
    
    If mode is explicitly 'reflexion', always use agent.
    If mode is 'fast', follow analysis result.
    """
    if mode == "reflexion":
        return True

    if analysis.mode != "retrieval":
        return True  # analytics/discovery always use agent

    if analysis.intent == "complex_reasoning":
        return True  # complex queries use agent

    # specific_fact and broad_summary -> fast-path
    return False
