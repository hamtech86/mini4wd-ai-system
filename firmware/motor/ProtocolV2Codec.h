#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Fixed-memory 310 protocol v2 codec. No Arduino dependency, heap, STL or VLA.
namespace mini4wd310 {

static const uint16_t kMagic = 0x344D;
static const uint8_t kVersion = 0x02;
static const uint16_t kHeaderSize = 29;
static const uint16_t kCrcSize = 2;
static const uint16_t kMaxWireSize = 194; // legacy/shared workspace ceiling
static const uint16_t kMaxV2WireSize = 188; // v2 ADC_BATCH maximum including delimiter
static const uint16_t kAdcBatchPayloadSize = 155;

enum MessageType : uint8_t {
  HELLO = 0x01, HELLO_ACK = 0x02, ARM = 0x03, ARM_ACK = 0x04,
  DISARM = 0x05, DISARM_ACK = 0x06,
  PWM_SET = 0x10, APPLY_ACK = 0x11, STOP_REQ = 0x20, STOP_ACK = 0x21,
  STATUS = 0x30, ERROR_MSG = 0x31, ADC_BATCH = 0x40
};

enum DriveDirectionV2 : uint8_t { DIRECTION_FWD = 0, DIRECTION_REV = 1 };

struct FrameView {
  uint8_t message_type;
  uint8_t session_uuid[16];
  uint32_t device_epoch_tag;
  uint32_t command_id;
  uint8_t* payload;
  uint16_t payload_length;
};

static inline uint16_t read_u16(const uint8_t* p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}
static inline uint32_t read_u32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline uint64_t read_u64(const uint8_t* p) {
  return (uint64_t)read_u32(p) | ((uint64_t)read_u32(p + 4) << 32);
}
static inline void write_u16(uint8_t* p, uint16_t v) {
  p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
}
static inline void write_u32(uint8_t* p, uint32_t v) {
  p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
  p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
static inline void write_u64(uint8_t* p, uint64_t v) {
  write_u32(p, (uint32_t)v); write_u32(p + 4, (uint32_t)(v >> 32));
}

static inline uint16_t crc16_ccitt_false(const uint8_t* data, uint16_t length) {
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < length; ++i) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

static inline bool uuid_is_zero(const uint8_t* uuid_bytes) {
  uint8_t aggregate = 0;
  for (uint8_t i = 0; i < 16; ++i) aggregate |= uuid_bytes[i];
  return aggregate == 0;
}

static inline uint16_t expected_payload_length(uint8_t type) {
  switch (type) {
    case HELLO: return 8;
    case HELLO_ACK: return 25;
    case ARM: return 4;
    case ARM_ACK: return 5;
    case DISARM: return 2;
    case DISARM_ACK: return 4;
    case PWM_SET: return 3;
    case APPLY_ACK: return 4;
    case STOP_REQ: return 3;
    case STOP_ACK: return 3;
    case STATUS: return 16;
    case ERROR_MSG: return 8;
    case ADC_BATCH: return kAdcBatchPayloadSize;
    default: return 0xFFFF;
  }
}

static inline uint32_t epoch_tag_for_boot_id(uint64_t boot_id) {
  uint32_t tag = (uint32_t)boot_id;
  return tag ? tag : 0xFFFFFFFFUL;
}

static inline bool validate_header(uint8_t type, const uint8_t* session,
                                   uint32_t epoch_tag, uint32_t command_id) {
  const bool zero_session_allowed =
      type == STOP_REQ || type == STOP_ACK || type == STATUS || type == ERROR_MSG;
  if (uuid_is_zero(session) && !zero_session_allowed) return false;
  const bool zero_command_allowed =
      type == HELLO || type == HELLO_ACK || type == STATUS ||
      type == ERROR_MSG || type == ADC_BATCH;
  if (zero_command_allowed ? command_id != 0 : command_id == 0) return false;
  if (type == HELLO && epoch_tag != 0) return false;
  if (type != HELLO && type != HELLO_ACK && type != STOP_REQ &&
      type != STOP_ACK && type != STATUS && type != ERROR_MSG && epoch_tag == 0) return false;
  return true;
}

static inline bool validate_payload(uint8_t type, const uint8_t* p, uint16_t n,
                                    uint32_t epoch_tag) {
  if (n != expected_payload_length(type)) return false;
  switch (type) {
    case HELLO:
      return read_u64(p) != 0;
    case HELLO_ACK: {
      const uint8_t result = p[0];
      const uint64_t boot = read_u64(p + 1);
      const uint64_t nonce = read_u64(p + 9);
      if (result > 4 || nonce == 0) return false;
      if (result == 0 && boot == 0) return false;
      if (result == 1 && boot != 0) return false; // BOOT_ID_INVALID
      if (boot && epoch_tag_for_boot_id(boot) != epoch_tag) return false;
      if (!boot && epoch_tag != 0) return false;
      return true;
    }
    case ARM:
      return read_u16(p) != 0 && p[2] == 0 && p[3] <= DIRECTION_REV;
    case ARM_ACK:
      return p[0] <= 6 && p[1] <= 7 &&
             (p[4] <= DIRECTION_REV || (p[0] != 0 && p[4] == 0xFF)) &&
             (p[0] != 0 || (p[1] == 1 && read_u16(p + 2) != 0));
    case DISARM:
      return read_u16(p) != 0;
    case DISARM_ACK:
      return p[0] <= 2 && p[1] <= 7 && read_u16(p + 2) != 0 &&
             (p[0] != 0 || p[1] == 0);
    case PWM_SET:
      return p[0] <= 30 && read_u16(p + 1) != 0;
    case APPLY_ACK:
      return p[0] <= 8 && p[1] <= 30 && read_u16(p + 2) != 0 &&
             (p[0] == 0 || p[1] == 0);
    case STOP_REQ:
      return p[0] != 0 && read_u16(p + 1) != 0;
    case STOP_ACK:
      return p[0] <= 2 && p[1] <= 4 && p[2] <= 2;
    case STATUS:
      return p[0] <= 7 && p[1] <= 30;
    case ERROR_MSG:
      return p[0] >= 1 && p[0] <= 14;
    case ADC_BATCH: {
      const uint64_t first = read_u64(p);
      if (p[8] != 0 || p[9] != 12) return false;
      if (first > UINT64_MAX - 12ULL) return false; // preserve representable next value
      for (uint8_t i = 0; i < 12; ++i) {
        const uint8_t* s = p + 11 + (uint16_t)i * 12;
        const uint8_t channel = s[4];
        const uint16_t raw = read_u16(s + 5);
        const uint8_t status = s[9];
        const uint16_t flags = read_u16(s + 10);
        if (channel > 5 || status > 3 || flags != 0) return false;
        if ((status == 0 && raw > 1023) || (status != 0 && raw != 0xFFFF)) return false;
      }
      return true;
    }
    default:
      return false;
  }
}

// Decode one delimiter-free COBS frame in place. The caller owns the RX workspace.
static inline bool decode_frame_in_place(uint8_t* buffer, uint16_t encoded_length,
                                         FrameView* out) {
  if (!buffer || !out || encoded_length == 0 || encoded_length >= kMaxWireSize) return false;
  uint16_t read = 0, write = 0;
  while (read < encoded_length) {
    const uint8_t code = buffer[read++];
    if (code == 0) return false;
    const uint16_t count = (uint16_t)code - 1;
    if ((uint32_t)read + count > encoded_length) return false;
    for (uint16_t i = 0; i < count; ++i) buffer[write++] = buffer[read++];
    if (code != 0xFF && read < encoded_length) buffer[write++] = 0;
  }
  const uint16_t decoded_length = write;
  if (decoded_length < kHeaderSize + kCrcSize) return false;
  const uint16_t body_length = decoded_length - kCrcSize;
  const uint16_t expected_crc = read_u16(buffer + body_length);
  if (crc16_ccitt_false(buffer, body_length) != expected_crc) return false;
  if (read_u16(buffer) != kMagic || buffer[2] != kVersion || buffer[4] != 0) return false;
  const uint8_t type = buffer[3];
  const uint16_t payload_length = body_length - kHeaderSize;
  if (payload_length != expected_payload_length(type)) return false;
  const uint32_t epoch = read_u32(buffer + 21);
  const uint32_t command = read_u32(buffer + 25);
  if (!validate_header(type, buffer + 5, epoch, command)) return false;
  if (!validate_payload(type, buffer + kHeaderSize, payload_length, epoch)) return false;
  out->message_type = type;
  memcpy(out->session_uuid, buffer + 5, 16);
  out->device_epoch_tag = epoch;
  out->command_id = command;
  out->payload = buffer + kHeaderSize;
  out->payload_length = payload_length;
  return true;
}

// Encode in place. Caller writes the payload at buffer + 1 + kHeaderSize.
// One leading byte is reserved so COBS expansion can be performed without a
// second 194-byte frame buffer or a large stack temporary.
static inline bool encode_frame_in_place(uint8_t type, const uint8_t* session,
                                         uint32_t epoch_tag, uint32_t command_id,
                                         uint8_t* buffer, uint16_t payload_length,
                                         uint16_t capacity, uint16_t* wire_length) {
  if (!buffer || !session || !wire_length || capacity < 2) return false;
  if (!validate_header(type, session, epoch_tag, command_id) ||
      !validate_payload(type, buffer + 1 + kHeaderSize, payload_length, epoch_tag)) return false;
  const uint16_t raw_length = kHeaderSize + payload_length + kCrcSize;
  if (raw_length + 2 > kMaxWireSize || raw_length + 2 > capacity) return false;
  uint8_t* raw = buffer + 1;
  write_u16(raw, kMagic);
  raw[2] = kVersion;
  raw[3] = type;
  raw[4] = 0;
  memcpy(raw + 5, session, 16);
  write_u32(raw + 21, epoch_tag);
  write_u32(raw + 25, command_id);
  const uint16_t crc = crc16_ccitt_false(raw, kHeaderSize + payload_length);
  write_u16(raw + kHeaderSize + payload_length, crc);

  // In-place COBS: raw starts one byte after the output origin.
  uint16_t read = 1;
  uint16_t write = 1;
  uint16_t code_index = 0;
  uint8_t code = 1;
  const uint16_t raw_end = (uint16_t)(1 + raw_length);
  while (read < raw_end) {
    const uint8_t value = buffer[read++];
    if (value == 0) {
      buffer[code_index] = code;
      code_index = write;
      buffer[write++] = 0;
      code = 1;
    } else {
      buffer[write++] = value;
      ++code;
      if (code == 0xFF) {
        buffer[code_index] = code;
        code_index = write;
        buffer[write++] = 0;
        code = 1;
      }
    }
  }
  buffer[code_index] = code;
  buffer[write++] = 0; // frame delimiter
  if (write > capacity || write > kMaxWireSize) return false;
  *wire_length = write;
  return true;
}

} // namespace mini4wd310
