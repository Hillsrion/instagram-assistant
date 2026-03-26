"""
SQLite storage for Instagram source groups.
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from api.database import get_db

def load_source_groups() -> Dict[str, Any]:
    """Load all source groups from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_groups")
    rows = cursor.fetchall()
    
    if not rows:
        # Create default groups if none exist
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
        for g in defaults.values():
            cursor.execute("""
                INSERT INTO source_groups (id, title, thread_ids, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (g['id'], g['title'], json.dumps(g['thread_ids']), g['created_at'], g['updated_at']))
        conn.commit()
        conn.close()
        return defaults

    groups = {}
    for row in rows:
        groups[row['id']] = {
            "id": row['id'],
            "title": row['title'],
            "thread_ids": json.loads(row['thread_ids']) if row['thread_ids'] else [],
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }
    conn.close()
    return groups

def save_source_groups(groups: Dict[str, Any]):
    """Save all source groups to database (bulk)."""
    conn = get_db()
    cursor = conn.cursor()
    for gid, g in groups.items():
        cursor.execute("""
            INSERT OR REPLACE INTO source_groups (id, title, thread_ids, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (g['id'], g['title'], json.dumps(g.get('thread_ids', [])), g.get('created_at', ''), g.get('updated_at', '')))
    conn.commit()
    conn.close()

def get_source_group(group_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific source group from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_groups WHERE id = ?", (group_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row['id'],
        "title": row['title'],
        "thread_ids": json.loads(row['thread_ids']) if row['thread_ids'] else [],
        "created_at": row['created_at'],
        "updated_at": row['updated_at']
    }

def save_source_group(group: Dict[str, Any]):
    """Save or update a single source group in database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO source_groups (id, title, thread_ids, created_at, updated_at)
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
