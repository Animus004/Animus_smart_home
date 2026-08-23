"""
Animus PC Local Music Resolution and Playback Daemon.
Exposes REST endpoints on port 8095 for track resolution, playback control,
authenticated status, Device Portal Bluetooth auto-reconnection, and Smart Room Orchestration.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

from resolver import YouTubeMusicResolver
from player import MpvPlayer
from orchestrator import SmartRoomOrchestrator, RoomAudioState
from projector_controller import ProjectorController
from fire_tv_controller import FireTvController
from ollama_manager import OllamaManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("music_daemon.main")

# Initialize Resolver, Player, Projector, Fire TV, Orchestrator, and OllamaManager instances
SECRETS_DIR = Path(__file__).parent / "secrets"
resolver = YouTubeMusicResolver(secrets_dir=SECRETS_DIR)
player = MpvPlayer(preferred_device_keyword="LG SNC4R")
projector = ProjectorController()
fire_tv = FireTvController()
ollama_mgr = OllamaManager()
orchestrator = SmartRoomOrchestrator(
    resolver=resolver,
    player=player,
    projector=projector,
    fire_tv=fire_tv
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[PC_MUSIC_DAEMON_START] Animus PC Smart Room Daemon v1.6.0 starting on port 8095...")
    logger.info(f"[PC_MUSIC_DAEMON_AUTH] YouTube Music Authentication: is_authenticated={resolver.is_authenticated}, method={resolver.auth_method}")
    # Inspect initial room audio state
    init_status = orchestrator.get_room_status()
    logger.info(f"[PC_MUSIC_DAEMON_AUDIO] Initial Room Audio State: {init_status['room_audio_state']} (Soundbar: {init_status.get('soundbar_name')})")

    yield

    logger.info("[PC_MUSIC_DAEMON_STOP] Shutting down orchestrator and releasing resources...")
    player.shutdown()


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
    source: str = Field(..., description="Source: ANDROID, HDMI_1, HDMI_2, HDMI_3, USB, AV, VGA")

class ProjectorPowerRequest(BaseModel):
    action: str = Field(..., description="Power action: ON, OFF, STATUS")

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


class VolumeRequest(BaseModel):
    volume: int = Field(..., ge=0, le=100, description="Target volume level from 0 to 100")


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
@app.get("/api/room/projector/status")
def get_projector_status():
    """Returns structured status and system information for the Zebronics PixaPlay 25 projector."""
    info = projector.get_device_info()
    return info


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


@app.post("/api/room/projector/source")
def set_projector_source(req: ProjectorSourceRequest):
    """Switches the input source (ANDROID, HDMI_1, HDMI_2, HDMI_3, USB, AV, VGA) on the projector."""
    success = projector.set_source(req.source)
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid or failed source switch to: {req.source}")
    return {"success": True, "source": req.source.upper()}


@app.post("/api/room/projector/power")
def set_projector_power(req: ProjectorPowerRequest):
    """Queries or manages projector power state."""
    act = req.action.strip().upper()
    if act == "STATUS":
        return projector.get_power_state()
    elif act == "ON":
        pwr = projector.get_power_state()
        if pwr.get("power_state") == "ON":
            return {"success": True, "action": "ON", "power_state": "ON", "message": "Already ON"}
        return {"success": False, "action": "ON", "error": "Power ON requires physical power key / wake"}
    elif act == "OFF":
        success = projector.power_off()
        pwr = projector.get_power_state()
        return {"success": success, "action": "OFF", "power_state": pwr.get("power_state"), "message": "OEM power-off sequence initiated"}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported power action: {req.action}")


@app.get("/api/room/status")
def get_room_status_endpoint() -> Dict[str, Any]:
    """Returns complete, structured smart room status across Movie Mode, Projector, Fire TV, and Audio."""
    return orchestrator.get_room_status()


@app.post("/api/room/movie-mode/start")
def start_movie_mode_endpoint() -> Dict[str, Any]:
    """Orchestrates starting Movie Mode."""
    logger.info("[API_MOVIE_MODE_START] Starting Movie Mode via API")
    return orchestrator.start_movie_mode()


@app.post("/api/room/movie-mode/stop")
def stop_movie_mode_endpoint() -> Dict[str, Any]:
    """Orchestrates stopping Movie Mode."""
    logger.info("[API_MOVIE_MODE_STOP] Stopping Movie Mode via API")
    return orchestrator.stop_movie_mode()


@app.get("/api/room/firetv/status")
def get_firetv_status() -> Dict[str, Any]:
    """Returns Fire TV Stick presence, power state, and Bluetooth connection telemetry."""
    return fire_tv.get_status()


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8095, log_level="info")

