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
from datetime import datetime
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.long_term_memory")


class LongTermMemoryStore:
    """
    Persistent SQLite Epistemic Memory Engine.
    Zero-Cloud, 100% Local, ACID-compliant storage for Animus Brain.
    """

    def __init__(self, db_path: Optional[Any] = None):
        self.is_memory = False
        self._keepalive_conn: Optional[sqlite3.Connection] = None
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / "secrets" / "agent_memory.db"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn_str = str(self.db_path)
            self._is_uri = False
        elif str(db_path) == ":memory:":
            self.is_memory = True
            mem_id = uuid.uuid4().hex
            self._conn_str = f"file:mem_{mem_id}?mode=memory&cache=shared"
            self._is_uri = True
            self._keepalive_conn = sqlite3.connect(self._conn_str, uri=True)
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn_str = str(self.db_path)
            self._is_uri = False
        
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_uri:
            conn = sqlite3.connect(self._conn_str, uri=True)
        else:
            conn = sqlite3.connect(self._conn_str)
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

            # 4. Persistent Goals Table (Cross-Session Continuity)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persistent_goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    target_category TEXT DEFAULT 'GENERAL',
                    subgoals_json TEXT NOT NULL DEFAULT '[]',
                    notes TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # 5. User Tasks & Priorities Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'MEDIUM',
                    category TEXT NOT NULL DEFAULT 'GENERAL',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # 6. Astra Structured Personal Epistemic Memory Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS structured_personal_memory (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    context TEXT,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_accessed_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

            # 7. Work Focus Sessions Table (Deep Work & Seated Telemetry)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS work_focus_sessions (
                    id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    ended_at REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    milestone_title TEXT,
                    breaks_taken INTEGER DEFAULT 0,
                    completion_type TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                )
            """)

            # Indexes for ultra-fast associative retrieval
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_cat ON user_facts(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_habits_context ON learned_habits(context)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_time ON conversation_episodes(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON persistent_goals(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON user_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spm_type ON structured_personal_memory(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spm_subject ON structured_personal_memory(subject)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spm_context ON structured_personal_memory(context)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_time ON work_focus_sessions(started_at)")
            conn.commit()
        finally:
            conn.close()

        # Seed initial core identity facts, goals, tasks, and structured baseline
        self._seed_core_identity()
        self._seed_structured_baseline()

    def _seed_core_identity(self) -> None:
        """Seeds stable user profile facts, baseline goal, and tasks if not already present."""
        defaults = [
            ("user_name", "Sayan Halder", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("user_nickname", "Sir", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("home_location", "Kalyani, West Bengal (741235)", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("preferred_ac_movie_temp", "22", "USER_PREFERENCE", "BEHAVIORAL_BASELINE"),
            ("preferred_ac_default_temp", "24", "USER_PREFERENCE", "BEHAVIORAL_BASELINE"),
            ("preferred_music_devices", "Speakers (LG SNC4R(79))", "USER_PREFERENCE", "HARDWARE_BASELINE"),
            ("preferred_movie_screen", "Zebronics Android Projector", "USER_PREFERENCE", "HARDWARE_BASELINE"),
        ]
        career_defaults = [
            ("career_target", "Data Analyst", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("self_teaching_platform", "ChatGPT & Project-Based Learning", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("completed_projects", "3 Excel Projects (Advanced formulas, data cleaning, sales dashboards)", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("current_project", "Blinkit Stock-Out SQL Analysis (Inventory turnover, out-of-stock duration, lost revenue calculation, window functions & CTEs)", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
            ("job_search_target", "Junior / Mid-Level Data Analyst", "STABLE_USER_FACT", "USER_EXPLICIT_SPECIFICATION"),
        ]

        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Migration: Ensure existing databases update legacy 'buddy' to 'Sir'
            cursor.execute("UPDATE user_facts SET value = 'Sir', updated_at = ? WHERE key IN ('user_nickname', 'preferred_address') AND value = 'buddy'", (now,))
            conn.commit()

            for key, val, cat, src in defaults + career_defaults:
                cursor.execute("""
                    INSERT OR REPLACE INTO user_facts (key, value, category, confidence, source, created_at, updated_at)
                    VALUES (?, ?, ?, 1.0, ?, ?, ?)
                """, (key, val, cat, src, now, now))

            # Seed / Ensure Data Analyst career roadmap is the primary active persistent goal
            data_analyst_subgoals = json.dumps([
                {"id": 1, "title": "Completed 3 Excel Portfolio Projects (Formulas, Data Cleaning, Sales Dashboards)", "completed": True, "is_current": False},
                {"id": 2, "title": "Blinkit Stock-Out SQL: Schema design & dark store inventory modeling", "completed": True, "is_current": False},
                {"id": 3, "title": "Blinkit Stock-Out SQL: Calculate out-of-stock duration & frequency per dark store using CTEs & LAG()", "completed": False, "is_current": True},
                {"id": 4, "title": "Blinkit Stock-Out SQL: Estimate lost revenue & customer demand penalty per out-of-stock SKU", "completed": False, "is_current": False},
                {"id": 5, "title": "Blinkit Stock-Out SQL: Write executive business summary and inventory replenishment recommendations", "completed": False, "is_current": False},
                {"id": 6, "title": "Build Power BI / Tableau interactive dashboard for Blinkit Project", "completed": False, "is_current": False},
                {"id": 7, "title": "Resume & GitHub portfolio case study write-up", "completed": False, "is_current": False},
                {"id": 8, "title": "SQL technical mock interviews & query speed challenges", "completed": False, "is_current": False}
            ])
            cursor.execute("""
                INSERT OR REPLACE INTO persistent_goals (id, title, status, target_category, subgoals_json, notes, created_at, updated_at)
                VALUES ('goal_data_analyst_career', 'Land Data Analyst Job — Portfolio & SQL Mastery', 'ACTIVE', 'CAREER', ?, 'Primary career objective: Self-taught Data Analyst roadmap', ?, ?)
            """, (data_analyst_subgoals, now, now))

            # Seed default tasks if table is empty or missing Blinkit tasks
            cursor.execute("SELECT COUNT(*) as cnt FROM user_tasks WHERE id LIKE 'task_blinkit%'")
            if cursor.fetchone()["cnt"] == 0:
                career_tasks = [
                    ("task_blinkit_duration", "Blinkit SQL: Calculate OOS duration per dark store with LAG()", "Window function CTE to measure out-of-stock window", "HIGH", "LEARNING"),
                    ("task_blinkit_revenue", "Blinkit SQL: Draft lost revenue estimation formula", "Join OOS events with inventory price table", "HIGH", "LEARNING"),
                    ("task_guitar", "Guitar practice session", "30-45 mins fingerstyle and chords practice", "MEDIUM", "PERSONAL"),
                ]
                for tid, ttitle, tdesc, tpri, tcat in career_tasks:
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_tasks (id, title, description, priority, category, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
                    """, (tid, ttitle, tdesc, tpri, tcat, now, now))

            conn.commit()
        finally:
            conn.close()

    def _seed_structured_baseline(self) -> None:
        """Seeds verified structured personal memories if not already present."""
        defaults = [
            # 1. Preferences
            ("pref_lighting_movie", "preference", "lighting", "movie", "low brightness (warm bias)", 1.0, "user"),
            ("pref_work_env", "preference", "work", "SQL/data analytics", "quiet environment, 15% volume, 24°C AC setpoint", 1.0, "user"),
            ("pref_movie_ac", "preference", "ac", "movie", "22°C cool setpoint", 1.0, "user"),
            ("pref_guitar", "preference", "guitar", "afternoon", "practice is often useful", 0.75, "user"),
            ("pref_streaming", "preference", "streaming", "movie", "preferred: Netflix, Apple TV, Prime Video, YouTube", 1.0, "user"),

            # 2. Hardware / Device Knowledge
            ("dev_projector", "device_knowledge", "projector", "hardware", "Zebronics PixaPlay 25 Android Projector (IP: 192.168.0.180)", 1.0, "verified_hardware"),
            ("dev_soundbar", "device_knowledge", "soundbar", "hardware", "LG SNC4R(79) Soundbar connected via PC Bluetooth/HDMI", 1.0, "verified_hardware"),
            ("dev_ac", "device_knowledge", "ac", "hardware", "Smart AC (16°C to 30°C, modes: COOL, AUTO, DRY, FAN)", 1.0, "verified_hardware"),

            # 3. Stable Facts
            ("fact_user_identity", "fact", "user", "identity", "Sayan Halder, addressed respectfully as Sir", 1.0, "user"),
            ("fact_location", "fact", "location", "general", "Kalyani, West Bengal (PIN: 741235)", 1.0, "user"),
            ("fact_career_goal", "fact", "career", "career_target", "Aspiring Junior / Mid-Level Data Analyst", 1.0, "user"),

            # 4. Project Knowledge
            ("proj_sql_blinkit", "project_knowledge", "sql", "SQL/data analytics", "Blinkit Stock-Out SQL Analysis: schema modeling, out-of-stock duration with CTEs & LAG(), lost revenue estimation", 1.0, "user"),
            ("proj_excel_portfolio", "project_knowledge", "excel", "career", "3 Completed Excel Portfolio Projects: Advanced formulas, data cleaning, interactive sales dashboards", 1.0, "user"),
            ("proj_bi_dashboard", "project_knowledge", "power_bi", "career", "Power BI / Tableau dashboard planned for Blinkit inventory metrics", 0.9, "user"),

            # 5. Routines
            ("routine_work", "routine", "work", "morning/afternoon", "Work and SQL self-study generally starts after 11:00 AM", 0.95, "user"),
            ("routine_guitar", "routine", "guitar", "afternoon/evening", "Guitar practice preferred around 17:00 or after lunch", 0.85, "user"),

            # 6. Constraints
            ("constraint_address", "constraint", "address", "communication", "Always address the user as Sir with quiet confidence and executive poise", 1.0, "user"),
            ("constraint_privacy", "constraint", "privacy", "security", "100% offline local privacy for daily smart home operations", 1.0, "user"),
            ("constraint_reminders", "constraint", "reminders", "autonomy", "Zero autonomous reminders; explicit user day and time confirmation required", 1.0, "user"),
            ("constraint_ac_limits", "constraint", "ac", "safety", "Strict physical bounds: 16°C to 30°C only", 1.0, "verified_hardware")
        ]
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            for mid, mtype, msubj, mctx, mval, mconf, msrc in defaults:
                cursor.execute("""
                    INSERT OR IGNORE INTO structured_personal_memory
                    (id, type, subject, context, value, confidence, source, created_at, updated_at, last_accessed_at, access_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '{}')
                """, (mid, mtype, msubj, mctx, mval, mconf, msrc, now, now, now))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # Astra Structured Personal Epistemic Memory CRUD & Associative Retrieval
    # =========================================================================

    def store_structured_memory(
        self,
        memory_type: str,
        subject: str,
        value: Any,
        context: Optional[str] = None,
        confidence: float = 1.0,
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stores or updates a structured personal epistemic memory.
        If an item with matching subject, type, and context exists, it is updated;
        otherwise, a new item is created.
        """
        now = time.time()
        s_type = str(memory_type).lower().replace("memorytype.", "")
        s_subj = str(subject).strip().lower()
        s_ctx = str(context).strip() if context else None
        s_val = str(value).strip() if not isinstance(value, str) else value
        s_meta = json.dumps(metadata or {})

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if s_ctx:
                cursor.execute(
                    "SELECT id, access_count FROM structured_personal_memory WHERE type = ? AND subject = ? AND context = ?",
                    (s_type, s_subj, s_ctx)
                )
            else:
                cursor.execute(
                    "SELECT id, access_count FROM structured_personal_memory WHERE type = ? AND subject = ? AND context IS NULL",
                    (s_type, s_subj)
                )
            existing = cursor.fetchone()

            if existing:
                item_id = existing["id"]
                cursor.execute("""
                    UPDATE structured_personal_memory
                    SET value = ?, confidence = ?, source = ?, updated_at = ?, metadata = ?
                    WHERE id = ?
                """, (s_val, confidence, source, now, s_meta, item_id))
            else:
                item_id = memory_id or f"mem_{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO structured_personal_memory
                    (id, type, subject, context, value, confidence, source, created_at, updated_at, last_accessed_at, access_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (item_id, s_type, s_subj, s_ctx, s_val, confidence, source, now, now, now, s_meta))

            conn.commit()
            logger.info(f"[STRUCTURED_MEMORY] Stored {s_type} for subject '{s_subj}' (context='{s_ctx}'): {s_val}")
            return {
                "id": item_id,
                "type": s_type,
                "subject": s_subj,
                "context": s_ctx,
                "value": s_val,
                "confidence": confidence,
                "source": source
            }
        finally:
            conn.close()

    def get_structured_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single structured memory by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM structured_personal_memory WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_structured_memories(self, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all structured personal memories, optionally filtered by type."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if memory_type:
                cursor.execute(
                    "SELECT * FROM structured_personal_memory WHERE type = ? ORDER BY updated_at DESC",
                    (memory_type.lower(),)
                )
            else:
                cursor.execute("SELECT * FROM structured_personal_memory ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_structured_memory(self, memory_id: str) -> bool:
        """Deletes a structured memory item by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM structured_personal_memory WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def retrieve_relevant_structured_memories(
        self,
        query: str,
        active_mode: Optional[str] = None,
        context: Optional[str] = None,
        limit: int = 6,
        include_universal_constraints: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Contextual Associative Retrieval Engine.
        Retrieves ONLY memories relevant to the user query and situational state,
        avoiding context dumping and memory hallucination.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM structured_personal_memory ORDER BY updated_at DESC")
            all_rows = [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

        if not all_rows:
            return []

        lower_q = (query or "").strip().lower()
        lower_mode = (active_mode or "").strip().lower()
        lower_ctx = (context or "").strip().lower()
        combined_text = f"{lower_q} {lower_mode} {lower_ctx}"

        # Topic detection flags for contextual association
        topic_work = any(w in combined_text for w in [
            "work", "sql", "code", "study", "data", "analyst", "blinkit", "cte", "lag", "excel", "table", "query", "queries"
        ])
        topic_movie = any(w in combined_text for w in [
            "movie", "cinema", "film", "watch", "projector", "netflix", "prime", "stream", "screen", "relax", "video"
        ])
        topic_guitar = any(w in combined_text for w in [
            "guitar", "instrument", "chords", "play guitar", "song", "practice"
        ])
        topic_climate = any(w in combined_text for w in [
            "ac", "temperature", "temp", "cool", "cold", "heat", "fan", "climate", "chilled"
        ])
        topic_lighting = any(w in combined_text for w in [
            "light", "lights", "brightness", "dim", "lamp", "glow"
        ])

        query_tokens = set(re.findall(r'\b[a-zA-Z0-9_]{3,}\b', combined_text))

        scored_items = []
        universal_constraints = []

        for item in all_rows:
            itype = item["type"].lower()
            isubj = item["subject"].lower()
            ictx = (item["context"] or "").lower()
            ival = str(item["value"]).lower()
            iconf = float(item["confidence"])

            # Separate universal constraints (address, privacy)
            if itype == "constraint" and isubj in ["address", "privacy"]:
                if include_universal_constraints:
                    universal_constraints.append(item)
                continue

            score = 0.0

            # 1. Subject relevance
            if isubj in combined_text:
                score += 5.0
            if any(t in isubj for t in query_tokens):
                score += 3.0

            # 2. Context relevance
            if ictx and ictx in combined_text:
                score += 4.0
            if ictx and any(t in ictx for t in query_tokens):
                score += 2.5

            # 3. Domain/Topic thematic alignment
            if topic_work and (isubj in ["work", "sql", "excel", "career"] or "sql" in ictx or "work" in ictx):
                score += 4.5
            if topic_movie and (isubj in ["movie", "projector", "soundbar", "streaming", "lighting"] or "movie" in ictx):
                score += 4.5
            if topic_guitar and (isubj == "guitar" or "guitar" in ictx):
                score += 5.0
            if topic_climate and (isubj == "ac" or "ac" in ictx or "temp" in ictx):
                score += 4.0
            if topic_lighting and (isubj == "lighting" or "lighting" in ictx):
                score += 4.0

            # 4. Token overlap inside value
            val_tokens = set(re.findall(r'\b[a-zA-Z0-9_]{3,}\b', ival))
            token_overlap = len(query_tokens.intersection(val_tokens))
            score += token_overlap * 1.5

            # 5. Confidence weight
            score += iconf * 0.5

            # Keep items with clear positive relevance
            if score >= 2.0:
                scored_items.append((score, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        selected = [item for _, item in scored_items[:limit]]

        # Prepend universal constraints without exceeding reasonable context
        final_results = universal_constraints + [x for x in selected if x["id"] not in [u["id"] for u in universal_constraints]]
        final_results = final_results[:limit + len(universal_constraints)]

        # Telemetry: update last accessed & count
        if final_results:
            self._record_memory_access_batch([r["id"] for r in final_results])

        return final_results

    def _record_memory_access_batch(self, memory_ids: List[str]) -> None:
        """Updates last_accessed_at and increments access_count for retrieved memories."""
        if not memory_ids:
            return
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in memory_ids)
            cursor.execute(f"""
                UPDATE structured_personal_memory
                SET last_accessed_at = ?, access_count = access_count + 1
                WHERE id IN ({placeholders})
            """, [now] + memory_ids)
            conn.commit()
        except Exception as e:
            logger.debug(f"Failed to record memory access batch: {e}")
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
    # Persistent Goal & Subgoal Continuity CRUD
    # =========================================================================

    def save_goal(
        self,
        goal_id: str,
        title: str,
        subgoals: Optional[List[Dict[str, Any]]] = None,
        status: str = "ACTIVE",
        notes: str = "",
        target_category: str = "GENERAL"
    ) -> None:
        """Saves or updates a persistent multi-step goal in SQLite."""
        now = time.time()
        subgoals_str = json.dumps(subgoals or [], separators=(',', ':'))
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO persistent_goals (id, title, status, target_category, subgoals_json, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    status=excluded.status,
                    target_category=excluded.target_category,
                    subgoals_json=excluded.subgoals_json,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
            """, (goal_id, title.strip(), status.upper(), target_category, subgoals_str, notes.strip(), now, now))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Saved persistent goal: {goal_id} ('{title}') [Status: {status}]")
        finally:
            conn.close()

    def get_active_goal(self) -> Optional[Dict[str, Any]]:
        """Retrieves the currently active continuous goal, if one exists."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, status, target_category, subgoals_json, notes, created_at, updated_at
                FROM persistent_goals
                WHERE status = 'ACTIVE'
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "status": row["status"],
                    "target_category": row["target_category"],
                    "subgoals": json.loads(row["subgoals_json"]),
                    "notes": row["notes"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            return None
        finally:
            conn.close()

    def update_subgoal_status(self, goal_id: str, subgoal_identifier: Any, completed: bool = True, is_current: bool = False) -> bool:
        """Updates completion status of a specific subgoal within an active goal (by index or id)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT subgoals_json FROM persistent_goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if not row:
                return False

            subgoals = json.loads(row["subgoals_json"])
            target_idx = -1
            if isinstance(subgoal_identifier, int):
                if 0 <= subgoal_identifier < len(subgoals):
                    target_idx = subgoal_identifier
                else:
                    for i, sg in enumerate(subgoals):
                        if sg.get("id") == subgoal_identifier:
                            target_idx = i
                            break
            else:
                for i, sg in enumerate(subgoals):
                    if str(sg.get("id")) == str(subgoal_identifier) or str(subgoal_identifier).lower() in sg.get("title", "").lower():
                        target_idx = i
                        break

            if target_idx != -1:
                subgoals[target_idx]["completed"] = completed
                if is_current:
                    for i, sg in enumerate(subgoals):
                        sg["is_current"] = (i == target_idx)
                subgoals_str = json.dumps(subgoals, separators=(',', ':'))
                now = time.time()
                cursor.execute("""
                    UPDATE persistent_goals
                    SET subgoals_json = ?, updated_at = ?
                    WHERE id = ?
                """, (subgoals_str, now, goal_id))
                conn.commit()
                return True
            return False
        finally:
            conn.close()

    def get_current_work_subgoal(self) -> Optional[Dict[str, Any]]:
        """Returns the currently active work subgoal from the active career goal."""
        active_goal = self.get_active_goal()
        if not active_goal:
            return None
        subgoals = active_goal.get("subgoals", [])
        for sg in subgoals:
            if sg.get("is_current") and not sg.get("completed"):
                return sg
        for sg in subgoals:
            if not sg.get("completed"):
                return sg
        return None

    def process_work_session_outcome(
        self,
        outcome_type: str,  # "NO_PROGRESS" | "PARTIAL" | "COMPLETED"
        user_summary: str = "",
        session_duration_seconds: float = 0.0,
        files_modified: bool = False
    ) -> Dict[str, Any]:
        """
        Truthful, non-hallucinatory work session progression:
        - NO_PROGRESS: (0 work / rest day / early wrap-up / user says didn't work)
          Keeps current subgoal untouched, keeps pending tasks untouched, creates ZERO new tasks.
        - PARTIAL: (User worked on queries/doc but didn't finish milestone)
          Keeps current subgoal active, logs progress notes into the active task, creates ZERO duplicate tasks.
        - COMPLETED: (Milestone finished with verified results or ChatGPT summary)
          Advances current subgoal to completed, activates next subgoal, marks active task complete,
          and queues tomorrow's next task.
        """
        now = time.time()
        active_goal = self.get_active_goal()
        curr_sg = self.get_current_work_subgoal()

        outcome_norm = outcome_type.upper().strip()

        # 1. NO PROGRESS: Rest day or zero work
        if outcome_norm in ("NO_PROGRESS", "ZERO_WORK", "NO_WORK", "BREAK"):
            roadmap = self.get_career_roadmap()
            logger.info("[LONG_TERM_MEMORY] Work session wrapup: NO_PROGRESS. Milestones and tasks remain unchanged.")
            return {
                "outcome": "NO_PROGRESS",
                "current_subgoal": curr_sg,
                "completed_subgoal": None,
                "next_subgoal": None,
                "tasks_created": 0,
                "subgoals_advanced": False,
                "roadmap": roadmap
            }

        # 2. PARTIAL PROGRESS: Still working on current milestone
        if outcome_norm in ("PARTIAL", "IN_PROGRESS", "PARTIAL_PROGRESS"):
            if curr_sg and user_summary:
                conn = self._get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE user_tasks
                        SET description = description || ' | Note: ' || ?, updated_at = ?
                        WHERE status IN ('PENDING', 'IN_PROGRESS', 'ACTIVE')
                          AND (LOWER(title) LIKE '%sql%' OR LOWER(title) LIKE '%blinkit%')
                        ORDER BY created_at DESC LIMIT 1
                    """, (user_summary.strip()[:200], now))
                    conn.commit()
                finally:
                    conn.close()

            roadmap = self.get_career_roadmap()
            logger.info(f"[LONG_TERM_MEMORY] Work session wrapup: PARTIAL. Maintained current subgoal: {curr_sg.get('title') if curr_sg else 'None'}")
            return {
                "outcome": "PARTIAL",
                "current_subgoal": curr_sg,
                "completed_subgoal": None,
                "next_subgoal": None,
                "tasks_created": 0,
                "subgoals_advanced": False,
                "roadmap": roadmap
            }

        # 3. COMPLETED: Milestone finished
        completed_sg = None
        next_sg = None
        tomorrow_task = None

        if active_goal:
            subgoals = active_goal.get("subgoals", [])
            curr_idx = -1
            for i, sg in enumerate(subgoals):
                if sg.get("is_current") and not sg.get("completed"):
                    curr_idx = i
                    break
            if curr_idx == -1:
                for i, sg in enumerate(subgoals):
                    if not sg.get("completed"):
                        curr_idx = i
                        break

            if curr_idx != -1:
                completed_sg = subgoals[curr_idx]
                completed_sg["completed"] = True
                completed_sg["is_current"] = False

                if curr_idx + 1 < len(subgoals):
                    next_sg = subgoals[curr_idx + 1]
                    next_sg["is_current"] = True
                    for j, sg in enumerate(subgoals):
                        if j != (curr_idx + 1) and not sg.get("completed"):
                            sg["is_current"] = False

                subgoals_str = json.dumps(subgoals, separators=(',', ':'))
                conn = self._get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE persistent_goals
                        SET subgoals_json = ?, updated_at = ?
                        WHERE id = ?
                    """, (subgoals_str, now, active_goal["id"]))
                    conn.commit()
                finally:
                    conn.close()

        # Mark active task related to completed subgoal as COMPLETED
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_tasks
                SET status = 'COMPLETED', updated_at = ?
                WHERE status IN ('PENDING', 'IN_PROGRESS', 'ACTIVE')
                  AND (LOWER(title) LIKE '%oos%' OR LOWER(title) LIKE '%duration%' OR LOWER(title) LIKE '%lag()%')
            """, (now,))
            conn.commit()
        finally:
            conn.close()

        # Queue tomorrow's next task based on the next subgoal
        if next_sg:
            tomorrow_title = next_sg["title"]
            tomorrow_desc = f"Execute tomorrow's prioritized focus: {next_sg['title']}"
            tomorrow_task_id = self.create_task(
                title=tomorrow_title,
                description=tomorrow_desc,
                priority="HIGH",
                category="LEARNING"
            )
            tomorrow_task = {"id": tomorrow_task_id, "title": tomorrow_title}

        roadmap = self.get_career_roadmap()
        logger.info(f"[LONG_TERM_MEMORY] Work session wrapup: COMPLETED. Advanced to: {next_sg.get('title') if next_sg else 'None'}")
        return {
            "outcome": "COMPLETED",
            "current_subgoal": next_sg,
            "completed_subgoal": completed_sg,
            "next_subgoal": next_sg,
            "tomorrow_task": tomorrow_task,
            "tasks_created": 1 if tomorrow_task else 0,
            "subgoals_advanced": True,
            "roadmap": roadmap
        }

    def advance_work_wrapup(self) -> Dict[str, Any]:
        """
        Advances the user's career roadmap, completes the active work subgoal,
        marks the current work task as completed, and schedules tomorrow's priority task.
        """
        return self.process_work_session_outcome("COMPLETED")


    def complete_goal(self, goal_id: str, notes: str = "") -> None:
        """Marks a persistent goal as COMPLETED."""
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE persistent_goals
                SET status = 'COMPLETED', notes = CASE WHEN ? != '' THEN ? ELSE notes END, updated_at = ?
                WHERE id = ?
            """, (notes, notes, now, goal_id))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Goal marked COMPLETED: {goal_id}")
        finally:
            conn.close()

    def get_recent_goals(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves recent goals across all statuses."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, status, target_category, subgoals_json, notes, created_at, updated_at
                FROM persistent_goals
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "status": r["status"],
                    "target_category": r["target_category"],
                    "subgoals": json.loads(r["subgoals_json"]),
                    "notes": r["notes"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]
        finally:
            conn.close()

    # =========================================================================
    # User Tasks & Priorities CRUD
    # =========================================================================

    def save_task(
        self,
        task_id: str,
        title: str,
        description: str = "",
        priority: str = "MEDIUM",
        category: str = "GENERAL",
        status: str = "PENDING"
    ) -> None:
        """Saves or updates a user task in SQLite."""
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # If an identical pending task already exists, update it to prevent duplicates and bump timestamp
            cursor.execute("SELECT id FROM user_tasks WHERE title = ? AND status = 'PENDING'", (title.strip(),))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE user_tasks
                    SET description = ?, priority = ?, category = ?, status = ?, created_at = ?, updated_at = ?
                    WHERE id = ?
                """, (description.strip(), priority.upper(), category.upper(), status.upper(), now, now, existing["id"]))
                conn.commit()
                logger.info(f"[LONG_TERM_MEMORY] Updated existing task: {existing['id']} ('{title}')")
                return

            cursor.execute("""
                INSERT INTO user_tasks (id, title, description, priority, category, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    priority=excluded.priority,
                    category=excluded.category,
                    status=excluded.status,
                    updated_at=excluded.updated_at
            """, (task_id, title.strip(), description.strip(), priority.upper(), category.upper(), status.upper(), now, now))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Saved task: {task_id} ('{title}')")
        finally:
            conn.close()

    def get_active_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves active (PENDING/IN_PROGRESS) user tasks ordered by newest first, then priority."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, description, priority, category, status, created_at, updated_at
                FROM user_tasks
                WHERE status IN ('PENDING', 'IN_PROGRESS', 'ACTIVE')
                ORDER BY created_at DESC, CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "description": r["description"],
                    "priority": r["priority"],
                    "category": r["category"],
                    "status": r["status"]
                }
                for r in rows
            ]
        finally:
            conn.close()

    get_pending_tasks = get_active_tasks

    def get_career_roadmap(self) -> Dict[str, Any]:
        """Returns structured view of the user's active career roadmap, facts, and tasks."""
        goal = self.get_active_goal()
        tasks = self.get_active_tasks(limit=10)
        facts = self.get_all_facts()
        return {
            "career_target": facts.get("career_target", "Data Analyst"),
            "current_project": facts.get("current_project", "Blinkit Stock-Out SQL Analysis"),
            "completed_projects": facts.get("completed_projects", "3 Excel Projects"),
            "self_teaching_platform": facts.get("self_teaching_platform", "ChatGPT & Project-Based Learning"),
            "active_goal": goal,
            "tasks": tasks
        }

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "MEDIUM",
        category: str = "WORK"
    ) -> str:
        """Creates a new task in SQLite with auto-generated task ID."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self.save_task(task_id, title, description, priority, category, status="PENDING")
        return task_id

    def update_task(
        self,
        identifier: str,
        title: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None
    ) -> bool:
        """Updates attributes of an existing task by ID or title match."""
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, priority, status FROM user_tasks WHERE id = ? OR LOWER(title) LIKE ?", (identifier, f"%{identifier.lower()}%"))
            row = cursor.fetchone()
            if not row:
                return False

            new_title = title if title is not None else row["title"]
            new_priority = priority.upper() if priority is not None else row["priority"]
            new_status = status.upper() if status is not None else row["status"]

            cursor.execute("""
                UPDATE user_tasks
                SET title = ?, priority = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (new_title, new_priority, new_status, now, row["id"]))
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Updated task {row['id']}: status={new_status}, priority={new_priority}")
            return True
        finally:
            conn.close()

    def delete_task(self, identifier: str) -> bool:
        """Deletes a task by ID or title match from SQLite."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_tasks WHERE id = ? OR LOWER(title) LIKE ?", (identifier, f"%{identifier.lower()}%"))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"[LONG_TERM_MEMORY] Deleted task matching '{identifier}'")
            return deleted
        finally:
            conn.close()

    def complete_task(self, identifier: str) -> Optional[str]:
        """Marks a task as COMPLETED by ID or title match."""
        now = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM user_tasks WHERE id = ? OR LOWER(title) LIKE ?", (identifier, f"%{identifier.lower()}%"))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE user_tasks SET status = 'COMPLETED', updated_at = ? WHERE id = ?", (now, row["id"]))
                conn.commit()
                return row["title"]
            return None
        finally:
            conn.close()

    # =========================================================================
    # Natural Language Fact & Preference Extractor
    # =========================================================================

    def extract_facts_from_utterance(self, text: str) -> List[Tuple[str, str]]:
        """
        Extracts semantic user preferences, schedule routines, and facts from natural language.
        e.g. "I love Interstellar", "My favorite music is Lofi", "I sleep at 1 AM", "I practice guitar at 5 PM"
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
            # Schedule / Routine patterns: e.g. "I usually wake up at 8 AM", "I practice guitar at 5 PM"
            (r'\bi\s+(?:usually\s+)?(?:practice|play|study|work\s+on)\s+([a-zA-Z_]+)\s+at\s+([^,.\n]+)', lambda m: (f"routine_{m.group(1).lower().replace(' ', '_')}", f"at {m.group(2).strip()}")),
            (r'\bi\s+(?:usually\s+)?(?:wake\s+up|sleep|go\s+to\s+bed)\s+at\s+([^,.\n]+)', lambda m: ("sleep_schedule", m.group(1).strip())),
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
        active_goal = self.get_active_goal()

        lines = ["[LONG-TERM EPISTEMIC MEMORY]"]
        if facts:
            lines.append("Confirmed User Knowledge:")
            for k, v in list(facts.items())[:8]:
                lines.append(f"  • {k}: {v}")

        if active_goal:
            lines.append(f"Active Objective: {active_goal['title']}")
            for sg in active_goal.get("subgoals", []):
                mark = "[✓]" if sg.get("completed") else ("[→]" if sg.get("is_current") else "[ ]")
                lines.append(f"  {mark} {sg.get('title', '')}")

        if past_turns:
            lines.append("Relevant Past Context:")
            for p in past_turns:
                lines.append(f"  • User: \"{p['user']}\" ➔ Animus: \"{p['agent']}\"")

        return "\n".join(lines)

    # =========================================================================
    # Work Focus Sessions & Deep Work Analytics
    # =========================================================================

    def record_work_session(
        self,
        started_at: Optional[float] = None,
        ended_at: Optional[float] = None,
        duration_seconds: Optional[float] = None,
        milestone_title: Optional[str] = None,
        breaks_taken: int = 0,
        completion_type: Optional[str] = None,
        notes: str = "",
        session_duration_seconds: Optional[float] = None,
        subgoal_title: Optional[str] = None,
        exit_reason: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Records a completed or auto-dormant deep work session."""
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        now = time.time()
        final_dur = float(duration_seconds if duration_seconds is not None else (session_duration_seconds if session_duration_seconds is not None else 0.0))
        final_dur = max(0.0, final_dur)
        final_ended = float(ended_at) if ended_at is not None else now
        final_started = float(started_at) if started_at is not None else (final_ended - final_dur)
        final_milestone = milestone_title or subgoal_title or ""
        final_completion = completion_type or exit_reason or "USER_COMPLETED"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO work_focus_sessions (id, started_at, ended_at, duration_seconds, milestone_title, breaks_taken, completion_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, final_started, final_ended, final_dur, final_milestone, breaks_taken, final_completion, notes))
            conn.commit()
            logger.info(f"[WORK_SESSION_RECORDED] id={session_id}, duration={final_dur:.1f}s, type={final_completion}, milestone={final_milestone}")
            return session_id
        finally:
            conn.close()

    def get_weekly_work_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Calculates deep work analytics over the past N days."""
        cutoff = time.time() - (days * 86400.0)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, started_at, ended_at, duration_seconds, milestone_title, breaks_taken, completion_type, notes
                FROM work_focus_sessions
                WHERE started_at >= ?
                ORDER BY started_at ASC
            """, (cutoff,))
            rows = cursor.fetchall()

            total_seconds = sum(float(r["duration_seconds"]) for r in rows)
            session_count = len(rows)
            avg_duration_sec = (total_seconds / session_count) if session_count > 0 else 0.0

            daily_buckets: Dict[str, float] = {}
            for r in rows:
                dt_str = datetime.fromtimestamp(float(r["started_at"])).strftime("%Y-%m-%d")
                daily_buckets[dt_str] = daily_buckets.get(dt_str, 0.0) + float(r["duration_seconds"])

            total_hours = round(total_seconds / 3600.0, 2)
            total_focus_min = round(total_seconds / 60.0, 1)
            avg_min = round(avg_duration_sec / 60.0, 1)

            return {
                "period_days": days,
                "total_sessions": session_count,
                "total_hours": total_hours,
                "total_focus_hours": total_hours,
                "total_focus_minutes": total_focus_min,
                "avg_session_minutes": avg_min,
                "average_session_minutes": avg_min,
                "daily_breakdown_hours": {k: round(v / 3600.0, 2) for k, v in daily_buckets.items()},
                "recent_sessions": [
                    {
                        "session_id": r["id"],
                        "date": datetime.fromtimestamp(float(r["started_at"])).strftime("%Y-%m-%d %H:%M"),
                        "duration_minutes": round(float(r["duration_seconds"]) / 60.0, 1),
                        "milestone": r["milestone_title"],
                        "completion_type": r["completion_type"]
                    }
                    for r in rows[-5:]
                ]
            }
        finally:
            conn.close()


# Global singleton instance
_global_lt_memory: Optional[LongTermMemoryStore] = None


def get_long_term_memory() -> LongTermMemoryStore:
    """Returns or initializes the global LongTermMemoryStore singleton."""
    global _global_lt_memory
    if _global_lt_memory is None:
        _global_lt_memory = LongTermMemoryStore()
    return _global_lt_memory

