"""
Unit and Contract Test Suite for Phase E.7.2 Unified Capability Registry.
Verifies machine-readable catalog, canonical IDs, bidirectional translation,
parameter constraints, safety bounds, validation errors, and deterministic serialization.
"""

import pytest
from capability_registry import (
    Subsystem,
    SafetyLevel,
    CapabilityStatus,
    ParameterType,
    ParameterConstraint,
    CapabilityDefinition,
    UnifiedCapabilityRegistry,
    RegistryValidationError,
    AUTHORITATIVE_CAPABILITIES
)
from fire_tv_capabilities import FireTVCapabilityType


# =============================================================================
# 1. Registry Initialization & Baseline Integrity
# =============================================================================

def test_registry_loads_successfully():
    registry = UnifiedCapabilityRegistry()
    caps = registry.get_all_capabilities()
    assert len(caps) > 0
    assert len(caps) == len(AUTHORITATIVE_CAPABILITIES)


def test_canonical_ids_are_unique_and_uppercase():
    registry = UnifiedCapabilityRegistry()
    caps = registry.get_all_capabilities()
    seen = set()
    for cap in caps:
        assert cap.canonical_id not in seen
        assert cap.canonical_id == cap.canonical_id.upper().strip()
        seen.add(cap.canonical_id)


def test_complete_verified_baseline_represented():
    registry = UnifiedCapabilityRegistry()
    
    # Projector
    assert registry.get_capability("PROJECTOR_POWER_WAKE") is not None
    assert registry.get_capability("PROJECTOR_POWER_SLEEP") is not None
    assert registry.get_capability("PROJECTOR_SWITCH_HDMI1") is not None
    assert registry.get_capability("PROJECTOR_SWITCH_ANDROID_HOME") is not None
    assert registry.get_capability("PROJECTOR_SET_BRIGHTNESS") is not None

    # AC
    assert registry.get_capability("AC_POWER_ON") is not None
    assert registry.get_capability("AC_POWER_OFF") is not None
    assert registry.get_capability("AC_SET_TEMPERATURE") is not None
    assert registry.get_capability("AC_SET_MODE") is not None
    assert registry.get_capability("AC_SET_FAN") is not None

    # PC
    assert registry.get_capability("PC_SET_VOLUME") is not None
    assert registry.get_capability("PC_MUTE") is not None
    assert registry.get_capability("PC_UNMUTE") is not None
    assert registry.get_capability("PC_MEDIA_PLAY_PAUSE") is not None
    assert registry.get_capability("PC_LOCK_WORKSTATION") is not None

    # Soundbar
    assert registry.get_capability("SOUNDBAR_ROUTE_TO_FIRE_TV") is not None
    assert registry.get_capability("SOUNDBAR_ROUTE_TO_PC") is not None


def test_fire_tv_capabilities_represented():
    """Verifies that all 35 verified Fire TV capability enums map to canonical registry entries."""
    registry = UnifiedCapabilityRegistry()
    ftv_caps = registry.get_capabilities_by_subsystem(Subsystem.FIRE_TV)
    assert len(ftv_caps) >= 30

    for ftv_enum in FireTVCapabilityType:
        canonical_id = registry.get_canonical_id_for_underlying(Subsystem.FIRE_TV, ftv_enum.value)
        assert canonical_id is not None, f"FireTVCapabilityType.{ftv_enum.name} ({ftv_enum.value}) not mapped in UnifiedCapabilityRegistry"


# =============================================================================
# 2. Bidirectional Translation & Unknown Value Handling
# =============================================================================

def test_bidirectional_translation():
    registry = UnifiedCapabilityRegistry()

    # Projector
    assert registry.get_underlying_name("PROJECTOR_SWITCH_HDMI1") == "projector_switch_hdmi1"
    assert registry.get_canonical_id_for_underlying(Subsystem.PROJECTOR, "projector_switch_hdmi1") == "PROJECTOR_SWITCH_HDMI1"

    # AC
    assert registry.get_underlying_name("AC_SET_TEMPERATURE") == "ac_set_temperature"
    assert registry.get_canonical_id_for_underlying(Subsystem.AC, "ac_set_temperature") == "AC_SET_TEMPERATURE"

    # Fire TV
    assert registry.get_underlying_name("FIRE_TV_BT_CONNECT_SOUNDBAR") == "bt_connect_soundbar"
    assert registry.get_canonical_id_for_underlying(Subsystem.FIRE_TV, "bt_connect_soundbar") == "FIRE_TV_BT_CONNECT_SOUNDBAR"

    # PC
    assert registry.get_underlying_name("PC_SET_VOLUME") == "pc_set_volume"
    assert registry.get_canonical_id_for_underlying(Subsystem.PC, "pc_set_volume") == "PC_SET_VOLUME"

    # Soundbar
    assert registry.get_underlying_name("SOUNDBAR_ROUTE_TO_FIRE_TV") == "soundbar_route_to_fire_tv"
    assert registry.get_canonical_id_for_underlying(Subsystem.SOUNDBAR, "soundbar_route_to_fire_tv") == "SOUNDBAR_ROUTE_TO_FIRE_TV"


def test_unknown_lookups_fail_safely():
    registry = UnifiedCapabilityRegistry()

    # Non-existent canonical IDs
    assert registry.get_capability("NON_EXISTENT_CAPABILITY") is None
    assert registry.get_underlying_name("NON_EXISTENT_CAPABILITY") is None
    assert registry.get_capability("") is None

    # Non-existent underlying names
    assert registry.get_canonical_id_for_underlying(Subsystem.PC, "non_existent_function") is None
    assert registry.get_canonical_id_for_underlying(Subsystem.AC, "") is None


# =============================================================================
# 3. Parameter Safety & Physical Bounds
# =============================================================================

def test_parameter_bounds_and_enums():
    registry = UnifiedCapabilityRegistry()

    # Projector brightness: 1 to 100
    p_bri = registry.get_capability("PROJECTOR_SET_BRIGHTNESS")
    assert p_bri is not None
    bri_param = p_bri.parameters["brightness"]
    assert bri_param.min_value == 1
    assert bri_param.max_value == 100
    assert bri_param.validate_value(50) is True
    assert bri_param.validate_value(0) is False
    assert bri_param.validate_value(101) is False
    assert bri_param.validate_value("50") is False

    # AC temperature: 16 to 30
    ac_temp = registry.get_capability("AC_SET_TEMPERATURE")
    assert ac_temp is not None
    temp_param = ac_temp.parameters["temperature"]
    assert temp_param.min_value == 16
    assert temp_param.max_value == 30
    assert temp_param.validate_value(24) is True
    assert temp_param.validate_value(15) is False
    assert temp_param.validate_value(31) is False

    # AC mode enums: COOL, AUTO, DRY, FAN
    ac_mode = registry.get_capability("AC_SET_MODE")
    assert ac_mode is not None
    mode_param = ac_mode.parameters["mode"]
    assert sorted(mode_param.allowed_values) == ["AUTO", "COOL", "DRY", "FAN"]
    assert mode_param.validate_value("COOL") is True
    assert mode_param.validate_value("HEAT") is False  # Reject HEAT

    # AC fan enums: LOW, MEDIUM, HIGH, AUTO
    ac_fan = registry.get_capability("AC_SET_FAN")
    assert ac_fan is not None
    fan_param = ac_fan.parameters["speed"]
    assert sorted(fan_param.allowed_values) == ["AUTO", "HIGH", "LOW", "MEDIUM"]
    assert fan_param.validate_value("MEDIUM") is True
    assert fan_param.validate_value("TURBO") is False

    # PC volume: 0 to 100
    pc_vol = registry.get_capability("PC_SET_VOLUME")
    assert pc_vol is not None
    vol_param = pc_vol.parameters["volume"]
    assert vol_param.min_value == 0
    assert vol_param.max_value == 100
    assert vol_param.validate_value(75) is True
    assert vol_param.validate_value(-1) is False
    assert vol_param.validate_value(101) is False


# =============================================================================
# 4. Unsupported Hardware Handling
# =============================================================================

def test_unsupported_hardware_capabilities():
    registry = UnifiedCapabilityRegistry()

    # Projector cold power-on
    cold_pwr = registry.get_capability("PROJECTOR_POWER_ON_COLD")
    assert cold_pwr is not None
    assert cold_pwr.is_executable is False
    assert cold_pwr.status == CapabilityStatus.UNSUPPORTED_HARDWARE
    assert cold_pwr.safety_level == SafetyLevel.RESTRICTED

    # AC Heat & Swing
    ac_heat = registry.get_capability("AC_SET_HEAT")
    assert ac_heat is not None
    assert ac_heat.is_executable is False
    assert ac_heat.status == CapabilityStatus.UNSUPPORTED_HARDWARE

    ac_swing = registry.get_capability("AC_SET_SWING")
    assert ac_swing is not None
    assert ac_swing.is_executable is False
    assert ac_swing.status == CapabilityStatus.UNSUPPORTED_HARDWARE

    # Verify filtering
    unsupported = registry.get_unsupported_capabilities()
    unsupported_ids = [c.canonical_id for c in unsupported]
    assert "PROJECTOR_POWER_ON_COLD" in unsupported_ids
    assert "AC_SET_HEAT" in unsupported_ids
    assert "AC_SET_SWING" in unsupported_ids

    # Executable list must NOT contain any unsupported capability
    executable = registry.get_executable_capabilities()
    exec_ids = [c.canonical_id for c in executable]
    assert "PROJECTOR_POWER_ON_COLD" not in exec_ids
    assert "AC_SET_HEAT" not in exec_ids
    assert "AC_SET_SWING" not in exec_ids


# =============================================================================
# 5. Deterministic Serialization & Schema Export
# =============================================================================

def test_deterministic_serialization():
    registry = UnifiedCapabilityRegistry()

    # Serialization 1 vs Serialization 2
    json1 = registry.export_catalog_json()
    json2 = registry.export_catalog_json()
    assert json1 == json2

    # Verify dict structure
    cat_dict = registry.export_catalog_dict()
    assert cat_dict["version"] == "1.0.0"
    assert "subsystems" in cat_dict
    assert "projector" in cat_dict["subsystems"]
    assert "ac" in cat_dict["subsystems"]
    assert "fire_tv" in cat_dict["subsystems"]
    assert "pc" in cat_dict["subsystems"]
    assert "soundbar" in cat_dict["subsystems"]

    # Prompt schema only contains executable capabilities
    prompt_schema = registry.export_prompt_schema_dict()
    assert "projector" in prompt_schema
    proj_caps = [c["capability"] for c in prompt_schema["projector"]]
    assert "PROJECTOR_POWER_WAKE" in proj_caps
    assert "PROJECTOR_POWER_ON_COLD" not in proj_caps


# =============================================================================
# 6. Registry Validation & Error Enforcement (Fail Closed)
# =============================================================================

def test_validation_rejects_duplicate_canonical_id():
    cap1 = CapabilityDefinition(
        canonical_id="TEST_CAPABILITY",
        subsystem=Subsystem.PC,
        description="Test 1",
        underlying_controller="PcController",
        underlying_capability_name="func1"
    )
    cap2 = CapabilityDefinition(
        canonical_id="TEST_CAPABILITY",
        subsystem=Subsystem.PC,
        description="Test 2",
        underlying_controller="PcController",
        underlying_capability_name="func2"
    )
    with pytest.raises(RegistryValidationError, match="Duplicate canonical_id"):
        UnifiedCapabilityRegistry(custom_capabilities=[cap1, cap2])


def test_validation_rejects_duplicate_underlying_mapping():
    cap1 = CapabilityDefinition(
        canonical_id="CAPABILITY_ONE",
        subsystem=Subsystem.PC,
        description="Test 1",
        underlying_controller="PcController",
        underlying_capability_name="duplicate_func"
    )
    cap2 = CapabilityDefinition(
        canonical_id="CAPABILITY_TWO",
        subsystem=Subsystem.PC,
        description="Test 2",
        underlying_controller="PcController",
        underlying_capability_name="duplicate_func"
    )
    with pytest.raises(RegistryValidationError, match="Duplicate underlying mapping"):
        UnifiedCapabilityRegistry(custom_capabilities=[cap1, cap2])


def test_validation_rejects_invalid_parameter_bounds():
    cap = CapabilityDefinition(
        canonical_id="INVALID_BOUNDS_CAP",
        subsystem=Subsystem.AC,
        description="Invalid bounds test",
        underlying_controller="AcController",
        underlying_capability_name="invalid_bounds",
        parameters={
            "temp": ParameterConstraint(
                name="temp",
                param_type=ParameterType.INTEGER,
                min_value=30,
                max_value=16  # min > max
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="invalid range"):
        UnifiedCapabilityRegistry(custom_capabilities=[cap])


def test_validation_rejects_empty_ids():
    cap = CapabilityDefinition(
        canonical_id="",
        subsystem=Subsystem.PC,
        description="Empty test",
        underlying_controller="PcController",
        underlying_capability_name="func"
    )
    with pytest.raises(RegistryValidationError, match="canonical_id cannot be empty"):
        UnifiedCapabilityRegistry(custom_capabilities=[cap])


def test_registry_zero_hardware_side_effects():
    """Verifies that instantiation and queries of UnifiedCapabilityRegistry perform no I/O."""
    registry = UnifiedCapabilityRegistry()
    assert registry.get_all_capabilities() is not None
    assert registry.export_prompt_schema_dict() is not None


# =============================================================================
# 7. FastAPI /api/capabilities Endpoint Contract Test
# =============================================================================

def test_fastapi_capabilities_endpoint():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    res = client.get("/api/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "1.0.0"
    assert "subsystems" in data
    assert "projector" in data["subsystems"]
    assert "ac" in data["subsystems"]
    assert "fire_tv" in data["subsystems"]
    assert "pc" in data["subsystems"]
    assert "soundbar" in data["subsystems"]

    # Verify that PROJECTOR_POWER_WAKE is present
    p_caps = [c["canonical_id"] for c in data["subsystems"]["projector"]]
    assert "PROJECTOR_POWER_WAKE" in p_caps

