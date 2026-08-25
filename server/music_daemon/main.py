"""
Animus PC Local Music Resolution and Playback Daemon.
Exposes REST endpoints on port 8095 for track resolution, playback control,
authenticated status, Device Portal Bluetooth auto-reconnection, and Smart Room Orchestration.
"""

from contextlib import asynccontextmanager
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

from resolver import YouTubeMusicResolver
from player import MpvPlayer
from orchestrator import SmartRoomOrchestrator, RoomAudioState
from projector_controller import ProjectorController
from fire_tv_controller import FireTvController
from fire_tv_capabilities import FireTVCapabilityRegistry, FireTVState
from firetv_service import FireTvService
from automation_registry import AutomationRegistry
from ollama_manager import OllamaManager
from ac_controller import AcController
from ac_command_router import AcCommandRouter
from pc_controller import PcController
from pc_command_router import PcCommandRouter
from room_state.aggregator import RoomStateAggregator
from capability_registry import UnifiedCapabilityRegistry
from context import PreferenceManager, ContextEngine
from planner import (
    PlanValidator,
    GeminiPlannerClient,
    GeminiApiUnavailableError,
    GeminiResponseError,
    PlanExecutor
)
from agent import AnimusPersonalAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("music_daemon.main")

# Initialize Resolver, Player, Projector, Fire TV, Orchestrator, OllamaManager, AC, PC, RoomState, and Capability Registry
SECRETS_DIR = Path(__file__).parent / "secrets"
resolver = YouTubeMusicResolver(secrets_dir=SECRETS_DIR)
player = MpvPlayer(preferred_device_keyword="LG SNC4R")
projector = ProjectorController()
fire_tv = FireTvController()
ac_controller = AcController()
ac_router = AcCommandRouter(controller=ac_controller)
pc_controller = PcController()
pc_router = PcCommandRouter(controller=pc_controller)
ollama_mgr = OllamaManager()

orchestrator = SmartRoomOrchestrator(
    resolver=resolver,
    player=player,
    projector=projector,
    fire_tv=fire_tv
)
room_state_aggregator = RoomStateAggregator(
    projector_controller=projector,
    ac_controller=ac_controller,
    fire_tv_controller=fire_tv,
    pc_controller=pc_controller,
    orchestrator=orchestrator
)
unified_capability_registry = UnifiedCapabilityRegistry()
preference_manager = PreferenceManager(registry=unified_capability_registry)
context_engine = ContextEngine(
    preference_manager=preference_manager,
    room_state_aggregator=room_state_aggregator
)
planner_validator = PlanValidator(registry=unified_capability_registry)
planner_client = GeminiPlannerClient(registry=unified_capability_registry, validator=planner_validator)

automation_registry = AutomationRegistry()
firetv_service = FireTvService(
    capabilities=orchestrator.capabilities,
    fire_tv=fire_tv,
    projector=projector,
    bt_helper=player.bt_helper,
    player=player,
    provider_registry=orchestrator.provider_registry,
    content_resolver=orchestrator.content_resolver,
    automation_registry=automation_registry
)
planner_executor = PlanExecutor(
    registry=unified_capability_registry,
    validator=planner_validator,
    room_state_aggregator=room_state_aggregator,
    projector_controller=projector,
    ac_controller=ac_controller,
    pc_controller=pc_controller,
    fire_tv_controller=fire_tv,
    firetv_service=firetv_service,
    orchestrator=orchestrator
)
animus_personal_agent = AnimusPersonalAgent(
    registry=unified_capability_registry,
    room_state_aggregator=room_state_aggregator,
    context_engine=context_engine,
    preference_manager=preference_manager,
    planner_client=planner_client,
    planner_executor=planner_executor
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[PC_MUSIC_DAEMON_START] Animus PC Smart Room Daemon v1.6.0 starting on port 8095...")
    logger.info(f"[PC_MUSIC_DAEMON_AUTH] YouTube Music Authentication: is_authenticated={resolver.is_authenticated}, method={resolver.auth_method}")
    # Inspect initial room audio state
    init_status = orchestrator.get_room_status()
    logger.info(f"[PC_MUSIC_DAEMON_AUDIO] Initial Room Audio State: {init_status['room_audio_state']} (Soundbar: {init_status.get('soundbar_name')})")

    # Pre-warm local Qwen LLM in dedicated GPU VRAM (keep_alive: 24h)
    threading.Thread(target=ollama_mgr.ensure_model_ready, name="OllamaPrewarm", daemon=True).start()

    yield

    logger.info("[PC_MUSIC_DAEMON_STOP] Shutting down orchestrator and releasing resources...")
    player.shutdown()
    ollama_mgr.shutdown()


app = FastAPI(
    title="Animus PC Smart Room Daemon",
    version="1.6.0",
    description="PC-local music resolution, audio playback engine, Smart Room Orchestrator, and Projector Controller for Animus Smart Room",
    lifespan=lifespan
)


class ProjectorKeyRequest(BaseModel):
    key: str = Field(..., description="Key name: home, back, menu, up, down, left, right, center, or integer keycode")

class ProjectorVolumeRequest(BaseModel):
    action: str = Field(..., description="Volume action: up, down, mute")

class ProjectorSourceRequest(BaseModel):
    source: str = Field(..., description="Source: ANDROID, HDMI_1, USB")

class ProjectorPowerRequest(BaseModel):
    action: str = Field(..., description="Power action: WAKE, SLEEP, OFF, ON, STATUS")

class ProjectorBrightnessRequest(BaseModel):
    brightness: int = Field(..., ge=0, le=100, description="Normalized brightness percentage from 0 to 100")

class AcPowerRequest(BaseModel):
    on: bool = Field(..., description="Power state: true for ON, false for OFF")

class AcTemperatureRequest(BaseModel):
    temperature: int = Field(..., ge=16, le=30, description="Target temperature in Celsius (16-30)")

class AcModeRequest(BaseModel):
    mode: str = Field(..., description="HVAC Mode: COOL, AUTO, DRY, FAN")

class AcFanRequest(BaseModel):
    speed: str = Field(..., description="Fan Speed: LOW, MEDIUM, HIGH, AUTO")

class AcNaturalCommandRequest(BaseModel):
    query: str = Field(..., description="Natural language AC command string")

class PcVolumeRequest(BaseModel):
    volume: int = Field(..., ge=0, le=100, description="Target master volume percentage (0-100)")

class PcMuteRequest(BaseModel):
    mute: bool = Field(..., description="Target mute state: true for MUTE, false for UNMUTE")

class PcMediaRequest(BaseModel):
    action: str = Field(..., description="Media action: PLAY_PAUSE, NEXT, PREVIOUS, STOP, PLAY, PAUSE")

class PcPowerRequest(BaseModel):
    action: str = Field(..., description="Power action: LOCK, SLEEP, STATUS")

class PcNaturalCommandRequest(BaseModel):
    query: str = Field(..., description="Natural language PC command string")

class PlayRequest(BaseModel):


    title: str = Field(..., min_length=1, max_length=200, description="Title of the track or song query")
    artist: Optional[str] = Field(default=None, max_length=200, description="Optional artist name")
    direct_video_id: Optional[str] = Field(default=None, max_length=50, description="Optional explicit YouTube/YTM video ID")


class QueueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title of the track to queue")
    artist: Optional[str] = Field(default=None, max_length=200, description="Optional artist name")
    direct_video_id: Optional[str] = Field(default=None, max_length=50, description="Optional explicit YouTube/YTM video ID")
    play_next: bool = Field(default=False, description="Whether to insert track at the top of the queue")


class QueueResponse(BaseModel):
    success: bool
    title: str
    artist: Optional[str] = None
    queue_length: int
    play_next: bool = False


class MovieModeRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=200, description="Optional movie/show title to search or launch on Fire TV")
    provider: Optional[str] = Field(default=None, max_length=50, description="Optional target provider: youtube, hotstar, netflix, zee5, apple_tv, etc.")


class FireTVPlaybackRequest(BaseModel):
    action: str = Field(..., description="Playback action: PLAY, PAUSE, TOGGLE, STOP, NEXT, PREVIOUS, VOLUME_UP, VOLUME_DOWN, MUTE")


class AudioSwitchRequest(BaseModel):
    target: str = Field(..., description="Target audio owner: PC, COMPUTER, FIRE_TV, TV")


class VolumeRequest(BaseModel):
    volume: int = Field(..., ge=0, le=100, description="Target volume level from 0 to 100")


class AutomationTriggerRequest(BaseModel):
    automation: str = Field(..., description="Name of the room automation to execute")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dynamic parameters for the automation")


class WatchServiceRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Movie/show title or query")
    provider: Optional[str] = Field(default=None, description="Optional provider: youtube, netflix, prime_video, apple_tv, hotstar, zee5")
    direct_play_first: bool = Field(default=True, description="Prefer direct deep link/autoplay before falling back to UI")


class CinemaStartServiceRequest(BaseModel):
    content: Optional[str] = Field(default=None, description="Optional content title/ID")
    provider: Optional[str] = Field(default=None, description="Optional streaming provider")


class CinemaStopServiceRequest(BaseModel):
    turn_off_projector: bool = Field(default=False, description="Whether to shut down projector")


class ProviderSwitchServiceRequest(BaseModel):
    target_provider: str = Field(..., description="Target streaming provider")
    content: Optional[str] = Field(default=None, description="Optional content query")


class AudioRouteServiceRequest(BaseModel):
    target: str = Field(..., description="Target audio host: FIRE_TV or PC")


class ServiceRecoveryRequest(BaseModel):
    subsystem: Optional[str] = Field(default="all", description="Subsystem to recover: all, adb, bluetooth, soundbar, hdmi, playback, app")


class ServiceAutomationExecuteRequest(BaseModel):
    automation_id: str = Field(..., description="ID of the automation from the registry")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters dictionary")


class PlayResponse(BaseModel):
    success: bool
    status: str
    title: Optional[str] = None
    artist: Optional[str] = None
    duration: Optional[int] = None
    video_id: Optional[str] = None
    audio_output_status: Optional[str] = None
    audio_device_id: Optional[str] = None
    audio_device_name: Optional[str] = None
    room_audio_state: Optional[str] = None
    reconnect_method: Optional[str] = None
    reconnect_duration_ms: Optional[int] = None
    is_authenticated: bool = False
    error: Optional[str] = None


class ControlResponse(BaseModel):
    success: bool
    status: str
    volume: Optional[int] = None
    room_audio_state: Optional[str] = None
    error: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    title: Optional[str] = None
    artist: Optional[str] = None
    duration: Optional[int] = None
    position: Optional[int] = None
    thumbnail_url: Optional[str] = None
    volume: int = 100
    audio_output_status: str = "DISCONNECTED"
    audio_device_id: Optional[str] = None
    audio_device_name: Optional[str] = None
    room_audio_state: str = "DISCONNECTED"
    reconnect_method: Optional[str] = None
    is_authenticated: bool = False
    auth_method: str = "none"


class RoomSoundbarResponse(BaseModel):
    success: bool
    room_audio_state: str
    message: str
    soundbar_name: Optional[str] = None
    soundbar_endpoint_id: Optional[str] = None
    duration_ms: Optional[int] = None


# Endpoints
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    room_st = orchestrator.get_room_status()
    auth_info = room_st["authentication"]
    return {
        "status": "UP",
        "service": "animus-music-daemon",
        "version": "1.5.0",
        "is_authenticated": auth_info["is_authenticated"],
        "auth_method": auth_info["auth_method"],
        "audio_output_status": "CONNECTED" if room_st["is_audio_ready"] else "DISCONNECTED",
        "room_audio_state": room_st["room_audio_state"],
        "audio_device_name": room_st.get("soundbar_name"),
        "device_portal_available": room_st["device_portal_available"]
    }


# High-Level Smart Room Soundbar Orchestration Endpoints
@app.post("/api/room/soundbar/connect", response_model=RoomSoundbarResponse)
def connect_soundbar():
    logger.info("[API_ROOM_CONNECT] Connect soundbar requested via Smart Room API")
    ok, state, msg = orchestrator.connect_soundbar(timeout_seconds=12.0)
    st = orchestrator.get_room_status()
    return RoomSoundbarResponse(
        success=ok,
        room_audio_state=state.value,
        message=msg,
        soundbar_name=st.get("soundbar_name"),
        soundbar_endpoint_id=st.get("soundbar_endpoint_id"),
        duration_ms=st.get("last_action_duration_ms")
    )


@app.post("/api/room/soundbar/disconnect", response_model=RoomSoundbarResponse)
def disconnect_soundbar():
    logger.info("[API_ROOM_DISCONNECT] Disconnect soundbar requested via Smart Room API")
    ok, state, msg = orchestrator.disconnect_soundbar()
    st = orchestrator.get_room_status()
    return RoomSoundbarResponse(
        success=ok,
        room_audio_state=state.value,
        message=msg,
        soundbar_name=st.get("soundbar_name"),
        soundbar_endpoint_id=st.get("soundbar_endpoint_id"),
        duration_ms=st.get("last_action_duration_ms")
    )


@app.get("/api/room/soundbar/status")
def get_room_soundbar_status() -> Dict[str, Any]:
    return orchestrator.get_room_status()


# Media Endpoints (Orchestrator-Backed)
@app.post("/api/music/play", response_model=PlayResponse)
def play_music(req: PlayRequest):
    logger.info(f"[PC_MUSIC_REQUEST] Play request received: title='{req.title}', artist='{req.artist}', direct_id='{req.direct_video_id}'")

    if not req.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title cannot be blank."
        )

    success, play_data, error_reason = orchestrator.safe_play(
        title=req.title,
        artist=req.artist,
        direct_video_id=req.direct_video_id
    )

    st = player.get_status()

    if not success:
        error_msg = error_reason or "Playback orchestration failed"
        logger.error(f"[PC_MUSIC_ERROR] Safe play failed for '{req.title}': {error_msg}")
        return PlayResponse(
            success=False,
            status="FAILED",
            audio_output_status=play_data.get("audio_output_status", "DISCONNECTED"),
            room_audio_state=orchestrator.current_state.value,
            reconnect_method=player.bt_helper.last_reconnect_method,
            reconnect_duration_ms=player.bt_helper.last_reconnect_duration_ms,
            error=error_msg,
            is_authenticated=resolver.is_authenticated
        )

    return PlayResponse(
        success=True,
        status="PLAYING",
        title=play_data.get("title"),
        artist=play_data.get("artist"),
        duration=play_data.get("duration"),
        video_id=play_data.get("video_id"),
        audio_output_status=play_data.get("audio_output_status"),
        audio_device_id=play_data.get("audio_device_id"),
        audio_device_name=play_data.get("audio_device_name"),
        room_audio_state=orchestrator.current_state.value,
        reconnect_method=player.bt_helper.last_reconnect_method,
        reconnect_duration_ms=player.bt_helper.last_reconnect_duration_ms,
        is_authenticated=play_data.get("is_authenticated", False)
    )


@app.post("/api/music/pause", response_model=ControlResponse)
def pause_music():
    success = orchestrator.safe_pause()
    if success:
        return ControlResponse(success=True, status="PAUSED", room_audio_state=orchestrator.current_state.value)
    return ControlResponse(success=False, status="FAILED", error="Could not pause playback", room_audio_state=orchestrator.current_state.value)


@app.post("/api/music/resume", response_model=ControlResponse)
def resume_music():
    success = orchestrator.safe_resume()
    if success:
        return ControlResponse(success=True, status="PLAYING", room_audio_state=orchestrator.current_state.value)
    return ControlResponse(success=False, status="FAILED", error="Could not resume playback", room_audio_state=orchestrator.current_state.value)


@app.post("/api/music/volume", response_model=ControlResponse)
def set_volume(req: VolumeRequest):
    applied = orchestrator.safe_set_volume(req.volume)
    st = player.get_status()
    return ControlResponse(success=True, status=st["status"], volume=applied, room_audio_state=orchestrator.current_state.value)


@app.get("/api/music/status", response_model=StatusResponse)
def get_music_status():
    st = player.get_status()
    auth_info = resolver.get_auth_status()
    room_st = orchestrator.get_room_status()
    return StatusResponse(
        status=st["status"],
        title=st["title"],
        artist=st["artist"],
        duration=st["duration"],
        position=st["position"],
        thumbnail_url=st.get("thumbnail_url"),
        volume=st["volume"],
        audio_output_status=st.get("audio_output_status", "DISCONNECTED"),
        audio_device_id=st.get("audio_device_id"),
        audio_device_name=st.get("audio_device_name"),
        room_audio_state=room_st["room_audio_state"],
        reconnect_method=player.bt_helper.last_reconnect_method,
        is_authenticated=auth_info["is_authenticated"],
        auth_method=auth_info["auth_method"]
    )


@app.post("/api/music/stop", response_model=ControlResponse)
def stop_music():
    orchestrator.safe_stop()
    return ControlResponse(success=True, status="STOPPED", room_audio_state=orchestrator.current_state.value)


# Queue & Advanced Playback Navigation Endpoints
@app.post("/api/music/queue", response_model=QueueResponse)
def queue_track(req: QueueRequest):
    logger.info(f"[API_QUEUE_TRACK] Enqueue requested: title='{req.title}', artist='{req.artist}', play_next={req.play_next}")
    if not req.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title cannot be blank."
        )
    res = orchestrator.queue_track(
        title=req.title,
        artist=req.artist,
        direct_video_id=req.direct_video_id,
        play_next=req.play_next
    )
    return QueueResponse(
        success=res["success"],
        title=res["title"],
        artist=res.get("artist"),
        queue_length=res["queue_length"],
        play_next=res.get("play_next", False)
    )


@app.get("/api/music/queue")
def get_queue():
    return orchestrator.get_queue_status()


@app.post("/api/music/next")
def skip_next():
    logger.info("[API_SKIP_NEXT] Skip next track requested via API")
    ok, data, err = orchestrator.skip_next()
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Could not skip next")
    return {"success": True, "data": data}


@app.post("/api/music/previous")
def skip_previous():
    logger.info("[API_SKIP_PREVIOUS] Skip previous track requested via API")
    ok, data, err = orchestrator.skip_previous()
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "No previous track")
    return {"success": True, "data": data}


@app.post("/api/music/queue/clear")
def clear_queue():
    logger.info("[API_QUEUE_CLEAR] Clear queue requested via API")
    return orchestrator.clear_queue()


# ==========================================
# Projector Subsystem Endpoints (v1.6.0)
# ==========================================
@app.get("/api/projector/status")
@app.get("/api/room/projector/status")
def get_projector_status():
    """Returns structured status and system information for the Zebronics PixaPlay 25 projector."""
    info = projector.get_device_info()
    return info


@app.get("/api/projector/health")
@app.get("/api/room/projector/health")
def get_projector_health():
    """Returns real-time thermal and cooling fan RPM metrics for the projector."""
    return projector.get_hardware_health()


@app.get("/api/projector/signal")
@app.get("/api/room/projector/signal")
def get_projector_signal():
    """Returns authoritative HDMI video stream handshake state from dumpsys tv_input."""
    return projector.get_signal_state()


@app.get("/api/projector/input")
@app.get("/api/room/projector/input")
def get_projector_input():
    """Returns active input source (HDMI_1, ANDROID_HOME, USB) on the single-port projector."""
    src = projector.get_current_source()
    return {"current_input": src.value, "hdmi_ports": 1}


@app.post("/api/projector/focus")
@app.post("/api/room/projector/focus")
def trigger_projector_focus():
    """Triggers camera-assisted electric motor auto-focus on the projector."""
    return projector.auto_focus()


@app.post("/api/projector/keystone")
@app.post("/api/room/projector/keystone")
def trigger_projector_keystone():
    """Triggers 6D gyro-assisted auto-keystone correction on the projector."""
    return projector.auto_keystone()


@app.get("/api/projector/brightness")
@app.get("/api/room/projector/brightness")
def get_projector_brightness():
    """Returns normalized projector screen brightness percentage (0-100%)."""
    pct = projector.get_brightness()
    return {"brightness_percent": pct}


@app.post("/api/projector/brightness")
@app.post("/api/room/projector/brightness")
def set_projector_brightness(req: ProjectorBrightnessRequest):
    """Sets normalized projector screen brightness (0-100%) with read-back verification."""
    verified, actual_pct = projector.set_brightness(req.brightness)
    return {
        "success": verified,
        "requested_percent": req.brightness,
        "actual_percent": actual_pct,
        "verified": verified
    }


@app.post("/api/projector/key")
@app.post("/api/room/projector/key")
def send_projector_key(req: ProjectorKeyRequest):
    """Sends a safe navigation/control key to the projector."""
    key_lower = req.key.strip().lower()
    success = False
    if key_lower == "home":
        success = projector.home()
    elif key_lower == "back":
        success = projector.back()
    elif key_lower == "menu":
        success = projector.menu()
    elif key_lower in ["up", "dpad_up"]:
        success = projector.dpad_up()
    elif key_lower in ["down", "dpad_down"]:
        success = projector.dpad_down()
    elif key_lower in ["left", "dpad_left"]:
        success = projector.dpad_left()
    elif key_lower in ["right", "dpad_right"]:
        success = projector.dpad_right()
    elif key_lower in ["center", "select", "enter", "ok"]:
        success = projector.dpad_center()
    elif key_lower.isdigit():
        success = projector.send_key(int(key_lower))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported key: {req.key}")

    return {"success": success, "key": req.key}


@app.post("/api/projector/volume")
@app.post("/api/room/projector/volume")
def set_projector_volume(req: ProjectorVolumeRequest):
    """Sends volume commands (up, down, mute) to the projector."""
    action = req.action.strip().lower()
    success = False
    if action == "up":
        success = projector.volume_up()
    elif action == "down":
        success = projector.volume_down()
    elif action == "mute":
        success = projector.volume_mute()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported volume action: {req.action}")

    return {"success": success, "action": req.action}


@app.post("/api/projector/source")
@app.post("/api/room/projector/source")
def set_projector_source(req: ProjectorSourceRequest):
    """Switches the input source (ANDROID, HDMI_1, USB) on the projector."""
    success = projector.set_source(req.source)
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid or failed source switch to: {req.source} (Note: Hardware has only 1 HDMI port)")
    return {"success": True, "source": req.source.upper()}


@app.post("/api/projector/power")
@app.post("/api/room/projector/power")
def set_projector_power(req: ProjectorPowerRequest):
    """Queries or manages projector power state (WAKE, SLEEP, OFF, ON, STATUS)."""
    act = req.action.strip().upper()
    if act == "STATUS":
        return projector.get_power_state()
    elif act == "WAKE":
        success = projector.wake()
        pwr = projector.get_power_state()
        return {"success": success, "action": "WAKE", "power_state": pwr.get("power_state"), "message": "Projector wake executed"}
    elif act == "SLEEP":
        success = projector.sleep()
        pwr = projector.get_power_state()
        return {"success": success, "action": "SLEEP", "power_state": pwr.get("power_state"), "message": "Projector sleep executed"}
    elif act == "ON":
        pwr = projector.get_power_state()
        if pwr.get("power_state") == "ON":
            return {"success": True, "action": "ON", "power_state": "ON", "message": "Already ON"}
        # If in standby, wake it up
        if pwr.get("power_state") in ["STANDBY", "SLEEPING", "AWAKE"]:
            ok = projector.wake()
            return {"success": ok, "action": "WAKE", "power_state": projector.get_power_state().get("power_state"), "message": "Woken from standby"}
        return {"success": False, "action": "ON", "error": "Cold power-on unavailable via ADB (requires IR blaster or physical button)"}
    elif act == "OFF":
        try:
            success = projector.power_off()
            pwr = projector.get_power_state()
            return {"success": success, "action": "OFF", "power_state": pwr.get("power_state"), "message": "OEM power-off sequence initiated"}
        except Exception as e:
            return {"success": False, "action": "OFF", "error": str(e), "message": f"Projector power-off failed: {e}"}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported power action: {req.action}")



@app.get("/api/room/status")
def get_room_status_endpoint() -> Dict[str, Any]:
    """Returns complete, structured smart room status across Movie Mode, Projector, Fire TV, and Audio."""
    return orchestrator.get_room_status()


@app.get("/api/room/state")
def get_room_state_endpoint() -> Dict[str, Any]:
    """Returns authoritative canonical RoomState snapshot compiled from verified physical controllers."""
    return room_state_aggregator.get_room_state().to_dict()


@app.get("/api/capabilities")
def get_capabilities_endpoint() -> Dict[str, Any]:
    """Returns authoritative machine-readable catalog of all smart room capabilities."""
    return unified_capability_registry.export_catalog_dict()




@app.post("/api/room/automation/trigger")
def trigger_room_automation_endpoint(req: AutomationTriggerRequest) -> Dict[str, Any]:
    """Dispatches any named smart room automation dynamically."""
    logger.info(f"[API_AUTOMATION_TRIGGER] Triggering automation '{req.automation}' with params={req.params}")
    res = orchestrator.execute_automation(req.automation, **(req.params or {}))
    return res


@app.post("/api/room/movie-mode/start")
def start_movie_mode_endpoint(req: Optional[MovieModeRequest] = None) -> Dict[str, Any]:
    """Orchestrates starting Movie Mode with optional content search or direct provider launch."""
    content = req.content if req else None
    provider = req.provider if req else None
    logger.info(f"[API_MOVIE_MODE_START] Starting Movie Mode via API (content='{content}', provider='{provider}')")
    return orchestrator.start_movie_mode(content=content, provider=provider)


@app.post("/api/room/movie-mode/stop")
def stop_movie_mode_endpoint() -> Dict[str, Any]:
    """Orchestrates stopping Movie Mode."""
    logger.info("[API_MOVIE_MODE_STOP] Stopping Movie Mode via API")
    return orchestrator.stop_movie_mode()


@app.post("/api/room/firetv/playback")
def firetv_playback_control_endpoint(req: FireTVPlaybackRequest) -> Dict[str, Any]:
    """Dispatches media transport and volume controls to Fire TV active media session."""
    logger.info(f"[API_FIRETV_PLAYBACK] Dispatching action '{req.action}' to Fire TV")
    return orchestrator.fire_tv_playback_control(req.action)


@app.get("/api/room/firetv/status")
def get_firetv_status() -> Dict[str, Any]:
    """Returns Fire TV Stick presence, power state, and Bluetooth connection telemetry."""
    return fire_tv.get_status()


@app.get("/api/room/firetv/capabilities")
def get_firetv_capabilities_endpoint() -> Dict[str, Any]:
    """Returns machine-readable Fire TV capability registry, provider catalog, and live FireTVState."""
    meta = FireTVCapabilityRegistry.get_registry_metadata()
    current_state = orchestrator.capabilities.get_state(movie_mode_active=orchestrator._in_movie_mode) if orchestrator.capabilities else None
    return {
        "registry": meta,
        "current_state": (current_state.model_dump() if hasattr(current_state, "model_dump") else current_state.dict()) if current_state else None
    }


@app.post("/api/room/audio/switch")
def switch_audio_ownership_endpoint(req: AudioSwitchRequest) -> Dict[str, Any]:
    """Switches authoritative audio ownership between PC and Fire TV."""
    target_clean = req.target.strip().upper()
    logger.info(f"[API_AUDIO_SWITCH] Switching audio ownership to {target_clean}")
    if target_clean in ["PC", "COMPUTER", "MY_COMPUTER", "PC_AUDIO"]:
        ok, state, msg = orchestrator.connect_soundbar(timeout_seconds=12.0)
        st = orchestrator.get_room_status()
        is_verified = ok and (st.get("soundbar_name") is not None)
        return {
            "success": is_verified,
            "target": "PC",
            "message": "Soundbar connected to computer." if is_verified else "Could not connect the soundbar to the computer.",
            "room_audio_state": state.value,
            "soundbar_name": st.get("soundbar_name")
        }
    elif target_clean in ["FIRE_TV", "FIRETV", "TV", "STICK"]:
        orchestrator.disconnect_soundbar()
        ftv_ok = fire_tv.connect_soundbar(timeout_seconds=6.0) if fire_tv else False
        is_verified = ftv_ok and fire_tv.is_required_bluetooth_connected() if fire_tv else False
        return {
            "success": is_verified,
            "target": "FIRE_TV",
            "message": "Audio switched to Fire TV." if is_verified else "Could not switch audio to Fire TV.",
            "fire_tv_connected": is_verified
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported audio switch target: {req.target}")


# =============================================================================
# SMART ROOM DUAL ALARM AUDIO ENDPOINTS
# =============================================================================

@app.post("/api/room/alarm/start")
def start_alarm_endpoint() -> Dict[str, Any]:
    """Starts alarm audio playback on PC/Soundbar, respecting Movie Mode ownership."""
    logger.info("[API_ALARM_START] Starting PC daemon alarm audio...")
    return orchestrator.start_alarm()


@app.post("/api/room/alarm/stop")
def stop_alarm_endpoint() -> Dict[str, Any]:
    """Stops alarm audio playback on PC daemon."""
    logger.info("[API_ALARM_STOP] Stopping PC daemon alarm audio...")
    return orchestrator.stop_alarm()


@app.get("/api/room/alarm/status")
def get_alarm_status_endpoint() -> Dict[str, Any]:
    """Returns whether alarm audio is currently playing on PC."""
    return orchestrator.get_alarm_status()


@app.get("/api/diagnostics/audio-devices")
def get_audio_devices():
    lg_dev, devices = player.bt_helper.scan_active_endpoints()
    auth_info = resolver.get_auth_status()
    st = player.get_status()
    dp_avail = player.bt_helper.device_portal.is_available()
    return {
        "devices": devices,
        "preferred": lg_dev or {"id": None, "name": None, "status": "NOT_IN_GRAPH"},
        "active": {
            "id": st.get("audio_device_id"),
            "name": st.get("audio_device_name"),
            "status": st.get("audio_output_status")
        },
        "device_portal": {
            "available": dp_avail,
            "last_reconnect_method": player.bt_helper.last_reconnect_method,
            "last_reconnect_duration_ms": player.bt_helper.last_reconnect_duration_ms
        },
        "authentication": auth_info
    }


# =============================================================================
# OLLAMA BRAIN LIFECYCLE MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/brain/ollama/status")
def get_ollama_status() -> Dict[str, Any]:
    """Returns authoritative Ollama server and model residency status."""
    return ollama_mgr.get_status()


@app.post("/brain/ollama/start")
def start_ollama_server() -> Dict[str, Any]:
    """Starts Ollama server in single-flight mode if not already running."""
    success = ollama_mgr.ensure_server_running()
    return {"success": success, "status": ollama_mgr.get_status()}


@app.post("/brain/ollama/warmup")
def warmup_ollama_model() -> Dict[str, Any]:
    """Preloads target model into GPU VRAM with 24h keep-alive."""
    success = ollama_mgr.ensure_model_ready()
    return {"success": success, "status": ollama_mgr.get_status()}


@app.post("/brain/ollama/recover")
def recover_ollama() -> Dict[str, Any]:
    """Executes watchdog recovery on Ollama server and model."""
    success = ollama_mgr.recover()
    return {"success": success, "status": ollama_mgr.get_status()}


# =============================================================================
# PHASE E.2 FIRE TV SERVICE LAYER ENDPOINTS
# =============================================================================

@app.post("/api/room/service/watch")
def service_watch_endpoint(req: WatchServiceRequest) -> Dict[str, Any]:
    """Idempotent, state-aware content playback workflow on Fire TV."""
    logger.info(f"[API_SERVICE_WATCH] Watch request: query='{req.query}', provider='{req.provider}', direct_play={req.direct_play_first}")
    res = firetv_service.watch_content(
        query=req.query,
        provider=req.provider,
        direct_play_first=req.direct_play_first
    )
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/cinema/start")
def service_cinema_start_endpoint(req: Optional[CinemaStartServiceRequest] = None) -> Dict[str, Any]:
    """Starts cinema workflow: wakes Fire TV, routes soundbar, switches HDMI 1, launches content."""
    content = req.content if req else None
    provider = req.provider if req else None
    logger.info(f"[API_SERVICE_CINEMA_START] Starting cinema (content='{content}', provider='{provider}')")
    res = firetv_service.start_cinema(content=content, provider=provider)
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/cinema/stop")
def service_cinema_stop_endpoint(req: Optional[CinemaStopServiceRequest] = None) -> Dict[str, Any]:
    """Stops cinema workflow: pauses Fire TV media, transfers soundbar to PC, optional projector shutdown."""
    turn_off = req.turn_off_projector if req else False
    logger.info(f"[API_SERVICE_CINEMA_STOP] Stopping cinema (turn_off_projector={turn_off})")
    res = firetv_service.stop_cinema(turn_off_projector=turn_off)
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/cinema/pause")
def service_cinema_pause_endpoint() -> Dict[str, Any]:
    """Pauses active media playback on Fire TV."""
    logger.info("[API_SERVICE_CINEMA_PAUSE] Pausing cinema content")
    res = firetv_service.pause_content()
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/cinema/resume")
def service_cinema_resume_endpoint() -> Dict[str, Any]:
    """Resumes paused media playback on Fire TV."""
    logger.info("[API_SERVICE_CINEMA_RESUME] Resuming cinema content")
    res = firetv_service.resume_content()
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/provider/switch")
def service_provider_switch_endpoint(req: ProviderSwitchServiceRequest) -> Dict[str, Any]:
    """Switches active streaming provider on Fire TV."""
    logger.info(f"[API_SERVICE_PROVIDER_SWITCH] Switching provider to '{req.target_provider}', content='{req.content}'")
    res = firetv_service.switch_provider(target_provider=req.target_provider, content=req.content)
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/audio/route")
def service_audio_route_endpoint(req: AudioRouteServiceRequest) -> Dict[str, Any]:
    """Routes LG Soundbar audio ownership between Fire TV and PC."""
    target_clean = req.target.strip().upper()
    logger.info(f"[API_SERVICE_AUDIO_ROUTE] Routing audio to {target_clean}")
    if target_clean in ["FIRE_TV", "FIRETV", "TV", "STICK"]:
        res = firetv_service.route_audio_to_firetv()
    elif target_clean in ["PC", "COMPUTER", "MY_COMPUTER", "PC_AUDIO"]:
        res = firetv_service.route_audio_to_pc()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported audio routing target: {req.target}")
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.post("/api/room/service/recover")
def service_recover_endpoint(req: Optional[ServiceRecoveryRequest] = None) -> Dict[str, Any]:
    """Executes subsystem recovery (adb, bluetooth, hdmi, playback, or full)."""
    sub = (req.subsystem if req and req.subsystem else "all").strip().lower()
    logger.info(f"[API_SERVICE_RECOVER] Recovering subsystem: {sub}")
    if sub == "adb":
        res = firetv_service.recover_firetv_adb()
    elif sub in ["bluetooth", "bt", "soundbar"]:
        res = firetv_service.recover_bluetooth()
    elif sub in ["hdmi", "projector"]:
        res = firetv_service.recover_projector_hdmi()
    elif sub in ["playback", "media"]:
        res = firetv_service.recover_stopped_playback()
    elif sub in ["app", "streaming"]:
        res = firetv_service.recover_stuck_app()
    else:
        res = firetv_service.full_entertainment_recovery()
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@app.get("/api/room/service/state")
def service_state_endpoint() -> Dict[str, Any]:
    """Returns authoritative live physical telemetry across all room entertainment subsystems."""
    st = firetv_service.get_live_state()
    return st.model_dump() if hasattr(st, "model_dump") else st.dict()


@app.get("/api/room/service/automations")
def service_automations_list_endpoint() -> Dict[str, Any]:
    """Returns all 67 declarative automations across 7 categories in the Automation Registry."""
    return {
        "count": automation_registry.count(),
        "automations": [a.to_dict() for a in automation_registry.list_all()]
    }


@app.post("/api/room/service/automation/execute")
def service_automation_execute_endpoint(req: ServiceAutomationExecuteRequest) -> Dict[str, Any]:
    """Executes any named automation from the 67 registered use cases."""
    logger.info(f"[API_SERVICE_AUTOMATION_EXECUTE] Executing automation ID '{req.automation_id}' with params={req.params}")
    res = firetv_service.execute_automation(req.automation_id, req.params)
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


# =========================================================================
# AIR CONDITIONER (AC) AUTHORITATIVE REST ENDPOINTS
# =========================================================================

@app.get("/api/ac/status")
def ac_status_endpoint() -> Dict[str, Any]:
    """Returns authoritative live physical telemetry from the Air Conditioner."""
    return ac_controller.get_status()


@app.post("/api/ac/power")
def ac_power_endpoint(req: AcPowerRequest) -> Dict[str, Any]:
    """Sets AC power ON or OFF with read-back verification."""
    ok, res = ac_controller.set_power(req.on)
    if not ok:
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/ac/temperature")
def ac_temperature_endpoint(req: AcTemperatureRequest) -> Dict[str, Any]:
    """Sets target AC thermostat temperature (16-30°C) with read-back verification."""
    ok, res = ac_controller.set_temperature(req.temperature)
    if not ok:
        status_code = 400 if res.get("status") == "INVALID_PARAMETER" else 500
        raise HTTPException(status_code=status_code, detail=res)
    return res


@app.post("/api/ac/mode")
def ac_mode_endpoint(req: AcModeRequest) -> Dict[str, Any]:
    """Sets AC HVAC mode (COOL, AUTO, DRY, FAN) with read-back verification."""
    ok, res = ac_controller.set_mode(req.mode)
    if not ok:
        status_code = 400 if res.get("status") in ["INVALID_PARAMETER", "UNSUPPORTED_HARDWARE"] else 500
        raise HTTPException(status_code=status_code, detail=res)
    return res


@app.post("/api/ac/fan")
def ac_fan_endpoint(req: AcFanRequest) -> Dict[str, Any]:
    """Sets AC fan blower speed (LOW, MEDIUM, HIGH, AUTO) with read-back verification."""
    ok, res = ac_controller.set_fan_speed(req.speed)
    if not ok:
        status_code = 400 if res.get("status") == "INVALID_PARAMETER" else 500
        raise HTTPException(status_code=status_code, detail=res)
    return res


@app.post("/api/ac/command")
def ac_natural_command_endpoint(req: AcNaturalCommandRequest) -> Dict[str, Any]:
    """Routes and executes natural language AC command queries."""
    res = ac_router.route_command(req.query)
    if not res.get("success") and res.get("status") == "UNRESOLVED_COMMAND":
        raise HTTPException(status_code=400, detail=res)
    return res


# =========================================================================
# PC HOST AUTHORITATIVE REST ENDPOINTS
# =========================================================================

@app.get("/api/pc/status")
def pc_status_endpoint() -> Dict[str, Any]:
    """Returns authoritative live physical telemetry across PC Audio, Bluetooth, Media, and Power."""
    return pc_controller.get_status()


@app.post("/api/pc/volume")
def pc_volume_endpoint(req: PcVolumeRequest) -> Dict[str, Any]:
    """Sets master PC volume (0-100%) with physical read-back verification."""
    ok, res = pc_controller.set_volume(req.volume)
    if not ok:
        status_code = 400 if res.get("status") == "INVALID_PARAMETER" else 500
        raise HTTPException(status_code=status_code, detail=res)
    return res


@app.post("/api/pc/mute")
def pc_mute_endpoint(req: PcMuteRequest) -> Dict[str, Any]:
    """Sets master PC mute state (true for MUTE, false for UNMUTE) with read-back verification."""
    ok, res = pc_controller.set_mute(req.mute)
    if not ok:
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/pc/media")
def pc_media_endpoint(req: PcMediaRequest) -> Dict[str, Any]:
    """Dispatches global Windows media session key events."""
    action = req.action.strip().upper()
    if action in ["PLAY_PAUSE", "PLAY", "PAUSE", "TOGGLE"]:
        ok, res = pc_controller.media_play_pause()
    elif action in ["NEXT", "NEXT_TRACK", "SKIP"]:
        ok, res = pc_controller.media_next()
    elif action in ["PREVIOUS", "PREV", "PREV_TRACK"]:
        ok, res = pc_controller.media_previous()
    elif action in ["STOP"]:
        ok, res = pc_controller.media_stop()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported media action: {req.action}")

    if not ok:
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/pc/power")
def pc_power_endpoint(req: PcPowerRequest) -> Dict[str, Any]:
    """Manages workstation lock, sleep, or power queries."""
    action = req.action.strip().upper()
    if action in ["LOCK", "LOCK_WORKSTATION"]:
        ok, res = pc_controller.lock_workstation()
    elif action in ["SLEEP", "STANDBY"]:
        ok, res = pc_controller.sleep()
    elif action in ["STATUS", "POWER_STATE"]:
        return pc_controller.get_power_state()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported power action: {req.action}")

    if not ok:
        raise HTTPException(status_code=500, detail=res)
    return res


@app.get("/api/pc/bluetooth")
def pc_bluetooth_endpoint() -> Dict[str, Any]:
    """Returns local Bluetooth radio status and all discovered paired/connected devices."""
    return pc_controller.get_bluetooth_status()


@app.post("/api/pc/command")
def pc_natural_command_endpoint(req: PcNaturalCommandRequest) -> Dict[str, Any]:
    """Routes and executes natural language PC command queries."""
    res = pc_router.route_command(req.query)
    if not res.get("success") and res.get("status") in ["UNRESOLVED_COMMAND", "SECURITY_REJECTED"]:
        status_code = 403 if res.get("status") == "SECURITY_REJECTED" else 400
        raise HTTPException(status_code=status_code, detail=res)
    return res


# =========================================================================
# CAPABILITY REGISTRY, ROOM STATE & GEMINI STRUCTURED PLANNER ENDPOINTS
# =========================================================================

class PlannerPlanRequest(BaseModel):
    request: str = Field(..., min_length=1, description="Natural language user planning intent/request")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional environmental context")
    preferences: Optional[Dict[str, Any]] = Field(default=None, description="Optional user preferences hierarchy")


@app.get("/api/capabilities")
def get_capabilities_catalog() -> Dict[str, Any]:
    """Returns authoritative machine-readable catalog of all smart room capabilities."""
    return unified_capability_registry.export_catalog_dict()


@app.get("/api/room/state")
def get_canonical_room_state() -> Dict[str, Any]:
    """Returns canonical, fresh RoomState snapshot with provenance tags."""
    st = room_state_aggregator.get_room_state()
    return st.to_sanitized_prompt_dict()


@app.get("/api/preferences")
def get_user_preferences() -> Dict[str, Any]:
    """Returns active user and room preferences with capability-bound validation."""
    return preference_manager.get_preferences().to_dict()


@app.get("/api/context")
def get_context_snapshot() -> Dict[str, Any]:
    """Returns full, fresh context snapshot (temporal, room semantic, weather PIN 741235, preferences)."""
    current_state = room_state_aggregator.get_room_state()
    return context_engine.build_context_snapshot(room_state=current_state).to_dict()


@app.post("/api/planner/plan")
def plan_room_orchestration(req: PlannerPlanRequest) -> Dict[str, Any]:
    """
    Translates user natural language intent into a structured, validated room plan.
    STRICTLY ZERO HARDWARE EXECUTION — planning and deterministic validation ONLY.
    """
    if not req.request.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning request cannot be empty."
        )

    current_state = room_state_aggregator.get_room_state()
    active_context = req.context or context_engine.build_context_snapshot(room_state=current_state).to_dict()
    active_preferences = req.preferences or preference_manager.get_preferences().to_dict()

    try:
        validation_res = planner_client.generate_and_validate_plan(
            user_request=req.request,
            room_state=current_state,
            context=active_context,
            preferences=active_preferences
        )
        return validation_res.to_dict()
    except GeminiApiUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "GEMINI_UNAVAILABLE",
                "message": str(e)
            }
        )
    except GeminiResponseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "status": "GEMINI_RESPONSE_ERROR",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"[PLANNER_ENDPOINT_ERROR] Unexpected planning error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "PLANNER_ERROR",
                "message": str(e)
            }
        )


@app.post("/api/planner/execute")
def execute_validated_plan_endpoint(req: PlannerPlanRequest) -> Dict[str, Any]:
    """
    Translates user natural language intent into a plan, executes PlanValidator,
    and dispatches only the validated plan through physical controllers with read-back verification.
    """
    if not req.request.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution request cannot be empty."
        )

    current_state = room_state_aggregator.get_room_state()
    active_context = req.context or context_engine.build_context_snapshot(room_state=current_state).to_dict()
    active_preferences = req.preferences or preference_manager.get_preferences().to_dict()

    try:
        # Step 1: Generate plan from Gemini
        validation_res = planner_client.generate_and_validate_plan(
            user_request=req.request,
            room_state=current_state,
            context=active_context,
            preferences=active_preferences
        )

        # Step 2: Ensure validation succeeded
        if not validation_res.valid:
            return {
                "execution_success": False,
                "overall_status": "VALIDATION_FAILED",
                "validation_errors": [e.model_dump() for e in validation_res.errors],
                "message": "Plan failed deterministic validation and was rejected before hardware execution."
            }

        # Step 3: Execute validated plan through PlanExecutor
        exec_res = planner_executor.execute_plan(validation_res)
        return exec_res.to_dict()

    except GeminiApiUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "GEMINI_UNAVAILABLE",
                "message": str(e)
            }
        )
    except GeminiResponseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "status": "GEMINI_RESPONSE_ERROR",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"[PLANNER_EXECUTE_ENDPOINT_ERROR] Execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "PLANNER_EXECUTION_ERROR",
                "message": str(e)
            }
        )


# =========================================================================
# PHASE F.1 PERSONAL AGENT REST ENDPOINTS
# =========================================================================

class AgentInteractRequest(BaseModel):
    utterance: str = Field(..., min_length=1, description="Natural language conversational turn/request from user")


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Title of the task")
    description: Optional[str] = Field(default=None, description="Optional task description")
    priority: str = Field(default="MEDIUM", description="Priority: LOW, MEDIUM, HIGH, CRITICAL")
    category: str = Field(default="GENERAL", description="Category: WORK, LEARNING, PERSONAL, GENERAL")


@app.post("/api/agent/interact")
def agent_interact_endpoint(req: AgentInteractRequest) -> Dict[str, Any]:
    """
    Primary conversational agent interaction endpoint.
    Processes intent, checks routines/memory, executes orchestration if clear, and provides feedback.
    """
    resp = animus_personal_agent.interact(req.utterance)
    return resp.model_dump()


@app.get("/api/agent/brief")
def agent_daily_brief_endpoint() -> Dict[str, Any]:
    """Generates a fresh morning or daily briefing."""
    current_state = room_state_aggregator.get_room_state()
    ctx = context_engine.build_context_snapshot(room_state=current_state)
    brief = animus_personal_agent.daily_brief_engine.generate_morning_brief(
        room_state=current_state,
        weather_info=ctx.weather.to_dict()
    )
    return {
        "brief": brief,
        "timestamp": time.time()
    }


@app.get("/api/agent/profile")
def get_agent_user_profile() -> Dict[str, Any]:
    """Returns the authoritative UserProfile."""
    return animus_personal_agent.user_model.to_dict()


@app.post("/api/agent/profile")
def update_agent_user_profile(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates fields on the authoritative UserProfile."""
    updated = animus_personal_agent.user_model.update_profile(updates)
    animus_personal_agent.persistence.save_state(
        animus_personal_agent.user_model,
        animus_personal_agent.memory,
        animus_personal_agent.task_manager
    )
    return updated.model_dump()


@app.get("/api/agent/tasks")
def get_agent_tasks(include_completed: bool = False) -> List[Dict[str, Any]]:
    """Lists all active or completed tasks."""
    tasks = animus_personal_agent.task_manager.list_tasks(include_completed=include_completed)
    return [t.model_dump() for t in tasks]


@app.post("/api/agent/tasks")
def create_agent_task(req: TaskCreateRequest) -> Dict[str, Any]:
    """Creates a new task in the agent task store."""
    from agent.models import TaskPriority
    try:
        p = TaskPriority(req.priority.upper())
    except ValueError:
        p = TaskPriority.MEDIUM
    task = animus_personal_agent.task_manager.create_task(
        title=req.title,
        description=req.description,
        priority=p,
        category=req.category
    )
    animus_personal_agent.persistence.save_state(
        animus_personal_agent.user_model,
        animus_personal_agent.memory,
        animus_personal_agent.task_manager
    )
    return task.model_dump()


@app.post("/api/agent/tasks/{task_id}/complete")
def complete_agent_task_endpoint(task_id: str) -> Dict[str, Any]:
    """Marks a task as completed."""
    completed = animus_personal_agent.task_manager.complete_task(task_id)
    if not completed:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    animus_personal_agent.persistence.save_state(
        animus_personal_agent.user_model,
        animus_personal_agent.memory,
        animus_personal_agent.task_manager
    )
    return {"status": "SUCCESS", "task": completed.model_dump()}


@app.get("/api/agent/memory")
def get_agent_memory_summary() -> Dict[str, Any]:
    """Returns structured 9-category memory summary."""
    return animus_personal_agent.memory.to_dict_summary()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8095, log_level="info")






