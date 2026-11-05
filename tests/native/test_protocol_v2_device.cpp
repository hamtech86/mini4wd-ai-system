#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../firmware/motor/ProtocolV2Device.h"

using namespace mini4wd310;

struct FakeOutput {
  uint8_t pwm;
  bool direction_low;
  uint32_t safe_calls;
  FakeOutput() : pwm(99), direction_low(false), safe_calls(0) {}
  bool safe_outputs() {
    pwm = 0;
    direction_low = true;
    ++safe_calls;
    return true;
  }
  bool set_pwm(uint8_t value) {
    if (!direction_low) return false;
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

  uint8_t arm_payload[3] = {0};
  write_u16(arm_payload, 1); arm_payload[2] = 0;
  DeviceReplyV2 arm = device.handle(frame(ARM, session_a, epoch, 1, arm_payload, 3));
  assert(arm.message_type == ARM_ACK && arm.payload[0] == 0);
  assert(arm.payload[1] == DEVICE_ARMED && read_u16(arm.payload + 2) == 1);
  assert(output.pwm == 0);

  uint8_t pwm_payload[3] = {12,0,0};
  write_u16(pwm_payload + 1, 1);
  DeviceReplyV2 applied = device.handle(frame(PWM_SET, session_a, epoch, 2, pwm_payload, 3));
  assert(applied.message_type == APPLY_ACK && applied.payload[0] == 0);
  assert(applied.payload[1] == 12 && output.pwm == 12);
  assert(device.state() == DEVICE_RUNNING);

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

  // A new UUID/HELLO/ARM is required; the old session cannot re-drive output.
  DeviceReplyV2 new_hello = device.handle(frame(HELLO, session_b, 0, 0, hello_payload, 8));
  assert(new_hello.message_type == HELLO_ACK && new_hello.payload[0] == 0);
  write_u16(arm_payload, 2);
  DeviceReplyV2 new_arm = device.handle(frame(ARM, session_b, epoch, 1, arm_payload, 3));
  assert(new_arm.message_type == ARM_ACK && new_arm.payload[0] == 0);
  write_u16(pwm_payload + 1, 2);
  DeviceReplyV2 new_pwm = device.handle(frame(PWM_SET, session_b, epoch, 2, pwm_payload, 3));
  assert(new_pwm.message_type == APPLY_ACK && new_pwm.payload[0] == 0);
  assert(output.pwm == 20 && device.state() == DEVICE_RUNNING);

  DeviceReplyV2 stale = device.handle(frame(PWM_SET, session_a, epoch, 5, pwm_payload, 3));
  assert(stale.message_type == APPLY_ACK && stale.payload[0] != 0);
  assert(output.pwm == 20); // stale frame cannot alter the active session output
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

int main() {
  test_boot_hello_arm_pwm_and_stop_preemption();
  test_duplicate_and_conflicting_stop_history();
  test_invalid_boot_never_arms();
  return 0;
}
