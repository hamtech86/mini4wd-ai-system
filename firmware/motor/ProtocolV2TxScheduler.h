#pragma once
#include <stdint.h>
#include <string.h>
#include "ProtocolV2Codec.h"
#include "ProtocolV2Device.h"

namespace mini4wd310 {

// One TX wire workspace. A pending reply is stored as decoded fields only;
// no second full-frame buffer or unbounded queue is allocated.
class ProtocolV2TxScheduler {
 public:
  ProtocolV2TxScheduler() : tx_length_(0), tx_offset_(0), pending_valid_(false),
                            failed_(false) {
    memset(tx_buffer_, 0, sizeof(tx_buffer_));
    memset(&pending_, 0, sizeof(pending_));
  }

  bool failed() const { return failed_; }
  bool busy() const { return tx_offset_ < tx_length_ || pending_valid_; }
  uint16_t remaining() const {
    return tx_offset_ < tx_length_ ? (uint16_t)(tx_length_ - tx_offset_) : 0;
  }

  bool enqueue(const DeviceReplyV2& reply) {
    if (!reply.valid || reply.payload_length > sizeof(reply.payload)) return false;
    if (tx_offset_ >= tx_length_) {
      tx_offset_ = tx_length_ = 0;
      if (!pending_valid_) return encode(reply);
      if (reply.message_type == STOP_ACK && pending_.message_type != STOP_ACK) {
        pending_ = reply;
        return true;
      }
      return false;
    }
    if (!pending_valid_) {
      pending_ = reply;
      pending_valid_ = true;
      return true;
    }
    if (reply.message_type == STOP_ACK && pending_.message_type != STOP_ACK) {
      pending_ = reply; // STOP_ACK supersedes a pending lower-priority reply.
      return true;
    }
    return reply.message_type == STOP_ACK && pending_.message_type == STOP_ACK;
  }

  template <typename SerialLike>
  void service(SerialLike& serial) {
    if (failed_) return;
    if (tx_offset_ >= tx_length_) {
      tx_offset_ = tx_length_ = 0;
      if (pending_valid_) {
        DeviceReplyV2 next = pending_;
        pending_valid_ = false;
        memset(&pending_, 0, sizeof(pending_));
        if (!encode(next)) return;
      } else {
        return;
      }
    }
    const int available = serial.availableForWrite();
    if (available <= 0) return;
    uint16_t chunk = (uint16_t)available;
    if (chunk > kChunkMax) chunk = kChunkMax;
    const uint16_t left = (uint16_t)(tx_length_ - tx_offset_);
    if (chunk > left) chunk = left;
    if (chunk == 0) return;
    const size_t written = serial.write(tx_buffer_ + tx_offset_, chunk);
    if (written > chunk) {
      failed_ = true;
      return;
    }
    tx_offset_ = (uint16_t)(tx_offset_ + written);
  }

 private:
  static const uint8_t kChunkMax = 16;
  uint8_t tx_buffer_[kMaxWireSize];
  uint16_t tx_length_;
  uint16_t tx_offset_;
  DeviceReplyV2 pending_;
  bool pending_valid_;
  bool failed_;

  bool encode(const DeviceReplyV2& reply) {
    memset(tx_buffer_, 0, sizeof(tx_buffer_));
    memcpy(tx_buffer_ + 1 + kHeaderSize, reply.payload, reply.payload_length);
    if (!encode_frame_in_place(reply.message_type, reply.session_uuid,
                               reply.epoch_tag, reply.command_id,
                               tx_buffer_, reply.payload_length,
                               sizeof(tx_buffer_), &tx_length_)) {
      tx_length_ = tx_offset_ = 0;
      failed_ = true;
      return false;
    }
    tx_offset_ = 0;
    return true;
  }
};

} // namespace mini4wd310
