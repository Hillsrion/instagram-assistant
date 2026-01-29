"""
SQLite Metadata Store for pre-filtering.
Allows filtering chunks BEFORE vector search.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Set, Tuple
from datetime import datetime

from .config import Config, default_config
from .chunker import Chunk


class MetadataStore:
    """
    SQLite Store for chunk metadata.

    Allows fast queries on:
    - Participants
    - Dates
    - Conversation ID
    - Message count
    """

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.db_path = self.config.index_dir / "metadata.db"
        self.conn: Optional[sqlite3.Connection] = None

    def _connect(self):
        """Connection to SQLite database."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

    def _create_tables(self):
        """Creates necessary tables."""
        self._connect()

        self.conn.executescript("""
            -- Main chunks table
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                chunk_id TEXT UNIQUE NOT NULL,
                conversation_id TEXT NOT NULL,
                date_start TEXT NOT NULL,
                date_end TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                file_source TEXT NOT NULL,
                year_start INTEGER,
                month_start INTEGER,
                year_end INTEGER,
                month_end INTEGER
            );

            -- Chunks <-> participants link table
            CREATE TABLE IF NOT EXISTS chunk_participants (
                chunk_idx INTEGER NOT NULL,
                participant TEXT NOT NULL,
                PRIMARY KEY (chunk_idx, participant)
            );

            -- Named entities table
            CREATE TABLE IF NOT EXISTS chunk_entities (
                chunk_idx INTEGER NOT NULL,
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (chunk_idx, category, value)
            );

            -- Indexes for fast lookups
            CREATE INDEX IF NOT EXISTS idx_conversation ON chunks(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_date_start ON chunks(date_start);
            CREATE INDEX IF NOT EXISTS idx_year_start ON chunks(year_start);
            CREATE INDEX IF NOT EXISTS idx_participant ON chunk_participants(participant);
            CREATE INDEX IF NOT EXISTS idx_entity_value ON chunk_entities(value);
        """)

        self.conn.commit()

    def build_index(self, chunks: List[Chunk]):
        """
        Builds the metadata index.

        Args:
            chunks: List of chunks to index
        """
        print(f"📋 Building metadata index ({len(chunks)} chunks)...")

        self._connect()
        self._create_tables()

        # Clear existing tables
        self.conn.execute("DELETE FROM chunk_participants")
        self.conn.execute("DELETE FROM chunks")
        self.conn.execute("DELETE FROM chunk_entities")

        # Insert chunks
        for idx, chunk in enumerate(chunks):
            # Parse dates
            try:
                dt_start = datetime.strptime(chunk.date_start, '%Y-%m-%d %H:%M:%S')
                dt_end = datetime.strptime(chunk.date_end, '%Y-%m-%d %H:%M:%S')
                year_start, month_start = dt_start.year, dt_start.month
                year_end, month_end = dt_end.year, dt_end.month
            except ValueError:
                year_start = month_start = year_end = month_end = None

            self.conn.execute("""
                INSERT INTO chunks
                (id, chunk_id, conversation_id, date_start, date_end,
                 message_count, file_source, year_start, month_start, year_end, month_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                idx, chunk.chunk_id, chunk.conversation_id,
                chunk.date_start, chunk.date_end, chunk.message_count,
                chunk.file_source, year_start, month_start, year_end, month_end
            ))

            # Insert participants
            for participant in chunk.participants:
                self.conn.execute("""
                    INSERT OR IGNORE INTO chunk_participants (chunk_idx, participant)
                    VALUES (?, ?)
                """, (idx, participant.lower()))

            # Insert entities
            if chunk.entities:
                for category, values in chunk.entities.items():
                    for value in values:
                        self.conn.execute("""
                            INSERT OR IGNORE INTO chunk_entities (chunk_idx, category, value)
                            VALUES (?, ?, ?)
                        """, (idx, category.lower(), value.lower()))

        self.conn.commit()
        print(f"✅ Metadata index built")

    def filter_by_participant(
        self,
        participant: str,
        chunk_indices: Optional[Set[int]] = None
    ) -> Set[int]:
        """
        Filter chunks by participant.

        Args:
            participant: Name (partial) of the participant
            chunk_indices: Starting set (None = all)

        Returns:
            Set of chunk indices
        """
        self._connect()

        query = """
            SELECT DISTINCT chunk_idx FROM chunk_participants
            WHERE participant LIKE ?
        """
        cursor = self.conn.execute(query, (f"%{participant.lower()}%",))
        result = {row[0] for row in cursor.fetchall()}

        if chunk_indices is not None:
            return result.intersection(chunk_indices)
        return result

    def filter_by_entity(
        self,
        value: str,
        category: Optional[str] = None,
        chunk_indices: Optional[Set[int]] = None
    ) -> Set[int]:
        """
        Filter chunks by named entity.
        
        Args:
            value: Entity value (e.g., "Paris")
            category: Optional category (e.g., "locations")
            chunk_indices: Starting set
            
        Returns:
            Set of chunk indices
        """
        self._connect()
        
        if category:
            query = """
                SELECT DISTINCT chunk_idx FROM chunk_entities
                WHERE category = ? AND value LIKE ?
            """
            params = (category.lower(), f"%{value.lower()}%")
        else:
            query = """
                SELECT DISTINCT chunk_idx FROM chunk_entities
                WHERE value LIKE ?
            """
            params = (f"%{value.lower()}%",)
            
        cursor = self.conn.execute(query, params)
        result = {row[0] for row in cursor.fetchall()}

        if chunk_indices is not None:
            return result.intersection(chunk_indices)
        return result

    def filter_by_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        chunk_indices: Optional[Set[int]] = None
    ) -> Set[int]:
        """
        Filter chunks by period.

        Args:
            start_date: Start date (format: YYYY, YYYY-MM, or YYYY-MM-DD)
            end_date: End date
            chunk_indices: Starting set

        Returns:
            Set of chunk indices
        """
        self._connect()

        conditions = []
        params = []

        if start_date:
            conditions.append("date_end >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("date_start <= ?")
            params.append(end_date)

        if not conditions:
            return chunk_indices if chunk_indices else set(range(self._count_chunks()))

        query = f"SELECT id FROM chunks WHERE {' AND '.join(conditions)}"
        cursor = self.conn.execute(query, params)
        result = {row[0] for row in cursor.fetchall()}

        if chunk_indices is not None:
            return result.intersection(chunk_indices)
        return result

    def filter_by_year(
        self,
        year: int,
        chunk_indices: Optional[Set[int]] = None
    ) -> Set[int]:
        """Filter chunks by year."""
        self._connect()

        query = """
            SELECT id FROM chunks
            WHERE year_start <= ? AND year_end >= ?
        """
        cursor = self.conn.execute(query, (year, year))
        result = {row[0] for row in cursor.fetchall()}

        if chunk_indices is not None:
            return result.intersection(chunk_indices)
        return result

    def filter_by_conversation(
        self,
        conversation_id: str,
        chunk_indices: Optional[Set[int]] = None
    ) -> Set[int]:
        """Filter chunks by conversation."""
        self._connect()

        query = "SELECT id FROM chunks WHERE conversation_id LIKE ?"
        cursor = self.conn.execute(query, (f"%{conversation_id}%",))
        result = {row[0] for row in cursor.fetchall()}

        if chunk_indices is not None:
            return result.intersection(chunk_indices)
        return result

    def get_all_participants(self) -> List[Tuple[str, int]]:
        """
        List all participants with their chunk count.

        Returns:
            List of (participant, count) sorted by count
        """
        self._connect()

        query = """
            SELECT participant, COUNT(*) as cnt
            FROM chunk_participants
            GROUP BY participant
            ORDER BY cnt DESC
        """
        cursor = self.conn.execute(query)
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_date_range(self) -> Tuple[str, str]:
        """Returns the global date range."""
        self._connect()

        cursor = self.conn.execute("""
            SELECT MIN(date_start), MAX(date_end) FROM chunks
        """)
        row = cursor.fetchone()
        return (row[0], row[1]) if row else (None, None)

    def _count_chunks(self) -> int:
        """Counts total chunks."""
        self._connect()
        cursor = self.conn.execute("SELECT COUNT(*) FROM chunks")
        return cursor.fetchone()[0]

    def get_adjacent_chunks(
        self,
        chunk_id: str,
        window: int = 1
    ) -> List[int]:
        """
        Retrieves indices of adjacent chunks (same conversation).

        Args:
            chunk_id: ID of the central chunk
            window: Number of chunks before/after

        Returns:
            List of chunk indices (including the central chunk)
        """
        self._connect()

        # Parse chunk_id to extract conversation_id and number
        parts = chunk_id.rsplit("_chunk_", 1)
        if len(parts) != 2:
            return []

        conv_id = parts[0]
        try:
            chunk_num = int(parts[1])
        except ValueError:
            return []

        # Find adjacent chunks
        adjacent_ids = []
        for offset in range(-window, window + 1):
            target_id = f"{conv_id}_chunk_{chunk_num + offset:03d}"
            adjacent_ids.append(target_id)

        # Retrieve indices
        placeholders = ','.join('?' * len(adjacent_ids))
        query = f"SELECT id FROM chunks WHERE chunk_id IN ({placeholders})"
        cursor = self.conn.execute(query, adjacent_ids)

        return [row[0] for row in cursor.fetchall()]

    def close(self):
        """Closes the connection."""
        if self.conn:
            self.conn.close()
            self.conn = None