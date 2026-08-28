"""
================================================================================
ANIMUS SMART ROOM — LOCAL TUYA AC READ ADAPTER DIAGNOSTIC RUNNER
================================================================================
Executes a physical LAN read diagnostic against the room Air Conditioner
and explicitly prints the diagnostic status:
- LOCAL_READ_SUCCESS
- LOCAL_READ_FAILED
- DECODE_FAILED
================================================================================
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath("server/music_daemon"))

from tuya_local_read_adapter import (
    TuyaLocalAcReadAdapter,
    ReadDiagnosticStatus,
    load_tuya_local_config,
)


def run_diagnostic():
    print("=" * 80)
    print("      ANIMUS SMART ROOM — LOCAL TUYA AC READ DIAGNOSTIC")
    print("=" * 80)
    print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Mode      : PURE READ-ONLY / LOCAL LAN TRANSPORT")
    print("-" * 80)

    cfg = load_tuya_local_config()
    masked_dev = cfg["device_id"][:4] + "***" if cfg["device_id"] else "<NOT SET>"
    masked_key = "***" if cfg["local_key"] else "<NOT SET>"
    masked_ip = cfg["local_ip"]

    print(f"Target LAN IP    : {masked_ip}")
    print(f"Target LAN Port  : {cfg['local_port']}")
    print(f"Target Device ID : {masked_dev}")
    print(f"Local Key Status : {'CONFIGURED' if cfg['local_key'] else 'MISSING'}")
    print("-" * 80)

    adapter = TuyaLocalAcReadAdapter()

    # Perform Read
    print("Executing Local LAN Read Operation...")
    result = adapter.read_ac_state()

    print("\n" + "=" * 80)
    print(f"DIAGNOSTIC STATUS: {result.status.value}")
    print("=" * 80)

    if result.status == ReadDiagnosticStatus.LOCAL_READ_SUCCESS:
        st = result.state
        print(f"  [+] Latency              : {result.latency_ms:.2f} ms")
        print(f"  [+] Transport            : {result.transport}")
        print(f"  [+] Power State          : {'ON' if st.power else 'OFF'}")
        print(f"  [+] Target Temperature   : {st.target_temperature} °C")
        print(f"  [+] Current Ambient Temp : {st.current_temperature if st.current_temperature is not None else 'N/A'} °C")
        print(f"  [+] Operating Mode       : {st.mode}")
        print(f"  [+] Blower Fan Speed     : {st.fan_speed}")
        print(f"  [+] Raw DPS Map          : {st.raw_dps}")
    elif result.status == ReadDiagnosticStatus.LOCAL_READ_FAILED:
        print(f"  [-] Failure Reason       : {result.error}")
        print(f"  [-] Latency              : {result.latency_ms:.2f} ms")
    elif result.status == ReadDiagnosticStatus.DECODE_FAILED:
        print(f"  [-] Decode Error         : {result.error}")
        print(f"  [-] Latency              : {result.latency_ms:.2f} ms")

    print("-" * 80)
    return result.status


if __name__ == "__main__":
    status = run_diagnostic()
    sys.exit(0 if status == ReadDiagnosticStatus.LOCAL_READ_SUCCESS else 1)
