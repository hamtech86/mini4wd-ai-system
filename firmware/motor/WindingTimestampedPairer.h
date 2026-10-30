#ifndef MINI4WD_WINDING_TIMESTAMPED_PAIRER_H
#define MINI4WD_WINDING_TIMESTAMPED_PAIRER_H

#include <stdint.h>
#include "WindingResistance.h"

// Pairs already-selected, calibrated voltage/current readings by acquisition
// time. This layer deliberately does not decide which physical ACS/voltage
// channels belong together; that mapping must come from the wiring contract.
namespace WindingTimestampedPairer {

enum PushStatus : uint8_t {
    NO_PAIR = 0,
    PAIR_READY,
    DROPPED_OLDER_VOLTAGE,
    DROPPED_OLDER_CURRENT,
    REPLACED_PENDING_VOLTAGE,
    REPLACED_PENDING_CURRENT
};

struct Reading {
    float value;
    uint32_t timestampUs;
};

struct Pair {
    WindingResistance::Sample sample;
    uint32_t voltageTimestampUs;
    uint32_t currentTimestampUs;
    uint32_t skewUs;
};

struct Collector {
    Reading voltage;
    Reading current;
    bool hasVoltage;
    bool hasCurrent;
    uint32_t pairedCount;
    uint32_t rejectedCount;
};

inline void initialize(Collector &c) {
    c.voltage = Reading{0.0f, 0};
    c.current = Reading{0.0f, 0};
    c.hasVoltage = false;
    c.hasCurrent = false;
    c.pairedCount = 0;
    c.rejectedCount = 0;
}

// Unsigned subtraction is intentional: it handles micros() rollover for
// intervals shorter than half the 32-bit timer range.
inline uint32_t distanceUs(uint32_t a, uint32_t b) {
    const uint32_t ab = a - b;
    const uint32_t ba = b - a;
    return ab < ba ? ab : ba;
}

inline bool isBefore(uint32_t a, uint32_t b) {
    return static_cast<int32_t>(a - b) < 0;
}

inline PushStatus tryPair(Collector &c, uint32_t maxSkewUs, Pair &out) {
    if (!c.hasVoltage || !c.hasCurrent) return NO_PAIR;
    const uint32_t skew = distanceUs(c.voltage.timestampUs,
                                     c.current.timestampUs);
    if (skew > maxSkewUs) {
        if (isBefore(c.voltage.timestampUs, c.current.timestampUs)) {
            c.hasVoltage = false;
            ++c.rejectedCount;
            return DROPPED_OLDER_VOLTAGE;
        }
        c.hasCurrent = false;
        ++c.rejectedCount;
        return DROPPED_OLDER_CURRENT;
    }
    out.sample = WindingResistance::Sample{c.voltage.value, c.current.value};
    out.voltageTimestampUs = c.voltage.timestampUs;
    out.currentTimestampUs = c.current.timestampUs;
    out.skewUs = skew;
    c.hasVoltage = false;
    c.hasCurrent = false;
    ++c.pairedCount;
    return PAIR_READY;
}

inline PushStatus pushVoltage(Collector &c, float value, uint32_t timestampUs,
                              uint32_t maxSkewUs, Pair &out) {
    PushStatus replacement = NO_PAIR;
    if (c.hasVoltage) {
        c.hasVoltage = false;
        ++c.rejectedCount;
        replacement = REPLACED_PENDING_VOLTAGE;
    }
    c.voltage = Reading{value, timestampUs};
    c.hasVoltage = true;
    const PushStatus pairing = tryPair(c, maxSkewUs, out);
    return pairing == NO_PAIR ? replacement : pairing;
}

inline PushStatus pushCurrent(Collector &c, float value, uint32_t timestampUs,
                              uint32_t maxSkewUs, Pair &out) {
    PushStatus replacement = NO_PAIR;
    if (c.hasCurrent) {
        c.hasCurrent = false;
        ++c.rejectedCount;
        replacement = REPLACED_PENDING_CURRENT;
    }
    c.current = Reading{value, timestampUs};
    c.hasCurrent = true;
    const PushStatus pairing = tryPair(c, maxSkewUs, out);
    return pairing == NO_PAIR ? replacement : pairing;
}

} // namespace WindingTimestampedPairer

#endif
