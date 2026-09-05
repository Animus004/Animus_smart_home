"""
Authoritative Host-Side Ollama Process Manager and Watchdog for Animus Smart Room.
Ensures single-flight process supervisor, explicit model loading, VRAM residency verification,
watchdog self-healing, and structured status reporting.
"""

import os
import sys
import time
import shutil
import logging
import threading
import subprocess
import requests
import psutil
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger("music_daemon.ollama_manager")

DEFAULT_OLLAMA_EXE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11434
DEFAULT_MODEL = "qwen3:4b-instruct"
DEFAULT_KEEP_ALIVE = "24h"

class OllamaState:
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    SERVER_READY = "SERVER_READY"
    MODEL_LOADING = "MODEL_LOADING"
    READY = "READY"
    BUSY = "BUSY"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"

class OllamaManager:
    """
    Manages local Ollama server process on the PC, ensuring:
    - Single-flight process execution (no duplicate ollama processes)
    - Pre-warmed model residency in GPU VRAM (keep_alive: 24h)
    - Watchdog monitoring and recovery from unexpected crashes
    - Structured status and diagnostics
    """
    def __init__(
        self,
        ollama_path: Optional[str] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        model: str = DEFAULT_MODEL,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
        auto_start_watchdog: bool = True
    ):
        self.ollama_path = ollama_path or (DEFAULT_OLLAMA_EXE if os.path.exists(DEFAULT_OLLAMA_EXE) else shutil.which("ollama"))
        self.host = host
        self.port = port
        self.model = model
        self.keep_alive = keep_alive
        self.base_url = f"http://{self.host}:{self.port}"
        
        self.current_state = OllamaState.OFFLINE
        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_error: Optional[str] = None
        self._consecutive_failures = 0
        
        if auto_start_watchdog:
            self.start_watchdog()

    def get_status(self) -> Dict[str, Any]:
        """Returns structured status including process PID, state, and loaded VRAM metrics."""
        is_running, pid = self._is_process_running()
        is_server_up = self._check_http_health()
        loaded_model_info = self._get_loaded_model_info() if is_server_up else None
        
        if not is_running and not is_server_up:
            if self.current_state != OllamaState.STARTING and self.current_state != OllamaState.RECOVERING:
                self.current_state = OllamaState.OFFLINE
        elif is_server_up:
            if loaded_model_info and loaded_model_info.get("name") == self.model:
                self.current_state = OllamaState.READY
            elif self.current_state != OllamaState.MODEL_LOADING:
                self.current_state = OllamaState.SERVER_READY

        return {
            "state": self.current_state,
            "host": self.host,
            "port": self.port,
            "target_model": self.model,
            "is_process_running": is_running,
            "pid": pid,
            "is_server_reachable": is_server_up,
            "loaded_model": loaded_model_info,
            "last_error": self._last_error,
            "consecutive_failures": self._consecutive_failures
        }

    def _is_process_running(self) -> Tuple[bool, Optional[int]]:
        """Checks whether ollama.exe or llama-server.exe is currently active in the OS process table."""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info['name'] or '').lower()
                if 'ollama' in name or 'llama-server' in name:
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False, None

    def terminate_all_processes(self):
        """Cleanly terminates all Ollama server and llama-server runner processes to release GPU VRAM."""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info['name'] or '').lower()
                if 'ollama' in name or 'llama-server' in name:
                    p = psutil.Process(proc.info['pid'])
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(1.0)

    def _check_http_health(self, timeout: float = 2.0) -> bool:
        """Checks if the Ollama HTTP server is responsive at /api/tags."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def _get_loaded_model_info(self) -> Optional[Dict[str, Any]]:
        """Queries /api/ps to retrieve loaded models and VRAM usage."""
        try:
            resp = requests.get(f"{self.base_url}/api/ps", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                for m in models:
                    if self.model in m.get("name", "") or self.model in m.get("model", ""):
                        return {
                            "name": m.get("name"),
                            "size": m.get("size", 0),
                            "size_vram": m.get("size_vram", 0),
                            "expires_at": m.get("expires_at"),
                            "details": m.get("details", {})
                        }
        except Exception as e:
            logger.debug(f"Failed to query /api/ps: {e}")
        return None

    def ensure_server_running(self, timeout: float = 60.0) -> bool:
        """
        Guarantees Ollama server is running (Single-Flight).
        If already running, returns True immediately.
        If offline, starts exactly ONE background instance of ollama serve.
        """
        with self._lock:
            is_running, pid = self._is_process_running()
            if is_running and self._check_http_health():
                return True

            logger.info("[OLLAMA_STARTUP] Starting Ollama server (single-flight)...")
            self.current_state = OllamaState.STARTING
            self._last_error = None

            if not self.ollama_path or not os.path.exists(self.ollama_path):
                self._last_error = f"Ollama binary not found at '{self.ollama_path}'"
                logger.error(self._last_error)
                self.current_state = OllamaState.FAILED
                return False

            try:
                # Launch ollama serve as detached background process with full user environment
                env = os.environ.copy()
                env["OLLAMA_HOST"] = f"0.0.0.0:{self.port}"
                cwd = os.path.dirname(self.ollama_path) if self.ollama_path else None
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

                self._process = subprocess.Popen(
                    [self.ollama_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    cwd=cwd,
                    creationflags=flags
                )
            except Exception as e:
                self._last_error = f"Failed to spawn Ollama server: {e}"
                logger.error(self._last_error)
                self.current_state = OllamaState.FAILED
                return False

            # Wait for server port /api/tags to become healthy
            start_t = time.time()
            while time.time() - start_t < timeout:
                if self._check_http_health():
                    time.sleep(1.5) # Allow internal CUDA discovery to settle
                    logger.info(f"[OLLAMA_SERVER_READY] Ollama HTTP server responsive on port {self.port} in {round(time.time() - start_t, 2)}s.")
                    self.current_state = OllamaState.SERVER_READY
                    return True
                time.sleep(0.5)

            self._last_error = f"Ollama server failed to respond on port {self.port} within {timeout}s"
            logger.error(self._last_error)
            self.current_state = OllamaState.FAILED
            return False

    def ensure_model_ready(self, timeout: float = 120.0) -> bool:
        """
        Ensures the target model is resident in GPU VRAM with 24h keep_alive.
        Single-flight: prevents duplicate model loading requests.
        """
        if not self.ensure_server_running(timeout=60.0):
            return False

        with self._lock:
            # Check if model is already loaded in /api/ps (either in VRAM or resident system RAM)
            loaded = self._get_loaded_model_info()
            if loaded and (loaded.get("size_vram", 0) > 0 or loaded.get("size", 0) > 0):
                self.current_state = OllamaState.READY
                return True

            logger.info(f"[OLLAMA_MODEL_LOAD] Pre-loading model '{self.model}' into GPU VRAM (keep_alive: {self.keep_alive})...")
            self.current_state = OllamaState.MODEL_LOADING
            t0 = time.time()

            try:
                # Preload model weights explicitly
                payload = {
                    "model": self.model,
                    "keep_alive": self.keep_alive,
                    "stream": False
                }
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=timeout
                )
                if resp.status_code == 200:
                    dur = round(time.time() - t0, 2)
                    logger.info(f"[OLLAMA_MODEL_READY] Model '{self.model}' resident in VRAM in {dur}s.")
                    self.current_state = OllamaState.READY
                    self._consecutive_failures = 0
                    return True
                elif resp.status_code == 409:
                    logger.warning("[OLLAMA_MODEL_BUSY] Model is currently being loaded by another operation (HTTP 409). Waiting...")
                    # Poll /api/ps until loaded
                    poll_start = time.time()
                    while time.time() - poll_start < 45.0:
                        loaded = self._get_loaded_model_info()
                        if loaded and (loaded.get("size_vram", 0) > 0 or loaded.get("size", 0) > 0):
                            self.current_state = OllamaState.READY
                            return True
                        time.sleep(1.0)
                
                self._last_error = f"Model load failed: HTTP {resp.status_code} - {resp.text}"
                logger.error(self._last_error)
                self.current_state = OllamaState.FAILED
                return False
            except Exception as e:
                self._last_error = f"Model loading exception: {e}"
                logger.error(self._last_error)
                self.current_state = OllamaState.FAILED
                return False

    def recover(self) -> bool:
        """Executes watchdog self-healing recovery sequence."""
        with self._lock:
            logger.warning("[OLLAMA_WATCHDOG_RECOVER] Initiating Ollama recovery sequence...")
            self.current_state = OllamaState.RECOVERING
            self._consecutive_failures += 1
            self.terminate_all_processes()

        # Re-start and warm up model
        if self.ensure_server_running(timeout=60.0):
            return self.ensure_model_ready(timeout=120.0)
        return False

    def start_watchdog(self, interval_seconds: float = 60.0):
        """Starts the background watchdog monitoring thread."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return

        def _watchdog_loop():
            while not self._stop_event.is_set():
                try:
                    if self.current_state == OllamaState.OFFLINE:
                        logger.info("[OLLAMA_WATCHDOG] Initial state is OFFLINE. Booting Ollama server and pre-warming model...")
                        if self.ensure_server_running(timeout=60.0):
                            self.ensure_model_ready(timeout=120.0)
                    elif self.current_state == OllamaState.READY or self.current_state == OllamaState.SERVER_READY:
                        if not self._check_http_health():
                            logger.warning("[OLLAMA_WATCHDOG] Server became unreachable. Triggering recovery...")
                            self.recover()
                        else:
                            # Verify model still resident in memory
                            loaded = self._get_loaded_model_info()
                            if not loaded or (loaded.get("size_vram", 0) == 0 and loaded.get("size", 0) == 0):
                                logger.info("[OLLAMA_WATCHDOG] Model unloaded from memory. Refreshing keep-alive residency...")
                                self.ensure_model_ready()
                except Exception as e:
                    logger.debug(f"[OLLAMA_WATCHDOG] Loop exception: {e}")

                self._stop_event.wait(interval_seconds)

        self._watchdog_thread = threading.Thread(target=_watchdog_loop, name="OllamaWatchdog", daemon=True)
        self._watchdog_thread.start()
        logger.info(f"[OLLAMA_WATCHDOG] Watchdog started (interval: {interval_seconds}s).")

    def shutdown(self):
        """Stops watchdog thread cleanly."""
        self._stop_event.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2.0)
        logger.info("[OLLAMA_MANAGER_SHUTDOWN] Ollama manager stopped.")
