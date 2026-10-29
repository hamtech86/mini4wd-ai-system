#ifndef MINI4WD_WINDING_MEASUREMENT_SEQUENCE_H
#define MINI4WD_WINDING_MEASUREMENT_SEQUENCE_H

#include <stdint.h>

// Pure policy state machine: no hardware writes occur here.
// The firmware adapter must force outputs off on STOP/fault. The adapter must
// not enable pulse actions until an independent hardware current limit exists.
namespace WindingMeasurement {

enum State : uint8_t {
    IDLE = 0, SETTLE, INJECT, SAMPLE, OFF, MOVE, AGGREGATE, COMPLETE, ABORTED
};

enum Reason : uint8_t {
    NO_REASON = 0, REASON_STOP, REASON_NOT_ARMED, REASON_DRIVE_ACTIVE,
    REASON_MOTOR_NOT_SETTLED, REASON_CURRENT_LIMIT_UNCONFIRMED,
    REASON_SAMPLE_INVALID, REASON_TIMEOUT
};

enum Action : uint8_t {
    ACTION_NONE = 0, ACTION_FORCE_OUTPUTS_OFF = 1,
    ACTION_REQUEST_INJECTION = 2, ACTION_REQUEST_SAMPLE = 4,
    ACTION_REQUEST_MOVE = 8, ACTION_REPORT_RESULT = 16,
    ACTION_REPORT_INVALID = 32
};

struct Inputs {
    bool startRequested;
    bool stopRequested;
    bool armed;
    bool normalDriveActive;
    bool motorSettled;
    bool hardwareCurrentLimitConfirmed;
    bool sampleReady;
    bool sampleValid;
    bool morePositionsRequired;
    bool moveComplete;
    bool timedOut;
};

struct Output {
    State state;
    Reason reason;
    uint8_t actions;
};

struct Controller {
    State state;
    Reason reason;
    bool measurementValid;
};

inline void initialize(Controller &c) {
    c.state = IDLE;
    c.reason = NO_REASON;
    c.measurementValid = false;
}

inline Output result(const Controller &c, uint8_t actions) {
    Output out = {c.state, c.reason, actions};
    return out;
}

inline Output tick(Controller &c, const Inputs &in) {
    // STOP and timeout dominate all normal transitions.
    if (in.stopRequested) {
        c.state = ABORTED;
        c.reason = REASON_STOP;
        c.measurementValid = false;
        return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
    }
    if (in.timedOut && c.state != IDLE && c.state != COMPLETE &&
        c.state != ABORTED) {
        c.state = ABORTED;
        c.reason = REASON_TIMEOUT;
        c.measurementValid = false;
        return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
    }

    switch (c.state) {
    case IDLE:
        if (!in.startRequested) return result(c, ACTION_NONE);
        if (!in.armed) {
            c.reason = REASON_NOT_ARMED;
            return result(c, ACTION_REPORT_INVALID);
        }
        if (in.normalDriveActive) {
            c.reason = REASON_DRIVE_ACTIVE;
            return result(c, ACTION_REPORT_INVALID);
        }
        c.reason = NO_REASON;
        c.measurementValid = false;
        c.state = SETTLE;
        return result(c, ACTION_FORCE_OUTPUTS_OFF);

    case SETTLE:
        if (!in.armed) {
            c.state = ABORTED;
            c.reason = REASON_NOT_ARMED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        if (!in.motorSettled) {
            c.reason = REASON_MOTOR_NOT_SETTLED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF);
        }
        if (!in.hardwareCurrentLimitConfirmed) {
            c.state = ABORTED;
            c.reason = REASON_CURRENT_LIMIT_UNCONFIRMED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        c.state = INJECT;
        return result(c, ACTION_FORCE_OUTPUTS_OFF);

    case INJECT:
        if (!in.armed || !in.hardwareCurrentLimitConfirmed) {
            c.state = ABORTED;
            c.reason = !in.armed ? REASON_NOT_ARMED :
                                   REASON_CURRENT_LIMIT_UNCONFIRMED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        c.state = SAMPLE;
        return result(c, ACTION_REQUEST_INJECTION);

    case SAMPLE:
        if (!in.armed || !in.hardwareCurrentLimitConfirmed) {
            c.state = ABORTED;
            c.reason = !in.armed ? REASON_NOT_ARMED :
                                   REASON_CURRENT_LIMIT_UNCONFIRMED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        if (!in.sampleReady) return result(c, ACTION_REQUEST_SAMPLE);
        c.measurementValid = in.sampleValid;
        c.reason = in.sampleValid ? NO_REASON : REASON_SAMPLE_INVALID;
        c.state = OFF;
        return result(c, ACTION_FORCE_OUTPUTS_OFF |
                         (in.sampleValid ? ACTION_NONE : ACTION_REPORT_INVALID));

    case OFF:
        // An invalid sample never advances to a position-changing pulse.
        if (!c.measurementValid) {
            c.state = ABORTED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        c.state = in.morePositionsRequired ? MOVE : AGGREGATE;
        return result(c, ACTION_FORCE_OUTPUTS_OFF);

    case MOVE:
        if (!in.armed || !in.hardwareCurrentLimitConfirmed) {
            c.state = ABORTED;
            c.reason = !in.armed ? REASON_NOT_ARMED :
                                   REASON_CURRENT_LIMIT_UNCONFIRMED;
            return result(c, ACTION_FORCE_OUTPUTS_OFF | ACTION_REPORT_INVALID);
        }
        if (!in.moveComplete) return result(c, ACTION_REQUEST_MOVE);
        c.state = SETTLE;
        return result(c, ACTION_FORCE_OUTPUTS_OFF);

    case AGGREGATE:
        c.state = COMPLETE;
        return result(c, c.measurementValid ? ACTION_REPORT_RESULT :
                                               ACTION_REPORT_INVALID);

    case COMPLETE:
    case ABORTED:
    default:
        return result(c, ACTION_FORCE_OUTPUTS_OFF);
    }
}

} // namespace WindingMeasurement

#endif
