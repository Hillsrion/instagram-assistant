"""
JSON file storage for conversations.
"""
import json
from pathlib import Path

CHATS_FILE = Path("rag_data/chats.json")
CHAT_PROJECTS_FILE = Path("rag_data/chat_projects.json")
SETTINGS_FILE = Path("rag_data/settings.json")


def load_settings() -> dict:
    """Load settings from file."""
    defaults = {
        "developerMode": False,
        "agentTone": "Professionnel",
        "globalInstructions": "",
        "interfaceTheme": "Système",
        "ownUsername": "",
    }
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return {**defaults, **data}
    return defaults




def save_settings(settings: dict) -> None:
    """Save settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


def load_chats() -> dict:
    """Load all chats from file."""
    # Migration check
    if not CHATS_FILE.exists() and Path("rag_data/conversations.json").exists():
        old_file = Path("rag_data/conversations.json")
        with open(old_file, 'r') as f:
            data = json.load(f)
        save_chats(data)
        return data
        
    if CHATS_FILE.exists():
        with open(CHATS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_chats(chats: dict) -> None:
    """Save all chats to file."""
    CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHATS_FILE, 'w') as f:
        json.dump(chats, f, indent=2)


def get_chat(chat_id: str) -> dict | None:
    """Get a single chat by ID."""
    chats = load_chats()
    return chats.get(chat_id)


def save_chat(chat_data: dict) -> None:
    """Save a single chat."""
    chats = load_chats()
    chats[chat_data['id']] = chat_data
    save_chats(chats)


def delete_chat(chat_id: str) -> bool:
    """Delete a chat."""
    chats = load_chats()
    if chat_id in chats:
        del chats[chat_id]
        save_chats(chats)
        return True
    return False


def load_projects() -> dict:
    """Load all chat projects from file."""
    if not CHAT_PROJECTS_FILE.exists() and Path("rag_data/projects.json").exists():
        old_file = Path("rag_data/projects.json")
        with open(old_file, 'r') as f:
            data = json.load(f)
        save_projects(data)
        return data

    if CHAT_PROJECTS_FILE.exists():
        with open(CHAT_PROJECTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_projects(projects: dict) -> None:
    """Save all chat projects to file."""
    CHAT_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAT_PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2)


def get_project(project_id: str) -> dict | None:
    """Get a single project by ID."""
    projects = load_projects()
    return projects.get(project_id)


def save_project(project: dict) -> None:
    """Save a single project."""
    projects = load_projects()
    projects[project['id']] = project
    save_projects(projects)


def delete_project(project_id: str) -> bool:
    """Delete a project."""
    projects = load_projects()
    if project_id in projects:
        del projects[project_id]
        save_projects(projects)
        return True
    return False
