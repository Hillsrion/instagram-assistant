"""
Utilitaires partagés pour les scripts CLI du pipeline RAG.
"""
import numpy as np
from pathlib import Path
from typing import Optional

# Configuration du batching (partagée entre scripts)
CHECKPOINT_DIR = Path("rag_data/checkpoints")
DEFAULT_BATCH_SIZE = 500


def format_duration(seconds: float) -> str:
    """Formate une durée en j h m s."""
    if seconds is None or seconds < 0:
        return "0s"

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}j")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")

    return " ".join(parts)


def print_header(title: str, step: Optional[str] = None, char: str = "=", width: int = 40):
    """Affiche un en-tête de section formaté.

    Args:
        title: Titre de la section
        step: Numéro d'étape (ex: "1/8")
        char: Caractère de bordure
        width: Largeur de la bordure
    """
    print(char * width)
    if step:
        print(f"{title} (Étape {step})")
    else:
        print(title)
    print(char * width)


def get_checkpoint_path(batch_idx: int, checkpoint_dir: Path = CHECKPOINT_DIR) -> Path:
    """Retourne le chemin du fichier checkpoint pour un batch."""
    return checkpoint_dir / f"embeddings_batch_{batch_idx:04d}.npy"


def count_existing_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR) -> int:
    """Compte le nombre de checkpoints existants."""
    if not checkpoint_dir.exists():
        return 0
    return len(list(checkpoint_dir.glob("embeddings_batch_*.npy")))


def count_existing_embeddings(checkpoint_dir: Path = CHECKPOINT_DIR) -> int:
    """Compte le nombre réel d'embeddings dans les checkpoints."""
    if not checkpoint_dir.exists():
        return 0

    total = 0
    for f in sorted(checkpoint_dir.glob("embeddings_batch_*.npy")):
        emb = np.load(f)
        total += len(emb)
    return total


def load_all_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR, verbose: bool = True) -> Optional[np.ndarray]:
    """Charge et concatène tous les checkpoints.

    Args:
        checkpoint_dir: Répertoire des checkpoints
        verbose: Afficher les messages de progression

    Returns:
        Array numpy contenant tous les embeddings, ou None si aucun checkpoint
    """
    if not checkpoint_dir.exists():
        return None

    checkpoint_files = sorted(checkpoint_dir.glob("embeddings_batch_*.npy"))
    if not checkpoint_files:
        return None

    if verbose:
        print(f"   Chargement de {len(checkpoint_files)} checkpoints...")

    embeddings_list = []
    for f in checkpoint_files:
        emb = np.load(f)
        embeddings_list.append(emb)
        if verbose:
            print(f"   - {f.name}: {len(emb)} embeddings")

    return np.vstack(embeddings_list)


def reset_checkpoints(checkpoint_dir: Path = CHECKPOINT_DIR) -> bool:
    """Supprime tous les checkpoints.

    Returns:
        True si des checkpoints ont été supprimés
    """
    if checkpoint_dir.exists():
        import shutil
        shutil.rmtree(checkpoint_dir)
        print("Checkpoints supprimés")
        return True
    return False
