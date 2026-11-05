#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../firmware/motor/ProtocolV2Codec.h"

using namespace mini4wd310;

static void test_crc_vector() {
  const uint8_t input[] = {'1','2','3','4','5','6','7','8','9'};
  assert(crc16_ccitt_false(input, 9) == 0x29B1);
}

static void test_hello_round_trip() {
  uint8_t tx[kMaxWireSize] = {0};
  uint8_t session[16] = {
    0x12,0x34,0x56,0x78,0x12,0x34,0x56,0x78,
    0x9A,0xBC,0xDE,0xF0,0x12,0x34,0x56,0x78
  };
  uint8_t* payload = tx + 1 + kHeaderSize;
  write_u64(payload, 0x0102030405060708ULL);
  uint16_t wire_length = 0;
  assert(encode_frame_in_place(HELLO, session, 0, 0, tx, 8,
                               sizeof(tx), &wire_length));
  assert(wire_length <= kMaxWireSize && tx[wire_length - 1] == 0);
  uint8_t rx[kMaxWireSize] = {0};
  memcpy(rx, tx, wire_length - 1);
  FrameView frame;
  assert(decode_frame_in_place(rx, wire_length - 1, &frame));
  assert(frame.message_type == HELLO);
  assert(memcmp(frame.session_uuid, session, 16) == 0);
  assert(frame.device_epoch_tag == 0 && frame.command_id == 0);
  assert(frame.payload_length == 8);
  assert(read_u64(frame.payload) == 0x0102030405060708ULL);
}

static void fill_adc_payload(uint8_t* p, uint64_t first) {
  write_u64(p, first);
  p[8] = 0; p[9] = 12; p[10] = 0;
  for (uint8_t i = 0; i < 12; ++i) {
    uint8_t* sample = p + 11 + (uint16_t)i * 12;
    write_u32(sample, 1000UL + i);
    sample[4] = i % 6;
    write_u16(sample + 5, 512);
    write_u16(sample + 7, (uint16_t)(i + 1));
    sample[9] = 0;
    write_u16(sample + 10, 0);
  }
}

static void test_adc_batch_round_trip_and_size() {
  uint8_t tx[kMaxWireSize] = {0};
  uint8_t session[16] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  fill_adc_payload(tx + 1 + kHeaderSize, 0x100000001ULL);
  uint16_t wire_length = 0;
  assert(encode_frame_in_place(ADC_BATCH, session, 1, 0, tx,
                               kAdcBatchPayloadSize, sizeof(tx), &wire_length));
  assert(wire_length <= 188);
  uint8_t rx[kMaxWireSize] = {0};
  memcpy(rx, tx, wire_length - 1);
  FrameView frame;
  assert(decode_frame_in_place(rx, wire_length - 1, &frame));
  assert(frame.message_type == ADC_BATCH);
  assert(read_u64(frame.payload) == 0x100000001ULL);
  assert(frame.payload[9] == 12);
  assert(frame.payload_length == kAdcBatchPayloadSize);
}

static void test_reject_uint64_exhaustion_batch() {
  uint8_t tx[kMaxWireSize] = {0};
  uint8_t session[16] = {1};
  fill_adc_payload(tx + 1 + kHeaderSize, UINT64_MAX - 11ULL);
  uint16_t wire_length = 0;
  assert(!encode_frame_in_place(ADC_BATCH, session, 1, 0, tx,
                                kAdcBatchPayloadSize, sizeof(tx), &wire_length));
}

static void test_reject_zero_session_and_wrong_version() {
  uint8_t tx[kMaxWireSize] = {0};
  uint8_t zero_session[16] = {0};
  write_u64(tx + 1 + kHeaderSize, 1);
  uint16_t wire_length = 0;
  assert(!encode_frame_in_place(HELLO, zero_session, 0, 0, tx, 8,
                                sizeof(tx), &wire_length));
}

int main() {
  test_crc_vector();
  test_hello_round_trip();
  test_adc_batch_round_trip_and_size();
  test_reject_uint64_exhaustion_batch();
  test_reject_zero_session_and_wrong_version();
  return 0;
}
