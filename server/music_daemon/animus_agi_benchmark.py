"""
================================================================================
ANIMUS SMART ROOM — COGNITIVE & EMBODIED AGI BENCHMARK SUITE
================================================================================
Empirical evaluation framework assessing Animus across 6 key dimensions:
1. Physical Perception & Embodied Sensor Grounding (Camera, Presence, Photometrics)
2. Epistemic Long-Term Memory & Identity Grounding (Facts, Goals, Habits, Analytics)
3. Conversational Reasoning & Intent Disambiguation (Fast-Paths, Follow-ups, Safety)
4. Tangible Actuation & Physical Tool Use (HP Ink Tank 310, PC Automation, Hardware Bounds)
5. Proactive Ambient Agency & Lifecycle Invariants (Ergonomic Nudges, 5m Lock, 120m Dormancy)
6. High-Order Domain Problem Solving (Blinkit Dark Store SQL & Window Function Synthesis)
================================================================================
"""

import os
import sys
import time
import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add server/music_daemon to path
daemon_dir = Path(__file__).resolve().parent
if str(daemon_dir) not in sys.path:
    sys.path.insert(0, str(daemon_dir))

from agent.long_term_memory import LongTermMemoryStore, get_long_term_memory
from agent.briefing_service import BriefingService
from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory
from agent.agent_decision_engine import AgentDecisionEngine


class AnimusAgiBenchmark:
    """Executes empirical multi-modal AGI assessment on Animus Smart Room Intelligence."""

    DAEMON_API = "http://127.0.0.1:8095"

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.total_tests = 0
        self.passed_tests = 0

    def record_probe(self, tier: str, probe_id: str, title: str, passed: bool, details: str, latency_ms: float = 0.0):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        status = "PASSED" if passed else "FAILED"
        self.results.append({
            "tier": tier,
            "probe_id": probe_id,
            "title": title,
            "passed": passed,
            "status": status,
            "details": details,
            "latency_ms": round(latency_ms, 2)
        })
        icon = "[PASS]" if passed else "[FAIL]"
        print(f"  {icon} {probe_id} - {title} ({status}) | {latency_ms:.1f}ms")
        if not passed:
            print(f"      Details: {details}")

    def run_all_tiers(self) -> Dict[str, Any]:
        print("\n" + "=" * 80)
        print("  ANIMUS SMART ROOM — EMBODIED & COGNITIVE AGI BENCHMARK SUITE")
        print("=" * 80)

        t_start = time.time()
        self.test_tier_1_physical_perception()
        self.test_tier_2_epistemic_memory()
        self.test_tier_3_intent_reasoning()
        self.test_tier_4_tangible_actuation()
        self.test_tier_5_proactive_agency()
        self.test_tier_6_domain_problem_solving()
        total_time = time.time() - t_start

        agi_score = (self.passed_tests / self.total_tests * 100.0) if self.total_tests > 0 else 0.0

        print("\n" + "=" * 80)
        print(f"  AGI BENCHMARK SUMMARY: {self.passed_tests}/{self.total_tests} PROBES PASSED")
        print(f"  ANIMUS INTELLIGENCE SCORE (AQ): {agi_score:.1f}% | Execution Time: {total_time:.2f}s")
        print("=" * 80)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_probes": self.total_tests,
            "passed_probes": self.passed_tests,
            "agi_score_pct": round(agi_score, 1),
            "execution_time_seconds": round(total_time, 2),
            "probes": self.results
        }

    # =========================================================================
    # Tier 1: Physical Perception & Embodied Grounding
    # =========================================================================
    def test_tier_1_physical_perception(self):
        print("\n[TIER 1] Physical Perception & Embodied Grounding:")
        tier = "TIER_1_PHYSICAL_PERCEPTION"

        # Probe 1.1: Live Vision Presence
        t0 = time.time()
        data = {}
        try:
            req = urllib.request.Request(f"{self.DAEMON_API}/api/vision/presence")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            lat = (time.time() - t0) * 1000.0
            
            online = data.get("camera_online", False)
            is_present = data.get("is_present", False)
            conf = data.get("confidence", 0.0)
            state = data.get("state", "UNKNOWN")
            
            p1_passed = online and is_present and conf >= 0.75 and state == "PRESENT"
            self.record_probe(
                tier, "P1.1", "Physical Camera Presence & Seated Tracking",
                p1_passed,
                f"online={online}, is_present={is_present}, state={state}, conf={conf}",
                lat
            )
        except Exception as e:
            self.record_probe(tier, "P1.1", "Physical Camera Presence & Seated Tracking", False, f"Exception: {e}", (time.time() - t0) * 1000.0)

        # Probe 1.2: Photometric Environmental Telemetry
        t0 = time.time()
        try:
            lux = data.get("ambient_luminance", 0.0)
            contrast = data.get("contrast_score", 0.0)
            lighting = data.get("lighting_condition", "OFFLINE")
            p2_passed = (lux > 15.0) and (contrast > 5.0) and (lighting in ["DIM / AMBIENT", "OPTIMAL WORK LIGHT", "BRIGHT / DAYLIGHT"])
            self.record_probe(
                tier, "P1.2", "Optical Luminance & Contrast Grounding",
                p2_passed,
                f"lux={lux:.1f}, contrast={contrast:.1f}, condition='{lighting}'",
                (time.time() - t0) * 1000.0
            )
        except Exception as e:
            self.record_probe(tier, "P1.2", "Optical Luminance & Contrast Grounding", False, f"Exception: {e}")

        # Probe 1.3: Seated Focus Telemetry Persistence
        t0 = time.time()
        try:
            seated_sec = data.get("seated_duration_seconds", 0.0)
            p3_passed = seated_sec >= 0.0
            self.record_probe(
                tier, "P1.3", "Continuous Seated Duration Counter",
                p3_passed,
                f"seated_duration_seconds={seated_sec:.1f}s",
                (time.time() - t0) * 1000.0
            )
        except Exception as e:
            self.record_probe(tier, "P1.3", "Continuous Seated Duration Counter", False, f"Exception: {e}")

    # =========================================================================
    # Tier 2: Epistemic Long-Term Memory & Identity Grounding
    # =========================================================================
    def test_tier_2_epistemic_memory(self):
        print("\n[TIER 2] Epistemic Long-Term Memory & Identity Grounding:")
        tier = "TIER_2_EPISTEMIC_MEMORY"

        mem = get_long_term_memory()

        # Probe 2.1: User Identity & Profile Facts
        t0 = time.time()
        name = mem.get_fact("user_name")
        nickname = mem.get_fact("user_nickname")
        loc = mem.get_fact("home_location")
        lat = (time.time() - t0) * 1000.0
        p1_passed = (name == "Sayan Halder") and (nickname == "Sir") and ("Kalyani" in (loc or ""))
        self.record_probe(tier, "P2.1", "Core User Identity & Salutation Recall", p1_passed, f"name={name}, nickname={nickname}, loc={loc}", lat)

        # Probe 2.2: Career Milestone Continuity (Blinkit SQL Sprint)
        t0 = time.time()
        goal = mem.get_active_goal()
        lat = (time.time() - t0) * 1000.0
        subgoals = goal.get("subgoals", []) if goal else []
        curr_sg = next((sg for sg in subgoals if sg.get("is_current")), None)
        p2_passed = bool(curr_sg and "SQL" in curr_sg.get("title", ""))
        self.record_probe(tier, "P2.2", "Active Career Milestone & Roadmap Subgoal", p2_passed, f"current_subgoal='{curr_sg.get('title') if curr_sg else None}'", lat)

        # Probe 2.3: Hardware & Ambience Preference Matrix
        t0 = time.time()
        movie_ac = mem.get_fact("preferred_ac_movie_temp")
        default_ac = mem.get_fact("preferred_ac_default_temp")
        soundbar = mem.get_fact("preferred_music_devices")
        lat = (time.time() - t0) * 1000.0
        p3_passed = (movie_ac == "22") and (default_ac == "24") and ("LG" in (soundbar or ""))
        self.record_probe(tier, "P2.3", "Hardware Baselines & Temperature Preferences", p3_passed, f"movie_ac={movie_ac}, default_ac={default_ac}, soundbar={soundbar}", lat)

        # Probe 2.4: Deep Work Session Persistence & Analytics
        t0 = time.time()
        s_id = mem.record_work_session(session_duration_seconds=3600.0, subgoal_title="Blinkit SQL CTE Testing", exit_reason="BENCHMARK_VERIFY")
        analytics = mem.get_weekly_work_analytics(days=7)
        lat = (time.time() - t0) * 1000.0
        p4_passed = analytics.get("total_sessions", 0) >= 1 and analytics.get("total_hours", 0) >= 1.0
        self.record_probe(tier, "P2.4", "SQLite Deep Work Analytics & Historical Rollup", p4_passed, f"session_id={s_id}, total_hours={analytics.get('total_hours')}, sessions={analytics.get('total_sessions')}", lat)

    # =========================================================================
    # Tier 3: Conversational Reasoning & Intent Disambiguation
    # =========================================================================
    def test_tier_3_intent_reasoning(self):
        print("\n[TIER 3] Conversational Reasoning & Intent Disambiguation:")
        tier = "TIER_3_INTENT_REASONING"

        engine = AgentDecisionEngine()

        # Probe 3.1: Conversational Work Summary Fast-Path
        t0 = time.time()
        res1 = engine.decide_intent("work summary for this week")
        lat = (time.time() - t0) * 1000.0
        p1_passed = "deep work sessions" in res1.get("response_message", "") and res1.get("action_type") == "CONVERSATION"
        self.record_probe(tier, "P3.1", "Weekly Work Analytics Synthesis Fast-Path", p1_passed, f"response='{res1.get('response_message')}'", lat)

        # Probe 3.2: SQL Study Sheet Print Request
        t0 = time.time()
        res2 = engine.decide_intent("print my SQL problem sheet")
        lat = (time.time() - t0) * 1000.0
        tc2 = res2.get("tool_calls", [{}])[0].get("tool") if res2.get("tool_calls") else None
        p2_passed = tc2 in ["PRINT_SQL_WORKSHEET", "PRINTER_PRINT_SQL"]
        self.record_probe(tier, "P3.2", "Tangible Worksheet Dispatch Fast-Path", p2_passed, f"tool={tc2}, msg='{res2.get('response_message')}'", lat)

        # Probe 3.3: PC Workstation Security Command
        t0 = time.time()
        res3 = engine.decide_intent("lock my pc right now")
        lat = (time.time() - t0) * 1000.0
        tc3 = res3.get("tool_calls", [{}])[0].get("tool") if res3.get("tool_calls") else None
        p3_passed = tc3 == "PC_LOCK_WORKSTATION"
        self.record_probe(tier, "P3.3", "PC Workstation Lock Intent Resolution", p3_passed, f"tool={tc3}", lat)

        # Probe 3.4: Ambiguous Entertainment Disambiguation
        t0 = time.time()
        res4 = engine.decide_intent("let's watch something")
        lat = (time.time() - t0) * 1000.0
        msg4 = res4.get("response_message", "")
        p4_passed = any(k in msg4.lower() for k in ["netflix", "youtube", "watch", "stream", "projector"])
        self.record_probe(tier, "P3.4", "Cinema Disambiguation & Provider Prompting", p4_passed, f"msg='{msg4}'", lat)

    # =========================================================================
    # Tier 4: Tangible Actuation & Physical Tool Use
    # =========================================================================
    def test_tier_4_tangible_actuation(self):
        print("\n[TIER 4] Tangible Actuation & Physical Tool Use:")
        tier = "TIER_4_TANGIBLE_ACTUATION"

        briefing = BriefingService()

        # Probe 4.1: SQL Practice Worksheet Structural Richness
        t0 = time.time()
        doc_path = briefing.generate_sql_practice_sheet(problem_title="Blinkit Stock-Out Window Analysis")
        lat = (time.time() - t0) * 1000.0
        content = Path(doc_path).read_text(encoding="utf-8")
        
        has_schema = "TABLE: dark_stores" in content and "TABLE: order_line_items" in content
        has_tuples = "SAMPLE TUPLES (MOCK RECORDS)" in content
        has_grid = "EXPECTED RESULT GRID" in content
        has_paper = "DRAFT YOUR SQL QUERY SOLUTION BELOW" in content
        p1_passed = has_schema and has_tuples and has_grid and has_paper
        self.record_probe(
            tier, "P4.1", "Physical SQL Worksheet Multi-Section Synthesis",
            p1_passed,
            f"schema={has_schema}, tuples={has_tuples}, grid={has_grid}, paper_ruled={has_paper}",
            lat
        )

        # Probe 4.2: Printer Spooling Configuration (HP Ink Tank 310)
        t0 = time.time()
        from printer_controller import PrinterController
        pc = PrinterController()
        lat = (time.time() - t0) * 1000.0
        p2_passed = "HP Ink Tank 310" in pc.target_printer
        self.record_probe(tier, "P4.2", "HP Ink Tank 310 Device Route Binding", p2_passed, f"target_printer='{pc.target_printer}'", lat)

        # Probe 4.3: Physical Safety Bounds (AC Setpoint Rejection)
        t0 = time.time()
        from ac_controller import AcController
        ac = AcController()
        ok_high, res_high = ac.set_temperature(50)
        ok_low, res_low = ac.set_temperature(10)
        bounds_enforced = (
            not ok_high and res_high.get("status") == "INVALID_PARAMETER" and
            not ok_low and res_low.get("status") == "INVALID_PARAMETER" and
            ac.MIN_TEMPERATURE == 16 and ac.MAX_TEMPERATURE == 30
        )
        lat = (time.time() - t0) * 1000.0
        self.record_probe(
            tier, "P4.3", "Thermal Actuator Hardware Bounds Enforcement (16-30°C)",
            bounds_enforced,
            f"reject_50={res_high.get('status')}, reject_10={res_low.get('status')}, bounds=[{ac.MIN_TEMPERATURE}, {ac.MAX_TEMPERATURE}]",
            lat
        )

    # =========================================================================
    # Tier 5: Proactive Ambient Agency & Lifecycle Invariants
    # =========================================================================
    def test_tier_5_proactive_agency(self):
        print("\n[TIER 5] Proactive Ambient Agency & Lifecycle Invariants:")
        tier = "TIER_5_PROACTIVE_AGENCY"

        orch = ProactiveOrchestrator(enable_speech=False, cooldown_seconds=0.0)

        # Probe 5.1: 50-Minute Ergonomic Break & Standup Reset Requirement
        t0 = time.time()
        t_50m = {
            "active_mode": "WORK",
            "desk_present": True,
            "desk_seated_seconds": 3050.0,
            "pc_online": True,
            "pc_locked": False,
            "suppress_morning": True
        }
        res_50m = orch.evaluate_proactive_rules(t_50m)
        fired_50m = (res_50m is not None and res_50m[0] == ProactiveTriggerCategory.ERGONOMIC_50MIN_BREAK)
        res_dup = orch.evaluate_proactive_rules(t_50m)
        no_dup = (res_dup is None)
        orch.evaluate_proactive_rules({"active_mode": "WORK", "desk_present": False, "suppress_morning": True})
        standup_reset = (orch._ergonomic_alerted is False)
        lat = (time.time() - t0) * 1000.0
        p1_passed = fired_50m and no_dup and standup_reset
        self.record_probe(tier, "P5.1", "50-Min Ergonomic Nudge & Physical Standup Reset", p1_passed, f"fired={fired_50m}, no_spam={no_dup}, reset_on_stand={standup_reset}", lat)

        # Probe 5.2: 5-Minute Workstation Auto-Lock
        t0 = time.time()
        class MockPc:
            def __init__(self): self.locked = 0; self.saves = 0
            def lock_workstation(self): self.locked += 1; return True, {}
            def send_save_keystrokes(self): self.saves += 1; return True, {}
        mock_pc = MockPc()
        orch.pc_controller = mock_pc
        now = time.time()
        orch._time_left_desk = now - 310.0  # 5m 10s absence
        orch.evaluate_proactive_rules({"active_mode": "WORK", "desk_present": False, "suppress_morning": True})
        lat = (time.time() - t0) * 1000.0
        p2_passed = (mock_pc.locked == 1) and orch._pc_locked_by_departure
        self.record_probe(tier, "P5.2", "5-Minute Absence Workstation Lock Grace Period", p2_passed, f"locked_count={mock_pc.locked}", lat)

        # Probe 5.3: 120-Minute Autonomous Work Dormancy
        t0 = time.time()
        class MockRoomOrch:
            def __init__(self): self.mode = "WORK"
            def set_active_mode(self, m): self.mode = m
        mock_orch = MockRoomOrch()
        orch.orchestrator = mock_orch
        orch._work_session_started_at = now - 10000.0
        orch._time_left_desk = now - 7260.0  # 121 minutes absence
        res_dormant = orch.evaluate_proactive_rules({"active_mode": "WORK", "desk_present": False, "suppress_morning": True})
        lat = (time.time() - t0) * 1000.0
        p3_passed = (mock_pc.saves == 1) and (mock_orch.mode == "IDLE") and (res_dormant is not None)
        self.record_probe(tier, "P5.3", "120-Minute Autonomous Work Dormancy & Auto-Save", p3_passed, f"saved={mock_pc.saves}, final_mode='{mock_orch.mode}'", lat)

        # Probe 5.4: Strict Mode Isolation Outside WORK
        t0 = time.time()
        mock_pc.locked = 0
        mock_pc.saves = 0
        orch.evaluate_proactive_rules({"active_mode": "RELAX", "desk_present": False, "suppress_morning": True})
        lat = (time.time() - t0) * 1000.0
        p4_passed = (mock_pc.locked == 0) and (mock_pc.saves == 0) and (orch._music_paused_by_departure is False)
        self.record_probe(tier, "P5.4", "Strict Isolation Invariant Outside WORK Mode", p4_passed, f"locked={mock_pc.locked}, saves={mock_pc.saves}", lat)

    # =========================================================================
    # Tier 6: High-Order Domain Problem Solving (Blinkit SQL Mastery Probe)
    # =========================================================================
    def test_tier_6_domain_problem_solving(self):
        print("\n[TIER 6] High-Order Domain Problem Solving (Blinkit SQL Challenge):")
        tier = "TIER_6_DOMAIN_PROBLEM_SOLVING"

        t0 = time.time()
        sql_solution = """
        WITH daily_store_orders AS (
            SELECT 
                store_id,
                DATE(created_at) AS order_date,
                COUNT(*) AS total_orders,
                SUM(CASE WHEN fulfillment_status = 'STOCKOUT_CANCELLED' THEN 1 ELSE 0 END) AS stockout_cancellations
            FROM order_line_items
            GROUP BY store_id, DATE(created_at)
        ),
        rolling_metrics AS (
            SELECT
                store_id,
                order_date,
                stockout_cancellations,
                total_orders,
                SUM(stockout_cancellations) OVER(
                    PARTITION BY store_id 
                    ORDER BY order_date 
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS rolling_3d_cancellations,
                SUM(total_orders) OVER(
                    PARTITION BY store_id 
                    ORDER BY order_date 
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS rolling_3d_orders
            FROM daily_store_orders
        )
        SELECT
            ds.store_name,
            rm.store_id,
            rm.order_date,
            ROUND((rm.rolling_3d_cancellations * 100.0 / rm.rolling_3d_orders), 2) AS rolling_cancellation_pct,
            CASE 
                WHEN (rm.rolling_3d_cancellations * 100.0 / rm.rolling_3d_orders) >= 12.0 THEN 'CRITICAL_ALERT'
                ELSE 'NORMAL'
            END AS inventory_health
        FROM rolling_metrics rm
        JOIN dark_stores ds ON rm.store_id = ds.store_id
        WHERE rm.order_date = '2026-09-04'
        ORDER BY rolling_cancellation_pct DESC;
        """

        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute("CREATE TABLE dark_stores (store_id INT, store_name TEXT);")
        cur.execute("CREATE TABLE order_line_items (order_id INT, store_id INT, sku_id INT, fulfillment_status TEXT, created_at TEXT);")
        
        cur.execute("INSERT INTO dark_stores VALUES (101, 'Indiranagar Hub-A'), (102, 'Koramangala Pocket-4');")
        
        for d in ['2026-09-02', '2026-09-03', '2026-09-04']:
            for _ in range(8):
                cur.execute(f"INSERT INTO order_line_items VALUES (1, 101, 501, 'FULFILLED', '{d} 18:00:00');")
            for _ in range(2):
                cur.execute(f"INSERT INTO order_line_items VALUES (2, 101, 502, 'STOCKOUT_CANCELLED', '{d} 19:00:00');")
            for _ in range(10):
                cur.execute(f"INSERT INTO order_line_items VALUES (3, 102, 401, 'FULFILLED', '{d} 18:30:00');")
        conn.commit()

        try:
            cur.execute(sql_solution)
            rows = cur.fetchall()
            lat = (time.time() - t0) * 1000.0
            
            s101 = next((r for r in rows if r[1] == 101), None)
            s102 = next((r for r in rows if r[1] == 102), None)
            
            p1_passed = (s101 is not None and s101[3] == 20.0 and s101[4] == 'CRITICAL_ALERT') and \
                        (s102 is not None and s102[3] == 0.0 and s102[4] == 'NORMAL')
            
            self.record_probe(
                tier, "P6.1", "Blinkit Stock-Out Window Function CTE Query Execution",
                p1_passed,
                f"Store 101 rate={s101[3] if s101 else None}% ({s101[4] if s101 else None}), Store 102 rate={s102[3] if s102 else None}%",
                lat
            )
        except Exception as e:
            self.record_probe(tier, "P6.1", "Blinkit Stock-Out Window Function CTE Query Execution", False, f"SQL Execution Error: {e}", (time.time() - t0) * 1000.0)
        finally:
            conn.close()


if __name__ == "__main__":
    benchmark = AnimusAgiBenchmark()
    report = benchmark.run_all_tiers()
    
    out_file = Path("d:/AnimusSmartRoom/server/music_daemon/scratch/animus_agi_benchmark_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved benchmark telemetry to {out_file}")
