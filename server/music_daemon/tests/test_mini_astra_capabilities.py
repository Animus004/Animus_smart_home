"""
================================================================================
ANIMUS SMART ROOM — MINI-ASTRA PHYSICAL CAPABILITIES TEST SUITE
================================================================================
Comprehensive verification of expanded physical device controls:
1. HP Ink Tank 310 series USB printing & spooler queue management
2. Zebronics Projector camera autofocus, gyro auto-keystone & source selection
3. Amazon Fire TV streaming playback & D-Pad navigation
4. PC workstation lock & allowlisted application launching
5. Air conditioner power on & blower fan speed
6. Ambient smart lighting scene presets & brightness
7. Fast-path deterministic routing
================================================================================
"""

import os
import sys
import tempfile
import pytest

# Ensure daemon directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from printer_controller import PrinterController, get_printer_controller
from light_controller import LightController, get_light_controller
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine
from agent.reality_observer import RealityObserver, ObservationSnapshot, VerificationStatus


class TestPrinterSubsystem:
    """Validates HP Ink Tank 310 USB and Windows Spooler integration."""

    def test_printer_status_query(self):
        pc = get_printer_controller()
        status = pc.get_status()
        assert isinstance(status, dict)
        assert "printer_name" in status
        assert "HP Ink Tank" in status["printer_name"]
        assert status.get("is_online") is True
        assert "job_count" in status

    def test_printer_file_security_rejection(self):
        pc = PrinterController(is_simulated=True)
        # Unauthorized executable
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"fake binary")
            bad_file = f.name
        try:
            ok, res = pc.print_file(bad_file)
            assert ok is False
            assert res.get("status") == "INVALID_EXTENSION"
        finally:
            if os.path.exists(bad_file):
                os.unlink(bad_file)

    def test_printer_file_print_simulated(self):
        pc = PrinterController(is_simulated=True)
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Blinkit Dark Store SQL Practice Sheet\nAuthor: Sayan Halder")
            txt_file = f.name
        try:
            ok, res = pc.print_file(txt_file)
            assert ok is True
            assert res.get("action") == "PRINT_FILE"
            assert res.get("verified") is True
        finally:
            if os.path.exists(txt_file):
                os.unlink(txt_file)

    def test_printer_cancel_all_jobs(self):
        pc = PrinterController(is_simulated=True)
        ok, res = pc.cancel_all_jobs()
        assert ok is True
        assert res.get("action") == "CANCEL_ALL_JOBS"


class TestMiniAstraDecisionEngineDispatch:
    """Validates tool dispatching for physical room subsystems."""

    @pytest.fixture
    def engine(self, tmp_path):
        from agent.long_term_memory import LongTermMemoryStore
        db_file = tmp_path / "test_mini_astra.db"
        mem = LongTermMemoryStore(db_path=db_file)
        return AgentDecisionEngine(memory_store=mem)

    def test_dispatch_printer_status(self, engine):
        res = engine._dispatch_single_tool(1, "PRINTER_GET_STATUS", {}, None)
        assert res.get("tool") == "PRINTER_GET_STATUS"
        assert res.get("status") in ["SUCCESS", "SIMULATED"]
        assert "telemetry" in res

    def test_dispatch_printer_cancel(self, engine):
        res = engine._dispatch_single_tool(2, "PRINTER_CANCEL_JOBS", {}, None)
        assert res.get("tool") == "PRINTER_CANCEL_JOBS"
        assert res.get("status") in ["SUCCESS", "SIMULATED"]

    def test_dispatch_ac_power_on(self, engine):
        res = engine._dispatch_single_tool(3, "AC_POWER_ON", {}, None)
        assert res.get("tool") == "AC_POWER_ON"
        assert res.get("status") in ["SUCCESS", "SIMULATED"]
        assert res.get("power") is True

    def test_dispatch_ac_set_fan(self, engine):
        res = engine._dispatch_single_tool(4, "AC_SET_FAN", {"fan_speed": "HIGH"}, None)
        assert res.get("tool") == "AC_SET_FAN"
        assert res.get("status") in ["SUCCESS", "SIMULATED", "FAILED"]
        assert res.get("fan_speed") == "HIGH"

    def test_dispatch_projector_calibration(self, engine):
        res_focus = engine._dispatch_single_tool(5, "PROJECTOR_AUTO_FOCUS", {}, None)
        assert res_focus.get("tool") == "PROJECTOR_AUTO_FOCUS"
        assert res_focus.get("status") in ["SUCCESS", "SIMULATED"]

        res_keystone = engine._dispatch_single_tool(6, "PROJECTOR_AUTO_KEYSTONE", {}, None)
        assert res_keystone.get("tool") == "PROJECTOR_AUTO_KEYSTONE"
        assert res_keystone.get("status") in ["SUCCESS", "SIMULATED"]

        res_source = engine._dispatch_single_tool(7, "PROJECTOR_SET_SOURCE", {"source": "HDMI_1"}, None)
        assert res_source.get("tool") == "PROJECTOR_SET_SOURCE"
        assert res_source.get("status") in ["SUCCESS", "SIMULATED", "FAILED"]
        assert res_source.get("source") == "HDMI_1"

        res_bright = engine._dispatch_single_tool(8, "PROJECTOR_SET_BRIGHTNESS", {"brightness": 75}, None)
        assert res_bright.get("tool") == "PROJECTOR_SET_BRIGHTNESS"
        assert res_bright.get("status") in ["SUCCESS", "SIMULATED", "FAILED"]

    def test_dispatch_fire_tv_media_and_nav(self, engine):
        res_play = engine._dispatch_single_tool(9, "FIRE_TV_MEDIA_PLAY", {}, None)
        assert res_play.get("status") == "SUCCESS"

        res_pause = engine._dispatch_single_tool(10, "FIRE_TV_MEDIA_PAUSE", {}, None)
        assert res_pause.get("status") == "SUCCESS"

        res_nav = engine._dispatch_single_tool(11, "FIRE_TV_KEY_NAVIGATE", {"key": "SELECT"}, None)
        assert res_nav.get("status") == "SUCCESS"
        assert res_nav.get("key") == "SELECT"

    def test_dispatch_pc_lock_and_app(self, engine):
        res_app = engine._dispatch_single_tool(12, "PC_LAUNCH_APP", {"app_name": "calc"}, None)
        assert res_app.get("tool") == "PC_LAUNCH_APP"
        assert res_app.get("status") in ["SUCCESS", "SIMULATED"]

        res_lock = engine._dispatch_single_tool(13, "PC_LOCK_WORKSTATION", {}, None)
        assert res_lock.get("tool") == "PC_LOCK_WORKSTATION"
        assert res_lock.get("status") in ["SUCCESS", "SIMULATED"]

    def test_dispatch_lighting_scenes(self, engine):
        res_scene = engine._dispatch_single_tool(14, "LIGHTING_SET_SCENE", {"scene": "FOCUS"}, None)
        assert res_scene.get("tool") == "LIGHTING_SET_SCENE"
        assert res_scene.get("status") == "SUCCESS"
        assert res_scene.get("scene") == "FOCUS"

        res_bright = engine._dispatch_single_tool(15, "LIGHTING_SET_BRIGHTNESS", {"brightness": 45}, None)
        assert res_bright.get("tool") == "LIGHTING_SET_BRIGHTNESS"
        assert res_bright.get("status") == "SUCCESS"
        assert res_bright.get("brightness") == 45

        res_power = engine._dispatch_single_tool(16, "LIGHTING_SET_POWER", {"power": False}, None)
        assert res_power.get("tool") == "LIGHTING_SET_POWER"
        assert res_power.get("status") == "SUCCESS"
        assert res_power.get("power") is False

    def test_dispatch_media_transport(self, engine):
        res_stop = engine._dispatch_single_tool(17, "MUSIC_STOP", {}, None)
        assert res_stop.get("status") == "SUCCESS"

        res_next = engine._dispatch_single_tool(18, "MUSIC_NEXT", {}, None)
        assert res_next.get("status") == "SUCCESS"

        res_prev = engine._dispatch_single_tool(19, "MUSIC_PREVIOUS", {}, None)
        assert res_prev.get("status") == "SUCCESS"


class TestFastPathMiniAstra:
    """Validates low-latency deterministic fast-paths for new physical capabilities."""

    @pytest.fixture
    def engine(self, tmp_path):
        from agent.long_term_memory import LongTermMemoryStore
        db_file = tmp_path / "test_mini_fastpath.db"
        mem = LongTermMemoryStore(db_path=db_file)
        return AgentDecisionEngine(memory_store=mem)

    def test_fastpath_printer_status(self, engine):
        dec = engine._try_fastpath_decision("check printer status")
        assert dec is not None
        assert dec["action_type"] == "TOOL_EXECUTION"
        assert dec["tool_calls"][0]["tool"] == "PRINTER_GET_STATUS"

    def test_fastpath_pc_lock(self, engine):
        dec = engine._try_fastpath_decision("lock the pc please")
        assert dec is not None
        assert dec["action_type"] == "TOOL_EXECUTION"
        assert dec["tool_calls"][0]["tool"] == "PC_LOCK_WORKSTATION"

    def test_fastpath_projector_focus(self, engine):
        dec = engine._try_fastpath_decision("autofocus the projector")
        assert dec is not None
        assert dec["action_type"] == "TOOL_EXECUTION"
        assert dec["tool_calls"][0]["tool"] == "PROJECTOR_AUTO_FOCUS"

    def test_fastpath_projector_keystone(self, engine):
        dec = engine._try_fastpath_decision("auto keystone projector")
        assert dec is not None
        assert dec["action_type"] == "TOOL_EXECUTION"
        assert dec["tool_calls"][0]["tool"] == "PROJECTOR_AUTO_KEYSTONE"

    def test_fastpath_lighting_scene(self, engine):
        dec = engine._try_fastpath_decision("relax lights")
        assert dec is not None
        assert dec["action_type"] == "TOOL_EXECUTION"
        assert dec["tool_calls"][0]["tool"] == "LIGHTING_SET_SCENE"
        assert dec["tool_calls"][0]["params"]["scene"] == "RELAX"


class TestPromptBuilderMiniAstraCatalog:
    """Validates that all physical tools are documented and exposed to LLM context."""

    def test_tool_catalog_contains_mini_astra_tools(self):
        pb = CognitivePromptBuilder()
        catalog = pb.get_default_tool_catalog()
        names = {t["name"] for t in catalog}

        expected_tools = [
            "PRINTER_GET_STATUS", "PRINTER_PRINT_FILE", "PRINTER_CANCEL_JOBS",
            "AC_POWER_ON", "AC_SET_FAN",
            "PROJECTOR_SET_SOURCE", "PROJECTOR_AUTO_FOCUS", "PROJECTOR_AUTO_KEYSTONE", "PROJECTOR_SET_BRIGHTNESS",
            "FIRE_TV_MEDIA_PLAY", "FIRE_TV_MEDIA_PAUSE", "FIRE_TV_MEDIA_NEXT", "FIRE_TV_MEDIA_PREVIOUS", "FIRE_TV_KEY_NAVIGATE",
            "PC_LOCK_WORKSTATION", "PC_LAUNCH_APP", "PC_SLEEP",
            "LIGHTING_SET_SCENE", "LIGHTING_SET_BRIGHTNESS", "LIGHTING_SET_POWER",
            "MUSIC_STOP", "MUSIC_NEXT", "MUSIC_PREVIOUS"
        ]

        for tool in expected_tools:
            assert tool in names, f"Expected Mini-Astra tool '{tool}' missing from catalog!"

    def test_sanitize_telemetry_includes_printer_and_lighting(self):
        pb = CognitivePromptBuilder()
        telem = pb.sanitize_room_telemetry(None)
        assert "printer" in telem
        assert "lighting" in telem
        assert telem["printer"]["model"] == "HP Ink Tank 310 series"
