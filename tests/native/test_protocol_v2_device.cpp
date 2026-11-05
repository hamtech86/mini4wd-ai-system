#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../firmware/motor/ProtocolV2Device.h"

using namespace mini4wd310;

struct FakeOutput {
  uint8_t pwm;
  bool direction_low;
  bool reverse;
  uint32_t safe_calls;
  FakeOutput() : pwm(99), direction_low(false), reverse(false), safe_calls(0) {}
  bool safe_outputs() {
    pwm = 0;
    direction_low = true;
    ++safe_calls;
    return true;
  }
  bool set_direction(uint8_t direction) {
    if (pwm != 0 || direction > DIRECTION_REV) return false;
    direction_low = false; reverse = direction == DIRECTION_REV; return true;
  }
  bool set_pwm(uint8_t value) {
    if (direction_low) return false;
    pwm = value;
    return true;
  }
};

static FrameView frame(uint8_t type, const uint8_t* session, uint32_t epoch,
                       uint32_t command, uint8_t* payload, uint16_t length) {
  FrameView f;
  f.message_type = type;
  memcpy(f.session_uuid, session, 16);
  f.device_epoch_tag = epoch;
  f.command_id = command;
  f.payload = payload;
  f.payload_length = length;
  return f;
}

static void test_boot_hello_arm_pwm_and_stop_preemption() {
  FakeOutput output;
  ProtocolV2Device<FakeOutput> device(output, 7, 100);
  const uint8_t session_a[16] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  const uint8_t session_b[16] = {2,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  const uint32_t epoch = epoch_tag_for_boot_id(7);
  assert(device.state() == DEVICE_IDLE);
  assert(output.pwm == 0 && output.direction_low && output.safe_calls == 1);

  uint8_t hello_payload[8] = {0};
  write_u64(hello_payload, 0x1122334455667788ULL);
  DeviceReplyV2 hello = device.handle(frame(HELLO, session_a, 0, 0, hello_payload, 8));
  assert(hello.valid && hello.message_type == HELLO_ACK);
  assert(hello.epoch_tag == epoch && read_u64(hello.payload + 1) == 7);
  assert(read_u64(hello.payload + 9) == 0x1122334455667788ULL);
  assert(read_u64(hello.payload + 17) == 100);

  uint8_t arm_payload[4] = {0};
  write_u16(arm_payload, 1); arm_payload[2] = 0; arm_payload[3] = DIRECTION_FWD;
  DeviceReplyV2 arm = device.handle(frame(ARM, session_a, epoch, 1, arm_payload, 4));
  assert(arm.message_type == ARM_ACK && arm.payload[0] == 0);
  assert(arm.payload[1] == DEVICE_ARMED && read_u16(arm.payload + 2) == 1);
  assert(arm.payload[4] == DIRECTION_FWD && !output.direction_low && !output.reverse);
  assert(output.pwm == 0);

  uint8_t pwm_payload[3] = {12,0,0};
  write_u16(pwm_payload + 1, 1);
  DeviceReplyV2 applied = device.handle(frame(PWM_SET, session_a, epoch, 2, pwm_payload, 3));
  assert(applied.message_type == APPLY_ACK && applied.payload[0] == 0);
  assert(applied.payload[1] == 12 && output.pwm == 12);
  assert(device.state() == DEVICE_RUNNING);

  // Exact HELLO retry must not reset command freshness while running.
  DeviceReplyV2 hello_retry = device.handle(frame(HELLO, session_a, 0, 0, hello_payload, 8));
  assert(hello_retry.message_type == HELLO_ACK && hello_retry.payload[0] == 0);
  DeviceReplyV2 replay = device.handle(frame(PWM_SET, session_a, epoch, 2, pwm_payload, 3));
  assert(replay.message_type == APPLY_ACK && replay.payload[0] == 0);
  assert(output.pwm == 12);

  // A different UUID cannot orphan a currently running output.
  DeviceReplyV2 busy_hello = device.handle(frame(HELLO, session_b, 0, 0, hello_payload, 8));
  assert(busy_hello.message_type == HELLO_ACK && busy_hello.payload[0] == 3);
  assert(output.pwm == 12);

  // STOP must synchronously zero PWM and invalidate ARM before the next queued PWM.
  uint8_t stop_payload[3] = {1,0,0};
  write_u16(stop_payload + 1, 9);
  DeviceReplyV2 stopped = device.handle(frame(STOP_REQ, session_a, epoch, 3, stop_payload, 3));
  assert(stopped.message_type == STOP_ACK);
  assert(stopped.payload[0] == 0 && stopped.payload[1] == 0 && stopped.payload[2] == 2);
  assert(output.pwm == 0 && output.direction_low);
  assert(device.state() == DEVICE_STOPPED && device.active_context_token() == 0);

  pwm_payload[0] = 20;
  DeviceReplyV2 queued = device.handle(frame(PWM_SET, session_a, epoch, 4, pwm_payload, 3));
  assert(queued.message_type == APPLY_ACK && queued.payload[0] != 0);
  assert(output.pwm == 0 && device.state() == DEVICE_STOPPED);

  // A new UUID may be bound after STOP, but STOP remains terminal until reset.
  DeviceReplyV2 new_hello = device.handle(frame(HELLO, session_b, 0, 0, hello_payload, 8));
  assert(new_hello.message_type == HELLO_ACK && new_hello.payload[0] == 0);
  write_u16(arm_payload, 2); arm_payload[3] = DIRECTION_REV;
  DeviceReplyV2 new_arm = device.handle(frame(ARM, session_b, epoch, 1, arm_payload, 4));
  assert(new_arm.message_type == ARM_ACK && new_arm.payload[0] != 0);
  assert(output.pwm == 0 && output.direction_low && device.state() == DEVICE_STOPPED);

}

static void test_duplicate_and_conflicting_stop_history() {
  FakeOutput output;
  ProtocolV2Device<FakeOutput> device(output, 3, 0);
  const uint8_t session[16] = {9,8,7,6,5,4,3,2,1,1,2,3,4,5,6,7};
  uint8_t hello_payload[8] = {0}; write_u64(hello_payload, 1);
  device.handle(frame(HELLO, session, 0, 0, hello_payload, 8));
  const uint32_t epoch = epoch_tag_for_boot_id(3);
  uint8_t stop[3] = {1,0,0}; write_u16(stop + 1, 44);
  DeviceReplyV2 first = device.handle(frame(STOP_REQ, session, epoch, 1, stop, 3));
  DeviceReplyV2 duplicate = device.handle(frame(STOP_REQ, session, epoch, 2, stop, 3));
  assert(first.payload[1] == 0 && duplicate.payload[1] == 1);
  stop[0] = 2;
  DeviceReplyV2 conflict = device.handle(frame(STOP_REQ, session, epoch, 3, stop, 3));
  assert(conflict.payload[1] == 2);
  assert(output.pwm == 0 && device.state() == DEVICE_STOPPED);
}

static void test_invalid_boot_never_arms() {
  FakeOutput output;
  ProtocolV2Device<FakeOutput> device(output, 0, 0);
  const uint8_t session[16] = {1};
  uint8_t hello_payload[8] = {0}; write_u64(hello_payload, 1);
  DeviceReplyV2 hello = device.handle(frame(HELLO, session, 0, 0, hello_payload, 8));
  assert(hello.message_type == HELLO_ACK && hello.payload[0] != 0);
  assert(device.state() == DEVICE_BOOT_ID_INVALID);
  assert(output.pwm == 0);
}


static void test_disarm_keeps_session_and_allows_direction_change() {
  FakeOutput output;
  ProtocolV2Device<FakeOutput> device(output, 11, 0);
  const uint8_t session[16] = {3,2,1,4,5,6,7,8,9,10,11,12,13,14,15,16};
  const uint32_t epoch = epoch_tag_for_boot_id(11);
  uint8_t hello[8] = {0}; write_u64(hello, 7);
  device.handle(frame(HELLO, session, 0, 0, hello, 8));
  uint8_t arm_fwd[4] = {0}; write_u16(arm_fwd, 10); arm_fwd[3] = DIRECTION_FWD;
  DeviceReplyV2 a = device.handle(frame(ARM, session, epoch, 1, arm_fwd, 4));
  assert(a.message_type == ARM_ACK && a.payload[0] == 0 && a.payload[4] == DIRECTION_FWD);
  uint8_t pwm[3] = {15,0,0}; write_u16(pwm + 1, 10);
  DeviceReplyV2 p = device.handle(frame(PWM_SET, session, epoch, 2, pwm, 3));
  assert(p.message_type == APPLY_ACK && p.payload[0] == 0 && output.pwm == 15);
  uint8_t disarm[2] = {0}; write_u16(disarm, 10);
  DeviceReplyV2 d = device.handle(frame(DISARM, session, epoch, 3, disarm, 2));
  assert(d.message_type == DISARM_ACK && d.payload[0] == 0 && d.payload[1] == DEVICE_IDLE);
  assert(read_u16(d.payload + 2) == 10 && output.pwm == 0 && output.direction_low);
  assert(device.state() == DEVICE_IDLE && device.active_context_token() == 0);
  uint8_t arm_rev[4] = {0}; write_u16(arm_rev, 11); arm_rev[3] = DIRECTION_REV;
  DeviceReplyV2 r = device.handle(frame(ARM, session, epoch, 4, arm_rev, 4));
  assert(r.message_type == ARM_ACK && r.payload[0] == 0 && r.payload[4] == DIRECTION_REV);
  assert(output.pwm == 0 && output.reverse && !output.direction_low);
  uint8_t stop[3] = {1,0,0}; write_u16(stop + 1, 1);
  DeviceReplyV2 s = device.handle(frame(STOP_REQ, session, epoch, 5, stop, 3));
  assert(s.message_type == STOP_ACK && output.pwm == 0 && output.direction_low);
  uint8_t disarm2[2] = {0}; write_u16(disarm2, 11);
  DeviceReplyV2 after_stop = device.handle(frame(DISARM, session, epoch, 6, disarm2, 2));
  assert(after_stop.message_type == DISARM_ACK && after_stop.payload[0] != 0);
  uint8_t arm_again[4] = {0}; write_u16(arm_again, 12); arm_again[3] = DIRECTION_FWD;
  DeviceReplyV2 forbidden = device.handle(frame(ARM, session, epoch, 7, arm_again, 4));
  assert(forbidden.message_type == ARM_ACK && forbidden.payload[0] != 0);
  assert(output.pwm == 0 && output.direction_low);
}

static void test_sample_sequence_allocator_is_monotonic_and_fails_closed() {
  FakeOutput output;
  ProtocolV2Device<FakeOutput> device(output, 21, 0);
  uint64_t value = 99;
  assert(device.allocate_sample_sequence64(&value));
  assert(value == 0 && device.next_sample_sequence64() == 1);
  assert(device.allocate_sample_sequence64(&value));
  assert(value == 1 && device.next_sample_sequence64() == 2);

  FakeOutput exhausted_output;
  ProtocolV2Device<FakeOutput> exhausted(exhausted_output, 22, UINT64_MAX);
  assert(!exhausted.allocate_sample_sequence64(&value));
  assert(exhausted.state() == DEVICE_FAULT_STOP);
  assert(exhausted_output.pwm == 0 && exhausted_output.direction_low);
}


int main() {
  test_boot_hello_arm_pwm_and_stop_preemption();
  test_duplicate_and_conflicting_stop_history();
  test_invalid_boot_never_arms();
  test_disarm_keeps_session_and_allows_direction_change();
  test_sample_sequence_allocator_is_monotonic_and_fails_closed();
  return 0;
}
