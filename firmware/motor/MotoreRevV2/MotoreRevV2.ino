/*
 * MotoreRevV2 — 310 protocol v2 firmware integration candidate.
 *
 * This sketch is deliberately separate from the legacy ASCII MotoreRev.ino.
 * It implements the v2 command path only. ADC_BATCH production is not yet
 * enabled; no fabricated/placeholder telemetry is emitted.
 *
 * Hardware map (Arduino Uno / L298N):
 * D5 PWM, D7 IN3, D8 IN4
 * A0 ACS1, A1 ACS2, A2 magnetic raw, A3 thermistor raw,
 * A4 voltage_v4, A5 voltage_v5.
 * Serial: 57600 baud.
 *
 * Safety boundary:
 * - Outputs are forced low before protocol processing.
 * - EEPROM journal is read/advanced only; provisioning is never written.
 * - No serial text/debug output is mixed into the binary protocol.
 * - Software output writes are not proof of physical current cessation.
 */

// Keep AVR UART rings bounded; the main loop drains RX continuously and TX is
// emitted in 16-byte scheduler slices. This saves 64 bytes of static SRAM.
#define SERIAL_RX_BUFFER_SIZE 32
#define SERIAL_TX_BUFFER_SIZE 32

#include <Arduino.h>
#include <EEPROM.h>
#include <new>

#include "ProtocolV2Codec.h"
#include "BootIdentityJournal.h"
#include "ProtocolV2Device.h"
#include "ProtocolV2TxScheduler.h"

namespace {

using namespace mini4wd310;

static const uint8_t PIN_PWM = 5;
static const uint8_t PIN_IN3 = 7;
static const uint8_t PIN_IN4 = 8;
static const uint32_t SERIAL_BAUD = 57600UL;

class UnoOutputAdapter {
 public:
  bool safe_outputs() {
    // Set output latches low before enabling the output drivers.
    digitalWrite(PIN_PWM, LOW);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    pinMode(PIN_PWM, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);
    analogWrite(PIN_PWM, 0);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    return true; // Software writes only; no physical feedback is available.
  }

  bool set_direction(uint8_t direction) {
    if (direction > DIRECTION_REV) return false;
    analogWrite(PIN_PWM, 0);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    if (direction == DIRECTION_FWD) {
      digitalWrite(PIN_IN3, HIGH);
      digitalWrite(PIN_IN4, LOW);
    } else {
      digitalWrite(PIN_IN3, LOW);
      digitalWrite(PIN_IN4, HIGH);
    }
    return true;
  }

  bool set_pwm(uint8_t pwm) {
    if (pwm > 30) return false;
    analogWrite(PIN_PWM, pwm);
    return true;
  }
};

class UnoEepromStorage {
 public:
  uint8_t read(uint16_t address) const {
    if (address >= EEPROM.length()) return 0;
    return EEPROM.read(address);
  }

  bool write(uint16_t address, uint8_t value) {
    if (address >= EEPROM.length()) return false;
    EEPROM.update(address, value);
    return EEPROM.read(address) == value;
  }
};

static UnoOutputAdapter output_adapter;
static UnoEepromStorage eeprom_storage;
static BootIdentityJournal<UnoEepromStorage> boot_journal(eeprom_storage);
static ProtocolV2TxScheduler tx_scheduler;

// Construct the device only after setup() has initialized safe GPIO states.
// Placement construction uses static storage; no heap allocation is used.
using Device = ProtocolV2Device<UnoOutputAdapter>;
alignas(Device) static uint8_t device_storage[sizeof(Device)];
static Device* device = 0;

static uint8_t rx_buffer[kMaxWireSize];
static uint16_t rx_length = 0;
static bool rx_discard_until_delimiter = false;

static void handle_rx_byte(uint8_t value) {
  if (value == 0) {
    if (rx_discard_until_delimiter) {
      rx_discard_until_delimiter = false;
      rx_length = 0;
      return;
    }
    if (rx_length == 0) return;
    FrameView frame;
    if (decode_frame_in_place(rx_buffer, rx_length, &frame)) {
      const DeviceReplyV2 reply = device->handle(frame);
      // STOP output action already occurred synchronously inside handle().
      // The scheduler only queues the best-effort ACK.
      tx_scheduler.enqueue(reply);
    }
    rx_length = 0;
    return;
  }

  if (rx_discard_until_delimiter) return;
  if (rx_length >= sizeof(rx_buffer) - 1) {
    rx_length = 0;
    rx_discard_until_delimiter = true;
    return;
  }
  rx_buffer[rx_length++] = value;
}

static void service_rx() {
  while (Serial.available() > 0) {
    const int value = Serial.read();
    if (value >= 0) handle_rx_byte(static_cast<uint8_t>(value));
  }
}

} // namespace

void setup() {
  // Establish electrically non-driving GPIO before constructing protocol state.
  output_adapter.safe_outputs();
  Serial.begin(SERIAL_BAUD);

  const BootIdentityResult identity = boot_journal.begin();
  device = new (device_storage) Device(output_adapter, 0, 0);
  if (identity.status == BOOT_ID_OK) {
    device->initialize_identity(identity.boot_id64, 0);
  }
  // Invalid, corrupt, exhausted or unprovisioned EEPROM remains fail-closed.
}

void loop() {
  service_rx();
  tx_scheduler.service(Serial);
  // ADC scheduling and ADC_BATCH production are intentionally not enabled
  // until the normative 12-slot sample layout and timestamp/context capture
  // are implemented and independently tested.
}
