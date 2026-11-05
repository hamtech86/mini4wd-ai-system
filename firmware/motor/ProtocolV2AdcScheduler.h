#pragma once
#include <stdint.h>
namespace mini4wd310 {
class AdcCadenceScheduler {
 public:
  AdcCadenceScheduler() : next_scan_us_(0), channel_index_(0), state_(0) {}
  bool active() const { return (state_ & 1U) != 0; }
  void start(uint32_t now_us) { next_scan_us_=now_us; channel_index_=0; state_=1U; }
  void stop() { state_=0; channel_index_=0; }
  bool take_due(uint32_t now_us, uint8_t* channel, uint32_t* scheduled, bool* missing) {
    if (!active() || !channel || !scheduled || !missing) return false;
    if (static_cast<int32_t>(now_us-next_scan_us_) < 0) return false;
    const uint32_t interval=(state_ & 2U) ? 75000UL : 25000UL;
    *missing=static_cast<uint32_t>(now_us-next_scan_us_) >= interval;
    *scheduled=next_scan_us_;
    switch(channel_index_) {
      case 0: *channel=0; break;
      case 1: *channel=1; break;
      case 2: *channel=4; break;
      case 3: *channel=5; break;
      case 4: *channel=2; break;
      default: *channel=3; break;
    }
    if (++channel_index_ == 6) { channel_index_=0; next_scan_us_+=interval; state_^=2U; }
    return true;
  }
 private:
  uint32_t next_scan_us_;
  uint8_t channel_index_;
  uint8_t state_;
};
}
