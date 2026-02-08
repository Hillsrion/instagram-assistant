"""
Shared utilities for RAG pipeline CLI scripts.
"""
import numpy as np
from pathlib import Path
from typing import Optional

# Batching configuration (shared between scripts)
CHECKPOINT_DIR = Path("rag_data/checkpoints")
DEFAULT_BATCH_SIZE = 500


def format_duration(seconds: float) -> str:
    """Formats a duration in d h m s."""
    if seconds is None or seconds < 0:
        return "0s"

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")

    return " ".join(parts)


def print_header(title: str, step: Optional[str] = None, char: str = "=", width: int = 40):
    """Prints a formatted section header.

    Args:
        title: Section title
        step: Step number (e.g., "1/8")
        char: Border character
        width: Border width
    """
    print(char * width)
    if step:
        print(f"{title} (Step {step})")
    else:
        print(title)
    print(char * width)


def get_checkpoint_path(batch_idx: int, checkpoint_dir: Path = CHECKPOINT_DIR) -> Path:
    """Returns the checkpoint file path for a batch."""
    return checkpoint_dir / f"embeddings_batch_{batch_idx:04d}.npy"


def count_existing_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR) -> int:
    """Counts the number of existing checkpoints."""
    if not checkpoint_dir.exists():
        return 0
    return len(list(checkpoint_dir.glob("embeddings_batch_*.npy")))


def count_existing_embeddings(checkpoint_dir: Path = CHECKPOINT_DIR) -> int:
    """Counts the actual number of embeddings in checkpoints."""
    if not checkpoint_dir.exists():
        return 0

    total = 0
    for f in sorted(checkpoint_dir.glob("embeddings_batch_*.npy")):
        emb = np.load(f)
        total += len(emb)
    return total


def load_all_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR, verbose: bool = True) -> Optional[np.ndarray]:
    """Loads and concatenates all checkpoints.

    Args:
        checkpoint_dir: Checkpoints directory
        verbose: Show progress messages

    Returns:
        Numpy array containing all embeddings, or None if no checkpoints
    """
    if not checkpoint_dir.exists():
        return None

    checkpoint_files = sorted(checkpoint_dir.glob("embeddings_batch_*.npy"))
    if not checkpoint_files:
        return None

    if verbose:
        print(f"   Loading {len(checkpoint_files)} checkpoints...")

    embeddings_list = []
    for f in checkpoint_files:
        emb = np.load(f)
        embeddings_list.append(emb)
        if verbose:
            print(f"   - {f.name}: {len(emb)} embeddings")

    return np.vstack(embeddings_list)


def reset_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR) -> bool:
    """Deletes all checkpoints.

    Returns:
        True if checkpoints were deleted
    """
    if checkpoint_dir.exists():
        import shutil
        shutil.rmtree(checkpoint_dir)
        print("Checkpoints deleted")
        return True
    return False