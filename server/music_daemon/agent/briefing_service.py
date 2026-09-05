"""
================================================================================
ANIMUS SMART ROOM — EXECUTIVE BRIEFING & PRINTABLE SHEET SYNTHESIZER
================================================================================
Synthesizes personalized, context-aware morning executive briefings and nightly
debriefs for Sir. Generates beautifully formatted physical printouts for the
HP Ink Tank 310 series USB printer and coordinates proactive day routines.
================================================================================
"""

from __future__ import annotations
import os
import time
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.briefing_service")


class BriefingService:
    """
    Synthesizes executive daily briefings and generates printable daily sheets.
    """

    DEFAULT_OUTPUT_DIR = Path("d:/AnimusSmartRoom/server/music_daemon/scratch")

    def __init__(
        self,
        memory_store: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        printer_controller: Optional[Any] = None,
        user_profile: Optional[Any] = None
    ):
        self.memory_store = memory_store
        self.task_manager = task_manager
        self.printer_controller = printer_controller
        self.user_profile = user_profile
        self.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. Spoken Briefing Generation
    # =========================================================================

    def generate_morning_briefing(
        self,
        room_state: Optional[Any] = None,
        weather_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Synthesizes a structured, concise executive morning briefing for Sir.
        """
        now = datetime.now()
        date_str = now.strftime("%A, %B %d")
        lines: List[str] = [f"Good morning, Sir! Here is your executive briefing for {date_str}:"]

        # 1. Active Long-Horizon Goal / Career Milestone
        active_milestone = None
        if self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal"):
            try:
                active_milestone = self.memory_store.get_current_work_subgoal()
            except Exception as e:
                logger.debug(f"[BRIEFING_MEMORY_QUERY_ERR] {e}")

        if active_milestone and isinstance(active_milestone, dict) and "title" in active_milestone:
            lines.append(f"- Primary Focus: {active_milestone['title']}")
        elif self.user_profile and hasattr(self.user_profile, "routines"):
            learning_prio = getattr(self.user_profile.routines, "learning_priority", "Blinkit SQL Analytics Sprint")
            lines.append(f"- Primary Focus: {learning_prio}")
        else:
            lines.append("- Primary Focus: Blinkit SQL Analytics & Product Portfolio Milestone")

        # 2. Pending Tasks
        pending = []
        if self.task_manager and hasattr(self.task_manager, "get_pending_tasks"):
            try:
                pending = self.task_manager.get_pending_tasks()
            except Exception as e:
                logger.debug(f"[BRIEFING_TASK_QUERY_ERR] {e}")

        if pending:
            top_tasks = [getattr(t, "title", str(t)) for t in pending[:3]]
            task_list_str = ", ".join(top_tasks)
            lines.append(f"- Pending Tasks ({len(pending)}): {task_list_str}")
        else:
            lines.append("- Tasks: All primary tasks are up to date.")

        # 3. Ambient Room & Weather
        temp = 24
        if weather_info and "outdoor_temperature_c" in weather_info:
            temp = weather_info["outdoor_temperature_c"]
            cond = weather_info.get("condition", "Clear")
            lines.append(f"- Climate: {cond}, {temp}°C outdoors.")
        elif room_state and hasattr(room_state, "ac"):
            ac_amb = getattr(room_state.ac, "ambient_temperature", None)
            val = getattr(ac_amb, "value", ac_amb) if ac_amb else 24
            lines.append(f"- Room Climate: {val}°C.")

        # 4. Evening Anchor
        lines.append("- Evening Anchor: Guitar practice routine planned for 5:30 PM.")

        # 5. Proactive Action Offer
        lines.append(
            "\nWould you like me to put on your morning focus playlist, or print your daily SQL study plan on the HP Ink Tank 310?"
        )

        return "\n".join(lines)

    def generate_nightly_debrief(
        self,
        room_state: Optional[Any] = None
    ) -> str:
        """
        Synthesizes an executive nightly wrap-up and debrief for Sir.
        """
        lines: List[str] = ["Good evening, Sir! Here is your nightly debrief:"]

        # 1. Closed Tasks & Accomplishments
        pending = []
        if self.task_manager and hasattr(self.task_manager, "get_pending_tasks"):
            try:
                pending = self.task_manager.get_pending_tasks()
            except Exception as e:
                logger.debug(f"[DEBRIEF_TASK_ERR] {e}")

        lines.append("- Work Session: Daily analytical sprints and system operations logged.")
        if pending:
            lines.append(f"- Rollover Items: {len(pending)} task(s) queued for tomorrow.")
        else:
            lines.append("- Status: All queued objectives completed.")

        # 2. Guitar Practice & Relaxation Cue
        lines.append("- Routine: 5:30 PM guitar practice session ready on the soundbar.")

        # 3. Proactive Action Offer
        lines.append(
            "\nShall I print tomorrow's checklist on the HP Ink Tank 310, and cue your guitar practice session?"
        )

        return "\n".join(lines)

    # =========================================================================
    # 2. Printable Document Generation (Physical HP Ink Tank 310)
    # =========================================================================

    def generate_executive_printable_sheet(
        self,
        sheet_type: str = "MORNING_PLAN",
        custom_notes: Optional[str] = None
    ) -> str:
        """
        Generates a clean, formatted plain-text executive study/task sheet.
        Returns the absolute path of the generated file ready for printing.
        """
        now = datetime.now()
        date_str = now.strftime("%A, %d %B %Y")
        time_str = now.strftime("%H:%M")

        border = "=" * 64
        sep = "-" * 64

        doc_lines: List[str] = [
            border,
            "              ANIMUS EXECUTIVE DAILY BRIEFING SHEET              ",
            f"               Generated: {date_str} at {time_str}               ",
            border,
            "",
            "OPERATOR: Sayantan Roy (Sir)",
            "HEADQUARTERS: Smart Room Alpha (Lucknow)",
            sep,
        ]

        # Milestone section
        active_milestone = None
        if self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal"):
            try:
                active_milestone = self.memory_store.get_current_work_subgoal()
            except Exception:
                pass

        doc_lines.append("[1] STRATEGIC MILESTONE & LEARNING FOCUS:")
        if active_milestone and isinstance(active_milestone, dict) and "title" in active_milestone:
            doc_lines.append(f"    Target: {active_milestone['title']}")
            if "description" in active_milestone:
                doc_lines.append(f"    Details: {active_milestone['description']}")
        else:
            doc_lines.append("    Target: Blinkit SQL Analytics & Problem Solving Portfolio")
        doc_lines.append(sep)

        # Task list section
        doc_lines.append("[2] ACTIONABLE TASK CHECKLIST:")
        pending = []
        if self.task_manager and hasattr(self.task_manager, "get_pending_tasks"):
            try:
                pending = self.task_manager.get_pending_tasks()
            except Exception:
                pass

        if pending:
            for idx, t in enumerate(pending[:8], start=1):
                title = getattr(t, "title", str(t))
                prio = getattr(t, "priority", "MEDIUM")
                prio_val = getattr(prio, "value", prio) if hasattr(prio, "value") else str(prio)
                doc_lines.append(f"    [ ] {idx}. {title} ({prio_val})")
        else:
            doc_lines.append("    [ ] 1. Complete Blinkit SQL query optimization problem")
            doc_lines.append("    [ ] 2. Review indexing strategies and query plans")
            doc_lines.append("    [ ] 3. Synthesize analytics findings into documentation")
        doc_lines.append(sep)

        # Daily anchors section
        doc_lines.append("[3] DAILY HABIT & WELLNESS ANCHORS:")
        doc_lines.append("    [ ] 17:30 PM - Fingerstyle Guitar Practice Session (30 min)")
        doc_lines.append("    [ ] Hydration & Posture check after 50-minute deep focus sprints")
        doc_lines.append("    [ ] Evening reflection & daily debrief wrap-up")
        doc_lines.append(sep)

        if custom_notes:
            doc_lines.append("[4] SPECIAL DIRECTIVES / NOTES:")
            doc_lines.append(f"    {custom_notes}")
            doc_lines.append(sep)

        doc_lines.append("PRODUCED BY ANIMUS SMART ROOM DAEMON (HP INK TANK 310 DIRECT)")
        doc_lines.append(border)

        content = "\n".join(doc_lines) + "\n"

        filename = f"executive_briefing_{now.strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = self.DEFAULT_OUTPUT_DIR / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"[BRIEFING_SHEET_CREATED] Executive sheet generated at {file_path}")
        return str(file_path.resolve())

    # =========================================================================
    # 3. Direct Physical Print Dispatch
    # =========================================================================

    def print_executive_sheet(
        self,
        file_path: Optional[str] = None,
        sheet_type: str = "MORNING_PLAN"
    ) -> Dict[str, Any]:
        """
        Dispatches the executive sheet directly to the physical HP Ink Tank 310 printer.
        """
        if not file_path:
            file_path = self.generate_executive_printable_sheet(sheet_type=sheet_type)

        if not self.printer_controller:
            from printer_controller import PrinterController
            self.printer_controller = PrinterController()

        logger.info(f"[BRIEFING_PRINT_DISPATCH] Dispatching {file_path} to HP Ink Tank 310...")
        success, msg = self.printer_controller.print_document(file_path)
        return {
            "success": success,
            "message": msg,
            "file_path": file_path,
            "target_printer": self.printer_controller.target_printer
        }

    # =========================================================================
    # 4. Physical SQL Practice Worksheet (HP Ink Tank 310 Direct)
    # =========================================================================

    def generate_sql_practice_sheet(
        self,
        problem_title: Optional[str] = None,
        category: str = "WINDOW_FUNCTIONS_AGGREGATION"
    ) -> str:
        """
        Synthesizes a physical pen-and-paper SQL practice worksheet for Sir,
        tailored for offline problem solving away from screens.
        """
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        border = "=" * 78
        sep = "-" * 78

        if not problem_title and self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal"):
            try:
                curr_sg = self.memory_store.get_current_work_subgoal()
                if curr_sg and "title" in curr_sg:
                    problem_title = curr_sg["title"]
            except Exception:
                pass

        title = problem_title or "Blinkit Dark Store Inventory Turnover & Stockout Velocity"

        doc_lines: List[str] = [
            border,
            "ANIMUS SMART ROOM — PHYSICAL SQL & ANALYTICS PRACTICE WORKSHEET",
            "TARGET DEVICE: HP Ink Tank 310 Series (Offline Spooler direct USB001)",
            f"DATE / TIME:   {date_str}",
            border,
            "",
            f"[PROBLEM STATEMENT] {title}",
            sep,
            "BUSINESS CONTEXT:",
            "  During peak demand surge hours (18:00 - 22:00), Blinkit dark stores face",
            "  rapid localized inventory depletion. Unfulfilled customer line-items cause",
            "  order cancellations and hurt customer retention in dense urban micro-clusters.",
            "",
            "SCHEMA DEFINITIONS:",
            "  TABLE: dark_stores (",
            "      store_id INT PRIMARY KEY,",
            "      store_name VARCHAR(100),",
            "      zone VARCHAR(50),",
            "      city VARCHAR(50)",
            "  );",
            "",
            "  TABLE: dark_store_inventory (",
            "      inventory_id INT PRIMARY KEY,",
            "      store_id INT REFERENCES dark_stores(store_id),",
            "      sku_id INT,",
            "      current_stock INT,",
            "      safety_threshold INT,",
            "      updated_at TIMESTAMP",
            "  );",
            "",
            "  TABLE: order_line_items (",
            "      order_id BIGINT,",
            "      store_id INT REFERENCES dark_stores(store_id),",
            "      sku_id INT,",
            "      quantity_ordered INT,",
            "      fulfillment_status VARCHAR(20),  -- 'FULFILLED', 'STOCKOUT_CANCELLED'",
            "      created_at TIMESTAMP",
            "  );",
            sep,
            "SAMPLE TUPLES (MOCK RECORDS):",
            "  TABLE: dark_stores",
            "  +----------+-----------------------+----------+-----------+",
            "  | store_id | store_name            | zone     | city      |",
            "  +----------+-----------------------+----------+-----------+",
            "  | 101      | Indiranagar Hub-A     | East     | Bengaluru |",
            "  | 102      | Koramangala Pocket-4  | South    | Bengaluru |",
            "  | 103      | Whitefield Central    | East     | Bengaluru |",
            "  +----------+-----------------------+----------+-----------+",
            "",
            "  TABLE: order_line_items",
            "  +----------+----------+--------+----------+--------------------+---------------------+",
            "  | order_id | store_id | sku_id | quantity | fulfillment_status | created_at          |",
            "  +----------+----------+--------+----------+--------------------+---------------------+",
            "  | 880191   | 101      | 5002   | 2        | FULFILLED          | 2026-09-02 18:14:00 |",
            "  | 880192   | 101      | 5002   | 1        | STOCKOUT_CANCELLED | 2026-09-02 18:22:15 |",
            "  | 880195   | 102      | 4109   | 3        | STOCKOUT_CANCELLED | 2026-09-03 19:05:10 |",
            "  | 880201   | 101      | 3301   | 1        | FULFILLED          | 2026-09-04 20:11:45 |",
            "  +----------+----------+--------+----------+--------------------+---------------------+",
            sep,
            "EXPECTED RESULT GRID:",
            "  +----------+-----------------------+------------+---------------------------+-------------+",
            "  | store_id | store_name            | end_date   | rolling_3d_cancel_rate   | alert_level |",
            "  +----------+-----------------------+------------+---------------------------+-------------+",
            "  | 101      | Indiranagar Hub-A     | 2026-09-04 | 14.28%                    | CRITICAL    |",
            "  | 102      | Koramangala Pocket-4  | 2026-09-04 | 12.50%                    | ELEVATED    |",
            "  +----------+-----------------------+------------+---------------------------+-------------+",
            sep,
            "CHALLENGE OBJECTIVES:",
            "  1. Write a CTE to compute the 3-day rolling cancellation rate per store",
            "     using window functions: SUM(CASE WHEN fulfillment_status = 'STOCKOUT_CANCELLED'",
            "     THEN 1 ELSE 0 END) OVER (PARTITION BY store_id ORDER BY created_at ...)",
            "  2. Filter for stores whose stockout rate exceeds 12% during peak evening surges.",
            "  3. Propose an optimal composite index on order_line_items to eliminate full table scans.",
            sep,
            "-- DRAFT YOUR SQL QUERY SOLUTION BELOW (PEN-AND-PAPER WORKSPACE):",
            "-- " + ("-" * 75),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "-- " + ("-" * 75),
            "-- INDEXING & BIG-O OPTIMIZATION NOTES:",
            "-- Recommendation: CREATE INDEX idx_orders_perf ON order_line_items(...);",
            "",
            "",
            border,
            "PRODUCED FOR SIR BY ANIMUS SMART ROOM COGNITIVE ENGINE",
            border
        ]

        content = "\n".join(doc_lines) + "\n"
        filename = f"sql_practice_worksheet_{now.strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = self.DEFAULT_OUTPUT_DIR / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"[SQL_WORKSHEET_CREATED] SQL worksheet generated at {file_path}")
        return str(file_path.resolve())

    def print_sql_worksheet(
        self,
        problem_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a fresh SQL practice worksheet directly to the HP Ink Tank 310.
        """
        file_path = self.generate_sql_practice_sheet(problem_title=problem_title)
        if not self.printer_controller:
            from printer_controller import get_printer_controller
            self.printer_controller = get_printer_controller()

        logger.info(f"[SQL_WORKSHEET_PRINT] Dispatching {file_path} to HP Ink Tank 310...")
        success, msg = self.printer_controller.print_document(file_path)
        return {
            "success": success,
            "message": msg,
            "file_path": file_path,
            "target_printer": getattr(self.printer_controller, "target_printer", "HP Ink Tank 310 series")
        }

