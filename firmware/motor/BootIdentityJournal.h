#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace mini4wd310 {

static const uint16_t kBootJournalBase = 0;
static const uint8_t kBootJournalSlots = 16;
static const uint8_t kBootJournalSlotSize = 16;
static const uint16_t kBootJournalBytes = 256;
static const uint16_t kProvisionRecordBase = 256;
static const uint8_t kProvisionRecordSize = 4;
static const uint8_t kBootJournalMagic = 0x42;   // ASCII 'B'
static const uint8_t kBootJournalVersion = 0x01;
static const uint8_t kBootMarkerInvalid = 0x00;
static const uint8_t kBootMarkerCommitted = 0xA5;

enum BootIdentityStatus : uint8_t {
  BOOT_ID_OK = 0,
  BOOT_ID_INVALID = 1,
  BOOT_ID_EXHAUSTED = 2
};

struct BootIdentityResult {
  BootIdentityStatus status;
  uint64_t boot_id64;
  uint8_t committed_slot;
};

static inline uint8_t crc8_atm(const uint8_t* data, uint8_t length) {
  uint8_t crc = 0;
  for (uint8_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit)
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
  }
  return crc;
}

static inline void make_boot_provision_record(uint8_t record[4]) {
  record[0] = 0x50;
  record[1] = 0x52;
  record[2] = 0x01;
  record[3] = crc8_atm(record, 3);
}

static inline bool boot_provision_record_valid(const uint8_t record[4]) {
  return record[0] == 0x50 && record[1] == 0x52 && record[2] == 0x01 &&
         record[3] == crc8_atm(record, 3);
}

static inline uint16_t boot_crc16(const uint8_t* data, uint8_t length) {
  uint16_t crc = 0xFFFF;
  for (uint8_t i = 0; i < length; ++i) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; ++bit)
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
  }
  return crc;
}

template <typename Storage>
class BootIdentityJournal {
 public:
  explicit BootIdentityJournal(Storage& storage) : storage_(storage) {}

  BootIdentityResult begin() {
    uint64_t highest = 0;
    uint8_t highest_slot = 0;
    bool found = false;
    if (!scan(&highest, &highest_slot, &found)) return result(BOOT_ID_INVALID, 0, 0);

    if (!found) {
      if (!provisioning_valid() || !journal_is_erased())
        return result(BOOT_ID_INVALID, 0, 0);
      if (!write_slot(0, 1)) return result(BOOT_ID_INVALID, 0, 0);
      uint64_t verify_generation = 0;
      uint8_t verify_slot = 0;
      bool verify_found = false;
      if (!scan(&verify_generation, &verify_slot, &verify_found) ||
          !verify_found || verify_generation != 1 || verify_slot != 0)
        return result(BOOT_ID_INVALID, 0, 0);
      return result(BOOT_ID_OK, 1, 0);
    }

    if (highest == UINT64_MAX) return result(BOOT_ID_EXHAUSTED, 0, highest_slot);
    const uint64_t next_generation = highest + 1;
    const uint8_t target = (uint8_t)((highest_slot + 1) % kBootJournalSlots);
    if (!write_slot(target, next_generation))
      return result(BOOT_ID_INVALID, 0, target);

    uint64_t verify_generation = 0;
    uint8_t verify_slot = 0;
    bool verify_found = false;
    if (!scan(&verify_generation, &verify_slot, &verify_found) ||
        !verify_found || verify_generation != next_generation || verify_slot != target)
      return result(BOOT_ID_INVALID, 0, target);
    return result(BOOT_ID_OK, next_generation, target);
  }

 private:
  Storage& storage_;

  static BootIdentityResult result(BootIdentityStatus status, uint64_t id, uint8_t slot) {
    BootIdentityResult r;
    r.status = status; r.boot_id64 = id; r.committed_slot = slot;
    return r;
  }

  uint16_t slot_address(uint8_t slot) const {
    return (uint16_t)slot * kBootJournalSlotSize;
  }

  bool provisioning_valid() const {
    uint8_t record[4];
    for (uint8_t i = 0; i < 4; ++i) record[i] = storage_.read(kProvisionRecordBase + i);
    return boot_provision_record_valid(record);
  }

  bool journal_is_erased() const {
    for (uint16_t address = 0; address < kBootJournalBytes; ++address)
      if (storage_.read(address) != 0xFF) return false;
    return true;
  }

  bool read_valid_slot(uint8_t slot, uint64_t* generation) const {
    uint8_t bytes[16];
    const uint16_t base = slot_address(slot);
    for (uint8_t i = 0; i < 16; ++i) bytes[i] = storage_.read(base + i);
    if (bytes[15] != kBootMarkerCommitted ||
        bytes[0] != kBootJournalMagic ||
        bytes[1] != kBootJournalVersion ||
        bytes[10] != 0 || bytes[11] != 0 || bytes[12] != 0)
      return false;
    if (boot_crc16(bytes, 13) !=
        ((uint16_t)bytes[13] | ((uint16_t)bytes[14] << 8)))
      return false;
    uint64_t value = 0;
    for (uint8_t i = 0; i < 8; ++i) value |= (uint64_t)bytes[2 + i] << (8 * i);
    if (value == 0) return false;
    *generation = value;
    return true;
  }

  bool scan(uint64_t* highest, uint8_t* highest_slot, bool* found) const {
    *highest = 0; *highest_slot = 0; *found = false;
    for (uint8_t i = 0; i < kBootJournalSlots; ++i) {
      uint64_t value = 0;
      if (!read_valid_slot(i, &value)) continue;
      // A generation must identify exactly one committed slot.
      for (uint8_t j = 0; j < i; ++j) {
        uint64_t prior = 0;
        if (read_valid_slot(j, &prior) && prior == value) return false;
      }
      if (!*found || value > *highest) {
        *highest = value;
        *highest_slot = i;
        *found = true;
      }
    }
    return true;
  }

  bool write_slot(uint8_t slot, uint64_t generation) {
    const uint16_t base = slot_address(slot);
    if (!storage_.write(base + 15, kBootMarkerInvalid) ||
        storage_.read(base + 15) != kBootMarkerInvalid)
      return false;

    uint8_t bytes[15];
    bytes[0] = kBootJournalMagic;
    bytes[1] = kBootJournalVersion;
    for (uint8_t i = 0; i < 8; ++i) bytes[2 + i] = (uint8_t)(generation >> (8 * i));
    bytes[10] = 0; bytes[11] = 0; bytes[12] = 0;
    const uint16_t crc = boot_crc16(bytes, 13);
    bytes[13] = (uint8_t)crc;
    bytes[14] = (uint8_t)(crc >> 8);

    for (uint8_t i = 0; i < 15; ++i)
      if (!storage_.write(base + i, bytes[i])) return false;
    for (uint8_t i = 0; i < 15; ++i)
      if (storage_.read(base + i) != bytes[i]) return false;

    if (!storage_.write(base + 15, kBootMarkerCommitted) ||
        storage_.read(base + 15) != kBootMarkerCommitted)
      return false;
    return true;
  }
};

} // namespace mini4wd310
