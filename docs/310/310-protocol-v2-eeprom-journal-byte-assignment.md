# 310 protocol v2 EEPROM journal byte assignment — 2026-11-05

This note resolves the two-byte magic/version values left implicit in the 310-4 v0.5 section 8.2 journal layout. It is a design amendment for the protocol v2 firmware implementation.

## Exact slot layout

The 16-slot journal occupies EEPROM bytes 0–255. Each slot is 16 bytes:

| Offset | Width | Value |
|---|---:|---|
| 0 | 1 | magic 0x42 (ASCII B) |
| 1 | 1 | journal format version 0x01 |
| 2–9 | 8 | generation_counter64, little-endian |
| 10–12 | 3 | reserved, all zero |
| 13–14 | 2 | CRC-16/CCITT-FALSE over bytes 0–12, little-endian |
| 15 | 1 | commit marker: 0x00 invalid, 0xA5 committed |

A slot is valid only when marker, magic, version, reserved bytes and CRC all match exactly, and generation_counter64 is nonzero.

The separate provisioning record occupies bytes 256–259: 0x50, 0x52, 0x01, CRC-8/ATM over the first three bytes (poly 0x07, init 0x00, xorout 0x00).

## Boot behavior

- First provisioned boot is permitted only when the provisioning record validates and all 256 journal bytes are exactly 0xFF. It commits generation 1.
- Normal boot scans all slots, selects the unique highest valid generation, and commits generation+1 to the next ring slot.
- The current highest valid slot is never overwritten during the same commit.
- The target marker is invalidated and read back before payload writes. Bytes 0–14 are then written and verified. Marker 0xA5 is written and read back last.
- Invalid individual slots may be ignored only while at least one valid committed slot remains.
- Duplicate valid generation values, no valid slot outside the exact factory-empty predicate, write/readback failure, ambiguous state, or UINT64_MAX exhaustion produce BOOT_ID_INVALID/EXHAUSTED. No random fallback, auto-provisioning, or repair.
- The device must commit the new boot identity before HELLO, ARM, or output enable.

This is a design decision and host/native model only. It does not establish EEPROM electrical behavior, brownout protection, fuse settings, or physical power-loss qualification.