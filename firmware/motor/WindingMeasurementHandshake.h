#ifndef MINI4WD_WINDING_MEASUREMENT_HANDSHAKE_H
#define MINI4WD_WINDING_MEASUREMENT_HANDSHAKE_H

#include <stdint.h>

// Adapter-facing handshake policy. No GPIO, timing, or motor I/O.
// A hardware adapter must supply truthful physical readback signals.
namespace WindingHandshake {

enum State : uint8_t {
    IDLE = 0, READY_INJECTION, INJECTION_ACTIVE, READY_SAMPLE,
    READY_MOVE, MOVE_ACTIVE, COMPLETE, ABORTED
};
enum Reason : uint8_t {
    NO_REASON = 0, REASON_STOP, REASON_NOT_ARMED, REASON_DRIVE_ACTIVE,
    REASON_CURRENT_LIMIT, REASON_OUTPUTS_NOT_OFF, REASON_BAD_SEQUENCE,
    REASON_SAMPLE_INVALID, REASON_ADAPTER_FAULT
};

struct Inputs {
    bool startRequested;
    bool stopRequested;
    bool armed;
    bool normalDriveActive;
    bool hardwareCurrentLimitConfirmed;
    bool outputsOffConfirmed;
    bool injectionRequested;
    bool injectionActive;
    bool injectionFinished;
    bool sampleReady;
    bool sampleValid;
    bool moveRequested;
    bool moveActive;
    bool moveComplete;
    bool adapterFault;
};

struct Output {
    State state;
    Reason reason;
    bool allowInjection;
    bool allowSample;
    bool allowMove;
    bool forceOutputsOff;
};

struct Controller { State state; Reason reason; };

inline void initialize(Controller &c) {
    c.state = IDLE;
    c.reason = NO_REASON;
}

inline Output makeOutput(const Controller &c, bool inject, bool sample,
                         bool move, bool forceOff) {
    Output out = {c.state, c.reason, inject, sample, move, forceOff};
    return out;
}

inline Output abort(Controller &c, Reason reason) {
    c.state = ABORTED;
    c.reason = reason;
    return makeOutput(c, false, false, false, true);
}

inline Output tick(Controller &c, const Inputs &in) {
    if (in.stopRequested) return abort(c, REASON_STOP);
    if (in.adapterFault) return abort(c, REASON_ADAPTER_FAULT);

    if (c.state != IDLE && c.state != COMPLETE && c.state != ABORTED) {
        if (!in.armed) return abort(c, REASON_NOT_ARMED);
        if (in.normalDriveActive) return abort(c, REASON_DRIVE_ACTIVE);
        if (!in.hardwareCurrentLimitConfirmed)
            return abort(c, REASON_CURRENT_LIMIT);
    }

    switch (c.state) {
    case IDLE:
        if (!in.startRequested) return makeOutput(c, false, false, false, true);
        if (!in.armed) return abort(c, REASON_NOT_ARMED);
        if (in.normalDriveActive) return abort(c, REASON_DRIVE_ACTIVE);
        if (!in.hardwareCurrentLimitConfirmed)
            return abort(c, REASON_CURRENT_LIMIT);
        if (!in.outputsOffConfirmed) return abort(c, REASON_OUTPUTS_NOT_OFF);
        c.state = READY_INJECTION;
        return makeOutput(c, false, false, false, true);

    case READY_INJECTION:
        if (!in.outputsOffConfirmed) return abort(c, REASON_OUTPUTS_NOT_OFF);
        if (in.injectionActive) {
            c.state = INJECTION_ACTIVE;
            return makeOutput(c, false, true, false, false);
        }
        if (in.injectionRequested)
            return makeOutput(c, true, false, false, false);
        return makeOutput(c, false, false, false, true);

    case INJECTION_ACTIVE:
        if (in.injectionActive)
            return makeOutput(c, false, true, false, false);
        if (!in.injectionFinished || !in.outputsOffConfirmed)
            return abort(c, REASON_OUTPUTS_NOT_OFF);
        c.state = READY_SAMPLE;
        return makeOutput(c, false, true, false, true);

    case READY_SAMPLE:
        if (!in.outputsOffConfirmed) return abort(c, REASON_OUTPUTS_NOT_OFF);
        if (!in.sampleReady) return makeOutput(c, false, true, false, true);
        if (!in.sampleValid) return abort(c, REASON_SAMPLE_INVALID);
        c.state = READY_MOVE;
        return makeOutput(c, false, false, false, true);

    case READY_MOVE:
        if (!in.outputsOffConfirmed) return abort(c, REASON_OUTPUTS_NOT_OFF);
        if (in.moveActive) {
            c.state = MOVE_ACTIVE;
            return makeOutput(c, false, false, false, true);
        }
        if (in.moveRequested)
            return makeOutput(c, false, false, true, true);
        c.state = COMPLETE;
        return makeOutput(c, false, false, false, true);

    case MOVE_ACTIVE:
        if (!in.outputsOffConfirmed) return abort(c, REASON_OUTPUTS_NOT_OFF);
        if (!in.moveComplete)
            return makeOutput(c, false, false, false, true);
        c.state = READY_INJECTION;
        return makeOutput(c, false, false, false, true);

    case COMPLETE:
    case ABORTED:
    default:
        return makeOutput(c, false, false, false, true);
    }
}

} // namespace WindingHandshake
#endif
