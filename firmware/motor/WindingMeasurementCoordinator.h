#ifndef MINI4WD_WINDING_MEASUREMENT_COORDINATOR_H
#define MINI4WD_WINDING_MEASUREMENT_COORDINATOR_H
#include <stdint.h>
#include "WindingMeasurementSequence.h"
#include "WindingPulseAuthorizationGuard.h"
#include "WindingHardwareAdapter.h"
#include "WindingMeasurementHandshake.h"
// Integration boundary only. Production uses DisabledAdapter: no GPIO,
// no motor-power writes, and no physical OFF/current-limit claims.
namespace WindingCoordinator {
enum State : uint8_t { COORDINATOR_IDLE = 0, COORDINATOR_RUNNING, COORDINATOR_COMPLETE, COORDINATOR_ABORTED };
enum Reason : uint8_t { COORDINATOR_OK = 0, REASON_ADAPTER_REFUSED, REASON_POLICY_ABORT, REASON_GUARD_DENIED };
struct Inputs { WindingMeasurement::Inputs sequence; WindingHandshake::Inputs handshake; uint32_t pulseDurationMs; };
struct Output {
    State state; Reason reason; WindingMeasurement::State sequenceState;
    bool requestWasRefused; bool forceOutputsOff; bool physicalOutputsOffConfirmed; bool injectionPermitted;
};
struct Controller {
    State state; Reason reason; WindingMeasurement::Controller sequence;
    WindingHandshake::Controller handshake; WindingPulseGuard::Guard pulseGuard;
    WindingHardware::DisabledAdapter adapter;
};
inline void initialize(Controller &c) {
    c.state = COORDINATOR_IDLE; c.reason = COORDINATOR_OK;
    WindingMeasurement::initialize(c.sequence); WindingHandshake::initialize(c.handshake);
    WindingPulseGuard::initialize(c.pulseGuard);
}
inline Output result(const Controller &c, bool refused, bool forceOff, bool offConfirmed, bool permitted) {
    Output out = {c.state, c.reason, c.sequence.state, refused, forceOff, offConfirmed, permitted}; return out;
}
inline Output abortSequence(Controller &c, Reason reason) {
    c.state = COORDINATOR_ABORTED; c.reason = reason;
    c.sequence.state = WindingMeasurement::ABORTED; c.sequence.measurementValid = false;
    c.adapter.forceOutputsOff(); return result(c, false, true, false, false);
}
inline Output tick(Controller &c, const Inputs &in) {
    if (c.state == COORDINATOR_ABORTED || c.state == COORDINATOR_COMPLETE)
        return result(c, false, true, false, false);

    // Logical step order comes from Sequence; physical interlocks/readback
    // remain exclusively controlled by the independent Handshake.
    // A completed sample may advance Sequence only after the handshake has
    // reached READY_SAMPLE, which itself requires injection finished and a
    // positive physical outputs-OFF readback. Early/stale sampleReady signals
    // are deliberately withheld from the logical sequence.
    WindingMeasurement::Inputs si = in.sequence;
    si.sampleReady = in.sequence.sampleReady &&
                     c.handshake.state == WindingHandshake::READY_SAMPLE &&
                     in.handshake.outputsOffConfirmed;
    WindingMeasurement::Output seq = WindingMeasurement::tick(c.sequence, si);
    if (seq.state == WindingMeasurement::ABORTED) return abortSequence(c, REASON_POLICY_ABORT);

    WindingHandshake::Inputs hi = in.handshake;
    hi.startRequested = in.sequence.startRequested;
    hi.injectionRequested = ((seq.actions & WindingMeasurement::ACTION_REQUEST_INJECTION) != 0);
    hi.sampleReady = si.sampleReady; hi.sampleValid = in.sequence.sampleValid;
    hi.moveRequested = ((seq.actions & WindingMeasurement::ACTION_REQUEST_MOVE) != 0);
    hi.moveComplete = in.sequence.moveComplete;
    WindingHandshake::Output ho = WindingHandshake::tick(c.handshake, hi);
    if (ho.state == WindingHandshake::ABORTED) return abortSequence(c, REASON_POLICY_ABORT);
    c.state = COORDINATOR_RUNNING;

    if (ho.allowInjection) {
        WindingPulseGuard::Inputs gi = {};
        gi.nowMs = in.handshake.nowMs; gi.startRequested = true; gi.armed = in.handshake.armed;
        gi.normalDriveActive = in.handshake.normalDriveActive;
        gi.hardwareCurrentLimitConfirmed = in.handshake.hardwareCurrentLimitConfirmed;
        gi.requestedDurationMs = in.pulseDurationMs;
        WindingPulseGuard::Output go = WindingPulseGuard::tick(c.pulseGuard, gi);
        if (!go.outputEnable) return abortSequence(c, REASON_GUARD_DENIED);
        WindingHardware::PulseRequest request = {in.pulseDurationMs};
        WindingHardware::AdapterStatus status = c.adapter.requestInjection(request);
        // The production adapter is intentionally disabled; never claim a
        // successful pulse or a verified physical OFF state.
        c.state = COORDINATOR_ABORTED; c.reason = REASON_ADAPTER_REFUSED;
        c.sequence.state = WindingMeasurement::ABORTED; c.sequence.measurementValid = false;
        c.adapter.forceOutputsOff();
        return result(c, status == WindingHardware::ADAPTER_REFUSED, true, false, false);
    }
    if (seq.state == WindingMeasurement::COMPLETE && ho.state == WindingHandshake::COMPLETE) {
        c.state = COORDINATOR_COMPLETE; c.adapter.forceOutputsOff();
        return result(c, false, true, false, false);
    }
    // No production position-move adapter exists; fail closed at MOVE.
    if ((seq.actions & WindingMeasurement::ACTION_REQUEST_MOVE) != 0 || ho.allowMove)
        return abortSequence(c, REASON_ADAPTER_REFUSED);
    if ((seq.actions & WindingMeasurement::ACTION_FORCE_OUTPUTS_OFF) || ho.forceOutputsOff) {
        c.adapter.forceOutputsOff(); return result(c, false, true, false, false);
    }
    return result(c, false, false, false, false);
}
} // namespace WindingCoordinator
#endif
