"""
Centralized output path management for evaluation results.

All evaluation results are stored in eval/results/,
organized by script name with descriptive filenames.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional


# Root directory for all evaluation results
EVAL_RESULTS_DIR = Path(__file__).parent.parent / "results"


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_run_dir(eval_type: str, models: List[str], timestamp: Optional[datetime] = None) -> Path:
    """Create and return a run-specific subfolder."""
    ts = timestamp or datetime.now()
    # Use a fixed format for the run folder to avoid sub-second mismatches
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    
    clean_models = [m.replace(":", "-").replace("/", "-") for m in models]
    models_str = "_vs_".join(clean_models[:2]) # Keep it relative short
    
    run_name = f"run_{ts_str}_{models_str}"
    return ensure_dir(EVAL_RESULTS_DIR / eval_type / run_name)


def get_generation_report_path(
    models: List[str],
    trials: int,
    timestamp: Optional[datetime] = None,
    format: str = "html"
) -> Path:
    """
    Get output path for generation evaluation report (in run subfolder).
    """
    run_dir = _get_run_dir("eval_generation", models, timestamp)
    filename = "report" if format == "html" else "results"
    return run_dir / f"{filename}.{format}"


def get_retrieval_report_path(
    config_name: str,
    timestamp: Optional[datetime] = None
) -> Path:
    """
    Get output path for retrieval evaluation report.

    Format: eval/results/eval_retrieval/retrieval_<config>_<timestamp>.json

    Args:
        config_name: Name of the benchmark configuration
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Path to the JSON report file
    """
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    filename = f"retrieval_{config_name}_{ts_str}.json"

    output_dir = ensure_dir(EVAL_RESULTS_DIR / "eval_retrieval")
    return output_dir / filename


def get_summaries_report_path(
    conversations: int,
    periods: int,
    timestamp: Optional[datetime] = None,
    format: str = "html"
) -> Path:
    """
    Get output path for summaries evaluation report.

    Format: eval/results/evaluate_summaries/summaries_<conv>conv_<periods>periods_<timestamp>.<ext>

    Args:
        conversations: Number of conversation summaries evaluated
        periods: Number of period summaries evaluated
        timestamp: Optional timestamp (defaults to now)
        format: Output format ("html" or "json")

    Returns:
        Path to the report file
    """
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    filename = f"summaries_{conversations}conv_{periods}periods_{ts_str}.{format}"

    output_dir = ensure_dir(EVAL_RESULTS_DIR / "evaluate_summaries")
    return output_dir / filename


def get_dashboard_path(
    timestamp: Optional[datetime] = None
) -> Path:
    """
    Get output path for multi-model dashboard.

    Format: eval/results/eval_generation/dashboard_<timestamp>.html

    Args:
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Path to the HTML dashboard file
    """
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    filename = f"dashboard_{ts_str}.html"

    output_dir = ensure_dir(EVAL_RESULTS_DIR / "eval_generation")
    return output_dir / filename


def get_comparison_report_path(
    timestamp: Optional[datetime] = None
) -> Path:
    """
    Get output path for config comparison report.

    Format: eval/results/compare_configs/comparison_<timestamp>.json

    Args:
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Path to the JSON report file
    """
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    filename = f"comparison_{ts_str}.json"

    output_dir = ensure_dir(EVAL_RESULTS_DIR / "compare_configs")
    return output_dir / filename


def get_multichunk_report_path(
    models: List[str],
    trials: int,
    timestamp: Optional[datetime] = None,
    format: str = "html"
) -> Path:
    """
    Get output path for multi-chunk generation evaluation report (in run subfolder).
    """
    run_dir = _get_run_dir("eval_generation_multichunk", models, timestamp)
    filename = "report" if format == "html" else "results"
    return run_dir / f"{filename}.{format}"


def get_enrichment_report_path(
    models: List[str],
    timestamp: Optional[datetime] = None,
    format: str = "html"
) -> Path:
    """
    Get output path for enrichment evaluation report.
    Format: eval/results/eval_enrichment/run_.../report.html
    """
    run_dir = _get_run_dir("eval_enrichment", models, timestamp)
    filename = "report" if format == "html" else "results"
    return run_dir / f"{filename}.{format}"
