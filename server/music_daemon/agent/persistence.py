"""
Local Persistence for Animus Personal Agent.
Saves and loads UserProfile, MemoryStore, and TaskManager records to/from JSON storage.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from agent.models import UserProfile, MemoryItem, Task, Reminder
from agent.memory import AgentMemoryStore
from agent.user_model import UserModel
from agent.task_manager import TaskManager

logger = logging.getLogger("music_daemon.agent.persistence")


class AgentPersistence:
    """
    Manages atomic load and save operations for agent state.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            self.storage_path = Path(__file__).parent.parent / "secrets" / "user_agent_state.json"
        else:
            self.storage_path = storage_path

    def save_state(
        self,
        user_model: UserModel,
        memory_store: AgentMemoryStore,
        task_manager: TaskManager
    ) -> bool:
        """Saves composite agent state to JSON."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "profile": user_model.to_dict(),
                "memory_items": [item.model_dump() for item in memory_store.get_all_active()],
                "tasks": [t.model_dump() for t in task_manager.list_tasks(include_completed=True)],
                "reminders": [r.model_dump() for r in task_manager.get_active_reminders()]
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"[PERSISTENCE_SAVED] Agent state saved to {self.storage_path}")
            return True
        except Exception as e:
            logger.error(f"[PERSISTENCE_SAVE_ERROR] Failed to save agent state: {e}")
            return False

    def load_state(self) -> Tuple[UserModel, AgentMemoryStore, TaskManager]:
        """Loads composite agent state or falls back to defaults."""
        if not self.storage_path.exists():
            logger.info("[PERSISTENCE_INIT] No existing state file found; initializing default models.")
            return UserModel(), AgentMemoryStore(), TaskManager()

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            profile = UserProfile(**data.get("profile", {}))
            user_model = UserModel(profile=profile)

            memory_items = [MemoryItem(**m) for m in data.get("memory_items", [])]
            memory_store = AgentMemoryStore(initial_items=memory_items)

            tasks = [Task(**t) for t in data.get("tasks", [])]
            reminders = [Reminder(**r) for r in data.get("reminders", [])]
            task_manager = TaskManager(initial_tasks=tasks, initial_reminders=reminders)

            logger.info(f"[PERSISTENCE_LOADED] Loaded agent state ({len(tasks)} tasks, {len(memory_items)} memory items).")
            return user_model, memory_store, task_manager
        except Exception as e:
            logger.warning(f"[PERSISTENCE_LOAD_ERROR] Failed to load agent state: {e}. Falling back to clean defaults.")
            return UserModel(), AgentMemoryStore(), TaskManager()
