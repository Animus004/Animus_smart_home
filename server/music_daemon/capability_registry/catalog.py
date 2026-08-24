"""
Authoritative Static Capability Catalog for Animus Smart Room.
Defines the complete verified baseline of all smart room physical capabilities
with rigorous parameter limits, safety levels, and hardware constraints.
"""

from typing import List
from capability_registry.models import (
    Subsystem,
    SafetyLevel,
    CapabilityStatus,
    ParameterType,
    ParameterConstraint,
    CapabilityDefinition
)

AUTHORITATIVE_CAPABILITIES: List[CapabilityDefinition] = [
    # =========================================================================
    # 1. PROJECTOR SUBSYSTEM (Zebronics PixaPlay 25)
    # =========================================================================
    CapabilityDefinition(
        canonical_id="PROJECTOR_POWER_WAKE",
        subsystem=Subsystem.PROJECTOR,
        description="Wakes projector from standby mode over ADB Wi-Fi.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_wake",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.health == 'OK'"],
        expected_state_transition={"projector.power": True}
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_POWER_SLEEP",
        subsystem=Subsystem.PROJECTOR,
        description="Puts projector into standby mode over ADB Wi-Fi.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_sleep",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"],
        expected_state_transition={"projector.power": False}
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_SWITCH_HDMI1",
        subsystem=Subsystem.PROJECTOR,
        description="Switches physical projector display input source to HDMI 1.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_switch_hdmi1",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"],
        expected_state_transition={"projector.input_source": "HDMI_1"}
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_SWITCH_ANDROID_HOME",
        subsystem=Subsystem.PROJECTOR,
        description="Switches physical projector input source to internal Android TV home launcher.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_switch_android_home",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"],
        expected_state_transition={"projector.input_source": "ANDROID_HOME"}
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_SET_BRIGHTNESS",
        subsystem=Subsystem.PROJECTOR,
        description="Adjusts physical projector display brightness scalar between 1 and 100.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_set_brightness",
        parameters={
            "brightness": ParameterConstraint(
                name="brightness",
                param_type=ParameterType.INTEGER,
                required=True,
                min_value=1,
                max_value=100,
                description="Target brightness level (1 to 100)"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_SET_PICTURE_MODE",
        subsystem=Subsystem.PROJECTOR,
        description="Sets physical projector picture mode preset.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_set_picture_mode",
        parameters={
            "mode": ParameterConstraint(
                name="mode",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["STANDARD", "VIVID", "MOVIE", "USER"],
                description="Target picture mode preset"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_SET_ASPECT_RATIO",
        subsystem=Subsystem.PROJECTOR,
        description="Sets physical projector display aspect ratio.",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_set_aspect_ratio",
        parameters={
            "ratio": ParameterConstraint(
                name="ratio",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["16:9", "4:3", "AUTO"],
                description="Target aspect ratio"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["projector.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="PROJECTOR_POWER_ON_COLD",
        subsystem=Subsystem.PROJECTOR,
        description="Cold power-on when projector is completely unpowered (unavailable via ADB; pending IR blaster hardware).",
        underlying_controller="ProjectorController",
        underlying_capability_name="projector_power_on_cold",
        idempotent=True,
        requires_device_online=False,
        readback_verification_expected=False,
        safety_level=SafetyLevel.RESTRICTED,
        status=CapabilityStatus.UNSUPPORTED_HARDWARE
    ),

    # =========================================================================
    # 2. AIR CONDITIONER SUBSYSTEM (Tuya Split Inverter AC)
    # =========================================================================
    CapabilityDefinition(
        canonical_id="AC_POWER_ON",
        subsystem=Subsystem.AC,
        description="Powers ON the air conditioner compressor and fan.",
        underlying_controller="AcController",
        underlying_capability_name="ac_power_on",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"ac.power": True}
    ),
    CapabilityDefinition(
        canonical_id="AC_POWER_OFF",
        subsystem=Subsystem.AC,
        description="Powers OFF the air conditioner unit.",
        underlying_controller="AcController",
        underlying_capability_name="ac_power_off",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"ac.power": False}
    ),
    CapabilityDefinition(
        canonical_id="AC_SET_TEMPERATURE",
        subsystem=Subsystem.AC,
        description="Sets target thermostat cooling temperature between 16 and 30 degrees Celsius.",
        underlying_controller="AcController",
        underlying_capability_name="ac_set_temperature",
        parameters={
            "temperature": ParameterConstraint(
                name="temperature",
                param_type=ParameterType.INTEGER,
                required=True,
                min_value=16,
                max_value=30,
                description="Target temperature in Celsius (16 to 30)"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["ac.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="AC_SET_MODE",
        subsystem=Subsystem.AC,
        description="Sets AC operating mode (COOL, AUTO, DRY, FAN). HEAT is unsupported on cooling-only hardware.",
        underlying_controller="AcController",
        underlying_capability_name="ac_set_mode",
        parameters={
            "mode": ParameterConstraint(
                name="mode",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["COOL", "AUTO", "DRY", "FAN"],
                description="Operating mode"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["ac.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="AC_SET_FAN",
        subsystem=Subsystem.AC,
        description="Sets AC blower fan speed (LOW, MEDIUM, HIGH, AUTO).",
        underlying_controller="AcController",
        underlying_capability_name="ac_set_fan",
        parameters={
            "speed": ParameterConstraint(
                name="speed",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["LOW", "MEDIUM", "HIGH", "AUTO"],
                description="Blower fan speed"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        preconditions=["ac.power == True"]
    ),
    CapabilityDefinition(
        canonical_id="AC_SET_HEAT",
        subsystem=Subsystem.AC,
        description="Heat mode (unsupported on cooling-only physical hardware).",
        underlying_controller="AcController",
        underlying_capability_name="ac_set_heat",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.RESTRICTED,
        status=CapabilityStatus.UNSUPPORTED_HARDWARE
    ),
    CapabilityDefinition(
        canonical_id="AC_SET_SWING",
        subsystem=Subsystem.AC,
        description="Louvre swing oscillation (unsupported over Wi-Fi on physical hardware).",
        underlying_controller="AcController",
        underlying_capability_name="ac_set_swing",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.RESTRICTED,
        status=CapabilityStatus.UNSUPPORTED_HARDWARE
    ),

    # =========================================================================
    # 3. FIRE TV SUBSYSTEM (Amazon Fire TV Stick Lite / 3rd Gen)
    # =========================================================================
    CapabilityDefinition(
        canonical_id="FIRE_TV_CONNECTIVITY_CHECK",
        subsystem=Subsystem.FIRE_TV,
        description="Checks TCP socket connectivity to Fire TV over ADB port 5555.",
        underlying_controller="FireTvController",
        underlying_capability_name="connectivity_check",
        idempotent=True,
        requires_device_online=False,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_POWER_WAKE",
        subsystem=Subsystem.FIRE_TV,
        description="Wakes Fire TV from sleep/screensaver over ADB.",
        underlying_controller="FireTvController",
        underlying_capability_name="power_wake",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.power_state": "AWAKE"}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_POWER_SLEEP",
        subsystem=Subsystem.FIRE_TV,
        description="Puts Fire TV to sleep over ADB.",
        underlying_controller="FireTvController",
        underlying_capability_name="power_sleep",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.power_state": "ASLEEP"}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_POWER_GET_STATE",
        subsystem=Subsystem.FIRE_TV,
        description="Reads physical wakefulness state of Fire TV via dumpsys power.",
        underlying_controller="FireTvController",
        underlying_capability_name="power_get_state",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_NAV_HOME",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_HOME to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="navigation_home",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_NAV_BACK",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_BACK to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="navigation_back",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_NAV_SELECT",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_DPAD_CENTER to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="navigation_select",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_NAV_DPAD",
        subsystem=Subsystem.FIRE_TV,
        description="Sends directional DPAD navigation keys to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="navigation_dpad",
        parameters={
            "direction": ParameterConstraint(
                name="direction",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["UP", "DOWN", "LEFT", "RIGHT"],
                description="DPAD navigation direction"
            )
        },
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_APP_LAUNCH_YOUTUBE",
        subsystem=Subsystem.FIRE_TV,
        description="Launches YouTube TV application directly on Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="app_launch_youtube",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.foreground_app": "com.google.android.youtube.tv"}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_APP_GET_FOREGROUND",
        subsystem=Subsystem.FIRE_TV,
        description="Reads focused foreground package name from dumpsys window.",
        underlying_controller="FireTvController",
        underlying_capability_name="app_get_foreground",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_DIRECT_YOUTUBE",
        subsystem=Subsystem.FIRE_TV,
        description="Launches YouTube video directly via Android Intent.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_direct_youtube",
        parameters={
            "video_id": ParameterConstraint(
                name="video_id",
                param_type=ParameterType.STRING,
                required=True,
                description="YouTube 11-character video ID"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_DIRECT_PROVIDER",
        subsystem=Subsystem.FIRE_TV,
        description="Launches media directly on target streaming provider (Netflix, Prime, Hotstar, JioCinema, SonyLIV, Zee5).",
        underlying_controller="FireTvController",
        underlying_capability_name="media_direct_provider",
        parameters={
            "provider": ParameterConstraint(
                name="provider",
                param_type=ParameterType.STRING,
                required=True,
                allowed_values=["youtube", "netflix", "prime", "hotstar", "jiocinema", "sonyliv", "zee5"],
                description="Streaming provider identifier"
            ),
            "content": ParameterConstraint(
                name="content",
                param_type=ParameterType.STRING,
                required=False,
                description="Content title, query, or URI"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_SEARCH_YOUTUBE",
        subsystem=Subsystem.FIRE_TV,
        description="Searches YouTube on Fire TV via deep link intent.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_search_youtube",
        parameters={
            "query": ParameterConstraint(
                name="query",
                param_type=ParameterType.STRING,
                required=True,
                description="Search query string"
            )
        },
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_VERIFY_YOUTUBE",
        subsystem=Subsystem.FIRE_TV,
        description="Verifies that YouTube is running in the foreground.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_verify_youtube",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_PLAY",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_PLAY to Fire TV active media session.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_play",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_PAUSE",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_PAUSE to Fire TV active media session.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_pause",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_TOGGLE",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_PLAY_PAUSE to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_toggle",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_STOP",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_STOP to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_stop",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_NEXT",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_NEXT to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_next",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MEDIA_PREVIOUS",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_MEDIA_PREVIOUS to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="media_previous",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_VOLUME_UP",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_VOLUME_UP to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="volume_up",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_VOLUME_DOWN",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_VOLUME_DOWN to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="volume_down",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_MUTE",
        subsystem=Subsystem.FIRE_TV,
        description="Sends KEYCODE_VOLUME_MUTE to Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="mute",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_GET_STATUS",
        subsystem=Subsystem.FIRE_TV,
        description="Reads Bluetooth adapter and bonded device connection status on Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_get_status",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_CONNECT_SOUNDBAR",
        subsystem=Subsystem.FIRE_TV,
        description="Connects LG SNC4R Soundbar to Fire TV with direct-to-fallback escalation.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_connect_soundbar",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.soundbar_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_CONNECT_SOUNDBAR_DIRECT",
        subsystem=Subsystem.FIRE_TV,
        description="Connects LG SNC4R Soundbar directly via input tap on paired settings UI coordinate.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_connect_soundbar_direct",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.soundbar_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_CONNECT_SOUNDBAR_FALLBACK",
        subsystem=Subsystem.FIRE_TV,
        description="Connects LG SNC4R Soundbar using fallback intent navigation when direct tap fails.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_connect_soundbar_fallback",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.soundbar_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_DISCONNECT_SOUNDBAR_DIRECT",
        subsystem=Subsystem.FIRE_TV,
        description="Disconnects LG SNC4R Soundbar from Fire TV.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_disconnect_soundbar_direct",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"fire_tv.soundbar_connected": False}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_BT_IS_SOUNDBAR_CONNECTED",
        subsystem=Subsystem.FIRE_TV,
        description="Checks if LG SNC4R Soundbar is actively connected to Fire TV over Bluetooth.",
        underlying_controller="FireTvController",
        underlying_capability_name="bt_is_soundbar_connected",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_AUDIO_SWITCH_TO_FIRE_TV",
        subsystem=Subsystem.FIRE_TV,
        description="Transfers Soundbar audio sink ownership from PC to Fire TV.",
        underlying_controller="FireTvService",
        underlying_capability_name="audio_switch_to_fire_tv",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"soundbar.current_owner": "FIRE_TV", "soundbar.is_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_AUDIO_SWITCH_TO_PC",
        subsystem=Subsystem.FIRE_TV,
        description="Restores Soundbar audio sink ownership from Fire TV back to PC.",
        underlying_controller="FireTvService",
        underlying_capability_name="audio_switch_to_pc",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"soundbar.current_owner": "PC", "soundbar.is_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_PROJECTOR_SWITCH_HDMI1",
        subsystem=Subsystem.FIRE_TV,
        description="Switches physical Projector to HDMI 1 (Fire TV input) via integrated service.",
        underlying_controller="FireTvService",
        underlying_capability_name="projector_switch_hdmi1",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"projector.input_source": "HDMI_1"}
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_PROJECTOR_VERIFY_HDMI1",
        subsystem=Subsystem.FIRE_TV,
        description="Verifies that Projector is currently displaying HDMI 1.",
        underlying_controller="FireTvService",
        underlying_capability_name="projector_verify_hdmi1",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.SAFE,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_AUTOMATION_MOVIE_MODE_START",
        subsystem=Subsystem.FIRE_TV,
        description="Orchestrates complete cinema workflow: wakes Fire TV, connects Soundbar, switches Projector to HDMI 1, launches content.",
        underlying_controller="FireTvService",
        underlying_capability_name="automation_movie_mode_start",
        parameters={
            "content": ParameterConstraint(name="content", param_type=ParameterType.STRING, required=False, description="Movie/show title or video ID"),
            "provider": ParameterConstraint(name="provider", param_type=ParameterType.STRING, required=False, description="Target streaming provider")
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.MEDIUM_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="FIRE_TV_AUTOMATION_MOVIE_MODE_STOP",
        subsystem=Subsystem.FIRE_TV,
        description="Stops cinema workflow: pauses media, transfers Soundbar to PC, optional projector shutdown.",
        underlying_controller="FireTvService",
        underlying_capability_name="automation_movie_mode_stop",
        parameters={
            "turn_off_projector": ParameterConstraint(name="turn_off_projector", param_type=ParameterType.BOOLEAN, required=False, default=False, description="Whether to put projector into standby")
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.MEDIUM_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),

    # =========================================================================
    # 4. PC HOST SUBSYSTEM (Windows Host / CoreAudio / BluetoothApis)
    # =========================================================================
    CapabilityDefinition(
        canonical_id="PC_SET_VOLUME",
        subsystem=Subsystem.PC,
        description="Sets master audio volume on Windows host between 0 and 100 via in-process CoreAudio COM.",
        underlying_controller="PcController",
        underlying_capability_name="pc_set_volume",
        parameters={
            "volume": ParameterConstraint(
                name="volume",
                param_type=ParameterType.INTEGER,
                required=True,
                min_value=0,
                max_value=100,
                description="Master volume level (0 to 100)"
            )
        },
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_MUTE",
        subsystem=Subsystem.PC,
        description="Mutes Windows master audio endpoint via CoreAudio COM.",
        underlying_controller="PcController",
        underlying_capability_name="pc_mute",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"pc.is_muted": True}
    ),
    CapabilityDefinition(
        canonical_id="PC_UNMUTE",
        subsystem=Subsystem.PC,
        description="Unmutes Windows master audio endpoint via CoreAudio COM.",
        underlying_controller="PcController",
        underlying_capability_name="pc_unmute",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"pc.is_muted": False}
    ),
    CapabilityDefinition(
        canonical_id="PC_MEDIA_PLAY_PAUSE",
        subsystem=Subsystem.PC,
        description="Sends VK_MEDIA_PLAY_PAUSE virtual keybd_event to active Windows media application.",
        underlying_controller="PcController",
        underlying_capability_name="pc_media_play_pause",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_MEDIA_NEXT",
        subsystem=Subsystem.PC,
        description="Sends VK_MEDIA_NEXT_TRACK virtual keybd_event to active Windows media application.",
        underlying_controller="PcController",
        underlying_capability_name="pc_media_next",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_MEDIA_PREVIOUS",
        subsystem=Subsystem.PC,
        description="Sends VK_MEDIA_PREV_TRACK virtual keybd_event to active Windows media application.",
        underlying_controller="PcController",
        underlying_capability_name="pc_media_previous",
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_MEDIA_STOP",
        subsystem=Subsystem.PC,
        description="Sends VK_MEDIA_STOP virtual keybd_event to active Windows media application.",
        underlying_controller="PcController",
        underlying_capability_name="pc_media_stop",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_LOCK_WORKSTATION",
        subsystem=Subsystem.PC,
        description="Locks the Windows workstation via user32.LockWorkStation.",
        underlying_controller="PcController",
        underlying_capability_name="pc_lock_workstation",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_SLEEP",
        subsystem=Subsystem.PC,
        description="Puts the Windows host PC into standby sleep via SetSuspendState.",
        underlying_controller="PcController",
        underlying_capability_name="pc_sleep",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.MEDIUM_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),
    CapabilityDefinition(
        canonical_id="PC_LAUNCH_APP",
        subsystem=Subsystem.PC,
        description="Launches an allowlisted local Windows application.",
        underlying_controller="PcController",
        underlying_capability_name="pc_launch_app",
        parameters={
            "app_key": ParameterConstraint(
                name="app_key",
                param_type=ParameterType.ENUM,
                required=True,
                allowed_values=["spotify", "chrome", "notepad", "calculator", "vlc", "taskmgr", "explorer"],
                description="Allowlisted application key"
            )
        },
        idempotent=False,
        requires_device_online=True,
        readback_verification_expected=False,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE
    ),

    # =========================================================================
    # 5. SOUNDBAR / AUDIO ROUTING SUBSYSTEM (LG SNC4R Dual Ownership)
    # =========================================================================
    CapabilityDefinition(
        canonical_id="SOUNDBAR_ROUTE_TO_FIRE_TV",
        subsystem=Subsystem.SOUNDBAR,
        description="Transfers LG SNC4R Soundbar Bluetooth audio connection from PC to Fire TV.",
        underlying_controller="SmartRoomOrchestrator",
        underlying_capability_name="soundbar_route_to_fire_tv",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"soundbar.current_owner": "FIRE_TV", "soundbar.is_connected": True}
    ),
    CapabilityDefinition(
        canonical_id="SOUNDBAR_ROUTE_TO_PC",
        subsystem=Subsystem.SOUNDBAR,
        description="Restores LG SNC4R Soundbar Bluetooth audio connection from Fire TV back to PC.",
        underlying_controller="SmartRoomOrchestrator",
        underlying_capability_name="soundbar_route_to_pc",
        idempotent=True,
        requires_device_online=True,
        readback_verification_expected=True,
        safety_level=SafetyLevel.LOW_RISK,
        status=CapabilityStatus.VERIFIED_EXECUTABLE,
        expected_state_transition={"soundbar.current_owner": "PC", "soundbar.is_connected": True}
    )
]
