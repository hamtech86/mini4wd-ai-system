#ifndef MINI4WD_WINDING_HARDWARE_ADAPTER_H
#define MINI4WD_WINDING_HARDWARE_ADAPTER_H

#include <stdint.h>

// This API is deliberately fail-closed. It is not a GPIO implementation.
// A future board-specific adapter must not replace this disabled adapter until
// independent current limiting, output-OFF readback, interlocks, and timing have
// been verified on the actual hardware.
namespace WindingHardware {

enum AdapterStatus : uint8_t {
    ADAPTER_DISABLED = 0,
    ADAPTER_REFUSED,
    ADAPTER_FAULT
};

struct PulseRequest {
    uint32_t durationMs;
};

class DisabledAdapter {
public:
    DisabledAdapter() : status_(ADAPTER_DISABLED) {}

    // No motor-power pin is touched. The request is always refused.
    AdapterStatus requestInjection(const PulseRequest &) {
        forceOutputsOff();
        status_ = ADAPTER_REFUSED;
        return status_;
    }

    // Safe stub: there are no enabled outputs to drive. Returns false because
    // physical OFF readback is unavailable and must never be inferred.
    bool forceOutputsOff() {
        status_ = ADAPTER_DISABLED;
        return false;
    }

    AdapterStatus status() const { return status_; }

private:
    AdapterStatus status_;
};

} // namespace WindingHardware
#endif
