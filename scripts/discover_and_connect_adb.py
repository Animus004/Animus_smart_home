"""
Animus Dynamic Hardware Auto-Discovery & ADB Connector.
Discovers Fire TV, Projector, and AC by their permanent hardware MAC addresses,
updates local.properties dynamically, and connects ADB targets automatically.
Runs in < 1 second. Zero manual intervention required across router reboots.
"""

import subprocess
import re
import socket
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT_DIR = Path(__file__).parent.parent
LOCAL_PROPS = ROOT_DIR / "local.properties"

# Permanent Hardware MACs
TARGET_MACS = {
    "firetv": "6c-99-9d-3e-5f-c1",
    "projector": "a8-4f-a4-26-cd-6b",
    "ac": "a4-e5-7c-0a-2c-a4"
}

def get_arp_table():
    """Parses Windows ARP cache into {mac: ip}."""
    table = {}
    try:
        out = subprocess.check_output("arp -a", shell=True, text=True)
        for line in out.splitlines():
            line = line.strip()
            m = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})', line)
            if m:
                ip = m.group(1)
                mac = m.group(2).lower().replace(":", "-")
                table[mac] = ip
    except Exception as e:
        print(f"[WARN] Failed to read ARP: {e}")
    return table

def test_port(ip, port=5555, timeout=0.25):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        res = s.connect_ex((ip, port))
        s.close()
        return res == 0
    except:
        return False

def fast_subnet_ping(prefix="192.168.1"):
    """Quick parallel ping sweep to refresh ARP cache if devices were dormant."""
    def _ping(i):
        ip = f"{prefix}.{i}"
        subprocess.run(f"ping -n 1 -w 150 {ip}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with ThreadPoolExecutor(max_workers=30) as ex:
        ex.map(_ping, range(2, 25))

def read_local_properties():
    props = {}
    if LOCAL_PROPS.exists():
        for line in LOCAL_PROPS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()
    return props

def update_property(key, val):
    if not LOCAL_PROPS.exists():
        return
    lines = LOCAL_PROPS.read_text(encoding="utf-8").splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={val}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={val}")
    LOCAL_PROPS.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

def main():
    print("=" * 60)
    print("   Animus Hardware Auto-Discovery & Dynamic Network Sync   ")
    print("=" * 60)

    props = read_local_properties()
    arp = get_arp_table()

    # Check if any MAC is missing from ARP; if so, do a fast ping sweep
    missing = [name for name, mac in TARGET_MACS.items() if mac not in arp]
    if missing:
        print(f"[*] Probing subnet for dormant devices: {', '.join(missing)}...")
        fast_subnet_ping()
        arp = get_arp_table()

    # 1. Fire TV
    ftv_mac = TARGET_MACS["firetv"]
    ftv_ip = arp.get(ftv_mac)
    if ftv_ip:
        print(f"[+] Found Fire TV ({ftv_mac}) at {ftv_ip}")
        old_target = props.get("firetv.adb.target", "")
        new_target = f"{ftv_ip}:5555"
        if old_target != new_target:
            print(f"    [SYNC] Updating firetv.adb.target: {old_target} -> {new_target}")
            update_property("firetv.adb.target", new_target)
        # Connect ADB
        print(f"    [ADB] Connecting to {new_target}...")
        subprocess.run(f"adb connect {new_target}", shell=True)
    else:
        cached = props.get("firetv.adb.target", "192.168.1.6:5555")
        print(f"[-] Fire TV MAC not in ARP, falling back to cached: {cached}")
        subprocess.run(f"adb connect {cached}", shell=True)

    # 2. Projector
    proj_mac = TARGET_MACS["projector"]
    proj_ip = arp.get(proj_mac)
    if proj_ip:
        print(f"[+] Found Projector ({proj_mac}) at {proj_ip}")
        old_target = props.get("projector.adb.target", "")
        new_target = f"{proj_ip}:5555"
        if old_target != new_target:
            print(f"    [SYNC] Updating projector.adb.target: {old_target} -> {new_target}")
            update_property("projector.adb.target", new_target)
        # Connect ADB
        print(f"    [ADB] Connecting to {new_target}...")
        subprocess.run(f"adb connect {new_target}", shell=True)
    else:
        cached = props.get("projector.adb.target", "192.168.1.13:5555")
        print(f"[-] Projector MAC not in ARP, falling back to cached: {cached}")
        subprocess.run(f"adb connect {cached}", shell=True)

    # 3. AC
    ac_mac = TARGET_MACS["ac"]
    ac_ip = arp.get(ac_mac)
    if ac_ip:
        print(f"[+] Found Physical AC ({ac_mac}) at {ac_ip}")
        old_ip = props.get("tuya.local.ip", "")
        if old_ip != ac_ip:
            print(f"    [SYNC] Updating tuya.local.ip: {old_ip} -> {ac_ip}")
            update_property("tuya.local.ip", ac_ip)

    print("\n[READY] Network hardware synchronization complete.\n")

if __name__ == "__main__":
    main()
