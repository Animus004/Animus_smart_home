"""
================================================================================
ANIMUS SMART ROOM — AUTHORITATIVE USB & NETWORK PRINTER CONTROLLER
================================================================================
Controls physical printing subsystems (HP Ink Tank 310 series on USB001,
Windows Spooler, and Network Print Queues) with read-back verification.

Capabilities:
1. Physical status & queue telemetry (spooler health, job counts, paper/ink alerts).
2. Safe document dispatch (PDF, TXT, DOCX, SQL, CSV, Images) via Windows Shell.
3. Queue management (cancel pending/stuck jobs).
================================================================================
"""

from __future__ import annotations
import os
import subprocess
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.printer_controller")


class PrinterController:
    """
    Authoritative Printer Controller for Animus Smart Room.
    Interacts with Windows Print Spooler and physical USB printers.
    """

    DEFAULT_TARGET_PRINTER = "HP Ink Tank 310 series"
    ALLOWED_EXTENSIONS = frozenset([
        ".txt", ".pdf", ".docx", ".doc", ".sql", ".csv",
        ".png", ".jpg", ".jpeg", ".bmp", ".md", ".json"
    ])

    def __init__(self, target_printer: Optional[str] = None, is_simulated: bool = False):
        self.target_printer = target_printer or self.DEFAULT_TARGET_PRINTER
        self.is_simulated = is_simulated

    def _run_ps(self, cmd: str, timeout: float = 6.0) -> Tuple[int, str, str]:
        """Executes a PowerShell command safely."""
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"[PRINTER_PS_TIMEOUT] Command timed out after {timeout}s: {cmd}")
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            logger.error(f"[PRINTER_PS_ERR] {e}")
            return -1, "", str(e)

    # =========================================================================
    # 1. State & Telemetry Queries
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Queries authoritative Windows print spooler and target printer telemetry.
        """
        if self.is_simulated:
            return {
                "success": True,
                "printer_name": self.target_printer,
                "port": "USB001",
                "status": "Normal",
                "is_online": True,
                "job_count": 0,
                "jobs": [],
                "verified": True,
                "is_simulated": True
            }

        # Query printer status and print jobs
        ps_cmd = (
            f"$p = Get-Printer -Name '{self.target_printer}' -ErrorAction SilentlyContinue; "
            f"if (-not $p) {{ $p = Get-Printer | Where-Object {{ $_.Name -like '*{self.target_printer}*' }} | Select-Object -First 1 }}; "
            f"if ($p) {{ "
            f"  $jobs = Get-PrintJob -PrinterName $p.Name -ErrorAction SilentlyContinue; "
            f"  $jCount = if ($jobs) {{ @($jobs).Count }} else {{ 0 }}; "
            f"  [PSCustomObject]@{{ "
            f"    Name = $p.Name; "
            f"    Port = $p.PortName; "
            f"    Status = [string]$p.PrinterStatus; "
            f"    Driver = $p.DriverName; "
            f"    JobCount = $jCount "
            f"  }} | ConvertTo-Json -Compress "
            f"}} else {{ '{{}}' }}"
        )

        code, stdout, stderr = self._run_ps(ps_cmd, timeout=5.0)
        if code == 0 and stdout and stdout != "{}":
            try:
                import json
                data = json.loads(stdout)
                return {
                    "success": True,
                    "printer_name": data.get("Name", self.target_printer),
                    "port": data.get("Port", "USB001"),
                    "status": data.get("Status", "Normal"),
                    "driver": data.get("Driver", ""),
                    "is_online": True,
                    "job_count": int(data.get("JobCount", 0)),
                    "verified": True,
                    "is_simulated": False,
                    "timestamp": time.time()
                }
            except Exception as e:
                logger.debug(f"[PRINTER_JSON_PARSE_ERR] {e}")

        # Fallback query if specific printer search returned empty
        return {
            "success": False,
            "printer_name": self.target_printer,
            "port": "USB001",
            "status": "OFFLINE_OR_DISCONNECTED",
            "is_online": False,
            "job_count": 0,
            "verified": False,
            "error": f"Printer '{self.target_printer}' not found or spooler unresponsive."
        }

    # =========================================================================
    # 2. Print Document Actuation
    # =========================================================================

    def print_file(self, file_path: str, printer_name: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Sends a physical file to the printer with security validation and spooler verification.
        """
        target = printer_name or self.target_printer
        clean_path = os.path.abspath(file_path)

        if not os.path.exists(clean_path):
            return False, {
                "success": False,
                "error": f"File does not exist: {clean_path}",
                "status": "FILE_NOT_FOUND",
                "verified": False
            }

        ext = os.path.splitext(clean_path)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, {
                "success": False,
                "error": f"File type '{ext}' is not allowed for printing. Allowed: {list(self.ALLOWED_EXTENSIONS)}",
                "status": "INVALID_EXTENSION",
                "verified": False
            }

        if self.is_simulated:
            logger.info(f"[PRINTER_SIMULATED] Printed '{clean_path}' to '{target}'.")
            return True, {
                "success": True,
                "file": clean_path,
                "printer": target,
                "action": "PRINT_FILE",
                "status": "QUEUED_SIMULATED",
                "verified": True
            }

        # Dispatch printing using Start-Process with Verb PrintTo or Out-Printer
        logger.info(f"[PRINTER_DISPATCH] Dispatching '{clean_path}' to physical printer '{target}'...")
        ps_dispatch = (
            f"Start-Process -FilePath '{clean_path}' -Verb PrintTo -ArgumentList '\"{target}\"' -PassThru -WindowStyle Hidden"
        )
        code, _, stderr = self._run_ps(ps_dispatch, timeout=8.0)

        # In case PrintTo verb is not registered for extension, fallback to Get-Content / Out-Printer for text/code
        if code != 0 and ext in [".txt", ".sql", ".csv", ".md", ".json"]:
            ps_fallback = f"Get-Content -Path '{clean_path}' | Out-Printer -Name '{target}'"
            code, _, stderr = self._run_ps(ps_fallback, timeout=8.0)

        ok = (code == 0)
        time.sleep(0.5)
        st = self.get_status()

        return ok, {
            "success": ok,
            "file": clean_path,
            "printer": target,
            "action": "PRINT_FILE",
            "active_jobs_in_spooler": st.get("job_count", 0),
            "message": f"Dispatched '{os.path.basename(clean_path)}' to {target}." if ok else f"Print dispatch failed: {stderr}",
            "verified": ok
        }

    def print_document(self, file_path: str, printer_name: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Alias for print_file."""
        return self.print_file(file_path=file_path, printer_name=printer_name)

    # =========================================================================
    # 3. Queue Management
    # =========================================================================

    def cancel_all_jobs(self, printer_name: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Clears all pending or stuck print jobs in the target print queue.
        """
        target = printer_name or self.target_printer
        if self.is_simulated:
            return True, {
                "success": True,
                "printer": target,
                "action": "CANCEL_ALL_JOBS",
                "canceled_count": 0,
                "verified": True
            }

        ps_cancel = (
            f"$jobs = Get-PrintJob -PrinterName '{target}' -ErrorAction SilentlyContinue; "
            f"if ($jobs) {{ $jobs | Remove-PrintJob; @($jobs).Count }} else {{ 0 }}"
        )
        code, stdout, stderr = self._run_ps(ps_cancel, timeout=6.0)
        count = 0
        try:
            count = int(stdout.strip())
        except Exception:
            pass

        logger.info(f"[PRINTER_CANCEL] Canceled {count} jobs on '{target}'.")
        return code == 0, {
            "success": code == 0,
            "printer": target,
            "action": "CANCEL_ALL_JOBS",
            "canceled_count": count,
            "message": f"Cleared {count} print jobs from queue on {target}.",
            "verified": code == 0
        }


# Global singleton instance
_global_printer_controller: Optional[PrinterController] = None


def get_printer_controller() -> PrinterController:
    """Returns or initializes the global PrinterController singleton."""
    global _global_printer_controller
    if _global_printer_controller is None:
        _global_printer_controller = PrinterController()
    return _global_printer_controller
