import pytest
from unittest.mock import MagicMock, patch
from projector_controller import (
    ProjectorController,
    ProjectorPowerState,
    ProjectorSource,
    ProjectorSignalState,
    ThermalStatus,
    FanStatus
)
from projector_command_router import ProjectorCommandRouter, CommandCategory

@pytest.fixture
def mock_controller():
    ctrl = MagicMock(spec=ProjectorController)
    ctrl.get_power_state.return_value = {
        "reachable": True,
        "connected": True,
        "wakefulness": "Awake",
        "display_state": "ON",
        "power_state": "ON",
        "interactive": True,
        "verified": True
    }
    ctrl.get_current_source.return_value = ProjectorSource.HDMI_1
    ctrl.get_signal_state.return_value = {
        "signal_state": "HDMI_SIGNAL_ACTIVE",
        "active_stream": True,
        "verified": True
    }
    ctrl.get_hardware_health.return_value = {
        "temperature_celsius": 32.1,
        "main_fan_rpm": 3245.0,
        "sub_fan_rpm": 3620.0,
        "thermal_status": "SAFE",
        "fan_status": "HEALTHY",
        "verified": True
    }
    ctrl.get_brightness.return_value = 40
    ctrl.set_brightness.return_value = (True, 70)
    ctrl.auto_focus.return_value = {"status": "TRIGGERED", "action": "auto_focus", "verified": False}
    ctrl.auto_keystone.return_value = {"status": "TRIGGERED", "action": "auto_keystone", "verified": False}
    ctrl.wake.return_value = True
    ctrl.sleep.return_value = True
    ctrl.power_off.return_value = True
    ctrl.set_hdmi.return_value = True
    ctrl.home.return_value = True
    ctrl.back.return_value = True
    ctrl.menu.return_value = True
    ctrl.dpad_up.return_value = True
    ctrl.dpad_down.return_value = True
    ctrl.dpad_left.return_value = True
    ctrl.dpad_right.return_value = True
    ctrl.dpad_center.return_value = True
    return ctrl

@pytest.fixture
def router(mock_controller):
    return ProjectorCommandRouter(controller=mock_controller)

# =========================================================================
# 1. Power Commands (1–6)
# =========================================================================

def test_power_turn_on_when_already_on_idempotent(router, mock_controller):
    res = router.route_command("Turn on the projector.")
    assert res["category"] == CommandCategory.POWER.value
    assert res["capability"] == "PROJECTOR_POWER_WAKE"
    assert res["success"] is True
    assert res["status"] == "ALREADY_ON"
    assert res["idempotent"] is True

def test_power_turn_on_from_standby_wakes(router, mock_controller):
    mock_controller.get_power_state.side_effect = [
        {"reachable": True, "power_state": "STANDBY", "interactive": False},
        {"reachable": True, "power_state": "ON", "display_state": "ON", "interactive": True}
    ]
    res = router.route_command("Turn on the projector.")
    assert res["capability"] == "PROJECTOR_POWER_WAKE"
    assert res["success"] is True
    assert res["status"] == "WOKEN_FROM_STANDBY"

def test_power_turn_on_when_cold_off_requires_ir(router, mock_controller):
    mock_controller.get_power_state.return_value = {"reachable": False, "power_state": "OFF"}
    res = router.route_command("Turn on the projector.")
    assert res["capability"] == "PROJECTOR_POWER_ON_COLD"
    assert res["success"] is False
    assert res["status"] == "NOT_AVAILABLE_VIA_ADB"
    assert "IR blaster" in res["error"]

def test_power_wake_commands(router, mock_controller):
    mock_controller.get_power_state.side_effect = [
        {"reachable": True, "power_state": "STANDBY", "interactive": False},
        {"reachable": True, "power_state": "ON", "display_state": "ON", "interactive": True}
    ]
    res = router.route_command("Wake the projector.")
    assert res["capability"] == "PROJECTOR_POWER_WAKE"

    mock_controller.get_power_state.side_effect = [
        {"reachable": True, "power_state": "STANDBY", "interactive": False},
        {"reachable": True, "power_state": "ON", "display_state": "ON", "interactive": True}
    ]
    res2 = router.route_command("Wake up the screen.")
    assert res2["capability"] == "PROJECTOR_POWER_WAKE"

def test_power_sleep_command(router, mock_controller):
    mock_controller.get_power_state.return_value = {
        "reachable": True,
        "power_state": "STANDBY",
        "display_state": "OFF"
    }
    res = router.route_command("Put the projector to sleep.")
    assert res["category"] == CommandCategory.POWER.value
    assert res["capability"] == "PROJECTOR_POWER_SLEEP"
    assert res["success"] is True
    assert res["status"] == "PUT_TO_SLEEP"


def test_power_off_graceful_oem(router, mock_controller):
    res = router.route_command("Turn the projector off.")
    assert res["category"] == CommandCategory.POWER.value
    assert res["capability"] == "PROJECTOR_POWER_OFF_OEM"
    assert res["success"] is True
    assert res["status"] == "OEM_SHUTDOWN_INITIATED"

    res2 = router.route_command("Shut down the projector safely.")
    assert res2["capability"] == "PROJECTOR_POWER_OFF_OEM"
    assert res2["success"] is True

# =========================================================================
# 2. Input / Source Commands (7–12)
# =========================================================================

def test_source_hdmi_already_on_hdmi_idempotent(router, mock_controller):
    mock_controller.get_current_source.return_value = ProjectorSource.HDMI_1
    res = router.route_command("Put the projector on HDMI.")
    assert res["category"] == CommandCategory.INPUT_SOURCE.value
    assert res["capability"] == "PROJECTOR_SWITCH_HDMI1"
    assert res["success"] is True
    assert res["status"] == "ALREADY_ON_HDMI_1"
    assert res["idempotent"] is True

def test_source_hdmi_switch_from_android(router, mock_controller):
    mock_controller.get_current_source.side_effect = [
        ProjectorSource.ANDROID_HOME,  # before
        ProjectorSource.HDMI_1         # after switch
    ]
    res = router.route_command("Switch the projector to HDMI 1.")
    assert res["capability"] == "PROJECTOR_SWITCH_HDMI1"
    assert res["success"] is True
    assert res["status"] == "SWITCHED_TO_HDMI_1"

def test_source_show_fire_tv(router, mock_controller):
    mock_controller.get_current_source.side_effect = [
        ProjectorSource.ANDROID_HOME,
        ProjectorSource.HDMI_1
    ]
    res = router.route_command("Show the Fire TV.")
    assert res["capability"] == "PROJECTOR_SWITCH_HDMI1"
    assert res["success"] is True

def test_source_switch_to_android_home(router, mock_controller):
    mock_controller.get_current_source.return_value = ProjectorSource.ANDROID_HOME
    res = router.route_command("Switch back to the projector's Android home.")
    assert res["capability"] == "PROJECTOR_SWITCH_ANDROID_HOME"
    assert res["success"] is True
    assert res["status"] == "SWITCHED_TO_ANDROID_HOME"

    res2 = router.route_command("Go to the projector home screen.")
    assert res2["capability"] == "PROJECTOR_SWITCH_ANDROID_HOME"
    assert res2["success"] is True

def test_source_open_usb_media_player(router, mock_controller):
    mock_controller.get_current_source.return_value = ProjectorSource.USB
    res = router.route_command("Open the USB media player.")
    assert res["capability"] == "PROJECTOR_SWITCH_USB_FILEMGR"
    assert res["success"] is True
    assert res["status"] == "SWITCHED_TO_USB"

# =========================================================================
# 3. Video / Signal Diagnostics (13–17)
# =========================================================================

def test_signal_query_active_streaming(router, mock_controller):
    mock_controller.get_signal_state.return_value = {
        "signal_state": "HDMI_SIGNAL_ACTIVE",
        "active_stream": True,
        "verified": True
    }
    mock_controller.get_power_state.return_value = {"power_state": "ON", "display_state": "ON"}

    res = router.route_command("Is the projector getting a signal?")
    assert res["category"] == CommandCategory.VIDEO_SIGNAL.value
    assert res["capability"] == "PROJECTOR_GET_SIGNAL_STATE"
    assert res["success"] is True
    assert res["status"] == "HDMI_SIGNAL_ACTIVE"

def test_signal_query_hdmi_working(router, mock_controller):
    res = router.route_command("Is HDMI working?")
    assert res["capability"] == "PROJECTOR_GET_SIGNAL_STATE"
    assert res["status"] == "HDMI_SIGNAL_ACTIVE"

def test_signal_query_fire_tv_reaching(router, mock_controller):
    res = router.route_command("Is the Fire TV signal reaching the projector?")
    assert res["capability"] == "PROJECTOR_GET_SIGNAL_STATE"
    assert res["status"] == "HDMI_SIGNAL_ACTIVE"

def test_signal_query_why_screen_black_when_screen_standby(router, mock_controller):
    mock_controller.get_power_state.return_value = {"power_state": "STANDBY", "display_state": "OFF"}
    res = router.route_command("Why is the projector screen black?")
    assert res["capability"] == "PROJECTOR_GET_SIGNAL_STATE"
    assert res["status"] == "SCREEN_STANDBY"

def test_signal_query_check_video_signal_lost(router, mock_controller):
    mock_controller.get_signal_state.return_value = {
        "signal_state": "HDMI_SIGNAL_LOST",
        "active_stream": False,
        "verified": True
    }
    mock_controller.get_power_state.return_value = {"power_state": "ON", "display_state": "ON"}
    res = router.route_command("Check the projector video signal.")
    assert res["status"] == "HDMI_SIGNAL_LOST"

# =========================================================================
# 4. Optical Maintenance Commands (18–23)
# =========================================================================

def test_auto_focus_commands(router, mock_controller):
    res1 = router.route_command("Focus the projector.")
    assert res1["category"] == CommandCategory.OPTICAL_MAINTENANCE.value
    assert res1["capability"] == "PROJECTOR_AUTO_FOCUS"
    assert res1["status"] == "FOCUS_TRIGGERED"
    assert res1["truthful_status"] == "TRIGGERED"

    res2 = router.route_command("The picture is blurry, fix it.")
    assert res2["capability"] == "PROJECTOR_AUTO_FOCUS"
    assert res2["status"] == "FOCUS_TRIGGERED"

    res3 = router.route_command("Auto focus the projector.")
    assert res3["capability"] == "PROJECTOR_AUTO_FOCUS"
    assert res3["status"] == "FOCUS_TRIGGERED"

def test_auto_keystone_commands(router, mock_controller):
    res1 = router.route_command("Fix the crooked picture.")
    assert res1["category"] == CommandCategory.OPTICAL_MAINTENANCE.value
    assert res1["capability"] == "PROJECTOR_AUTO_KEYSTONE"
    assert res1["status"] == "KEYSTONE_TRIGGERED"
    assert res1["truthful_status"] == "TRIGGERED"

    res2 = router.route_command("Auto align the projector.")
    assert res2["capability"] == "PROJECTOR_AUTO_KEYSTONE"
    assert res2["status"] == "KEYSTONE_TRIGGERED"

    res3 = router.route_command("Run auto keystone.")
    assert res3["capability"] == "PROJECTOR_AUTO_KEYSTONE"
    assert res3["status"] == "KEYSTONE_TRIGGERED"

# =========================================================================
# 5. Brightness Commands (24–28) & Boundaries
# =========================================================================

def test_brightness_set_explicit_percentage(router, mock_controller):
    mock_controller.set_brightness.return_value = (True, 70)
    res = router.route_command("Set the projector brightness to 70%.")
    assert res["category"] == CommandCategory.BRIGHTNESS.value
    assert res["capability"] == "PROJECTOR_SET_BRIGHTNESS"
    assert res["requested_percent"] == 70
    assert res["actual_percent"] == 70
    assert res["success"] is True
    assert res["status"] == "BRIGHTNESS_SET_VERIFIED"

def test_brightness_dim_command(router, mock_controller):
    mock_controller.set_brightness.return_value = (True, 30)
    res = router.route_command("Dim the projector to 30%.")
    assert res["requested_percent"] == 30
    assert res["actual_percent"] == 30

def test_brightness_make_brighter_and_darker(router, mock_controller):
    mock_controller.get_brightness.return_value = 50
    mock_controller.set_brightness.return_value = (True, 65)
    res = router.route_command("Make the projector brighter.")
    assert res["requested_percent"] == 65

    mock_controller.set_brightness.return_value = (True, 35)
    res2 = router.route_command("Make the projector darker.")
    assert res2["requested_percent"] == 35

def test_brightness_query(router, mock_controller):
    mock_controller.get_brightness.return_value = 45
    res = router.route_command("What is the projector brightness?")
    assert res["capability"] == "PROJECTOR_GET_BRIGHTNESS"
    assert res["brightness_percent"] == 45
    assert res["status"] == "BRIGHTNESS_READ"

def test_brightness_boundaries_and_rejections(router, mock_controller):
    # Valid boundaries: 0%, 1%, 50%, 99%, 100%
    for b in [0, 1, 50, 99, 100]:
        mock_controller.set_brightness.return_value = (True, b)
        res = router.route_command(f"Set the projector brightness to {b}%.")
        assert res["success"] is True
        assert res["requested_percent"] == b

    # Invalid values: 101, 150
    for invalid_b in [101, 150]:
        res_inv = router.route_command(f"Set the projector brightness to {invalid_b}%.")
        assert res_inv["success"] is False
        assert res_inv["status"] == "INVALID_PARAMETER"

# =========================================================================
# 6. Hardware Health Commands (29–33)
# =========================================================================

def test_hardware_health_queries(router, mock_controller):
    mock_controller.get_hardware_health.return_value = {
        "temperature_celsius": 31.5,
        "main_fan_rpm": 3248.0,
        "sub_fan_rpm": 3520.0,
        "thermal_status": "SAFE",
        "fan_status": "HEALTHY",
        "verified": True
    }

    commands = [
        "How hot is the projector?",
        "Check projector temperature.",
        "Are the projector fans working?",
        "Is the projector overheating?",
        "Give me the projector health."
    ]

    for cmd in commands:
        res = router.route_command(cmd)
        assert res["category"] == CommandCategory.HARDWARE_HEALTH.value
        assert res["capability"] == "PROJECTOR_GET_HARDWARE_HEALTH"
        assert res["success"] is True
        assert res["truthful_status"] == "SAFE"
        assert "31.5°C" in res["message"]

# =========================================================================
# 7. Navigation Commands (34–40)
# =========================================================================

def test_navigation_keys(router, mock_controller):
    nav_tests = [
        ("Go back on the projector.", "PROJECTOR_NAV_BACK"),
        ("Open the projector menu.", "PROJECTOR_NAV_MENU"),
        ("Move up.", "PROJECTOR_NAV_DPAD_UP"),
        ("Move down.", "PROJECTOR_NAV_DPAD_DOWN"),
        ("Move left.", "PROJECTOR_NAV_DPAD_LEFT"),
        ("Move right.", "PROJECTOR_NAV_DPAD_RIGHT"),
        ("Select that.", "PROJECTOR_NAV_SELECT"),
    ]

    for cmd, expected_cap in nav_tests:
        res = router.route_command(cmd)
        assert res["category"] == CommandCategory.NAVIGATION.value
        assert res["capability"] == expected_cap
        assert res["success"] is True
        assert res["truthful_status"] == "VERIFIED"

# =========================================================================
# 8. Negative / Safety Tests (41–46)
# =========================================================================

def test_safety_reject_hdmi_2(router, mock_controller):
    res = router.route_command("Switch the projector to HDMI 2.")
    assert res["category"] == CommandCategory.SAFETY_NEGATIVE.value
    assert res["capability"] == "PROJECTOR_SWITCH_HDMI2"
    assert res["success"] is False
    assert res["status"] == "UNSUPPORTED_HARDWARE"
    assert "ONE physical HDMI port" in res["error"]

def test_safety_reject_hdmi_3(router, mock_controller):
    res = router.route_command("Switch the projector to HDMI 3.")
    assert res["category"] == CommandCategory.SAFETY_NEGATIVE.value
    assert res["capability"] == "PROJECTOR_SWITCH_HDMI3"
    assert res["success"] is False
    assert res["status"] == "UNSUPPORTED_HARDWARE"
    assert "ONE physical HDMI port" in res["error"]

def test_safety_cold_power_on_rejection(router, mock_controller):
    res = router.route_command("Turn on the projector from completely cold power-off.")
    assert res["category"] == CommandCategory.SAFETY_NEGATIVE.value
    assert res["capability"] == "PROJECTOR_POWER_ON_COLD"
    assert res["success"] is False
    assert res["status"] == "NOT_AVAILABLE_VIA_ADB"
    assert res["physical_result"] == "IR_REQUIRED"

def test_unresolved_query_fallback(router, mock_controller):
    res = router.route_command("Make the projector dance a salsa.")
    assert res["category"] == "UNKNOWN"
    assert res["success"] is False
    assert res["status"] == "UNRESOLVED_COMMAND"
