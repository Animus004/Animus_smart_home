# ANIMUS SMART ROOM — HARDWARE BASELINE FREEZE
**Document Status:** FROZEN & IMMUTABLE  
**Acceptance Status:** `GREEN — READY FOR BRAIN`  
**Validation Date:** 2026-08-23  

---

## 1. Frozen Hardware Inventory & Topology

| Device Target | Model / Hardware Platform | Serial / Network Target | Protocol / Transport | Required Capabilities & Identifiers |
| :--- | :--- | :--- | :--- | :--- |
| **Projector** | Zebronics PixaPlay 25 (`HiDPTAndroid Hi3751V350`) | `192.168.1.11:5555` | Android 12 ADB over Wi-Fi | `HDMI 1` source (`com.newlink.nlsource`), OEM shutdown (`com.zhiying.powerservice/.PowerActivity`) |
| **Streaming Stick** | Amazon Fire TV Stick Lite / 3rd Gen (`AFTSS` / `sheldon`) | `192.168.1.5:5555` | Fire OS 7 (Android 9) ADB | YouTube (`com.amazon.firetv.youtube`), Hotstar (`in.startv.hotstar`), A2DP sink tracking |
| **Soundbar System** | LG SNC4R Wireless Soundbar + Rear Speakers | Bluetooth MAC: `54:15:89:DC:A5:79` | Windows WASAPI & Fire OS A2DP | Endpoint: `wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}`, Fallback `2270W` excluded |
| **Air Conditioner** | Tuya Inverter Split AC (`category: kt`) | Device ID: `76776532a4e57c0a2ca4` | Tuya 3.3 TCP (6668) & Cloud | Product ID: `XT0UJtiNvEocE9Mu`, Local IP: `192.168.1.4`, Local Key verified, 16 recovery unit tests |
| **Mobile Controller** | Motorola edge 40 | `192.168.1.13:34563` | Android Wireless Debugging | Room controller Android client |
| **Audio Daemon** | Animus FastAPI Python Daemon | `127.0.0.1:8095` | HTTP / Named Pipe IPC | Headless `mpv.com`, YouTube Music OAuth resolver, Named pipe `\\.\pipe\mpv-animus` |

---

## 2. Core Architectural & Hardware Invariants

1. **Rule of Hardware Truth:**
   $$\mathbf{COMMAND\ ACCEPTED\ \ne\ HARDWARE\ ACTION\ CONFIRMED}$$
   $$\mathbf{API\ SUCCESS\ \ne\ PHYSICAL\ SUCCESS}$$
   Telemetry and state must always reflect physical observation (e.g. ActivityManager tokens, PowerManager wakefulness, raw Bluetooth manager dumpsys, WASAPI endpoint bindings).
2. **Audio Routing Arbitration Matrix:**
   - **PC Music Mode**: PC $\rightarrow$ Windows WASAPI $\rightarrow$ `Speakers (LG SNC4R(79))`. Monitor speakers (`2270W (NVIDIA High Definition Audio)`) are **strictly excluded**.
   - **Movie Mode**: Fire TV Stick (`192.168.1.5:5555`) $\rightarrow$ Bluetooth A2DP (`54:15:89:DC:A5:79`) $\rightarrow$ LG SNC4R Soundbar. PC audio is halted and released.
3. **Power State Truthfulness (Uncollapsed State Vector):**
   $$\mathbf{State\ Vector} = \big[\text{Fire TV Power} \times \text{HDMI Signal} \times \text{Projector Power} \times \text{HDMI Source} \times \text{BT Audio} \times \text{WASAPI Endpoint}\big]$$
   - $\text{Fire TV OFF} \ne \text{Projector OFF}$
   - $\text{Projector ON} \ne \text{HDMI Signal Available}$
   - $\text{HDMI Signal Available} \ne \text{LG Audio Connected}$
   - $\text{Fire TV AWAKE} \ne \text{Movie Mode HEALTHY}$
4. **Projector Optical Power Rail Architecture:**
   The PixaPlay 25 optical LED engine power rail is hardware-coupled to the main SoC. Android software display sleep (`KEYCODE_SLEEP`) is disabled by OEM firmware. Safe shutdown must always invoke `com.zhiying.powerservice/.PowerActivity` for proper cooling sequence.
5. **AC Wi-Fi Recovery Guarantee:**
   Post-outage Wi-Fi recovery is managed by `AcRecoveryController.kt` via Tuya UDP 6666/6667 local broadcast probing without unbinding, deleting device, or resetting credentials.

---

## 3. Physical Acceptance & Regression Record

- **Part 1/5 (Projector Physical Acceptance)**: 8/8 Phases Passed (`PASS`).
- **Part 2/5 (Fire TV Physical Acceptance)**: 10/10 Phases Passed (`PASS`).
- **Part 3/5 (LG SNC4R Soundbar Acceptance)**: 8/8 Phases Passed (`PASS`).
- **Part 4/5 (Cross-Device Synchronization & CEC)**: 8/8 Phases Passed (`PASS`).
- **PixaPlay 25 Display-OFF Investigation**: Completed (`Option C: Hardware-coupled`).
- **Part 5/5 (Master Whole-System Torture Test)**: 20/20 Gates Passed (`GREEN — READY FOR BRAIN`).
- **Automated Regression Suite**:
  - Python Pytest Suite: `55/55 passed` (100% green).
  - Kotlin/Android Gradle Suite: `:core:test :app:testDebugUnitTest` (`BUILD SUCCESSFUL`).
