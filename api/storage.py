"""
SQLite storage for chats, projects, and settings.
Replaces JSON file storage.
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from api.database import get_db

CHATS_JSON_FILE = Path("rag_data/chats.json")
CHAT_PROJECTS_JSON_FILE = Path("rag_data/chat_projects.json")
SETTINGS_JSON_FILE = Path("rag_data/settings.json")


def load_settings() -> dict:
    """Load settings from database."""
    defaults = {
        "developerMode": False,
        "agentTone": "Professionnel",
        "globalInstructions": "",
        "interfaceTheme": "Système",
        "ownUsername": "",
    }
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return defaults
        
    settings = {}
    for row in rows:
        try:
            settings[row['key']] = json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            settings[row['key']] = row['value']
            
    return {**defaults, **settings}


def save_settings(settings: dict) -> None:
    """Save settings to database."""
    conn = get_db()
    cursor = conn.cursor()
    for k, v in settings.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
    conn.commit()
    conn.close()


def load_chats() -> dict:
    """Load all chats from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats")
    rows = cursor.fetchall()
    conn.close()
    
    chats = {}
    for row in rows:
        chats[row['id']] = {
            "id": row['id'],
            "project_id": row['project_id'],
            "title": row['title'],
            "is_favorite": bool(row['is_favorite']),
            "created_at": row['created_at'],
            "updated_at": row['updated_at'],
            "messages": json.loads(row['messages']) if row['messages'] else []
        }
    return chats


def save_chats(chats: dict) -> None:
    """Save all chats to database (bulk update)."""
    conn = get_db()
    cursor = conn.cursor()
    for chat_id, c in chats.items():
        cursor.execute("""
            INSERT OR REPLACE INTO chats 
            (id, project_id, title, is_favorite, created_at, updated_at, messages)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            c.get('id'), c.get('project_id'), c.get('title'),
            1 if c.get('is_favorite') else 0,
            c.get('created_at'), c.get('updated_at'),
            json.dumps(c.get('messages', []))
        ))
    conn.commit()
    conn.close()


def get_chat(chat_id: str) -> dict | None:
    """Get a single chat by ID from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row['id'],
        "project_id": row['project_id'],
        "title": row['title'],
        "is_favorite": bool(row['is_favorite']),
        "created_at": row['created_at'],
        "updated_at": row['updated_at'],
        "messages": json.loads(row['messages']) if row['messages'] else []
    }


def save_chat(chat_data: dict) -> None:
    """Save a single chat to database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO chats 
        (id, project_id, title, is_favorite, created_at, updated_at, messages)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        chat_data.get('id'), chat_data.get('project_id'), chat_data.get('title'),
        1 if chat_data.get('is_favorite') else 0,
        chat_data.get('created_at'), chat_data.get('updated_at'),
        json.dumps(chat_data.get('messages', []))
    ))
    conn.commit()
    conn.close()


def delete_chat(chat_id: str) -> bool:
    """Delete a chat from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def load_projects() -> dict:
    """Load all chat projects from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_projects")
    rows = cursor.fetchall()
    conn.close()
    
    projects = {}
    for row in rows:
        projects[row['id']] = {
            "id": row['id'],
            "title": row['title'],
            "description": row['description'],
            "tone": row['tone'],
            "instructions": row['instructions'],
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }
    return projects


def save_projects(projects: dict) -> None:
    """Save all chat projects to database."""
    conn = get_db()
    cursor = conn.cursor()
    for pid, p in projects.items():
        cursor.execute("""
            INSERT OR REPLACE INTO chat_projects 
            (id, title, description, tone, instructions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            p.get('id'), p.get('title'), p.get('description'),
            p.get('tone'), p.get('instructions'),
            p.get('created_at'), p.get('updated_at')
        ))
    conn.commit()
    conn.close()


def get_project(project_id: str) -> dict | None:
    """Get a single project by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row['id'],
        "title": row['title'],
        "description": row['description'],
        "tone": row['tone'],
        "instructions": row['instructions'],
        "created_at": row['created_at'],
        "updated_at": row['updated_at']
    }


def save_project(project: dict) -> None:
    """Save a single project to database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO chat_projects 
        (id, title, description, tone, instructions, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project.get('id'), project.get('title'), project.get('description'),
        project.get('tone'), project.get('instructions'),
        project.get('created_at'), project.get('updated_at')
    ))
    conn.commit()
    conn.close()


def delete_project(project_id: str) -> bool:
    """Delete a project from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_projects WHERE id = ?", (project_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# Source Groups
def load_source_groups() -> dict:
    """Load all source groups from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_groups")
    rows = cursor.fetchall()
    conn.close()
    
    groups = {}
    for row in rows:
        groups[row['id']] = {
            "id": row['id'],
            "title": row['title'],
            "thread_ids": json.loads(row['thread_ids']) if row['thread_ids'] else [],
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }
    return groups

def save_source_group(group: dict) -> None:
    """Save a single source group to database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO source_groups 
        (id, title, thread_ids, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        group.get('id'), group.get('title'),
        json.dumps(group.get('thread_ids', [])),
        group.get('created_at'), group.get('updated_at')
    ))
    conn.commit()
    conn.close()

def delete_source_group(group_id: str) -> bool:
    """Delete a source group from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM source_groups WHERE id = ?", (group_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
