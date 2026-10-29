#ifndef MINI4WD_WINDING_RESISTANCE_H
#define MINI4WD_WINDING_RESISTANCE_H

#include <stdint.h>
#include <math.h>

// Calculation-only layer. This module does not energize the motor or inject
// current. The caller must provide synchronized, calibrated V/I samples and
// must establish hardware current limiting before enabling any injection.
namespace WindingResistance {

constexpr uint8_t MAX_SAMPLES = 32;

enum InvalidReason : uint8_t {
    VALID = 0,
    INVALID_NULL_INPUT,
    INVALID_SAMPLE_COUNT,
    INVALID_NONFINITE,
    INVALID_VOLTAGE_RANGE,
    INVALID_CURRENT_RANGE,
    INVALID_CURRENT_RESOLUTION,
    INVALID_POLARITY,
    INVALID_RESISTANCE_RANGE
};

struct Sample {
    float voltageV;  // Signed motor-terminal voltage, measured synchronously.
    float currentA;  // Signed winding-path current, calibrated ACS712 value.
};

struct Config {
    float minVoltageV;
    float maxVoltageV;
    float minCurrentA;
    float maxCurrentA;
    float minCurrentResolutionA;
    float minResistanceOhm;
    float maxResistanceOhm;
};

struct Result {
    bool valid;
    InvalidReason reason;
    uint8_t validCount;
    float medianOhm;
    float minOhm;
    float maxOhm;
};

inline void sortAscending(float *values, uint8_t count) {
    for (uint8_t i = 1; i < count; ++i) {
        const float value = values[i];
        int8_t j = (int8_t)i - 1;
        while (j >= 0 && values[(uint8_t)j] > value) {
            values[(uint8_t)j + 1] = values[(uint8_t)j];
            --j;
        }
        values[(uint8_t)j + 1] = value;
    }
}

inline Result calculate(const Sample *samples, uint8_t count,
                        const Config &config) {
    Result result = {false, INVALID_NULL_INPUT, 0, 0.0f, 0.0f, 0.0f};
    if (samples == 0) return result;
    if (count == 0 || count > MAX_SAMPLES) {
        result.reason = INVALID_SAMPLE_COUNT;
        return result;
    }

    float resistances[MAX_SAMPLES];
    float minR = 1.0e30f;
    float maxR = 0.0f;

    for (uint8_t i = 0; i < count; ++i) {
        const float voltage = samples[i].voltageV;
        const float current = samples[i].currentA;

        if (!isfinite(voltage) || !isfinite(current)) {
            result.reason = INVALID_NONFINITE;
            return result;
        }
        if (fabs(voltage) < config.minVoltageV ||
            fabs(voltage) > config.maxVoltageV) {
            result.reason = INVALID_VOLTAGE_RANGE;
            return result;
        }
        if (fabs(current) < config.minCurrentA ||
            fabs(current) > config.maxCurrentA) {
            result.reason = INVALID_CURRENT_RANGE;
            return result;
        }
        if (fabs(current) < config.minCurrentResolutionA) {
            result.reason = INVALID_CURRENT_RESOLUTION;
            return result;
        }
        // A voltage/current sign mismatch is inconsistent with a stationary
        // resistive measurement; reject instead of hiding it with abs().
        if ((voltage < 0.0f) != (current < 0.0f)) {
            result.reason = INVALID_POLARITY;
            return result;
        }

        const float resistance = fabs(voltage / current);
        if (!isfinite(resistance) ||
            resistance < config.minResistanceOhm ||
            resistance > config.maxResistanceOhm) {
            result.reason = INVALID_RESISTANCE_RANGE;
            return result;
        }

        resistances[i] = resistance;
        if (resistance < minR) minR = resistance;
        if (resistance > maxR) maxR = resistance;
    }

    sortAscending(resistances, count);
    result.valid = true;
    result.reason = VALID;
    result.validCount = count;
    result.minOhm = minR;
    result.maxOhm = maxR;
    if ((count & 1U) != 0U) {
        result.medianOhm = resistances[count / 2];
    } else {
        result.medianOhm =
            (resistances[count / 2 - 1] + resistances[count / 2]) / 2.0f;
    }
    return result;
}

} // namespace WindingResistance

#endif
