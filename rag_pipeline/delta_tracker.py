"""
Delta Tracker for incremental index updates.
Tracks file changes to enable efficient re-indexing.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple, Set

from .config import Config, default_config


@dataclass
class FileState:
    """State of a tracked file."""
    file_path: str
    content_hash: str
    last_modified: str  # ISO timestamp
    last_indexed: str   # ISO timestamp
    chunk_ids: List[str] = field(default_factory=list)
    file_size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FileState":
        return cls(**data)


@dataclass
class DeltaResult:
    """Result of change detection."""
    new_files: List[Path]
    modified_files: List[Path]
    deleted_files: List[str]  # file paths that were tracked but no longer exist

    @property
    def has_changes(self) -> bool:
        return bool(self.new_files or self.modified_files or self.deleted_files)

    def summary(self) -> str:
        return (
            f"New: {len(self.new_files)}, "
            f"Modified: {len(self.modified_files)}, "
            f"Deleted: {len(self.deleted_files)}"
        )


class DeltaTracker:
    """
    Track file changes for incremental indexing.

    Stores file hashes and modification times to detect:
    - New files (not in state)
    - Modified files (hash changed)
    - Deleted files (in state but not on disk)
    """

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.state_path = self.config.index_dir / "file_state.json"
        self.file_states: Dict[str, FileState] = {}
        self._load_state()

    def _load_state(self):
        """Load tracked file states from disk."""
        if not self.state_path.exists():
            self.file_states = {}
            return

        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.file_states = {
                k: FileState.from_dict(v)
                for k, v in data.get('files', {}).items()
            }
            print(f"Loaded state for {len(self.file_states)} tracked files")

        except Exception as e:
            print(f"Warning: Could not load file state: {e}")
            self.file_states = {}

    def save_state(self):
        """Save tracked file states to disk."""
        data = {
            'last_updated': datetime.now().isoformat(),
            'total_files': len(self.file_states),
            'files': {k: v.to_dict() for k, v in self.file_states.items()}
        }

        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Saved state for {len(self.file_states)} files")

    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        return sha256.hexdigest()

    def detect_changes(self, directory: Path = None) -> DeltaResult:
        """
        Detect file changes since last indexing.

        Args:
            directory: Directory to scan (defaults to conversations_dir)

        Returns:
            DeltaResult with lists of new, modified, and deleted files
        """
        directory = directory or self.config.conversations_dir

        if not directory.exists():
            return DeltaResult(new_files=[], modified_files=[], deleted_files=[])

        # Get current files
        current_files = set(directory.glob('*.txt'))
        current_paths = {str(f): f for f in current_files}

        new_files = []
        modified_files = []
        deleted_files = []

        # Check for new and modified files
        for file_path in current_files:
            path_str = str(file_path)

            if path_str not in self.file_states:
                # New file
                new_files.append(file_path)
            else:
                # Check if modified
                current_hash = self.compute_hash(file_path)
                if current_hash != self.file_states[path_str].content_hash:
                    modified_files.append(file_path)

        # Check for deleted files
        for tracked_path in self.file_states:
            if tracked_path not in current_paths:
                deleted_files.append(tracked_path)

        return DeltaResult(
            new_files=new_files,
            modified_files=modified_files,
            deleted_files=deleted_files
        )

    def update_file_state(
        self,
        file_path: Path,
        chunk_ids: List[str]
    ):
        """
        Update tracking state for a file after indexing.

        Args:
            file_path: Path to the indexed file
            chunk_ids: List of chunk IDs created from this file
        """
        path_str = str(file_path)
        now = datetime.now().isoformat()

        self.file_states[path_str] = FileState(
            file_path=path_str,
            content_hash=self.compute_hash(file_path),
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            last_indexed=now,
            chunk_ids=chunk_ids,
            file_size=file_path.stat().st_size
        )

    def remove_file_state(self, file_path: str):
        """Remove a file from tracking (after deletion)."""
        if file_path in self.file_states:
            del self.file_states[file_path]

    def get_chunk_ids_for_file(self, file_path: str) -> List[str]:
        """Get chunk IDs associated with a tracked file."""
        if file_path in self.file_states:
            return self.file_states[file_path].chunk_ids
        return []

    def get_all_chunk_ids_for_files(self, file_paths: List[str]) -> Set[str]:
        """Get all chunk IDs for a list of files."""
        chunk_ids = set()
        for path in file_paths:
            chunk_ids.update(self.get_chunk_ids_for_file(path))
        return chunk_ids

    def get_stats(self) -> dict:
        """Get tracking statistics."""
        total_chunks = sum(len(fs.chunk_ids) for fs in self.file_states.values())
        total_size = sum(fs.file_size for fs in self.file_states.values())

        return {
            'tracked_files': len(self.file_states),
            'total_chunks': total_chunks,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }

    def clear(self):
        """Clear all tracking state."""
        self.file_states = {}
        if self.state_path.exists():
            self.state_path.unlink()
