# 310-5 boot identity EEPROM provisioning procedure

Status: design and compile-only evidence. No board was connected, uploaded, or written.

## Purpose

MotoreRevV2 fails closed if the EEPROM provisioning record is absent or invalid. The first boot journal generation is created only after the four-byte provisioning record is valid. The separate ProvisionBootIdentity sketch provides a controlled way to create that record without modifying the boot journal.

## Write boundary

The utility writes only EEPROM addresses 256–259:
- bytes 256–258: 0x50, 0x52, 0x01
- byte 259: CRC-8/ATM over the first three bytes (0x05)

It never writes EEPROM addresses 0–255, which are reserved for the 16-slot boot identity journal.

## Preconditions and safeguards

- Motor output pins D5, D7 and D8 are driven low before serial input is processed.
- No EEPROM write occurs at startup.
- The boot journal region 0–255 must be completely erased (0xFF); otherwise provisioning is refused.
- The provisioning record must be erased or contain only the expected bytes and 0xFF. Unexpected partial data is refused.
- An already valid record is accepted idempotently without writing.
- A two-line confirmation is required: PROVISION followed by CONFIRM-310-BOOT-ID.
- Every written byte is read back and the complete CRC-protected record is verified.
- A power interruption during a valid-prefix write can be retried only when each existing byte is either 0xFF or its exact expected value.

## Controlled procedure

1. Obtain separate upper-command authorization for physical upload and EEPROM provisioning. This document is not that authorization.
2. Disconnect the motor/load and keep the driver power stage unpowered.
3. Upload only ProvisionBootIdentity.ino to the Uno; do not upload the motor-control sketch for this operation.
4. At 57600 baud, send PROVISION, then send CONFIRM-310-BOOT-ID.
5. Require the exact PROVISIONED readback message. Any REFUSED or FAIL result blocks further use.
6. Power down, then upload the separately reviewed MotoreRevV2 image under its own authorization.
7. On first MotoreRevV2 boot, BootIdentityJournal.begin() creates generation 1. Subsequent boots advance the generation. This remains software intent until power-fail behavior is separately qualified.

## Verification boundary

The Arduino Uno CI workflow compiles this provisioning utility but never uploads or runs it. Native tests verify the shared four-byte record and CRC. CI does not establish EEPROM write endurance, brownout behavior, interrupted-write recovery on a real ATmega328P, or motor safety.
