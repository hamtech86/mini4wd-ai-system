#ifndef MINI4WD_WINDING_PULSE_AUTHORIZATION_GUARD_H
#define MINI4WD_WINDING_PULSE_AUTHORIZATION_GUARD_H

#include <stdint.h>

// Pure authorization/deadline policy. This class performs NO GPIO or motor I/O.
// A future hardware adapter must default every output OFF and must independently
// verify physical current limiting before honoring outputEnable=true.
namespace WindingPulseGuard {

enum State : uint8_t { IDLE = 0, ACTIVE, COMPLETE, ABORTED };
enum Reason : uint8_t {
    NO_REASON = 0, REASON_STOP, REASON_NOT_ARMED, REASON_DRIVE_ACTIVE,
    REASON_CURRENT_LIMIT_UNCONFIRMED, REASON_BAD_DURATION, REASON_DEADLINE
};

struct Inputs {
    uint32_t nowMs;
    bool startRequested;
    bool stopRequested;
    bool armed;
    bool normalDriveActive;
    bool hardwareCurrentLimitConfirmed;
    uint32_t requestedDurationMs;
};

struct Output {
    State state;
    Reason reason;
    bool outputEnable;
};

struct Guard {
    State state;
    Reason reason;
    uint32_t startedAtMs;
    uint32_t durationMs;
};

static const uint32_t MAX_PULSE_DURATION_MS = 100; // conservative policy ceiling

inline void initialize(Guard &g) {
    g.state = IDLE;
    g.reason = NO_REASON;
    g.startedAtMs = 0;
    g.durationMs = 0;
}

inline Output result(const Guard &g, bool enable) {
    Output out = {g.state, g.reason, enable};
    return out;
}

inline Output tick(Guard &g, const Inputs &in) {
    // A stop request dominates every other condition, including terminal states.
    if (in.stopRequested && g.state == ACTIVE) {
        g.state = ABORTED;
        g.reason = REASON_STOP;
        return result(g, false);
    }

    if (g.state == ACTIVE) {
        if (!in.armed || !in.hardwareCurrentLimitConfirmed ||
            in.normalDriveActive) {
            g.state = ABORTED;
            g.reason = !in.armed ? REASON_NOT_ARMED :
                (!in.hardwareCurrentLimitConfirmed ?
                    REASON_CURRENT_LIMIT_UNCONFIRMED : REASON_DRIVE_ACTIVE);
            return result(g, false);
        }
        // Unsigned subtraction is wrap-safe for durations far below 2^31 ms.
        if ((uint32_t)(in.nowMs - g.startedAtMs) >= g.durationMs) {
            g.state = COMPLETE;
            g.reason = REASON_DEADLINE;
            return result(g, false);
        }
        return result(g, true);
    }

    if (g.state != IDLE || !in.startRequested) return result(g, false);

    if (in.stopRequested) {
        g.state = ABORTED;
        g.reason = REASON_STOP;
    } else if (!in.armed) {
        g.state = ABORTED;
        g.reason = REASON_NOT_ARMED;
    } else if (in.normalDriveActive) {
        g.state = ABORTED;
        g.reason = REASON_DRIVE_ACTIVE;
    } else if (!in.hardwareCurrentLimitConfirmed) {
        g.state = ABORTED;
        g.reason = REASON_CURRENT_LIMIT_UNCONFIRMED;
    } else if (in.requestedDurationMs == 0 ||
               in.requestedDurationMs > MAX_PULSE_DURATION_MS) {
        g.state = ABORTED;
        g.reason = REASON_BAD_DURATION;
    } else {
        g.state = ACTIVE;
        g.reason = NO_REASON;
        g.startedAtMs = in.nowMs;
        g.durationMs = in.requestedDurationMs;
        return result(g, true);
    }
    return result(g, false);
}

} // namespace WindingPulseGuard
#endif
