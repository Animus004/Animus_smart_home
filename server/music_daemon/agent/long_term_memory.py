"""
================================================================================
ANIMUS SMART ROOM — PERSISTENT LONG-TERM EPISTEMIC MEMORY ENGINE
================================================================================
SQLite-backed persistent long-term associative memory for Animus.
Maintains user facts, learned behavioral habits, episodic conversation recall,
and preference matrices across all server lifecycles and daemon restarts.
================================================================================
"""

from __future__ import annotations
import os
import sqlite3
import time
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.long_term_memory")


class LongTermMemoryStore:
    """
    Persistent SQLite Epistemic Memory Engine.
    Zero-Cloud, 100% Local, ACID-compliant storage for Animus Brain.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / "secrets" / "agent_memory.db"
        else:
            self.db_path = db_path
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes database schema with indexed memory tables."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. User Facts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # 2. Learned Habits Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_habits (
                    habit_key TEXT PRIMARY KEY,
                    context TEXT NOT NULL,
                    preferred_action TEXT NOT NULL,
                    preferred_parameters TEXT NOT NULL,
                    observation_count INTEGER NOT NULL DEFAULT 1,
                    last_observed REAL NOT NULL
                )
            """)

            # 3. Conversation Episodes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    user_utterance TEXT NOT NULL,
                    agent_response TEXT NOT NULL,
                    intent_category TEXT NOT NULL,
                    extracted_topics TEXT,
                    mood_vibe TEXT
                )
            """)

            # Indexes for ultra-fast associative retrieval
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_cat ON user_facts(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_habits_context ON learned_habits(context)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_time ON conversation_episodes(timestamp)")
            conn.commit()
        finally:
            conn.close()

        # Seed initial core identity facts if table is empty
        self._seed_core_identity()

    def _seed_core_identity(self) -> None:
        """Seeds stable user profile facts if not already present."""
        defaults = [
            ("user_name", "Sayan Halder", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("user_nickname", "buddy", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("home_location", "Kalyani, West Bengal (741235)", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("preferred_ac_movie_temp", "22", "USER_PREFERENCE", "BEHAVIORAL_BASELINE"),
            ("preferred_ac_default_temp", "24", "USER_PREFERENCE", "BEHAVIORAL_BASELINE"),
            ("preferred_music_devices", "Speakers (LG SNC4R(79))", "USER_PREFERENCE", "HARDWARE_BASELINE"),
            ("preferred_movie_screen", "Zebronics Android Projector", "USER_PREFERENCE", "HARDWARE_BASELINE"),
        ]
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            for key, val, cat, src in defaults:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_facts (key, value, category, confidence, source, created_at, updated_at)
                    VALUES (?, ?, ?, 1.0, ?, ?, ?)
                """, (key, val, cat, src, time.time(), time.time()))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # Fact & Preference CRUD
    # =========================================================================

    def save_fact(self, key: str, value: str, category: str = "STABLE_USER_FACT", source: str = "USER_CONVERSATION") -> None:
        """Saves or updates a permanent fact about the user."""
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_facts (key, value, category, confidence, source, created_at, updated_at)
                VALUES (?, ?, ?, 1.0, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    category=excluded.category,
                    confidence=1.0,
                    source=excluded.source,
                    updated_at=excluded.updated_at
            """, (key.strip().lower(), value.strip(), category, source, now, now))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Saved fact: {key} = {value}")
        finally:
            conn.close()

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieves a stored fact by key."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_facts WHERE key = ?", (key.strip().lower(),))
            row = cursor.fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    def get_all_facts(self) -> Dict[str, str]:
        """Returns all stored facts as a key-value dictionary."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_facts ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()

    # =========================================================================
    # Behavioral Habit & Preference Learning
    # =========================================================================

    def record_habit_observation(self, context: str, action: str, parameters: Dict[str, Any]) -> None:
        """Records an observed user choice to build predictive habits."""
        habit_key = f"{context.lower()}:{action.lower()}"
        param_str = json.dumps(parameters, separators=(',', ':'))
        now = time.time()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learned_habits (habit_key, context, preferred_action, preferred_parameters, observation_count, last_observed)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(habit_key) DO UPDATE SET
                    preferred_parameters=excluded.preferred_parameters,
                    observation_count=learned_habits.observation_count + 1,
                    last_observed=excluded.last_observed
            """, (habit_key, context.lower(), action.lower(), param_str, now))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Updated habit: {habit_key}")
        finally:
            conn.close()

    def get_habit(self, context: str) -> Optional[Dict[str, Any]]:
        """Retrieves the strongest learned habit for a given room context."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preferred_action, preferred_parameters, observation_count
                FROM learned_habits
                WHERE context = ?
                ORDER BY observation_count DESC, last_observed DESC
                LIMIT 1
            """, (context.lower(),))
            row = cursor.fetchone()
            if row:
                return {
                    "action": row["preferred_action"],
                    "parameters": json.loads(row["preferred_parameters"]),
                    "count": row["observation_count"]
                }
            return None
        finally:
            conn.close()

    # =========================================================================
    # Conversation Episodic Recall
    # =========================================================================

    def record_conversation_turn(
        self,
        user_utterance: str,
        agent_response: str,
        intent_category: str = "GENERAL",
        topics: Optional[List[str]] = None,
        mood: Optional[str] = None
    ) -> None:
        """Saves a conversation turn into persistent episodic history."""
        now = time.time()
        topics_str = json.dumps(topics or [])
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_episodes (timestamp, user_utterance, agent_response, intent_category, extracted_topics, mood_vibe)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, user_utterance.strip(), agent_response.strip(), intent_category, topics_str, mood or "NEUTRAL"))
            conn.commit()
        finally:
            conn.close()

        # Trigger automatic background fact extraction from user utterance
        self.extract_facts_from_utterance(user_utterance)

    def search_past_conversations(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Performs associative search across historical conversation episodes."""
        words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 2]
        if not words:
            return []

        like_clauses = " OR ".join(["user_utterance LIKE ? OR agent_response LIKE ?" for _ in words])
        params = []
        for w in words:
            params.extend([f"%{w}%", f"%{w}%"])

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT timestamp, user_utterance, agent_response, intent_category
                FROM conversation_episodes
                WHERE {like_clauses}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """, params)
            rows = cursor.fetchall()
            return [
                {
                    "timestamp": r["timestamp"],
                    "user": r["user_utterance"],
                    "agent": r["agent_response"],
                    "intent": r["intent_category"]
                }
                for r in rows
            ]
        finally:
            conn.close()

    # =========================================================================
    # Natural Language Fact & Preference Extractor
    # =========================================================================

    def extract_facts_from_utterance(self, text: str) -> List[Tuple[str, str]]:
        """
        Extracts semantic user preferences and facts from natural language.
        e.g. "I love Interstellar", "My favorite music is Lofi", "I sleep at 1 AM"
        """
        extracted = []

        patterns = [
            # "my favorite X is Y"
            (r'\bmy\s+favorite\s+([a-zA-Z_]+)\s+is\s+([^,.\n]+)', lambda m: (f"favorite_{m.group(1).lower().replace(' ', '_')}", m.group(2).strip())),
            # "i love / i like X"
            (r'\bi\s+(?:love|really\s+like|enjoy)\s+([^,.\n]+)', lambda m: (f"liked_topic_{m.group(1).lower()[:15].replace(' ', '_')}", m.group(1).strip())),
            # "i prefer X"
            (r'\bi\s+prefer\s+([^,.\n]+)', lambda m: (f"preference_{m.group(1).lower()[:15].replace(' ', '_')}", m.group(1).strip())),
            # "my birthday is X"
            (r'\bmy\s+birthday\s+is\s+([^,.\n]+)', lambda m: ("birthday", m.group(1).strip())),
            # "remind me that X is Y"
            (r'\bremember\s+that\s+([^,.\n]+)\s+is\s+([^,.\n]+)', lambda m: (m.group(1).lower().strip().replace(' ', '_'), m.group(2).strip())),
        ]

        for pat, extractor in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                k, v = extractor(m)
                self.save_fact(k, v, category="USER_PREFERENCE", source="NATURAL_EXTRACTION")
                extracted.append((k, v))

        return extracted

    def build_memory_context_prompt(self, current_query: str) -> str:
        """
        Generates a concise, highly relevant long-term memory prompt block
        ready for direct injection into the LLM context window.
        """
        facts = self.get_all_facts()
        past_turns = self.search_past_conversations(current_query, limit=2)

        lines = ["[LONG-TERM EPITEMIC MEMORY]"]
        if facts:
            lines.append("Confirmed User Knowledge:")
            for k, v in list(facts.items())[:8]:
                lines.append(f"  • {k}: {v}")

        if past_turns:
            lines.append("Relevant Past Context:")
            for p in past_turns:
                lines.append(f"  • User: \"{p['user']}\" ➔ Sonia: \"{p['agent']}\"")

        return "\n".join(lines)


# Global singleton instance
_global_lt_memory: Optional[LongTermMemoryStore] = None


def get_long_term_memory() -> LongTermMemoryStore:
    """Returns or initializes the global LongTermMemoryStore singleton."""
    global _global_lt_memory
    if _global_lt_memory is None:
        _global_lt_memory = LongTermMemoryStore()
    return _global_lt_memory
