#ifndef MINI4WD_WINDING_MEASUREMENT_COORDINATOR_H
#define MINI4WD_WINDING_MEASUREMENT_COORDINATOR_H

#include <stdint.h>
#include "WindingMeasurementSequence.h"
#include "WindingPulseAuthorizationGuard.h"
#include "WindingHardwareAdapter.h"
#include "WindingMeasurementHandshake.h"

// Integration boundary only. It deliberately uses DisabledAdapter: no GPIO,
// no motor-power writes, and no physical OFF/current-limit claims.
namespace WindingCoordinator {
enum State : uint8_t { COORDINATOR_IDLE = 0, COORDINATOR_RUNNING, COORDINATOR_COMPLETE, COORDINATOR_ABORTED };
enum Reason : uint8_t { COORDINATOR_OK = 0, REASON_ADAPTER_REFUSED, REASON_POLICY_ABORT, REASON_GUARD_DENIED };
struct Inputs {
    WindingHandshake::Inputs handshake;
    uint32_t pulseDurationMs;
};
struct Output {
    State state;
    Reason reason;
    bool requestWasRefused;
    bool forceOutputsOff;
    bool physicalOutputsOffConfirmed;
    bool injectionPermitted;
};
struct Controller {
    State state;
    Reason reason;
    WindingHandshake::Controller handshake;
    WindingPulseGuard::Guard pulseGuard;
    WindingHardware::DisabledAdapter adapter;
};
inline void initialize(Controller &c) {
    c.state = COORDINATOR_IDLE; c.reason = COORDINATOR_OK;
    WindingHandshake::initialize(c.handshake);
    WindingPulseGuard::initialize(c.pulseGuard);
}
inline Output result(const Controller &c, bool refused, bool forceOff, bool offConfirmed, bool permitted) {
    Output out = {c.state, c.reason, refused, forceOff, offConfirmed, permitted}; return out;
}
inline Output tick(Controller &c, const Inputs &in) {
    if (c.state == COORDINATOR_ABORTED || c.state == COORDINATOR_COMPLETE)
        return result(c, false, true, false, false);

    WindingHandshake::Output handshakeOut = WindingHandshake::tick(c.handshake, in.handshake);
    if (handshakeOut.state == WindingHandshake::ABORTED) {
        c.state = COORDINATOR_ABORTED; c.reason = REASON_POLICY_ABORT;
        c.adapter.forceOutputsOff();
        return result(c, false, true, false, false);
    }
    if (handshakeOut.state == WindingHandshake::COMPLETE) {
        c.state = COORDINATOR_COMPLETE;
        c.adapter.forceOutputsOff();
        return result(c, false, true, false, false);
    }
    c.state = COORDINATOR_RUNNING;

    if (handshakeOut.allowInjection) {
        WindingPulseGuard::Inputs guardIn = {};
        guardIn.nowMs = in.handshake.nowMs;
        guardIn.startRequested = true;
        guardIn.armed = in.handshake.armed;
        guardIn.normalDriveActive = in.handshake.normalDriveActive;
        guardIn.hardwareCurrentLimitConfirmed = in.handshake.hardwareCurrentLimitConfirmed;
        guardIn.requestedDurationMs = in.pulseDurationMs;
        WindingPulseGuard::Output guardOut = WindingPulseGuard::tick(c.pulseGuard, guardIn);
        if (!guardOut.outputEnable) {
            c.state = COORDINATOR_ABORTED; c.reason = REASON_GUARD_DENIED;
            c.adapter.forceOutputsOff();
            return result(c, false, true, false, false);
        }
        WindingHardware::PulseRequest request = {in.pulseDurationMs};
        WindingHardware::AdapterStatus status = c.adapter.requestInjection(request);
        c.state = COORDINATOR_ABORTED; c.reason = REASON_ADAPTER_REFUSED;
        c.adapter.forceOutputsOff();
        // Even a future adapter response must not be treated as proof of
        // physical current limiting or output-OFF readback by this stub.
        return result(c, status == WindingHardware::ADAPTER_REFUSED, true, false, false);
    }

    if (handshakeOut.forceOutputsOff) {
        const bool physicalOff = c.adapter.forceOutputsOff();
        return result(c, false, true, physicalOff, false);
    }
    return result(c, false, false, false, false);
}
} // namespace WindingCoordinator
#endif
