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
                            batch_building_(false), batch_count_(0), failed_(false) {
    memset(tx_buffer_, 0, sizeof(tx_buffer_));
    memset(&pending_, 0, sizeof(pending_));
  }

  bool failed() const { return failed_; }
  bool busy() const { return batch_building_ || tx_offset_ < tx_length_ || pending_valid_; }
  bool batch_building() const { return batch_building_; }
  uint16_t remaining() const {
    return tx_offset_ < tx_length_ ? (uint16_t)(tx_length_ - tx_offset_) : 0;
  }

  bool enqueue(const DeviceReplyV2& reply) {
    if (!reply.valid || reply.payload_length > sizeof(reply.payload)) return false;
    if (batch_building_ || tx_offset_ < tx_length_ || pending_valid_) {
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
    tx_offset_ = tx_length_ = 0;
    return encode(reply);
  }

  // Acquire the single TX workspace and build ADC_BATCH directly in its
  // payload area. No RX-workspace staging copy or second batch buffer exists.
  bool begin_adc_batch(uint64_t first_sequence, uint8_t loss_snapshot) {
    if (failed_ || busy()) return false;
    batch_building_ = true;
    batch_count_ = 0;
    tx_length_ = tx_offset_ = 0;
    uint8_t* payload = tx_buffer_ + 1 + kHeaderSize;
    memset(payload, 0, kAdcBatchPayloadSize);
    write_u64(payload, first_sequence);
    payload[8] = 0;
    payload[9] = 12;
    payload[10] = loss_snapshot;
    return true;
  }

  bool append_adc_sample(uint32_t timestamp_us, uint8_t channel_code,
                         uint16_t adc_raw, uint16_t stage_context_token,
                         uint8_t acquisition_status, uint16_t sample_flags) {
    if (!batch_building_ || batch_count_ >= 12 || channel_code > 5 ||
        acquisition_status > 3 || sample_flags != 0 ||
        (acquisition_status == 0 && adc_raw > 1023) ||
        (acquisition_status != 0 && adc_raw != 0xFFFF)) return false;
    uint8_t* sample = tx_buffer_ + 1 + kHeaderSize + 11 +
                      static_cast<uint16_t>(batch_count_) * 12;
    write_u32(sample, timestamp_us);
    sample[4] = channel_code;
    write_u16(sample + 5, adc_raw);
    write_u16(sample + 7, stage_context_token);
    sample[9] = acquisition_status;
    write_u16(sample + 10, sample_flags);
    ++batch_count_;
    return true;
  }

  bool finish_adc_batch(const uint8_t* session, uint32_t epoch_tag) {
    if (!batch_building_ || batch_count_ != 12 || !session) return false;
    batch_building_ = false;
    batch_count_ = 0;
    // A control reply that arrived during assembly wins. The sample sequence
    // remains consumed; caller records the whole-batch loss and gap.
    if (pending_valid_) return false;
    const uint8_t* payload = tx_buffer_ + 1 + kHeaderSize;
    if (!validate_header(ADC_BATCH, session, epoch_tag, 0) ||
        !validate_payload(ADC_BATCH, payload, kAdcBatchPayloadSize, epoch_tag)) {
      tx_length_ = tx_offset_ = 0;
      return false;
    }
    if (!encode_frame_in_place(ADC_BATCH, session, epoch_tag, 0,
                               tx_buffer_, kAdcBatchPayloadSize,
                               sizeof(tx_buffer_), &tx_length_)) {
      tx_length_ = tx_offset_ = 0;
      failed_ = true;
      return false;
    }
    tx_offset_ = 0;
    return true;
  }

  void abort_adc_batch() {
    if (!batch_building_) return;
    batch_building_ = false;
    batch_count_ = 0;
    tx_length_ = tx_offset_ = 0;
  }

  template <typename SerialLike>
  void service(SerialLike& serial) {
    if (failed_) return;
    if (batch_building_) {
      if (!pending_valid_) return;
      // A control reply arrived while ADC owned TX workspace; discard batch.
      batch_building_ = false;
      batch_count_ = 0;
      tx_length_ = tx_offset_ = 0;
    }
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
  uint8_t tx_buffer_[kMaxV2WireSize];
  uint16_t tx_length_;
  uint16_t tx_offset_;
  DeviceReplyV2 pending_;
  bool pending_valid_;
  bool batch_building_;
  uint8_t batch_count_;
  bool failed_;

  bool encode(const DeviceReplyV2& reply) {
    return encode_fields(reply.message_type, reply.session_uuid, reply.epoch_tag,
                         reply.command_id, reply.payload, reply.payload_length);
  }

  bool encode_fields(uint8_t type, const uint8_t* session, uint32_t epoch_tag,
                     uint32_t command_id, const uint8_t* payload, uint16_t length) {
    memset(tx_buffer_, 0, sizeof(tx_buffer_));
    memcpy(tx_buffer_ + 1 + kHeaderSize, payload, length);
    if (!encode_frame_in_place(type, session, epoch_tag, command_id,
                               tx_buffer_, length, sizeof(tx_buffer_), &tx_length_)) {
      tx_length_ = tx_offset_ = 0;
      failed_ = true;
      return false;
    }
    tx_offset_ = 0;
    return true;
  }
};

} // namespace mini4wd310
