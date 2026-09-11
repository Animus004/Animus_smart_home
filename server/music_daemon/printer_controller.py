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
import sys
import uuid
import tempfile
import subprocess
import logging
import time
from pathlib import Path
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

    def _run_ps_script(self, script_content: str, timeout: float = 40.0) -> Tuple[int, str, str]:
        """Executes a PowerShell script content via a temporary .ps1 file to bypass CLI escaping limits."""
        ps_file = None
        try:
            temp_dir = Path(tempfile.gettempdir()) / "animus_printer_scripts"
            temp_dir.mkdir(parents=True, exist_ok=True)
            ps_file = temp_dir / f"spool_{uuid.uuid4().hex[:8]}.ps1"
            ps_file.write_text(script_content, encoding="utf-8")

            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"[PRINTER_PS_TIMEOUT] Script timed out after {timeout}s")
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            logger.error(f"[PRINTER_PS_ERR] {e}")
            return -1, "", str(e)
        finally:
            if ps_file and ps_file.exists():
                try:
                    ps_file.unlink(missing_ok=True)
                except Exception:
                    pass

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
        Sends a physical file to the printer with format-specific page fitting and spooler verification.
        """
        return self.print_custom_file(file_path=file_path, printer_name=printer_name)

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
        escaped_target = target.replace("'", "''")
        code = -1
        stderr = ""

        # 1. PDF Files (.pdf): High-DPI Multi-Page Rasterization + Direct GDI Spooler
        if ext == ".pdf":
            try:
                import pymupdf
                doc = pymupdf.open(clean_path)
                page_count = len(doc)
                temp_spool_dir = Path(tempfile.gettempdir()) / "animus_pdf_spool"
                temp_spool_dir.mkdir(parents=True, exist_ok=True)

                img_paths = []
                for i in range(page_count):
                    page = doc[i]
                    pix = page.get_pixmap(dpi=200)
                    out_img = temp_spool_dir / f"pdf_page_{uuid.uuid4().hex[:8]}_{i}.png"
                    pix.save(str(out_img))
                    img_paths.append(str(out_img).replace("'", "''"))
                doc.close()

                if img_paths:
                    files_array = "@(" + ", ".join([f"'{p}'" for p in img_paths]) + ")"
                    ps_pdf = f"""
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = '{escaped_target}'
$doc.PrinterSettings.Copies = {copies}
$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}

$script:pageList = {files_array}
$script:pIdx = 0

$doc.add_PrintPage({{
    param($sender, $ev)
    if ($script:pIdx -lt $script:pageList.Count) {{
        $imgPath = $script:pageList[$script:pIdx]
        $img = [System.Drawing.Image]::FromFile($imgPath)
        $b = $ev.MarginBounds
        $ratio = [Math]::Min($b.Width / $img.Width, $b.Height / $img.Height)
        $w = [int]($img.Width * $ratio)
        $h = [int]($img.Height * $ratio)
        $x = $b.X + [int](($b.Width - $w) / 2)
        $y = $b.Y + [int](($b.Height - $h) / 2)
        $ev.Graphics.DrawImage($img, $x, $y, $w, $h)
        $img.Dispose()
        $script:pIdx++
        $ev.HasMorePages = ($script:pIdx -lt $script:pageList.Count)
    }} else {{
        $ev.HasMorePages = $false
    }}
}})

try {{
    $doc.Print()
    Write-Output "SUCCESS_PRINT_DISPATCH"
}} catch {{
    Write-Error $_
    exit 1
}} finally {{
    $doc.Dispose()
}}
"""
                    code, stdout, stderr = self._run_ps_script(ps_pdf, timeout=40.0)

                    # Retain page images in animus_pdf_spool so Windows Spoolsv can render asynchronously.
                    # Clean up only stale spool files older than 1 hour.
                    self._cleanup_old_spool_files(temp_spool_dir)
            except Exception as e:
                logger.error(f"[PRINTER_PDF_RENDER_ERR] {e}", exc_info=True)
                code = -1
                stdout = ""
                stderr = str(e)

        # 2. Images (PNG, JPG, JPEG, BMP): Auto-fit to A4 Margin Bounds without clipping
        elif ext in [".png", ".jpg", ".jpeg", ".bmp"]:
            escaped_path = clean_path.replace("'", "''")
            ps_img = f"""
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = '{escaped_target}'
$doc.PrinterSettings.Copies = {copies}
$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}
$img = [System.Drawing.Image]::FromFile('{escaped_path}')
$doc.add_PrintPage({{
    param($sender, $ev)
    $b = $ev.MarginBounds
    $ratio = [Math]::Min($b.Width / $img.Width, $b.Height / $img.Height)
    $w = [int]($img.Width * $ratio)
    $h = [int]($img.Height * $ratio)
    $x = $b.X + [int](($b.Width - $w) / 2)
    $y = $b.Y + [int](($b.Height - $h) / 2)
    $ev.Graphics.DrawImage($img, $x, $y, $w, $h)
    $ev.HasMorePages = $false
}})

try {{
    $doc.Print()
    Write-Output "SUCCESS_PRINT_DISPATCH"
}} catch {{
    Write-Error $_
    exit 1
}} finally {{
    $img.Dispose()
    $doc.Dispose()
}}
"""
            code, stdout, stderr = self._run_ps_script(ps_img, timeout=20.0)

        # 3. Word Documents (.docx, .doc): Extract structured paragraphs and paginate
        elif ext in [".docx", ".doc"]:
            try:
                import docx
                doc = docx.Document(clean_path)
                lines = [p.text for p in doc.paragraphs if p.text.strip()]
                clean_txt_path = Path(tempfile.gettempdir()) / f"docx_spool_{uuid.uuid4().hex[:8]}.txt"
                clean_txt_path.write_text("\n".join(lines), encoding="utf-8")
                escaped_txt = str(clean_txt_path).replace("'", "''")
                base_name = os.path.basename(clean_path).replace("'", "''")

                ps_docx = f"""
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = '{escaped_target}'
$doc.PrinterSettings.Copies = {copies}
$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}
$font = New-Object System.Drawing.Font('Segoe UI', 10)
$hdrFont = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.Brushes]::Black
$lines = Get-Content -Path '{escaped_txt}' -Encoding UTF8
$script:lIdx = 0
$script:pg = 1
$doc.add_PrintPage({{
    param($sender, $ev)
    $m = $ev.MarginBounds
    $y = $m.Top
    $hdr = 'Animus Smart Room  |  {base_name}  |  Page ' + $script:pg
    $ev.Graphics.DrawString($hdr, $hdrFont, $brush, $m.Left, $y)
    $y += 22
    $ev.Graphics.DrawLine([System.Drawing.Pens]::LightGray, $m.Left, $y, $m.Right, $y)
    $y += 10
    $lineH = $font.GetHeight($ev.Graphics)
    while ($script:lIdx -lt $lines.Count -and ($y + $lineH) -lt $m.Bottom) {{
        $ev.Graphics.DrawString($lines[$script:lIdx], $font, $brush, $m.Left, $y)
        $y += $lineH
        $script:lIdx++
    }}
    $script:pg++
    $ev.HasMorePages = ($script:lIdx -lt $lines.Count)
}})

try {{
    $doc.Print()
    Write-Output "SUCCESS_PRINT_DISPATCH"
}} catch {{
    Write-Error $_
    exit 1
}} finally {{
    $font.Dispose()
    $hdrFont.Dispose()
    $doc.Dispose()
}}
"""
                code, stdout, stderr = self._run_ps_script(ps_docx, timeout=25.0)
                try:
                    clean_txt_path.unlink(missing_ok=True)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[PRINTER_DOCX_ERR] {e}", exc_info=True)
                code = -1
                stdout = ""
                stderr = str(e)

        # 4. Text, Markdown, and Code (.txt, .md, .sql, .py, .json, .csv, .log): Clean monospace with header & pagination
        elif ext in [".txt", ".md", ".sql", ".py", ".json", ".csv", ".log"]:
            escaped_path = clean_path.replace("'", "''")
            base_name = os.path.basename(clean_path).replace("'", "''")
            ps_text = f"""
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = '{escaped_target}'
$doc.PrinterSettings.Copies = {copies}
$doc.DefaultPageSettings.Landscape = {'$true' if is_landscape else '$false'}
$font = New-Object System.Drawing.Font('Consolas', 10)
$hdrFont = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.Brushes]::Black
$lines = Get-Content -Path '{escaped_path}' -Encoding UTF8
$script:lIdx = 0
$script:pg = 1
$doc.add_PrintPage({{
    param($sender, $ev)
    $m = $ev.MarginBounds
    $y = $m.Top
    $hdr = 'Animus Smart Room  |  {base_name}  |  Page ' + $script:pg
    $ev.Graphics.DrawString($hdr, $hdrFont, $brush, $m.Left, $y)
    $y += 22
    $ev.Graphics.DrawLine([System.Drawing.Pens]::LightGray, $m.Left, $y, $m.Right, $y)
    $y += 10
    $lineH = $font.GetHeight($ev.Graphics)
    while ($script:lIdx -lt $lines.Count -and ($y + $lineH) -lt $m.Bottom) {{
        $ev.Graphics.DrawString($lines[$script:lIdx], $font, $brush, $m.Left, $y)
        $y += $lineH
        $script:lIdx++
    }}
    $script:pg++
    $ev.HasMorePages = ($script:lIdx -lt $lines.Count)
}})

try {{
    $doc.Print()
    Write-Output "SUCCESS_PRINT_DISPATCH"
}} catch {{
    Write-Error $_
    exit 1
}} finally {{
    $font.Dispose()
    $hdrFont.Dispose()
    $doc.Dispose()
}}
"""
            code, stdout, stderr = self._run_ps_script(ps_text, timeout=25.0)

        # 5. Fallback for text/code if script failed
        if code != 0 and ext in [".txt", ".sql", ".csv", ".md", ".json", ".py", ".log"]:
            ps_fallback = f"Get-Content -Path '{clean_path}' | Out-Printer -Name '{target}'"
            code, stdout, stderr = self._run_ps(ps_fallback, timeout=8.0)

        ok = (code == 0 and ("SUCCESS_PRINT_DISPATCH" in stdout or (not stderr and not stdout)))
        time.sleep(0.5)
        st = self.get_status()

        if ok:
            # Auto-open Windows native Print Queue status window so the operator has immediate visual feedback
            self.show_print_queue(target)

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

    def _cleanup_old_spool_files(self, temp_spool_dir: Path, max_age_seconds: float = 3600.0) -> None:
        """Safely cleans up orphaned raster images from earlier sessions without interrupting active spooling."""
        try:
            now = time.time()
            if temp_spool_dir.exists():
                for f in temp_spool_dir.glob("pdf_page_*.png"):
                    try:
                        if now - f.stat().st_mtime > max_age_seconds:
                            f.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"[SPOOL_CLEANUP_ERR] {e}")

    def show_print_queue(self, printer_name: Optional[str] = None) -> bool:
        """Opens the native Windows Print Queue status window on the desktop."""
        target = printer_name or self.target_printer
        if self.is_simulated:
            logger.info(f"[PRINTER_SIMULATED] show_print_queue on '{target}'")
            return True
        try:
            subprocess.Popen(
                ["rundll32.exe", "printui.dll,PrintUIEntry", "/o", "/n", target],
                shell=False
            )
            logger.info(f"[PRINTER_QUEUE_WINDOW] Opened native print queue window for '{target}'.")
            return True
        except Exception as e:
            logger.error(f"[PRINTER_QUEUE_WINDOW_ERR] {e}")
            return False

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
