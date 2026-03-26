import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path("rag_data/sira.db")

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    
    conn.executescript("""
        -- Settings table (one row or key-value)
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        -- Chat Projects table
        CREATE TABLE IF NOT EXISTS chat_projects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            tone TEXT,
            instructions TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Chats table
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT NOT NULL,
            is_favorite INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            messages TEXT, -- JSON string
            FOREIGN KEY (project_id) REFERENCES chat_projects (id) ON DELETE SET NULL
        );

        -- Source Groups (Instagram conversation groups)
        CREATE TABLE IF NOT EXISTS source_groups (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            thread_ids TEXT, -- JSON array string
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"✅ Database initialized at {DB_PATH}")
