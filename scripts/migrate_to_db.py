import json
import sqlite3
from pathlib import Path
from api.database import get_db, init_db

# Paths
CHATS_FILE = Path("rag_data/chats.json")
CHAT_PROJECTS_FILE = Path("rag_data/chat_projects.json")
SETTINGS_FILE = Path("rag_data/settings.json")
SOURCE_GROUPS_FILE = Path("rag_data/instagram_groups.json")

def migrate():
    # Ensure tables exist
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # 1. Migrate Settings
    if SETTINGS_FILE.exists():
        print(f"Migrating settings from {SETTINGS_FILE}...")
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            for k, v in settings.items():
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
        print("✅ Settings migrated")

    # 2. Migrate Projects
    if CHAT_PROJECTS_FILE.exists():
        print(f"Migrating projects from {CHAT_PROJECTS_FILE}...")
        try:
            with open(CHAT_PROJECTS_FILE, 'r', encoding='utf-8') as f:
                projects = json.load(f)
                # Projects is likely a dict {id: data} or list [data]
                if isinstance(projects, dict):
                    projects = list(projects.values())
                
                for p in projects:
                    cursor.execute("""
                        INSERT OR REPLACE INTO chat_projects 
                        (id, title, description, tone, instructions, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        p.get('id'), p.get('title'), p.get('description'),
                        p.get('tone'), p.get('instructions'),
                        p.get('created_at'), p.get('updated_at')
                    ))
            print("✅ Projects migrated")
        except json.JSONDecodeError:
            print("⚠️ Project file empty or malformed - skipping")

    # 3. Migrate Chats
    if CHATS_FILE.exists():
        print(f"Migrating chats from {CHATS_FILE}...")
        try:
            with open(CHATS_FILE, 'r', encoding='utf-8') as f:
                chats = json.load(f)
                if isinstance(chats, dict):
                    chats = list(chats.values())
                
                for c in chats:
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
            print("✅ Chats migrated")
        except json.JSONDecodeError:
            print("⚠️ Chat file empty or malformed - skipping")

    # 4. Migrate Source Groups
    if SOURCE_GROUPS_FILE.exists():
        print(f"Migrating source groups from {SOURCE_GROUPS_FILE}...")
        try:
            with open(SOURCE_GROUPS_FILE, 'r', encoding='utf-8') as f:
                groups = json.load(f)
                if isinstance(groups, dict):
                    groups = list(groups.values())
                
                for g in groups:
                    cursor.execute("""
                        INSERT OR REPLACE INTO source_groups 
                        (id, title, thread_ids, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        g.get('id'), g.get('title'), 
                        json.dumps(g.get('thread_ids', [])),
                        g.get('created_at'), g.get('updated_at')
                    ))
            print("✅ Source groups migrated")
        except json.JSONDecodeError:
            print("⚠️ Source groups file empty - skipping")

    conn.commit()
    conn.close()
    print("\n🚀 Migration complete!")

if __name__ == "__main__":
    migrate()
