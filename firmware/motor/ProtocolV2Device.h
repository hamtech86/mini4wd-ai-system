#pragma once
#include <stdint.h>
#include <string.h>
#include "ProtocolV2Codec.h"
#include "BootIdentityJournal.h"

namespace mini4wd310 {

enum DeviceStateV2 : uint8_t {
  DEVICE_IDLE = 0,
  DEVICE_ARMED = 1,
  DEVICE_RUNNING = 2,
  DEVICE_STOP_LATCHED = 3,
  DEVICE_STOPPED = 4,
  DEVICE_FAULT = 5,
  DEVICE_FAULT_STOP = 6,
  DEVICE_BOOT_ID_INVALID = 7
};

enum DeviceErrorV2 : uint8_t {
  DEVICE_ERR_NOT_ARMED = 1,
  DEVICE_ERR_SESSION = 2,
  DEVICE_ERR_COMMAND_ID = 3,
  DEVICE_ERR_ID_CONFLICT = 4,
  DEVICE_ERR_CONTEXT = 5,
  DEVICE_ERR_STATE = 6,
  DEVICE_ERR_OUTPUT = 7
};

// Adapter contract: safe_outputs() must synchronously request PWM=0 and both
// direction pins LOW. It must return false if any write cannot be confirmed.
// This is a software-output contract, not proof of physical current cessation.
struct DeviceReplyV2 {
  uint8_t message_type;
  uint8_t session_uuid[16];
  uint32_t epoch_tag;
  uint32_t command_id;
  uint8_t payload[25];
  uint8_t payload_length;
  bool valid;
};

template <typename Output>
class ProtocolV2Device {
 public:
  ProtocolV2Device(Output& output, uint64_t boot_id64, uint64_t next_sample_sequence64)
      : output_(output), boot_id64_(boot_id64), next_sample_sequence64_(next_sample_sequence64),
        state_(boot_id64 ? DEVICE_IDLE : DEVICE_BOOT_ID_INVALID),
        session_bound_(false), active_token_(0), active_pwm_(0), active_direction_(0xFF), command_high_water_(0),
        command_cache_next_(0), output_healthy_(false) {
    memset(session_uuid_, 0, sizeof(session_uuid_));
    memset(command_cache_, 0, sizeof(command_cache_));
    memset(stop_history_, 0, sizeof(stop_history_));
    // Safe outputs are requested before this object may process any frame.
    output_healthy_ = output_.safe_outputs();
    if (!output_healthy_) state_ = DEVICE_FAULT;
  }

  DeviceStateV2 state() const { return state_; }
  uint8_t active_pwm() const { return active_pwm_; }
  uint16_t active_context_token() const { return active_token_; }
  uint8_t active_direction() const { return active_direction_; }
  uint64_t boot_id64() const { return boot_id64_; }
  uint64_t next_sample_sequence64() const { return next_sample_sequence64_; }
  const uint8_t* session_uuid() const { return session_uuid_; }
  bool session_bound() const { return session_bound_; }
  bool can_begin_adc_batch() const {
    return next_sample_sequence64_ <= UINT64_MAX - 12ULL &&
        state_ != DEVICE_STOP_LATCHED && state_ != DEVICE_STOPPED &&
        state_ != DEVICE_FAULT && state_ != DEVICE_FAULT_STOP &&
        state_ != DEVICE_BOOT_ID_INVALID;
  }
  void latch_sample_sequence_exhaustion() {
    outputs_safe();
    state_ = DEVICE_FAULT_STOP;
  }

  // Allocate exactly one scheduled ADC-attempt identity. UINT64_MAX is a
  // terminal boundary: it is never emitted and the device fails closed.
  bool allocate_sample_sequence64(uint64_t* allocated) {
    if (!allocated || next_sample_sequence64_ == UINT64_MAX ||
        state_ == DEVICE_STOP_LATCHED || state_ == DEVICE_STOPPED ||
        state_ == DEVICE_FAULT || state_ == DEVICE_FAULT_STOP ||
        state_ == DEVICE_BOOT_ID_INVALID) {
      if (next_sample_sequence64_ == UINT64_MAX) {
        outputs_safe();
        state_ = DEVICE_FAULT_STOP;
      }
      return false;
    }
    *allocated = next_sample_sequence64_++;
    return true;
  }

  bool initialize_identity(uint64_t boot_id64, uint64_t next_sample_sequence64) {
    if (!output_healthy_ || boot_id64 == 0 || state_ != DEVICE_BOOT_ID_INVALID)
      return false;
    boot_id64_ = boot_id64;
    next_sample_sequence64_ = next_sample_sequence64;
    state_ = DEVICE_IDLE;
    return true;
  }

  void set_next_sample_sequence64(uint64_t next) {
    if (next >= next_sample_sequence64_) next_sample_sequence64_ = next;
  }

  // Call only after the codec has validated framing, CRC, header and payload.
  // STOP is handled synchronously before any later queued drive command.
  DeviceReplyV2 handle(const FrameView& frame) {
    if (frame.message_type == HELLO) return handle_hello(frame);
    if (frame.message_type == STOP_REQ) return handle_stop(frame);
    if (frame.message_type == ARM) return handle_arm(frame);
    if (frame.message_type == DISARM) return handle_disarm(frame);
    if (frame.message_type == PWM_SET) return handle_pwm(frame);
    return error_reply(frame, DEVICE_ERR_STATE);
  }

 private:
  struct CommandCacheEntry {
    bool used;
    uint32_t command_id;
    uint8_t request_type;
    uint8_t request_payload[4];
    uint8_t request_length;
    uint8_t ack_type;
    uint8_t ack_payload[5];
    uint8_t ack_length;
  };
  struct StopHistoryEntry {
    bool used;
    uint8_t session[16];
    uint16_t stop_request_id;
    uint8_t stop_reason;
  };

  Output& output_;
  uint64_t boot_id64_;
  uint64_t next_sample_sequence64_;
  DeviceStateV2 state_;
  uint8_t session_uuid_[16];
  bool session_bound_;
  uint16_t active_token_;
  uint8_t active_pwm_;
  uint8_t active_direction_;
  uint32_t command_high_water_;
  CommandCacheEntry command_cache_[4];
  uint8_t command_cache_next_;
  bool output_healthy_;
  StopHistoryEntry stop_history_[4];

  static bool same_session(const uint8_t* a, const uint8_t* b) {
    return memcmp(a, b, 16) == 0;
  }
  static bool zero_session(const uint8_t* a) {
    return uuid_is_zero(a);
  }
  static void copy_header(const FrameView& f, DeviceReplyV2* r, uint8_t type) {
    r->message_type = type;
    memcpy(r->session_uuid, f.session_uuid, 16);
    r->epoch_tag = f.device_epoch_tag;
    r->command_id = f.command_id;
    r->payload_length = 0;
    r->valid = true;
  }
  static DeviceReplyV2 blank_reply(const FrameView& f, uint8_t type) {
    DeviceReplyV2 r;
    memset(&r, 0, sizeof(r));
    copy_header(f, &r, type);
    return r;
  }
  DeviceReplyV2 error_reply(const FrameView& f, uint8_t code) const {
    DeviceReplyV2 r = blank_reply(f, ERROR_MSG);
    r.command_id = 0; // ERROR uses command_id=0; related ID is in its payload.
    r.payload[0] = code;
    r.payload[1] = f.message_type;
    write_u16(r.payload + 2, 0);
    write_u32(r.payload + 4, f.command_id);
    r.payload_length = 8;
    return r;
  }
  bool outputs_safe() {
    const bool ok = output_.safe_outputs();
    active_pwm_ = 0;
    active_token_ = 0;
    active_direction_ = 0xFF;
    return ok;
  }
  DeviceReplyV2 handle_hello(const FrameView& f) {
    DeviceReplyV2 r = blank_reply(f, HELLO_ACK);
    const uint64_t nonce = read_u64(f.payload);
    uint8_t result = 0;
    if (boot_id64_ == 0 || state_ == DEVICE_BOOT_ID_INVALID || state_ == DEVICE_FAULT ||
        state_ == DEVICE_FAULT_STOP) {
      result = 1; // BOOT_ID_INVALID / unavailable
    } else if (nonce == 0 || zero_session(f.session_uuid)) {
      result = 2;
    } else if (session_bound_ && same_session(session_uuid_, f.session_uuid)) {
      // Idempotent HELLO retry must not reset command freshness/cache.
    } else if (state_ == DEVICE_IDLE || state_ == DEVICE_STOP_LATCHED ||
               state_ == DEVICE_STOPPED) {
      // A new UUID may bind only while output is already non-driving.
      memcpy(session_uuid_, f.session_uuid, 16);
      session_bound_ = true;
      command_high_water_ = 0;
      memset(command_cache_, 0, sizeof(command_cache_));
      command_cache_next_ = 0;
    } else {
      result = 3; // SESSION_BUSY; do not orphan an active/armed run.
    }
    r.epoch_tag = result == 0 ? epoch_tag_for_boot_id(boot_id64_) : 0;
    r.payload[0] = result;
    write_u64(r.payload + 1, result == 0 ? boot_id64_ : 0);
    write_u64(r.payload + 9, nonce);
    write_u64(r.payload + 17, next_sample_sequence64_);
    r.payload_length = 25;
    return r;
  }

  bool find_cached(const FrameView& f, uint8_t* ack_type, uint8_t* ack_payload,
                   uint8_t* ack_length, bool* conflict) const {
    *conflict = false;
    for (uint8_t i = 0; i < 4; ++i) {
      const CommandCacheEntry& e = command_cache_[i];
      if (!e.used || e.command_id != f.command_id) continue;
      const bool exact = e.request_type == f.message_type &&
          e.request_length == f.payload_length &&
          memcmp(e.request_payload, f.payload, f.payload_length) == 0;
      if (!exact) { *conflict = true; return true; }
      *ack_type = e.ack_type;
      *ack_length = e.ack_length;
      memcpy(ack_payload, e.ack_payload, e.ack_length);
      return true;
    }
    return false;
  }
  bool command_is_fresh(const FrameView& f) const {
    return f.command_id != 0 && f.command_id > command_high_water_;
  }
  void cache_command(const FrameView& f, uint8_t ack_type,
                     const uint8_t* ack_payload, uint8_t ack_length) {
    CommandCacheEntry& e = command_cache_[command_cache_next_];
    e.used = true;
    e.command_id = f.command_id;
    e.request_type = f.message_type;
    e.request_length = (uint8_t)f.payload_length;
    memcpy(e.request_payload, f.payload, f.payload_length);
    e.ack_type = ack_type;
    e.ack_length = ack_length;
    memcpy(e.ack_payload, ack_payload, ack_length);
    command_cache_next_ = (uint8_t)((command_cache_next_ + 1) % 4);
    command_high_water_ = f.command_id;
  }
  DeviceReplyV2 cached_or_error(const FrameView& f, uint8_t expected_ack) const {
    uint8_t ack_type = 0, ack_payload[5] = {0}, ack_length = 0;
    bool conflict = false;
    if (find_cached(f, &ack_type, ack_payload, &ack_length, &conflict)) {
      if (conflict) return error_reply(f, DEVICE_ERR_ID_CONFLICT);
      DeviceReplyV2 r = blank_reply(f, ack_type);
      memcpy(r.payload, ack_payload, ack_length);
      r.payload_length = ack_length;
      return r;
    }
    (void)expected_ack;
    return error_reply(f, DEVICE_ERR_COMMAND_ID);
  }
  DeviceReplyV2 handle_arm(const FrameView& f) {
    if (!session_bound_ || !same_session(session_uuid_, f.session_uuid) ||
        f.device_epoch_tag != epoch_tag_for_boot_id(boot_id64_))
      return arm_ack(f, 2, state_, 0, 0xFF, false);
    if (f.payload[2] != 0 || read_u16(f.payload) == 0 || f.payload[3] > DIRECTION_REV)
      return arm_ack(f, 3, state_, 0, 0xFF, false);
    uint8_t old_type = 0, old_payload[5] = {0}, old_length = 0;
    bool conflict = false;
    if (find_cached(f, &old_type, old_payload, &old_length, &conflict))
      return cached_or_error(f, ARM_ACK);
    if (conflict || !command_is_fresh(f))
      return error_reply(f, conflict ? DEVICE_ERR_ID_CONFLICT : DEVICE_ERR_COMMAND_ID);
    // STOP is terminal for this session. Only a normal DISARM returns to IDLE.
    if (state_ != DEVICE_IDLE)
      return arm_ack(f, 4, state_, 0, 0xFF, true);
    if (!outputs_safe()) {
      state_ = DEVICE_FAULT;
      return arm_ack(f, 5, state_, 0, 0xFF, true);
    }
    const uint8_t requested_direction = f.payload[3];
    if (!output_.set_direction(requested_direction)) {
      outputs_safe(); state_ = DEVICE_FAULT;
      return arm_ack(f, 5, state_, 0, 0xFF, true);
    }
    active_token_ = read_u16(f.payload);
    active_direction_ = requested_direction;
    state_ = DEVICE_ARMED;
    DeviceReplyV2 r = arm_ack(f, 0, state_, active_token_, active_direction_, false);
    cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 arm_ack(const FrameView& f, uint8_t result, DeviceStateV2 state,
                        uint16_t token, uint8_t direction, bool cache) {
    DeviceReplyV2 r = blank_reply(f, ARM_ACK);
    r.payload[0] = result;
    r.payload[1] = (uint8_t)state;
    write_u16(r.payload + 2, token);
    r.payload[4] = direction;
    r.payload_length = 5;
    if (cache) cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 handle_disarm(const FrameView& f) {
    if (!session_bound_ || !same_session(session_uuid_, f.session_uuid) ||
        f.device_epoch_tag != epoch_tag_for_boot_id(boot_id64_))
      return disarm_ack(f, 1, state_, read_u16(f.payload), false);
    uint8_t old_type = 0, old_payload[5] = {0}, old_length = 0;
    bool conflict = false;
    if (find_cached(f, &old_type, old_payload, &old_length, &conflict))
      return cached_or_error(f, DISARM_ACK);
    if (conflict || !command_is_fresh(f))
      return error_reply(f, conflict ? DEVICE_ERR_ID_CONFLICT : DEVICE_ERR_COMMAND_ID);
    const uint16_t token = read_u16(f.payload);
    if ((state_ != DEVICE_ARMED && state_ != DEVICE_RUNNING) || token == 0 || token != active_token_)
      return disarm_ack(f, 2, state_, token, true);
    if (!outputs_safe()) {
      state_ = DEVICE_FAULT;
      return disarm_ack(f, 2, state_, token, true);
    }
    state_ = DEVICE_IDLE; // Session and command high-water remain bound for the next stage.
    DeviceReplyV2 r = disarm_ack(f, 0, state_, token, false);
    cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 disarm_ack(const FrameView& f, uint8_t result, DeviceStateV2 state,
                           uint16_t token, bool cache) {
    DeviceReplyV2 r = blank_reply(f, DISARM_ACK);
    r.payload[0] = result; r.payload[1] = (uint8_t)state;
    write_u16(r.payload + 2, token); r.payload_length = 4;
    if (cache) cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 handle_pwm(const FrameView& f) {
    if (!session_bound_ || !same_session(session_uuid_, f.session_uuid) ||
        f.device_epoch_tag != epoch_tag_for_boot_id(boot_id64_))
      return apply_ack(f, 2, 0, read_u16(f.payload + 1), false);
    uint8_t old_type = 0, old_payload[5] = {0}, old_length = 0;
    bool conflict = false;
    if (find_cached(f, &old_type, old_payload, &old_length, &conflict))
      return cached_or_error(f, APPLY_ACK);
    if (conflict || !command_is_fresh(f))
      return error_reply(f, conflict ? DEVICE_ERR_ID_CONFLICT : DEVICE_ERR_COMMAND_ID);
    const uint8_t pwm = f.payload[0];
    const uint16_t token = read_u16(f.payload + 1);
    if (state_ != DEVICE_ARMED && state_ != DEVICE_RUNNING)
      return apply_ack(f, 3, 0, token, true);
    if (token == 0 || token != active_token_)
      return apply_ack(f, 4, 0, token, true);
    if (pwm != 0 && (state_ == DEVICE_STOP_LATCHED || state_ == DEVICE_STOPPED ||
                     state_ == DEVICE_FAULT || state_ == DEVICE_FAULT_STOP))
      return apply_ack(f, 5, 0, token, true);
    if (!output_.set_pwm(pwm)) {
      outputs_safe();
      state_ = DEVICE_FAULT;
      return apply_ack(f, 6, 0, token, true);
    }
    active_pwm_ = pwm;
    state_ = pwm == 0 ? DEVICE_ARMED : DEVICE_RUNNING;
    DeviceReplyV2 r = apply_ack(f, 0, pwm, token, false);
    cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 apply_ack(const FrameView& f, uint8_t result, uint8_t pwm,
                          uint16_t token, bool cache) {
    DeviceReplyV2 r = blank_reply(f, APPLY_ACK);
    r.payload[0] = result;
    r.payload[1] = pwm;
    write_u16(r.payload + 2, token);
    r.payload_length = 4;
    if (cache) cache_command(f, r.message_type, r.payload, r.payload_length);
    return r;
  }
  DeviceReplyV2 handle_stop(const FrameView& f) {
    // Safety action is first: it is independent of session freshness/history capacity.
    const bool prior_fault = state_ == DEVICE_FAULT || state_ == DEVICE_FAULT_STOP ||
        state_ == DEVICE_BOOT_ID_INVALID;
    const bool safe = outputs_safe();
    if (!safe || prior_fault) state_ = DEVICE_FAULT_STOP;
    else state_ = DEVICE_STOPPED;
    const uint8_t relation = !session_bound_ ? 2 :
        (same_session(session_uuid_, f.session_uuid) ? 0 : 1);
    const uint8_t reason = f.payload[0];
    const uint16_t request_id = read_u16(f.payload + 1);
    uint8_t outcome = 0; // NEW_RECORDED
    bool found = false;
    for (uint8_t i = 0; i < 4; ++i) {
      StopHistoryEntry& e = stop_history_[i];
      if (!e.used || e.stop_request_id != request_id ||
          !same_session(e.session, f.session_uuid)) continue;
      found = true;
      outcome = e.stop_reason == reason ? 1 : 2; // DUPLICATE_MATCH / ID_CONFLICT
      break;
    }
    if (!found) {
      bool slot_found = false;
      for (uint8_t i = 0; i < 4; ++i) {
        if (!stop_history_[i].used) {
          StopHistoryEntry& e = stop_history_[i];
          e.used = true; memcpy(e.session, f.session_uuid, 16);
          e.stop_request_id = request_id; e.stop_reason = reason;
          slot_found = true; break;
        }
      }
      if (!slot_found) outcome = 3; // HISTORY_FULL_UNRECORDED
    }
    DeviceReplyV2 r = blank_reply(f, STOP_ACK);
    r.payload[0] = relation;
    r.payload[1] = outcome;
    r.payload[2] = (!safe || prior_fault) ? 1 : 2; // FAULT_STOP / STOPPED
    r.payload_length = 3;
    return r;
  }
};

} // namespace mini4wd310
