#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../firmware/motor/BootIdentityJournal.h"

using namespace mini4wd310;

class MemoryStorage {
 public:
  uint8_t bytes[260];
  int writes;
  int fail_at;
  bool write_then_fail;
  MemoryStorage() : writes(0), fail_at(-1), write_then_fail(false) {
    memset(bytes, 0xFF, sizeof(bytes));
  }
  uint8_t read(uint16_t address) const { return address < sizeof(bytes) ? bytes[address] : 0; }
  bool write(uint16_t address, uint8_t value) {
    const int current = writes++;
    if (address >= sizeof(bytes)) return false;
    if (current == fail_at) {
      if (write_then_fail) bytes[address] = value;
      return false;
    }
    bytes[address] = value;
    return true;
  }
  void provision() {
    bytes[256] = 0x50; bytes[257] = 0x52; bytes[258] = 0x01;
    bytes[259] = crc8_atm(bytes + 256, 3);
  }
  void clear_fault() { writes = 0; fail_at = -1; write_then_fail = false; }
};

static void put_slot(MemoryStorage& storage, uint8_t slot, uint64_t generation) {
  uint8_t* p = storage.bytes + (uint16_t)slot * 16;
  p[0] = kBootJournalMagic;
  p[1] = kBootJournalVersion;
  for (uint8_t i = 0; i < 8; ++i) p[2 + i] = (uint8_t)(generation >> (8 * i));
  p[10] = p[11] = p[12] = 0;
  const uint16_t crc = boot_crc16(p, 13);
  p[13] = (uint8_t)crc; p[14] = (uint8_t)(crc >> 8);
  p[15] = kBootMarkerCommitted;
}

static void test_first_and_normal_boot_increment() {
  MemoryStorage storage;
  storage.provision();
  BootIdentityJournal<MemoryStorage> journal(storage);
  BootIdentityResult first = journal.begin();
  assert(first.status == BOOT_ID_OK && first.boot_id64 == 1 && first.committed_slot == 0);
  BootIdentityResult second = journal.begin();
  assert(second.status == BOOT_ID_OK && second.boot_id64 == 2 && second.committed_slot == 1);
  BootIdentityResult third = journal.begin();
  assert(third.status == BOOT_ID_OK && third.boot_id64 == 3 && third.committed_slot == 2);
}

static void test_no_auto_provisioning_or_repair() {
  MemoryStorage storage;
  BootIdentityJournal<MemoryStorage> journal(storage);
  BootIdentityResult missing = journal.begin();
  assert(missing.status == BOOT_ID_INVALID);
  storage.provision();
  storage.bytes[20] = 0x00; // journal is not factory-erased
  BootIdentityResult damaged_empty = journal.begin();
  assert(damaged_empty.status == BOOT_ID_INVALID);
}

static void test_corrupt_all_slots_is_invalid() {
  MemoryStorage storage;
  storage.provision();
  BootIdentityJournal<MemoryStorage> journal(storage);
  assert(journal.begin().status == BOOT_ID_OK);
  memset(storage.bytes, 0, 256); // destroys all committed records
  BootIdentityResult result = journal.begin();
  assert(result.status == BOOT_ID_INVALID);
}

static void test_duplicate_generation_is_invalid() {
  MemoryStorage storage;
  put_slot(storage, 0, 7);
  put_slot(storage, 1, 7);
  BootIdentityJournal<MemoryStorage> journal(storage);
  assert(journal.begin().status == BOOT_ID_INVALID);
}

static void test_generation_exhaustion_fails_closed() {
  MemoryStorage storage;
  put_slot(storage, 0, UINT64_MAX);
  BootIdentityJournal<MemoryStorage> journal(storage);
  BootIdentityResult result = journal.begin();
  assert(result.status == BOOT_ID_EXHAUSTED);
}

static void test_write_failure_boundaries_do_not_reuse_committed_id() {
  MemoryStorage baseline;
  baseline.provision();
  BootIdentityJournal<MemoryStorage> initial(baseline);
  assert(initial.begin().boot_id64 == 1);

  // One marker invalidation + 15 payload writes + final marker commit.
  for (int fail = 0; fail < 17; ++fail) {
    for (int ambiguous = 0; ambiguous < 2; ++ambiguous) {
      MemoryStorage trial = baseline;
      trial.clear_fault();
      trial.fail_at = fail;
      trial.write_then_fail = ambiguous != 0;
      BootIdentityJournal<MemoryStorage> attempt(trial);
      BootIdentityResult failed = attempt.begin();
      assert(failed.status == BOOT_ID_INVALID);

      trial.clear_fault();
      BootIdentityJournal<MemoryStorage> recovery(trial);
      BootIdentityResult recovered = recovery.begin();
      assert(recovered.status == BOOT_ID_OK);
      if (fail == 16 && ambiguous) {
        // Commit marker reached storage despite an ambiguous return; it is
        // discovered on restart and the next boot generation is burned.
        assert(recovered.boot_id64 == 3);
      } else {
        assert(recovered.boot_id64 == 2);
      }
    }
  }
}

int main() {
  test_first_and_normal_boot_increment();
  test_no_auto_provisioning_or_repair();
  test_corrupt_all_slots_is_invalid();
  test_duplicate_generation_is_invalid();
  test_generation_exhaustion_fails_closed();
  test_write_failure_boundaries_do_not_reuse_committed_id();
  return 0;
}
