"""
Centralized output path management for evaluation results.

All evaluation results are stored in eval/results/,
organized by script name with descriptive filenames.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional


# Root directory for all evaluation results
EVAL_RESULTS_DIR = Path(__file__).parent / "results"


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generation_base_name(models: List[str], trials: int, timestamp: Optional[datetime] = None) -> tuple:
    """Generate base filename components for generation reports."""
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    # Clean model names for filename (replace colons and special chars)
    clean_models = [m.replace(":", "-").replace("/", "-") for m in models]
    models_str = "_vs_".join(clean_models[:3])  # Limit to first 3 models

    base = f"gen_{trials}trials_{models_str}_{ts_str}"
    output_dir = ensure_dir(EVAL_RESULTS_DIR / "eval_generation")
    return output_dir, base


def get_generation_report_path(
    models: List[str],
    trials: int,
    timestamp: Optional[datetime] = None,
    format: str = "html"
) -> Path:
    """
    Get output path for generation evaluation report.

    Format: eval/results/eval_generation/gen_<trials>trials_<model1>_vs_<model2>_<timestamp>.<ext>

    Args:
        models: List of model names being compared
        trials: Number of trials run
        timestamp: Optional timestamp (defaults to now)
        format: Output format ("html" or "json")

    Returns:
        Path to the report file
    """
    output_dir, base = _generation_base_name(models, trials, timestamp)
    return output_dir / f"{base}.{format}"


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
    Get output path for multi-chunk generation evaluation report.

    Format: eval/results/eval_generation_multichunk/multichunk_<trials>trials_<model1>_vs_<model2>_<timestamp>.<ext>

    Args:
        models: List of model names being compared
        trials: Number of trials run
        timestamp: Optional timestamp (defaults to now)
        format: Output format ("html" or "json")

    Returns:
        Path to the report file
    """
    ts = timestamp or datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    # Clean model names for filename (replace colons and special chars)
    clean_models = [m.replace(":", "-").replace("/", "-") for m in models]
    models_str = "_vs_".join(clean_models[:3])  # Limit to first 3 models

    filename = f"multichunk_{trials}trials_{models_str}_{ts_str}.{format}"

    output_dir = ensure_dir(EVAL_RESULTS_DIR / "eval_generation_multichunk")
    return output_dir / filename
