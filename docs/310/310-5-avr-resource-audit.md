# 310-5 AVR resource audit — command-only v2 image

Date: 2026-11-05

## Scope and build identity

This audit applies only to the currently linked command-only image of:

- Sketch: `firmware/motor/MotoreRevV2/MotoreRevV2.ino`
- Target: Arduino Uno / ATmega328P, `arduino:avr:uno`
- Arduino AVR core: 1.8.8
- Build commit: `66c57f9d6f482f9aaabad2152e84c1d1b84831f3`
- Arduino Uno Firmware Compile workflow #164 / run ID `42027088535`
- Artifact ID `13413524110` (expires 2026-11-19)

The build uses non-LTO `-fstack-usage` analysis flags. The ELF, linker map, disassembly, size report, and full/top-30 GCC stack reports are retained in the workflow artifact.

## Static SRAM

`avr-size` reports:

| Section | Bytes |
|---|---:|
| .data | 146 |
| .bss | 746 |
| .data + .bss | **892** |
| Static limit | 900 |
| Remaining below static limit | **8** |
| Physical SRAM | 2048 |
| Remaining after static allocation | 1156 |

This passes the 900-byte static allocation cap for the linked command-only image. The ADC capture primitive in the source is not referenced by `loop()` and is removed from this linked image; therefore this 892-byte result does not qualify an ADC-enabled build.

## Stack frame inventory

GCC emitted 228 non-empty `.su` records. Largest relevant frames:

| Function | Frame bytes |
|---|---:|
| `loop()` | 168 |
| `ProtocolV2Device::cached_or_error()` | 74 |
| `ProtocolV2Device::find_cached()` | 19 |
| `ProtocolV2Device::error_reply()` | 7 |
| `ProtocolV2Device::blank_reply()` | 4 |
| `setup()` | 41 |
| `BootIdentityJournal::scan()` | 41 |
| `BootIdentityJournal::read_valid_slot()` | 33 |
| `BootIdentityJournal::write_slot()` | 32 |
| UART TX-empty ISR `__vector_19` | 17 |
| Maximum ISR frame in this image | 17 |

## Conservative nested-stack bound

The retained AVR disassembly confirms the deepest command-processing chain in the linked image:

`main -> loop -> ProtocolV2Device::cached_or_error -> ProtocolV2Device::find_cached`

The corresponding GCC frames are 2 + 168 + 74 + 19 bytes. Add three two-byte call return addresses (main→loop, loop→cached_or_error, cached_or_error→find_cached). The largest active UART interrupt is TX-empty `__vector_19`: its frame is 17 bytes, it calls `HardwareSerial::_tx_udr_empty_irq()` (2-byte frame) with a two-byte call return address, and ATmega328P interrupt entry pushes a two-byte PC:

`2 + 168 + 74 + 19 + 6 + 17 + 2 + 2 + 2 = 292 bytes`

UART RX `__vector_18` is 10 bytes and does not call another function. The Timer0 overflow ISR frame is 11 bytes. The other 17-byte vectors have no deeper call chain in this sketch and are not enabled by the sketch.

Other relevant branches are smaller:
- `cached_or_error -> error_reply -> blank_reply`: 74 + 7 + 4 bytes, replacing (not adding to) the `find_cached` branch.
- `loop -> TX encode`: 168 + 27 bytes plus small codec helpers.
- `setup -> BootIdentityJournal::scan -> read_valid_slot`: 2 + 41 + 41 + 33 bytes plus small storage/CRC helpers and call return addresses.

AVR interrupt entry clears the global interrupt-enable bit; the current image has no ISR that re-enables nested interrupts. The 17-byte ISR frame plus two-byte hardware-pushed PC is therefore added once, not recursively.

The conservative bound for the command-only image is **292 bytes**, below the 700-byte stack ceiling. Remaining SRAM after this bound is:

`2048 - 892 - 292 = 864 bytes`

This exceeds the required 448-byte reserve by 416 bytes.

## Qualification boundary

This is a static compiler/disassembly audit for the exact command-only image, not a measurement on a board. It does not qualify:
- ADC capture code while linked or executing;
- any future scheduler, ADC timeout, STATUS/loss reporting, or batch queue path;
- nested ISR behavior if later code re-enables interrupts;
- serial sustained-load timing or host/device interoperability;
- EEPROM brownout/power-fail behavior;
- physical motor stop, direction polarity, current limit, or BOD behavior.

Any change that links additional functions, changes compiler/core flags, changes UART buffer sizes, or changes the device state machine requires a new size and stack audit. Do not enable ADC acquisition until the scheduler is implemented, the actual ADC-enabled image is rebuilt, and the SRAM/stack budget is requalified.


## ADC-helper link-audit image (compile-only, not a release HEX)

A second compile uses `M4WD_ADC_RESOURCE_AUDIT` to retain both `capture_adc_attempt()` and `record_not_acquired_attempt()` in the linked image through a volatile, false-by-default audit gate. The macro is absent from the normal build; the audit HEX is not uploaded or used on hardware. This allows the compiler to emit stack frames for the ADC helper path without enabling a sampling cadence in the production sketch.

- Source/workflow commit: `6c3492d28d08ed146e0e51dbf0e368bd85cbf277`
- Arduino Uno Firmware Compile workflow #181 / run ID `42029342721`
- Artifact ID `13415696144` (expires 2026-11-19)
- ADC audit image: text=12652, data=146, bss=749; static allocation **895 bytes**, 5 bytes below the 900-byte cap; 1153 bytes remain before stack.
- GCC emitted 25 `.su` files for the audit build. ADC-related frames: `loop()` 168 bytes and `append_adc_attempt()` 23 bytes; `encode_frame_in_place()` 25 bytes and `validate_payload()` 17 bytes are the deepest encoding branch. The audit image's largest individual frame remains 168 bytes.

Conservative ADC branch including main/loop, append, encode, validation, call return addresses, and the largest active UART TX ISR is 266 bytes:

`2 + 168 + 23 + 25 + 17 + 8 + 23 = 266 bytes`

The command/ACK path remains the larger bound at 292 bytes (see above). The normal production image on the same commit is text=11536, data=146, bss=747; static allocation 893 bytes (7 bytes below the 900-byte cap). Using the larger bound with the ADC audit image:

`2048 - 895 - 292 = 861 bytes`

This leaves 413 bytes above the required 448-byte reserve. Therefore the **currently linked ADC-helper code path** meets the static and conservative stack arithmetic limits in this compile-only audit image. This does not qualify a scheduler, six-channel acquisition cadence, batch deadlines, loss accounting, sustained UART load, or hardware behavior. The audit macro's volatile gate is false and no conversion was executed. Any later scheduler/state additions require a fresh linked audit.
