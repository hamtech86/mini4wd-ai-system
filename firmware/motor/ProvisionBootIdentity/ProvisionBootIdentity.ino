/*
 * One-shot EEPROM boot-journal provisioning utility.
 *
 * This is a separate service image, never the motor-control firmware.
 * It writes only the four-byte provisioning record at EEPROM 256..259.
 * It never writes the 256-byte boot journal at EEPROM 0..255.
 *
 * No EEPROM write occurs at power-up. Two exact serial commands are required:
 *   PROVISION
 *   CONFIRM-310-BOOT-ID
 *
 * This sketch must not be uploaded or run without separate hardware approval.
 */
#include <Arduino.h>
#include <EEPROM.h>
#include <string.h>
#include "../BootIdentityJournal.h"

namespace {
using namespace mini4wd310;
static const uint16_t kProvisionBase = kProvisionRecordBase;
static const char kFirstCommand[] = "PROVISION";
static const char kConfirmCommand[] = "CONFIRM-310-BOOT-ID";
static char input[32];
static uint8_t input_length = 0;
static bool confirm_pending = false;

static void safe_motor_pins() {
  digitalWrite(5, LOW);
  digitalWrite(7, LOW);
  digitalWrite(8, LOW);
  pinMode(5, OUTPUT);
  pinMode(7, OUTPUT);
  pinMode(8, OUTPUT);
  analogWrite(5, 0);
  digitalWrite(7, LOW);
  digitalWrite(8, LOW);
}

static bool journal_region_erased() {
  for (uint16_t address = 0; address < kBootJournalBytes; ++address) {
    if (EEPROM.read(address) != 0xFF) return false;
  }
  return true;
}


static void report(const __FlashStringHelper* message) {
  Serial.println(message);
}

static void provision_once() {
  if (!journal_region_erased()) {
    report(F("REFUSED: boot journal region 0..255 is not erased"));
    return;
  }
  uint8_t expected[4];
  uint8_t current[4];
  make_boot_provision_record(expected);
  for (uint8_t i = 0; i < 4; ++i) current[i] = EEPROM.read(kProvisionBase + i);
  if (boot_provision_record_valid(current)) {
    report(F("ALREADY_PROVISIONED: no EEPROM writes performed"));
    return;
  }
  // Power-loss retry is allowed only when each byte is erased or already
  // equals its expected value. Unexpected contents require manual review.
  for (uint8_t i = 0; i < 4; ++i) {
    if (current[i] != 0xFF && current[i] != expected[i]) {
      report(F("REFUSED: partial provisioning record contains unexpected data"));
      return;
    }
  }
  for (uint8_t i = 0; i < 4; ++i) EEPROM.update(kProvisionBase + i, expected[i]);
  for (uint8_t i = 0; i < 4; ++i) current[i] = EEPROM.read(kProvisionBase + i);
  if (!boot_provision_record_valid(current)) {
    report(F("FAIL: provisioning record readback mismatch"));
    return;
  }
  report(F("PROVISIONED: four-byte record verified; boot journal remains untouched"));
}

static void handle_line() {
  input[input_length] = '\0';
  if (!confirm_pending && strcmp(input, kFirstCommand) == 0) {
    confirm_pending = true;
    report(F("CONFIRM REQUIRED: type CONFIRM-310-BOOT-ID"));
  } else if (confirm_pending && strcmp(input, kConfirmCommand) == 0) {
    confirm_pending = false;
    provision_once();
  } else {
    confirm_pending = false;
    report(F("IGNORED: exact two-command confirmation required"));
  }
  input_length = 0;
}
} // namespace

void setup() {
  safe_motor_pins();
  Serial.begin(57600);
  report(F("BOOT-ID EEPROM PROVISIONER — NO WRITE AT STARTUP"));
  report(F("Writes only EEPROM 256..259 after PROVISION then CONFIRM-310-BOOT-ID"));
}

void loop() {
  while (Serial.available() > 0) {
    const int value = Serial.read();
    if (value < 0) break;
    const char ch = static_cast<char>(value);
    if (ch == '\r') continue;
    if (ch == '\n') {
      handle_line();
    } else if (input_length < sizeof(input) - 1) {
      input[input_length++] = ch;
    } else {
      input_length = 0;
      confirm_pending = false;
      report(F("IGNORED: input line too long"));
    }
  }
}
