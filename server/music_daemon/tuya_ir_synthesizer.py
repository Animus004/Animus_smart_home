"""
================================================================================
ANIMUS SMART ROOM — EXTENDED TUYA IR SYNTHESIZER & PROJECTOR SCANNER
================================================================================
Generates FastLZ-compressed 38kHz NEC and Extended NEC infrared carrier pulses
covering all major OEM Android Smart Projector platforms (MStar, Amlogic,
Allwinner, Rockchip, Zebronics PixaPlay series).
================================================================================
"""

import struct
import base64
from typing import List, Tuple


def fastlz_compress_level1(data: bytes) -> bytes:
    """Compresses binary pulse data using FastLZ Level 1."""
    out = bytearray()
    ip = 0
    length = len(data)
    while ip < length:
        chunk_len = min(32, length - ip)
        out.append(chunk_len - 1)
        out.extend(data[ip : ip + chunk_len])
        ip += chunk_len
    return bytes(out)


def timings_to_tuya_base64(durations_us: List[int]) -> str:
    """Packs durations into Little-Endian uint16, compresses with FastLZ, and encodes Base64."""
    packed = bytearray()
    for d in durations_us:
        val = max(1, min(65535, int(d)))
        packed.extend(struct.pack("<H", val))
    compressed = fastlz_compress_level1(bytes(packed))
    return base64.b64encode(compressed).decode("ascii")


def generate_nec_frame(addr_low: int, addr_high: int, cmd: int, is_extended: bool = False) -> List[int]:
    """Generates 38kHz NEC frame with 9000µs leader, 32-bit payload, and 560µs stop."""
    timings = [9000, 4500]
    
    if is_extended:
        payload = [addr_low & 0xFF, addr_high & 0xFF, cmd & 0xFF, (~cmd) & 0xFF]
    else:
        payload = [addr_low & 0xFF, (~addr_low) & 0xFF, cmd & 0xFF, (~cmd) & 0xFF]

    for b in payload:
        for bit_idx in range(8):
            bit = (b >> bit_idx) & 1
            timings.append(560)
            timings.append(1690 if bit == 1 else 560)

    timings.append(560)
    timings.append(40000)
    return timings


def generate_all_projector_candidates() -> List[Tuple[str, str]]:
    """Generates comprehensive list of OEM projector power codes."""
    candidates = []

    # Common OEM Profiles for Zebronics PixaPlay / Chinese Android Smart Projectors
    profiles = [
        # (Label, addr_low, addr_high, cmd, is_extended)
        ("PixaPlay 25 / MStar Std Power (0x00/0x12)", 0x00, 0xFF, 0x12, False),
        ("PixaPlay 22 / Amlogic Power (0x00/0x14)", 0x00, 0xFF, 0x14, False),
        ("PixaPlay 18 / Std Android (0x00/0x40)", 0x00, 0xFF, 0x40, False),
        ("PixaPlay 15 / Power 0x45 (0x00/0x45)", 0x00, 0xFF, 0x45, False),
        ("PixaPlay 11 / Power 0x0C (0x00/0x0C)", 0x00, 0xFF, 0x0C, False),
        ("Zebronics Extended 0x00BF (0x12)", 0x00, 0xBF, 0x12, True),
        ("Zebronics Extended 0x00BF (0x45)", 0x00, 0xBF, 0x45, True),
        ("Zebronics Extended 0x00BF (0x40)", 0x00, 0xBF, 0x40, True),
        ("Zebronics Extended 0x01FE (0x12)", 0x01, 0xFE, 0x12, True),
        ("Zebronics Extended 0x01FE (0x45)", 0x01, 0xFE, 0x45, True),
        ("Zebronics Extended 0x01FE (0x14)", 0x01, 0xFE, 0x14, True),
        ("Zebronics Extended 0x807F (0x12)", 0x80, 0x7F, 0x12, True),
        ("Zebronics Extended 0x807F (0x45)", 0x80, 0x7F, 0x45, True),
        ("Zebronics Extended 0x807F (0x14)", 0x80, 0x7F, 0x14, True),
        ("Zebronics Extended 0x807F (0x0C)", 0x80, 0x7F, 0x0C, True),
        ("Zebronics Extended 0x20DF (0x12)", 0x20, 0xDF, 0x12, True),
        ("Zebronics Extended 0x20DF (0x40)", 0x20, 0xDF, 0x40, True),
        ("Zebronics Extended 0x40BF (0x12)", 0x40, 0xBF, 0x12, True),
        ("Zebronics Extended 0x40BF (0x45)", 0x40, 0xBF, 0x45, True),
        ("Zebronics Custom 0x02 (0x12)", 0x02, 0xFD, 0x12, False),
        ("Zebronics Custom 0x04 (0x12)", 0x04, 0xFB, 0x12, False),
        ("Zebronics Custom 0x08 (0x12)", 0x08, 0xF7, 0x12, False),
        ("Zebronics Custom 0x10 (0x12)", 0x10, 0xEF, 0x12, False),
    ]

    for label, al, ah, cmd, ext in profiles:
        t = generate_nec_frame(al, ah, cmd, ext)
        b64 = timings_to_tuya_base64(t)
        candidates.append((label, b64))

    return candidates


# Backward compatibility alias
generate_zebronics_projector_power_codes = generate_all_projector_candidates


if __name__ == "__main__":
    c = generate_all_projector_candidates()
    print(f"Generated {len(c)} candidates.")
