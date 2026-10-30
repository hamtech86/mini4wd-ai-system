#ifndef MINI4WD_WINDING_SAMPLE_AGGREGATOR_H
#define MINI4WD_WINDING_SAMPLE_AGGREGATOR_H

#include <stdint.h>
#include <math.h>
#include "WindingResistance.h"

// Fixed-memory aggregation for synchronized V/I measurement points.
// No hardware access, drive commands, or current injection is performed here.
namespace WindingSampleAggregator {

constexpr uint8_t MAX_POINTS = WindingResistance::MAX_SAMPLES;

enum AddStatus : uint8_t {
    ADD_ACCEPTED = 0,
    ADD_REJECTED_INVALID,
    ADD_REJECTED_FULL
};

struct Summary {
    bool valid;
    uint8_t count;
    WindingResistance::InvalidReason reason;
    float medianOhm;
    float minOhm;
    float maxOhm;
};

struct Collector {
    WindingResistance::Sample samples[MAX_POINTS];
    uint8_t count;
    bool sawInvalid;
    WindingResistance::InvalidReason firstInvalidReason;
};

inline void initialize(Collector &collector) {
    collector.count = 0;
    collector.sawInvalid = false;
    collector.firstInvalidReason = WindingResistance::VALID;
}

inline AddStatus add(Collector &collector,
                     const WindingResistance::Sample &sample,
                     const WindingResistance::Config &config) {
    // Validate each pair using the same formal calculation contract.
    const WindingResistance::Result check =
        WindingResistance::calculate(&sample, 1, config);
    if (!check.valid) {
        collector.sawInvalid = true;
        if (collector.firstInvalidReason == WindingResistance::VALID) {
            collector.firstInvalidReason = check.reason;
        }
        return ADD_REJECTED_INVALID;
    }
    if (collector.count >= MAX_POINTS) {
        collector.sawInvalid = true;
        if (collector.firstInvalidReason == WindingResistance::VALID) {
            collector.firstInvalidReason =
                WindingResistance::INVALID_SAMPLE_COUNT;
        }
        return ADD_REJECTED_FULL;
    }
    collector.samples[collector.count++] = sample;
    return ADD_ACCEPTED;
}

inline Summary summarize(const Collector &collector,
                         bool requireAllAcceptedPoints) {
    Summary summary = {
        false, collector.count, WindingResistance::INVALID_SAMPLE_COUNT,
        0.0f, 0.0f, 0.0f
    };
    if (collector.count == 0) {
        summary.reason = collector.sawInvalid
            ? collector.firstInvalidReason
            : WindingResistance::INVALID_SAMPLE_COUNT;
        return summary;
    }
    if (requireAllAcceptedPoints && collector.sawInvalid) {
        summary.reason = collector.firstInvalidReason;
        return summary;
    }

    // Config has already been applied on insertion; compute aggregate using
    // broad finite bounds and preserve sign/range checking in each accepted pair.
    const WindingResistance::Config aggregateConfig = {
        0.0f, 1.0e30f, 0.0f, 1.0e30f, 0.0f, 0.0f, 1.0e30f
    };
    const WindingResistance::Result result = WindingResistance::calculate(
        collector.samples, collector.count, aggregateConfig);
    if (!result.valid) {
        summary.reason = result.reason;
        return summary;
    }
    summary.valid = true;
    summary.reason = WindingResistance::VALID;
    summary.medianOhm = result.medianOhm;
    summary.minOhm = result.minOhm;
    summary.maxOhm = result.maxOhm;
    return summary;
}

} // namespace WindingSampleAggregator

#endif
