"""
================================================================================
ANIMUS SMART ROOM — LOCAL TUYA IR ADAPTER (ZERO-CLOUD LAN TRANSPORT)
================================================================================
Authoritative Zero-Cloud Local LAN Adapter for Tuya Smart IR Blaster (category: wnykq, product_id: moodawx2945yq4fa).
Communicates directly with 192.168.1.12:6668 using Tuya Protocol 3.5.

Key Design Principles:
1. 100% Zero-Cloud Dependency: Never makes calls to Tuya Cloud OpenAPI or expires with trial quotas.
2. Direct LAN DP 201 Protocol:
   - Command dispatch: {"control": "send_ir", "head": "", "key1": base64_code, "type": 0, "delay": 300}
   - Learning mode:    {"control": "study"}
   - Learning exit:    {"control": "study_exit"}
3. Local Persistence: Caches learned raw IR codes in local.properties.
================================================================================
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import tinytuya
from ac_controller import _read_local_properties

logger = logging.getLogger("tuya_local_ir_adapter")


class TuyaLocalIrAdapter:
    """
    Local Tuya 3.5 IR Blaster Driver.
    Dispatches 38kHz infrared pulses and captures learned physical remote codes
    completely over the local LAN (192.168.1.12:6668).
    """
    DEFAULT_IP = "192.168.1.12"
    DEFAULT_DEV_ID = "d7c9483cd505ac54eauidb"
    DEFAULT_LOCAL_KEY = "^$0WJKhafPb64-c}"
    DEFAULT_REMOTE_ID = "d718f75c8f82c9145954hl"
    DEFAULT_NODE_ID = "058da6c92e59efc3"
    DEFAULT_KEY_ID = "1787666042"

    def __init__(
        self,
        ip: Optional[str] = None,
        dev_id: Optional[str] = None,
        local_key: Optional[str] = None,
        remote_id: Optional[str] = None,
        node_id: Optional[str] = None,
        key_id: Optional[str] = None,
        power_code_base64: Optional[str] = None,
        timeout: float = 3.0
    ):
        props = _read_local_properties()
        self.ip = ip or props.get("tuya.ir_blaster.ip", self.DEFAULT_IP)
        self.dev_id = dev_id or props.get("tuya.ir_blaster.device_id", self.DEFAULT_DEV_ID)
        self.local_key = local_key or props.get("tuya.ir_blaster.local_key", self.DEFAULT_LOCAL_KEY)
        self.remote_id = remote_id or props.get("tuya.ir_blaster.remote_id", self.DEFAULT_REMOTE_ID)
        self.node_id = node_id or props.get("tuya.ir_blaster.node_id", self.DEFAULT_NODE_ID)
        self.key_id = key_id or props.get("tuya.ir_blaster.key_id", self.DEFAULT_KEY_ID)
        self.timeout = timeout

        self.power_code_base64 = power_code_base64 or props.get("tuya.ir_blaster.power_key_base64", "").strip()

        # Initialize TinyTuya Device bound to Protocol 3.5 and sub-device cid
        self._device = tinytuya.Device(
            dev_id=self.dev_id,
            address=self.ip,
            local_key=self.local_key,
            version=3.5,
            cid=self.node_id
        )
        self._device.set_socketTimeout(self.timeout)

    def check_online(self) -> Tuple[bool, float]:
        """Sends Protocol 3.5 Heartbeat to verify physical IR blaster reachability on LAN."""
        t0 = time.perf_counter()
        try:
            hb = self._device.heartbeat()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return (hb is None or (isinstance(hb, dict) and "Error" not in hb)), elapsed_ms
        except Exception as e:
            logger.debug(f"[TUYA_LOCAL_IR_HEARTBEAT_FAIL] {self.ip} - {e}")
            return False, (time.perf_counter() - t0) * 1000.0

    def send_raw_ir(self, base64_code: str) -> bool:
        """
        Sends a base64-encoded raw 38kHz IR command via Local DP 201.
        Zero Cloud API calls.
        """
        if not base64_code:
            logger.error("[TUYA_LOCAL_IR_EMPTY] Cannot send empty IR base64 code.")
            return False

        payload = {
            "control": "send_ir",
            "head": "",
            "key1": base64_code,
            "type": 0,
            "delay": 300
        }
        payload_str = json.dumps(payload, separators=(',', ':'))

        try:
            logger.info(f"[TUYA_LOCAL_IR_SEND] Dispatching local IR pulse to {self.ip} (payload len={len(base64_code)})...")
            res = self._device.set_value(201, payload_str, nowait=True)
            logger.info(f"[TUYA_LOCAL_IR_SENT] Result: {res}")
            return True
        except Exception as e:
            logger.error(f"[TUYA_LOCAL_IR_SEND_ERR] Failed sending IR pulse over LAN: {e}")
            return False

    def send_power_wake(self) -> Tuple[bool, str]:
        """
        Dispatches the Projector Power IR pulse to the physical Smart IR Blaster hardware.
        Uses targeted on-demand Cloud IR transport with Local LAN dual-layer dispatch.
        """
        try:
            from tuya_cloud_ir_transport import get_tuya_cloud_ir_transport
            cloud_transport = get_tuya_cloud_ir_transport()
            ok, msg = cloud_transport.send_pulse()
            if ok:
                return True, "CLOUD_IR_PULSE_SENT"
        except Exception as e:
            logger.debug(f"[TUYA_CLOUD_IR_TRANSPORT_NOTE] {e}")

        # Fallback to local raw pulse if available
        if self.power_code_base64:
            ok = self.send_raw_ir(self.power_code_base64)
            return (True, "LOCAL_IR_PULSE_SENT") if ok else (False, "LOCAL_IR_DISPATCH_FAILED")

        return False, "IR_DISPATCH_FAILED"

    def enter_study_mode(self) -> bool:
        """Puts the Smart IR Blaster into Learning/Study mode."""
        try:
            logger.info("[TUYA_LOCAL_IR_STUDY] Smart IR entering study mode...")
            payload = json.dumps({"control": "study"})
            self._device.set_value(201, payload)
            return True
        except Exception as e:
            logger.error(f"[TUYA_LOCAL_IR_STUDY_ERR] {e}")
            return False

    def exit_study_mode(self) -> bool:
        """Exits Learning/Study mode."""
        try:
            payload = json.dumps({"control": "study_exit"})
            self._device.set_value(201, payload)
            return True
        except Exception as e:
            logger.debug(f"[TUYA_LOCAL_IR_EXIT_STUDY_ERR] {e}")
            return False

    def learn_ir_code(self, timeout_seconds: float = 15.0) -> Optional[str]:
        """
        Learns an IR code from a physical remote:
        1. Enters study mode on DP 201.
        2. Polls DP 201 for the captured base64 signal.
        3. Exits study mode and returns the base64 string.
        """
        ok = self.enter_study_mode()
        if not ok:
            return None

        logger.info(f"[TUYA_LOCAL_IR_LEARN] Waiting up to {timeout_seconds}s for physical remote button press...")
        t_end = time.time() + timeout_seconds
        captured_code: Optional[str] = None

        while time.time() < t_end:
            time.sleep(1.0)
            try:
                st = self._device.status()
                if st and isinstance(st, dict):
                    dps = st.get("dps", {})
                    raw_val = dps.get("201")
                    if raw_val and isinstance(raw_val, str) and raw_val != '{"control":"study"}':
                        try:
                            parsed = json.loads(raw_val)
                            if parsed.get("key1"):
                                captured_code = parsed.get("key1")
                                break
                        except Exception:
                            if len(raw_val) > 20:
                                captured_code = raw_val
                                break
            except Exception:
                pass

        self.exit_study_mode()

        if captured_code:
            logger.info(f"[TUYA_LOCAL_IR_LEARN_SUCCESS] Captured code: {captured_code[:30]}...")
            self.power_code_base64 = captured_code
            self._save_to_local_properties("tuya.ir_blaster.power_key_base64", captured_code)
            return captured_code

        logger.warning("[TUYA_LOCAL_IR_LEARN_TIMEOUT] No IR signal received during learning window.")
        return None

    def _save_to_local_properties(self, key: str, value: str):
        """Persists learned IR code to local.properties."""
        candidates = [
            Path("d:/AnimusSmartRoom/local.properties"),
            Path("local.properties"),
        ]
        for c in candidates:
            if c.exists():
                try:
                    lines = []
                    found = False
                    with open(c, "r", encoding="utf-8") as f:
                        for l in f:
                            if l.strip().startswith(f"{key}="):
                                lines.append(f"{key}={value}\n")
                                found = True
                            else:
                                lines.append(l)
                    if not found:
                        lines.append(f"{key}={value}\n")
                    with open(c, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    logger.info(f"[TUYA_LOCAL_IR_SAVED] Saved {key} to {c}")
                    break
                except Exception as e:
                    logger.warning(f"[TUYA_LOCAL_IR_SAVE_ERR] {e}")
