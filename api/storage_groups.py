import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# The groups are stored in the RAG data directory
GROUPS_FILE = Path("rag_data/instagram_groups.json")

def _ensure_dir():
    """Ensure the rag_data directory exists."""
    os.makedirs(GROUPS_FILE.parent, exist_ok=True)

def load_source_groups() -> Dict[str, Any]:
    """Load all source groups from JSON."""
    if not GROUPS_FILE.exists():
        # Create default groups
        _ensure_dir()
        defaults = {
            "famille": {
                "id": "famille",
                "title": "Famille",
                "thread_ids": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            "amis": {
                "id": "amis",
                "title": "Amis",
                "thread_ids": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            "travail": {
                "id": "travail",
                "title": "Travail",
                "thread_ids": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }
        save_source_groups(defaults)
        return defaults
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading source groups: {e}")
        return {}

def save_source_groups(groups: Dict[str, Any]):
    """Save all source groups to JSON."""
    _ensure_dir()
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(groups, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving source groups: {e}")

def get_source_group(group_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific source group."""
    groups = load_source_groups()
    return groups.get(group_id)

def save_source_group(group: Dict[str, Any]):
    """Save or update a single source group."""
    groups = load_source_groups()
    groups[group["id"]] = group
    save_source_groups(groups)

def delete_source_group(group_id: str) -> bool:
    """Delete a source group."""
    groups = load_source_groups()
    if group_id in groups:
        del groups[group_id]
        save_source_groups(groups)
        return True
    return False
