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
        ".png", ".jpg", ".jpeg", ".bmp", ".md", ".json",
        ".py", ".xlsx", ".pptx", ".html", ".log"
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

    def print_custom_file(
        self,
        file_path: str,
        copies: int = 1,
        orientation: str = "portrait",
        fit_to_page: bool = True,
        printer_name: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Sends a custom file to the HP Ink Tank printer with format-specific page fitting,
        orientation control, copy count, and spooler verification.
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
                "error": f"File type '{ext}' is not allowed for printing. Allowed: {sorted(list(self.ALLOWED_EXTENSIONS))}",
                "status": "INVALID_EXTENSION",
                "verified": False
            }

        copies = max(1, min(int(copies or 1), 10))
        is_landscape = (orientation.lower() == "landscape")

        if self.is_simulated:
            logger.info(f"[PRINTER_SIMULATED] Custom print '{clean_path}' to '{target}' (copies={copies}, orientation={orientation}).")
            return True, {
                "success": True,
                "file": clean_path,
                "printer": target,
                "copies": copies,
                "orientation": orientation,
                "action": "PRINT_CUSTOM_FILE",
                "status": "QUEUED_SIMULATED",
                "verified": True
            }

        logger.info(f"[PRINTER_CUSTOM_DISPATCH] Dispatching '{clean_path}' (type={ext}, copies={copies}, orient={orientation}) to '{target}'...")
        code = -1
        stderr = ""

        # 1. Images (PNG, JPG, JPEG, BMP): Auto-fit to A4 Margin Bounds without clipping
        if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
            escaped_path = clean_path.replace("'", "''")
            escaped_target = target.replace("'", "''")
            ps_img = (
                f"Add-Type -AssemblyName System.Drawing; "
                f"$doc = New-Object System.Drawing.Printing.PrintDocument; "
                f"$doc.PrinterSettings.PrinterName = '{escaped_target}'; "
                f"$doc.PrinterSettings.Copies = {copies}; "
                f"$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}; "
                f"$img = [System.Drawing.Image]::FromFile('{escaped_path}'); "
                f"$doc.add_PrintPage({{ "
                f"  param($sender, $ev) "
                f"  $bounds = $ev.MarginBounds; "
                f"  $ratio = [Math]::Min($bounds.Width / $img.Width, $bounds.Height / $img.Height); "
                f"  $w = [int]($img.Width * $ratio); "
                f"  $h = [int]($img.Height * $ratio); "
                f"  $x = $bounds.X + [int](($bounds.Width - $w) / 2); "
                f"  $y = $bounds.Y + [int](($bounds.Height - $h) / 2); "
                f"  $ev.Graphics.DrawImage($img, $x, $y, $w, $h); "
                f"  $ev.HasMorePages = $false; "
                f"}}); "
                f"$doc.Print(); "
                f"$img.Dispose(); "
                f"$doc.Dispose();"
            )
            code, _, stderr = self._run_ps(ps_img, timeout=12.0)

        # 2. Text, Markdown, and Code (.txt, .md, .sql, .py, .json, .csv, .log): Clean monospace with header & pagination
        elif ext in [".txt", ".md", ".sql", ".py", ".json", ".csv", ".log"]:
            escaped_path = clean_path.replace("'", "''")
            escaped_target = target.replace("'", "''")
            base_name = os.path.basename(clean_path).replace("'", "''")
            ps_text = (
                f"Add-Type -AssemblyName System.Drawing; "
                f"$doc = New-Object System.Drawing.Printing.PrintDocument; "
                f"$doc.PrinterSettings.PrinterName = '{escaped_target}'; "
                f"$doc.PrinterSettings.Copies = {copies}; "
                f"$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}; "
                f"$font = New-Object System.Drawing.Font('Consolas', 10); "
                f"$hdrFont = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold); "
                f"$brush = [System.Drawing.Brushes]::Black; "
                f"$lines = Get-Content -Path '{escaped_path}' -Encoding UTF8; "
                f"$script:lIdx = 0; "
                f"$script:pg = 1; "
                f"$doc.add_PrintPage({{ "
                f"  param($sender, $ev) "
                f"  $m = $ev.MarginBounds; "
                f"  $y = $m.Top; "
                f"  $hdr = 'Animus Smart Room  |  {base_name}  |  Page ' + $script:pg; "
                f"  $ev.Graphics.DrawString($hdr, $hdrFont, $brush, $m.Left, $y); "
                f"  $y += 22; "
                f"  $ev.Graphics.DrawLine([System.Drawing.Pens]::LightGray, $m.Left, $y, $m.Right, $y); "
                f"  $y += 10; "
                f"  $lineH = $font.GetHeight($ev.Graphics); "
                f"  while ($script:lIdx -lt $lines.Count -and ($y + $lineH) -lt $m.Bottom) {{ "
                f"    $ev.Graphics.DrawString($lines[$script:lIdx], $font, $brush, $m.Left, $y); "
                f"    $y += $lineH; "
                f"    $script:lIdx++; "
                f"  }}; "
                f"  $script:pg++; "
                f"  $ev.HasMorePages = ($script:lIdx -lt $lines.Count); "
                f"}}); "
                f"$doc.Print(); "
                f"$font.Dispose(); "
                f"$hdrFont.Dispose(); "
                f"$doc.Dispose();"
            )
            code, _, stderr = self._run_ps(ps_text, timeout=15.0)

        # 3. PDF and Office (.pdf, .docx, .doc, .xlsx, .pptx, .html)
        if code != 0:
            # Fallback to Windows Shell PrintTo verb
            escaped_path = clean_path.replace("'", "''")
            escaped_target = target.replace("'", "''")
            ps_shell = (
                f"Start-Process -FilePath '{escaped_path}' -Verb PrintTo -ArgumentList '\"{escaped_target}\"' -PassThru -WindowStyle Hidden"
            )
            code, _, stderr = self._run_ps(ps_shell, timeout=10.0)

        # 4. Ultimate fallback for text/code if Shell PrintTo was unavailable
        if code != 0 and ext in [".txt", ".sql", ".csv", ".md", ".json", ".py", ".log"]:
            ps_fallback = f"Get-Content -Path '{clean_path}' | Out-Printer -Name '{target}'"
            code, _, stderr = self._run_ps(ps_fallback, timeout=8.0)

        ok = (code == 0)
        time.sleep(0.5)
        st = self.get_status()

        return ok, {
            "success": ok,
            "file": clean_path,
            "file_name": os.path.basename(clean_path),
            "printer": target,
            "copies": copies,
            "orientation": orientation,
            "action": "PRINT_CUSTOM_FILE",
            "active_jobs_in_spooler": st.get("job_count", 0),
            "message": f"Successfully dispatched '{os.path.basename(clean_path)}' ({copies} cop{'y' if copies==1 else 'ies'}, {orientation}) to {target}." if ok else f"Print dispatch failed: {stderr}",
            "verified": ok
        }

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
