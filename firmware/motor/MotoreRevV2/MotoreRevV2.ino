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

// UART ring sizes are set as global compiler properties in the Uno workflow
// so the sketch and HardwareSerial core are built with identical class layouts.
#include <Arduino.h>
#include <EEPROM.h>
#include <new>

#include "ProtocolV2Codec.h"
#include "BootIdentityJournal.h"
#include "ProtocolV2Device.h"
#include "ProtocolV2TxScheduler.h"

namespace {

using namespace mini4wd310;

static_assert(kMaxV2WireSize == 188, "v2 wire-size change requires an SRAM review");

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

// RX owns its one frame workspace. ADC_BATCH assembly is owned directly by
// the TX scheduler's one TX workspace; no second payload/frame shadow exists.
static uint8_t rx_buffer[kMaxV2WireSize];
static uint16_t rx_length = 0;
static bool rx_discard_until_delimiter = false;
static uint8_t adc_batch_count = 0;
static uint32_t adc_loss_counter = 0;

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

// Called by the separately qualified sampling scheduler for each scheduled
// channel attempt. No fixed sampling cadence is selected in this sketch.
static bool capture_adc_attempt(uint8_t channel_code) {
  if (channel_code > 5 || !device || !device->session_bound() ||
      (device->state() != DEVICE_ARMED && device->state() != DEVICE_RUNNING))
    return false;

  uint64_t sequence = 0;
  if (!device->allocate_sample_sequence64(&sequence)) return false;

  if (adc_batch_count == 0) {
    if (!tx_scheduler.begin_adc_batch(sequence, static_cast<uint8_t>(adc_loss_counter))) {
      ++adc_loss_counter;
      return false;
    }
  } else if (!tx_scheduler.batch_building()) {
    // A control ACK/STOP preempted the in-progress batch.
    adc_batch_count = 0;
    ++adc_loss_counter;
    return false;
  }

  // Stage identity is sampled immediately before the individual conversion.
  const uint16_t stage_token = device->active_context_token();
  const uint32_t conversion_start_us = micros();
  const uint16_t raw = static_cast<uint16_t>(analogRead(A0 + channel_code));
  const uint32_t conversion_end_us = micros();
  const uint32_t midpoint_us = conversion_start_us +
      static_cast<uint32_t>(conversion_end_us - conversion_start_us) / 2UL;

  if (!tx_scheduler.append_adc_sample(midpoint_us, channel_code, raw,
                                      stage_token, 0, 0)) {
    tx_scheduler.abort_adc_batch();
    adc_batch_count = 0;
    ++adc_loss_counter;
    return false;
  }
  ++adc_batch_count;

  if (adc_batch_count == 12) {
    const bool queued = tx_scheduler.finish_adc_batch(
        device->session_uuid(), epoch_tag_for_boot_id(device->boot_id64()));
    adc_batch_count = 0;
    if (!queued) {
      ++adc_loss_counter;
      return false;
    }
  }
  return true;
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
