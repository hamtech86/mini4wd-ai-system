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

- Source/workflow commit: `89546dec41e283c248abf55ff8c4b731cb6a4a33`
- Arduino Uno Firmware Compile workflow #186 / run ID `42029806781`
- Artifact ID `13415083050` (expires 2026-11-19)
- ADC audit image: text=12652, data=146, bss=749; static allocation **895 bytes**, 5 bytes below the 900-byte cap; 1153 bytes remain before stack.
- GCC emitted 25 `.su` files for the audit build. ADC-related frames: `loop()` 168 bytes and `append_adc_attempt()` 23 bytes; `encode_frame_in_place()` 25 bytes and `validate_payload()` 17 bytes are the deepest encoding branch. The audit image's largest individual frame remains 168 bytes.

Conservative ADC branch including main/loop, append, encode, validation, call return addresses, and the largest active UART TX ISR is 266 bytes:

`2 + 168 + 23 + 25 + 17 + 8 + 23 = 266 bytes`

The command/ACK path remains the larger bound at 292 bytes (see above). The normal production image on the same commit is text=11644, data=146, bss=747; static allocation 893 bytes (7 bytes below the 900-byte cap). Using the larger bound with the ADC audit image:

`2048 - 895 - 292 = 861 bytes`

This leaves 413 bytes above the required 448-byte reserve. Therefore the **currently linked ADC-helper code path** meets the static and conservative stack arithmetic limits in this compile-only audit image. This does not qualify a scheduler, six-channel acquisition cadence, batch deadlines, loss accounting, sustained UART load, or hardware behavior. The audit macro's volatile gate is false and no conversion was executed. Any later scheduler/state additions require a fresh linked audit.


## 2026-11-05 integrated ADC scheduler / STATUS image

Exact code/test HEAD: 04669f877c3973a6c955277dca1bffbcf4ec15c0
Arduino Uno Firmware Compile workflow #196 / run ID 42038018027
Artifact ID: 13418962974 (expires 2026-11-19)

The compile-only ADC audit macro retains the complete scheduler, ADC conversion helper, NOT_ACQUIRED path, ADC_BATCH producer, and STATUS emission path. It is not a hardware execution image.

### Static SRAM

| Image | .data | .bss | Static total | Margin below 900 |
|---|---:|---:|---:|---:|
| Production integrated sketch | 146 | 615 | 761 | 139 |
| ADC audit image | 146 | 616 | 762 | 138 |

RX workspace is 48 bytes (largest host command wire frame 41 bytes); TX workspace is 188 bytes. UART RX/TX rings remain 32 bytes each.

### Stack inventory and conservative call-chain bound

GCC .su reports 171 bytes for loop(), 12 bytes for capture_adc_attempt(), 25 bytes for append_adc_attempt(), 25 bytes for encode_frame_in_place(), 17 bytes for validate_payload(), 74 bytes for cached_or_error(), and 19 bytes for find_cached(). The largest active ISR is UART TX at 17 bytes; HardwareSerial::_tx_udr_empty_irq() is 2 bytes. ATmega328P interrupt entry pushes a 2-byte PC; the ISR call adds a 2-byte return address. The sketch does not enable nested interrupts from an ISR.

The deepest command-processing chain remains the conservative bound:
2 (main frame) + 171 (loop) + 74 (cached_or_error) + 19 (find_cached) + 6 (three call return addresses) + 17 (UART TX ISR) + 2 (TX ISR helper frame) + 2 (ISR helper return address) + 2 (hardware-pushed PC) = **295 bytes**.

The deepest ADC acquisition/encode chain is bounded by:
2 + 171 + 12 + 25 + 25 + 17 + 10 (five call return addresses) + 17 + 2 + 2 + 2 = **285 bytes**.

The STATUS encode chain is below the command path. Therefore the conservative maximum remains **295 bytes**, below the 700-byte stack ceiling. Using the larger static image:
2048 - 762 - 295 = **991 bytes remaining**, which is 543 bytes above the required 448-byte reserve.

This is a compiler/disassembly bound for the exact image, not an on-board stack watermark. It qualifies the software memory arithmetic only; it does not qualify physical STOP, current limiting, direction polarity, BOD, EEPROM power-fail behavior, analog accuracy, or sustained physical UART behavior.


## 2026-11-06 exact unified PR build

- Source HEAD: 082ee1df09684415f26a5d7fa0541afe19d6d07c
- Arduino Uno Firmware Compile run: 42091319752
- Artifact ID: 13445132659
- Target: arduino:avr:uno, Arduino AVR core 1.8.8
- Build manifest now records the actual checked-out Git SHA separately from the GitHub PR event/merge SHA.

### Exact linked image sizes

| Image | text | .data | .bss | .data + .bss |
|---|---:|---:|---:|---:|
| MotoreRevV2 production integrated sketch | 13,132 B | 146 B | 615 B | **761 B** |
| MotoreRevV2 ADC resource-audit image | 13,232 B | 146 B | 616 B | **762 B** |
| Separate boot identity provisioner (compile-only) | 3,044 B | included in 252 B global total | — | **252 B global total** |

The two motor-control images remain below the 900-byte static cap. The provisioner is a separate service image and is never used as the motor-control firmware.

### Stack review

The current production and ADC audit .su inventories retain the same largest relevant frames: loop 171 B, ProtocolV2Device::cached_or_error 74 B, find_cached 19 B, and ADC append path 25 B. The conservative nested command-processing chain remains:

2 + 171 + 74 + 19 + 6 + 17 + 2 + 2 + 2 = **295 B**

This includes the main frame, loop/cached lookup frames, call return addresses, UART TX ISR frame/helper and interrupt-entry PC. The ADC path remains below this bound. This is a static disassembly/.su review, not an on-board stack watermark.

Using the larger motor-control image:
2048 - 762 - 295 = **991 B** remaining, which is **543 B above** the required 448-byte reserve.

### Artifact hashes

- MotoreRevV2 HEX: f2f4ad306eb2b643122df8c5417ebcdb7c6e346f463121d3b139f7dd21adf075
- MotoreRevV2 ELF: e87ef4b5d41e9c944ffe47be36b4e39d76f50eaef33fc5da9d17d9548fa5b82c
- MotoreRevV2 map: 51fa18bb5714ebb7d13dfa1535165b970d3bdf9af38d6642f1c30d1f297b6f17

The separate provisioning image was compile-tested only. No HEX was uploaded, no EEPROM was written, and no physical test was performed.


## 2026-11-08 194-byte RX/TX workspace re-audit

This section supersedes the earlier workspace sizes for the unified MotoreRevV2 candidate.

- Exact source HEAD: `c2ba0a431a96d586c4449b4b98f8c31acd55bfb3`
- Arduino Uno Firmware Compile run: `42463230241`
- Artifact ID: `13609549698`
- Target: `arduino:avr:uno`, Arduino AVR core 1.8.8
- The RX frame workspace is exactly 194 bytes (`rx_buffer[194]`).
- The TX frame workspace is exactly 194 bytes (`tx_buffer_[194]`); the maximum encoded protocol-v2 frame remains 188 bytes.
- HardwareSerial RX and TX rings are each 24 bytes. The foreground RX budget is 24 bytes per loop pass, and the same ring-size macros are used for the sketch and core build.
- The command cache uses `command_id == 0` as its empty sentinel. Protocol v2 command IDs are required to be nonzero, so this removes the redundant per-entry `used` byte without changing replay/conflict identity semantics.

### Exact linked image sizes

| Image | text | .data | .bss | .data + .bss |
|---|---:|---:|---:|---:|
| MotoreRevV2 production integrated sketch | 13,274 B | 146 B | 747 B | **893 B** |
| MotoreRevV2 ADC resource-audit image | 13,374 B | 146 B | 748 B | **894 B** |
| Separate boot identity provisioner | 3,044 B | included in 252 B global total | — | **252 B global total** |

Both motor-control images are below the 900-byte static SRAM ceiling. The ADC audit image is the larger image and is used for reserve arithmetic.

### Updated conservative stack bound

GCC `.su` and the retained AVR disassembly report:

- `main()`: 2 B
- `loop()`: 171 B
- `ProtocolV2Device::cached_or_error()`: 74 B
- `ProtocolV2Device::find_cached()`: 18 B
- Three call return addresses in the main command-processing chain: 6 B
- UART TX-empty ISR `__vector_19`: 17 B
- `HardwareSerial::_tx_udr_empty_irq()`: 2 B
- ISR helper call return address: 2 B
- ATmega328P interrupt-entry PC: 2 B

Conservative simultaneous bound:

`2 + 171 + 74 + 18 + 6 + 17 + 2 + 2 + 2 = 294 B`

The sketch does not enable nested interrupts from an ISR; the interrupt frame is therefore added once. This remains a static compiler/disassembly bound, not an on-board stack watermark.

Using the larger ADC audit image:

`2048 - 894 - 294 = 860 B` remaining.

This is 412 B above the required 448 B reserve. The static allocation, stack bound and reserve arithmetic meet their software audit limits for this exact build.

### Artifact hashes

- MotoreRevV2 HEX: `97cdfa5d148ecf953371598e549b7e5e6e2c656be6a693fc208b22027ef41e69`
- MotoreRevV2 ELF: `08fd69e35cdd527636879e5d06aeee552d40868c20084e7f6bf45c4a840e765d`
- MotoreRevV2 map: `14c79f95b62d70fa28808d16fd40e9a662d283e7f34924fee01d202365681550`

The artifact is compile/audit evidence only. No HEX was uploaded. This does not qualify physical UART throughput with 24-byte rings, ADC timing, physical STOP, BOD/voltage monitoring, EEPROM power-fail behavior, current limiting, direction polarity, analog calibration, or motor cutoff. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.
