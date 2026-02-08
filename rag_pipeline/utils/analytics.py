"""
Analytics module for conversation statistics and insights.
Direct SQL-based analytics without LLM involvement for instant results.
"""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from rag_pipeline.core.config import Config, default_config


class ConversationAnalytics:
    """
    Provides analytics and statistics on conversations.

    All methods use direct SQL queries for fast, accurate results.
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

    def count_messages(
        self,
        participant: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> int:
        """
        Count total messages with optional filters.

        Args:
            participant: Filter by participant name (partial match)
            date_start: Start date (ISO format)
            date_end: End date (ISO format)
            conversation_id: Filter by conversation ID

        Returns:
            Total message count matching filters
        """
        self._connect()

        # Build query dynamically
        conditions = []
        params = []

        if date_start:
            conditions.append("date_end >= ?")
            params.append(date_start)

        if date_end:
            conditions.append("date_start <= ?")
            params.append(date_end)

        if conversation_id:
            conditions.append("conversation_id LIKE ?")
            params.append(f"%{conversation_id}%")

        # Base query
        if participant:
            # Join with participants table
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT SUM(chunks.message_count) as total
                FROM chunks
                WHERE {where_clause}
                AND chunks.id IN (
                    SELECT DISTINCT chunk_idx FROM chunk_participants
                    WHERE participant LIKE ?
                )
            """
            params.append(f"%{participant.lower()}%")
        else:
            # No participant filter
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT SUM(message_count) as total
                FROM chunks
                WHERE {where_clause}
            """

        cursor = self.conn.execute(query, params)
        result = cursor.fetchone()
        return result[0] or 0 if result else 0

    def get_participant_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all participants.

        Returns:
            Dict mapping participant name to stats:
            {
                "participant_name": {
                    "message_count": int,
                    "conversations": int,
                    "chunks": int,
                    "date_start": str,
                    "date_end": str
                }
            }
        """
        self._connect()

        query = """
            SELECT
                cp.participant,
                SUM(c.message_count) as total_messages,
                COUNT(DISTINCT c.conversation_id) as conversations,
                COUNT(DISTINCT cp.chunk_idx) as chunks,
                MIN(c.date_start) as first_date,
                MAX(c.date_end) as last_date
            FROM chunk_participants cp
            JOIN chunks c ON cp.chunk_idx = c.id
            GROUP BY cp.participant
            ORDER BY total_messages DESC
        """

        cursor = self.conn.execute(query)
        results = {}

        for row in cursor.fetchall():
            results[row[0]] = {
                "message_count": row[1] or 0,
                "conversations": row[2] or 0,
                "chunks": row[3] or 0,
                "date_start": row[4],
                "date_end": row[5]
            }

        return results

    def get_conversation_timeline(
        self,
        participant: str
    ) -> List[Dict]:
        """
        Get timeline of conversations with a specific participant.

        Args:
            participant: Participant name

        Returns:
            List of conversation records sorted chronologically:
            [
                {
                    "conversation_id": str,
                    "date_start": str,
                    "date_end": str,
                    "message_count": int,
                    "chunks": int
                }
            ]
        """
        self._connect()

        query = """
            SELECT
                DISTINCT c.conversation_id,
                MIN(c.date_start) as conv_start,
                MAX(c.date_end) as conv_end,
                SUM(c.message_count) as total_messages,
                COUNT(*) as chunks
            FROM chunks c
            WHERE c.id IN (
                SELECT DISTINCT chunk_idx FROM chunk_participants
                WHERE participant LIKE ?
            )
            GROUP BY c.conversation_id
            ORDER BY conv_start ASC
        """

        cursor = self.conn.execute(query, (f"%{participant.lower()}%",))
        results = []

        for row in cursor.fetchall():
            results.append({
                "conversation_id": row[0],
                "date_start": row[1],
                "date_end": row[2],
                "message_count": row[3] or 0,
                "chunks": row[4] or 0
            })

        return results

    def get_topic_participants(self, topic: str) -> List[str]:
        """
        Get list of participants who discussed a specific topic.

        Args:
            topic: Topic/entity name (will search in named entities)

        Returns:
            List of participant names (deduplicated)
        """
        self._connect()

        query = """
            SELECT DISTINCT cp.participant
            FROM chunk_participants cp
            WHERE cp.chunk_idx IN (
                SELECT DISTINCT chunk_idx FROM chunk_entities
                WHERE value LIKE ?
            )
            ORDER BY cp.participant ASC
        """

        cursor = self.conn.execute(query, (f"%{topic.lower()}%",))
        return [row[0] for row in cursor.fetchall()]

    def get_participants_by_conversation(
        self,
        conversation_id: str
    ) -> List[Dict]:
        """
        Get all participants in a conversation with message counts.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of participants with their message counts
        """
        self._connect()

        query = """
            SELECT
                cp.participant,
                SUM(c.message_count) as message_count,
                COUNT(*) as chunks
            FROM chunk_participants cp
            JOIN chunks c ON cp.chunk_idx = c.id
            WHERE c.conversation_id LIKE ?
            GROUP BY cp.participant
            ORDER BY message_count DESC
        """

        cursor = self.conn.execute(
            query,
            (f"%{conversation_id}%",)
        )
        results = []

        for row in cursor.fetchall():
            results.append({
                "participant": row[0],
                "message_count": row[1] or 0,
                "chunks": row[2] or 0
            })

        return results

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the overall date range of all conversations.

        Returns:
            Tuple of (start_date, end_date) in ISO format
        """
        self._connect()

        cursor = self.conn.execute("""
            SELECT MIN(date_start), MAX(date_end) FROM chunks
        """)
        row = cursor.fetchone()
        return (row[0], row[1]) if row and row[0] else (None, None)

    def get_conversation_stats(self) -> Dict:
        """
        Get overall statistics about all conversations.

        Returns:
            {
                "total_messages": int,
                "total_conversations": int,
                "total_chunks": int,
                "total_participants": int,
                "date_start": str,
                "date_end": str
            }
        """
        self._connect()

        cursor = self.conn.execute("""
            SELECT
                SUM(message_count) as total_messages,
                COUNT(DISTINCT conversation_id) as conversations,
                COUNT(*) as chunks,
                (SELECT COUNT(DISTINCT participant) FROM chunk_participants) as participants,
                MIN(date_start) as date_start,
                MAX(date_end) as date_end
            FROM chunks
        """)
        row = cursor.fetchone()

        if not row:
            return {
                "total_messages": 0,
                "total_conversations": 0,
                "total_chunks": 0,
                "total_participants": 0,
                "date_start": None,
                "date_end": None
            }

        return {
            "total_messages": row[0] or 0,
            "total_conversations": row[1] or 0,
            "total_chunks": row[2] or 0,
            "total_participants": row[3] or 0,
            "date_start": row[4],
            "date_end": row[5]
        }

    def get_message_count_by_month(
        self,
        participant: Optional[str] = None
    ) -> List[Dict]:
        """
        Get message counts grouped by month.

        Args:
            participant: Optional participant filter

        Returns:
            List of monthly stats:
            [
                {
                    "year": int,
                    "month": int,
                    "month_name": str,
                    "message_count": int
                }
            ]
        """
        self._connect()

        if participant:
            query = """
                SELECT
                    c.year_start as year,
                    c.month_start as month,
                    SUM(c.message_count) as total
                FROM chunks c
                WHERE c.id IN (
                    SELECT DISTINCT chunk_idx FROM chunk_participants
                    WHERE participant LIKE ?
                )
                GROUP BY year, month
                ORDER BY year, month
            """
            params = (f"%{participant.lower()}%",)
        else:
            query = """
                SELECT
                    year_start as year,
                    month_start as month,
                    SUM(message_count) as total
                FROM chunks
                GROUP BY year, month
                ORDER BY year, month
            """
            params = ()

        cursor = self.conn.execute(query, params)
        results = []
        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        for row in cursor.fetchall():
            year, month, total = row[0], row[1], row[2]
            results.append({
                "year": year,
                "month": month,
                "month_name": month_names[month] if month else "",
                "message_count": total or 0
            })

        return results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
