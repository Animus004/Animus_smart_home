"""
================================================================================
ANIMUS SMART ROOM — TUYA CLOUD IR POWER TRANSPORT
================================================================================
Authoritative Minimal-Cloud Dispatcher for Smart IR Blaster.
Zero Background Polling. Zero Quota Waste.
Dispatches strictly on-demand for Projector Cold Wake via:
POST /v1.0/infrareds/{ir_id}/remotes/{remote_id}/learning-codes
================================================================================
"""

import time
import json
import hmac
import hashlib
import logging
import requests
from typing import Tuple, Optional, Dict, Any

from ac_controller import _read_local_properties

logger = logging.getLogger("tuya_cloud_ir_transport")


class TuyaCloudIrTransport:
    """
    On-Demand Tuya Cloud IR Dispatcher.
    Uses HMAC-SHA256 authenticated Tuya OpenAPI to push learned/raw infrared waveforms
    directly to the Tuya Smart IR Blaster hardware.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_id: Optional[str] = None,
        access_secret: Optional[str] = None,
        ir_id: Optional[str] = None,
        remote_id: Optional[str] = None,
        power_hex_code: Optional[str] = None,
        timeout: float = 6.0
    ):
        props = _read_local_properties()
        self.endpoint = (endpoint or props.get("tuya.region.endpoint", "https://openapi.tuyain.com")).rstrip("/")
        self.access_id = access_id or props.get("tuya.access.id", "").strip()
        self.access_secret = access_secret or props.get("tuya.access.secret", "").strip()
        self.ir_id = ir_id or props.get("tuya.ir_blaster.device_id", "d7c9483cd505ac54eauidb").strip()
        self.remote_id = remote_id or props.get("tuya.ir_blaster.remote_id", "d718f75c8f82c9145954hl").strip()
        self.power_hex_code = power_hex_code or props.get("tuya.ir_blaster.power_key_hex", "").strip()
        self.timeout = timeout

        self._token: Optional[str] = None
        self._token_expire_time: float = 0.0

    def _get_token(self) -> str:
        """Fetches or reuses cached access token from Tuya Cloud OpenAPI."""
        now = time.time()
        if self._token and now < self._token_expire_time:
            return self._token

        t_ms = str(int(now * 1000))
        http_method = "GET"
        url_path = "/v1.0/token?grant_type=1"

        content_sha256 = hashlib.sha256("".encode("utf-8")).hexdigest()
        string_to_sign = f"{http_method}\n{content_sha256}\n\n{url_path}"
        sign_str = self.access_id + t_ms + string_to_sign

        sign = hmac.new(
            self.access_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()

        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "t": t_ms,
            "sign_method": "HMAC-SHA256"
        }

        url = self.endpoint + url_path
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Tuya Cloud token acquisition failed: {data}")

        self._token = data["result"]["access_token"]
        expires_in = data["result"].get("expire_time", 7200)
        self._token_expire_time = now + (expires_in - 120)  # Refresh 2m before expiry
        return self._token

    def send_pulse(self, code_hex: Optional[str] = None) -> Tuple[bool, str]:
        """
        Dispatches the infrared pulse waveform to the physical Smart IR Blaster hardware.
        """
        code = code_hex or self.power_hex_code
        if not code:
            logger.error("[TUYA_CLOUD_IR_EMPTY] No IR hex code available.")
            return False, "EMPTY_CODE"

        try:
            token = self._get_token()
            t_ms = str(int(time.time() * 1000))
            http_method = "POST"
            url_path = f"/v1.0/infrareds/{self.ir_id}/remotes/{self.remote_id}/learning-codes"

            body_dict = {"code": code}
            body_str = json.dumps(body_dict, separators=(",", ":"))

            content_sha256 = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
            string_to_sign = f"{http_method}\n{content_sha256}\n\n{url_path}"
            sign_str = self.access_id + token + t_ms + string_to_sign

            sign = hmac.new(
                self.access_secret.encode("utf-8"),
                sign_str.encode("utf-8"),
                hashlib.sha256
            ).hexdigest().upper()

            headers = {
                "client_id": self.access_id,
                "access_token": token,
                "sign": sign,
                "t": t_ms,
                "sign_method": "HMAC-SHA256",
                "Content-Type": "application/json"
            }

            url = self.endpoint + url_path
            logger.info(f"[TUYA_CLOUD_IR_DISPATCH] Sending IR wake to {self.ir_id} (remote={self.remote_id})...")
            resp = requests.post(url, headers=headers, data=body_str, timeout=self.timeout)
            res_data = resp.json()

            if res_data.get("success"):
                logger.info("[TUYA_CLOUD_IR_SUCCESS] IR Power Pulse delivered to physical hardware.")
                return True, "CLOUD_IR_DISPATCH_SUCCESS"
            else:
                logger.error(f"[TUYA_CLOUD_IR_ERROR] API returned error: {res_data}")
                return False, f"CLOUD_IR_ERROR: {res_data.get('msg', 'UNKNOWN')}"

        except Exception as e:
            logger.error(f"[TUYA_CLOUD_IR_EXCEPTION] Failed dispatching IR pulse: {e}")
            return False, str(e)


# Global singleton instance for easy import
_global_transport: Optional[TuyaCloudIrTransport] = None


def get_tuya_cloud_ir_transport() -> TuyaCloudIrTransport:
    """Returns or initializes the global TuyaCloudIrTransport singleton."""
    global _global_transport
    if _global_transport is None:
        _global_transport = TuyaCloudIrTransport()
    return _global_transport
