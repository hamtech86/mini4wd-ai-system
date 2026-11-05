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
#include "ProtocolV2AdcScheduler.h"

namespace {

using namespace mini4wd310;

static_assert(kMaxV2WireSize == 188, "v2 wire-size change requires an SRAM review");
static const uint8_t kMaxHostCommandWireSize = 41;
static const uint8_t kRxWorkspaceSize = 48;
static_assert(kRxWorkspaceSize >= kMaxHostCommandWireSize, "RX workspace too small for the largest host command");

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
static AdcCadenceScheduler adc_scheduler;

// Construct the device only after setup() has initialized safe GPIO states.
// Placement construction uses static storage; no heap allocation is used.
using Device = ProtocolV2Device<UnoOutputAdapter>;
alignas(Device) static uint8_t device_storage[sizeof(Device)];
static Device* device = 0;

// RX owns its one frame workspace. ADC_BATCH assembly is owned directly by
// the TX scheduler's one TX workspace; no second payload/frame shadow exists.
static uint8_t rx_buffer[kRxWorkspaceSize];
static uint16_t rx_length = 0;
static bool rx_discard_until_delimiter = false;
static uint8_t adc_batch_count = 0;
static uint32_t adc_loss_counter = 0;
#if defined(M4WD_ADC_RESOURCE_AUDIT)
// Build-only volatile gate retains the otherwise unreferenced ADC helper call
// chain for AVR resource analysis. The macro is absent from production builds.
static volatile bool adc_resource_audit_link = false;
#endif

static void add_adc_loss_count(uint32_t count) {
  adc_loss_counter = saturating_add_u32(adc_loss_counter, count);
  // UINT32_MAX is the saturated sentinel; never wrap the transport counter.
}

static void discard_partial_adc_batch() {
  if (tx_scheduler.batch_building()) {
    const uint8_t dropped_attempts = adc_batch_count;
    tx_scheduler.abort_adc_batch();
    adc_batch_count = 0;
    add_adc_loss_count(dropped_attempts);
  }
}

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
      // STOP's output-safe action has already happened synchronously. Any
      // control reply preempts an incomplete telemetry batch; count all
      // sample attempts already written to TX workspace as lost.
      if (reply.valid && tx_scheduler.batch_building()) {
        discard_partial_adc_batch();
      }
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
  // Bound foreground RX work so a continuous stream cannot starve STOP or
  // the cadence scheduler. The Uno RX ring is 32 bytes; 32 reads drain one
  // full ring while guaranteeing the loop returns to safety work.
  for (uint8_t budget = 0; budget < 32 && Serial.available() > 0; ++budget) {
    const int value = Serial.read();
    if (value >= 0) handle_rx_byte(static_cast<uint8_t>(value));
  }
}

// ADC reference is AVCC. The foreground conversion routine has an explicit
// 2 ms bound (nominal 104 us at 16 MHz / 128 prescaler); it never calls the
// unbounded Arduino analogRead() implementation.
static bool adc_ready = false;
static const uint32_t kAdcConversionTimeoutUs = 2000UL;

static bool append_adc_attempt(uint8_t channel_code, uint32_t timestamp_us,
                               uint16_t raw, uint16_t stage_token,
                               uint8_t acquisition_status) {
  if (!device || !device->session_bound() ||
      (device->state() != DEVICE_ARMED && device->state() != DEVICE_RUNNING))
    return false;

  if (adc_batch_count == 0 && !device->can_begin_adc_batch()) {
    device->latch_sample_sequence_exhaustion();
    return false;
  }
  uint64_t sequence = 0;
  if (!device->allocate_sample_sequence64(&sequence)) return false;

  if (adc_batch_count == 0) {
    if (!tx_scheduler.begin_adc_batch(sequence, static_cast<uint8_t>(adc_loss_counter))) {
      add_adc_loss_count(1);
      return false;
    }
  } else if (!tx_scheduler.batch_building()) {
    // A prior partial batch and this scheduled attempt are both lost.
    const uint8_t dropped_attempts = static_cast<uint8_t>(adc_batch_count + 1);
    adc_batch_count = 0;
    add_adc_loss_count(dropped_attempts);
    return false;
  }

  if (!tx_scheduler.append_adc_sample(timestamp_us, channel_code, raw,
                                      stage_token, acquisition_status, 0)) {
    const uint8_t dropped_attempts = static_cast<uint8_t>(adc_batch_count + 1);
    tx_scheduler.abort_adc_batch();
    adc_batch_count = 0;
    add_adc_loss_count(dropped_attempts);
    return false;
  }
  ++adc_batch_count;

  if (adc_batch_count == 12) {
    const bool queued = tx_scheduler.finish_adc_batch(
        device->session_uuid(), epoch_tag_for_boot_id(device->boot_id64()));
    adc_batch_count = 0;
    if (!queued) {
      add_adc_loss_count(12);
      return false;
    }
    enqueue_status();
  }
  return true;
}

// Called by the separately qualified scheduler for one actual conversion
// attempt. PRECONDITION_INVALID and CONVERSION_TIMEOUT are explicit wire slots.
static bool capture_adc_attempt(uint8_t channel_code) {
  if (channel_code > 5) return false;
  if (!device || !device->session_bound() ||
      (device->state() != DEVICE_ARMED && device->state() != DEVICE_RUNNING))
    return false;
  const uint16_t stage_token = device->active_context_token();
  const uint32_t attempt_start_us = micros();
  if (!adc_ready) {
    return append_adc_attempt(channel_code, attempt_start_us, 0xFFFF, stage_token, ADC_PRECONDITION_INVALID);
  }

  ADMUX = static_cast<uint8_t>((ADMUX & 0xF0) | (channel_code & 0x0F));
  const uint32_t conversion_start_us = micros();
  ADCSRA |= _BV(ADSC);
  while (ADCSRA & _BV(ADSC)) {
    if (static_cast<uint32_t>(micros() - conversion_start_us) >=
        kAdcConversionTimeoutUs) {
      ADCSRA &= static_cast<uint8_t>(~_BV(ADEN));
      adc_ready = false;
      return append_adc_attempt(channel_code, micros(), 0xFFFF, stage_token, ADC_CONVERSION_TIMEOUT);
    }
  }
  const uint16_t raw = ADC;
  const uint32_t conversion_end_us = micros();
  const uint32_t midpoint_us = conversion_start_us +
      static_cast<uint32_t>(conversion_end_us - conversion_start_us) / 2UL;
  return append_adc_attempt(channel_code, midpoint_us, raw, stage_token, ADC_ACQ_OK);
}

// The scheduler calls this only when it can identify an intentional missed
// acquisition slot. It is not used for host-side frame loss or UART backpressure.
static bool record_not_acquired_attempt(uint8_t channel_code, uint32_t scheduled_us) {
  if (channel_code > 5) return false;
  // A missed slot is timestamped in the past; its stage may have changed
  // before this loop could account for it. Zero deliberately leaves context
  // unresolved rather than assigning it to a later stage.
  return append_adc_attempt(channel_code, scheduled_us, 0xFFFF, 0, ADC_NOT_ACQUIRED);
}

static void enqueue_status() {
  if (!device || !device->session_bound()) return;
  DeviceReplyV2 status;
  memset(&status, 0, sizeof(status));
  status.message_type = STATUS;
  memcpy(status.session_uuid, device->session_uuid(), 16);
  status.epoch_tag = epoch_tag_for_boot_id(device->boot_id64());
  status.command_id = 0;
  status.payload[0] = static_cast<uint8_t>(device->state());
  status.payload[1] = device->active_pwm();
  write_u16(status.payload + 2, device->active_context_token());
  write_u32(status.payload + 4, adc_loss_counter);
  write_u64(status.payload + 8, device->next_sample_sequence64());
  status.payload_length = 16;
  status.valid = true;
  (void)tx_scheduler.enqueue(status);
}

} // namespace

void setup() {
  // Establish electrically non-driving GPIO before constructing protocol state.
  output_adapter.safe_outputs();
  Serial.begin(SERIAL_BAUD);
  ADMUX = _BV(REFS0); // AVCC reference, ADC0 selected
  ADCSRA = _BV(ADEN) | _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0); // prescaler 128
  DIDR0 = 0x3F; // disable digital input buffers on A0..A5
  delay(2); // AVCC reference settling before declaring ADC preconditions valid
  adc_ready = (ADCSRA & _BV(ADEN)) != 0;

  const BootIdentityResult identity = boot_journal.begin();
  device = new (device_storage) Device(output_adapter, 0, 0);
  if (identity.status == BOOT_ID_OK) {
    device->initialize_identity(identity.boot_id64, 0);
  }
  // Invalid, corrupt, exhausted or unprovisioned EEPROM remains fail-closed.
}

void loop() {
  service_rx();

  const bool acquisition_state = device &&
      (device->state() == DEVICE_ARMED || device->state() == DEVICE_RUNNING);
  if (!acquisition_state) {
    adc_scheduler.stop();
  } else {
    if (!adc_scheduler.active()) adc_scheduler.start(micros());
    uint8_t channel_code = 0;
    uint32_t scheduled_us = 0;
    bool not_acquired = false;
    if (adc_scheduler.take_due(micros(), &channel_code, &scheduled_us,
                               &not_acquired)) {
      if (not_acquired) {
        (void)record_not_acquired_attempt(channel_code, scheduled_us);
      } else {
        (void)capture_adc_attempt(channel_code);
      }
    }
  }

#if defined(M4WD_ADC_RESOURCE_AUDIT)
  if (adc_resource_audit_link && !acquisition_state) {
    (void)capture_adc_attempt(0);
    (void)record_not_acquired_attempt(0, micros());
  }
#endif
  tx_scheduler.service(Serial);
}
