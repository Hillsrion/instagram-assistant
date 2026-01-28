"""
JSON file storage for conversations.
"""
import json
from pathlib import Path

CONVERSATIONS_FILE = Path("rag_data/conversations.json")


def load_conversations() -> dict:
    """Load all conversations from file."""
    if CONVERSATIONS_FILE.exists():
        with open(CONVERSATIONS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_conversations(conversations: dict) -> None:
    """Save all conversations to file."""
    CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERSATIONS_FILE, 'w') as f:
        json.dump(conversations, f, indent=2)


def get_conversation(conv_id: str) -> dict | None:
    """Get a single conversation by ID."""
    conversations = load_conversations()
    return conversations.get(conv_id)


def save_conversation(conv: dict) -> None:
    """Save a single conversation."""
    conversations = load_conversations()
    conversations[conv['id']] = conv
    save_conversations(conversations)


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation."""
    conversations = load_conversations()
    if conv_id in conversations:
        del conversations[conv_id]
        save_conversations(conversations)
        return True
    return False
