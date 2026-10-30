#include <assert.h>
#include "../../firmware/motor/WindingMeasurementCoordinator.h"
using namespace WindingCoordinator;

static Inputs safeStart() {
    Inputs in = {};
    in.sequence.startRequested = true;
    in.sequence.armed = true;
    in.sequence.hardwareCurrentLimitConfirmed = true;
    in.handshake.armed = true;
    in.handshake.hardwareCurrentLimitConfirmed = true;
    in.handshake.outputsOffConfirmed = true;
    in.handshake.injectionStartTimeoutMs = 25;
    in.pulseDurationMs = 20;
    return in;
}

int main() {
    // Sequence and physical handshake now advance together. The only
    // production adapter remains disabled, so first pulse request aborts.
    Controller c; initialize(c);
    Inputs in = safeStart();
    Output out = tick(c, in);
    assert(out.state == COORDINATOR_RUNNING);
    assert(out.sequenceState == WindingMeasurement::SETTLE);
    assert(!out.injectionPermitted && !out.requestWasRefused);

    in.sequence.startRequested = false;
    in.sequence.motorSettled = true;
    out = tick(c, in);
    assert(out.state == COORDINATOR_RUNNING);
    assert(out.sequenceState == WindingMeasurement::INJECT);

    out = tick(c, in);
    assert(out.state == COORDINATOR_ABORTED);
    assert(out.reason == REASON_ADAPTER_REFUSED);
    assert(out.sequenceState == WindingMeasurement::ABORTED);
    assert(out.requestWasRefused && out.forceOutputsOff);
    assert(!out.physicalOutputsOffConfirmed && !out.injectionPermitted);

    // Terminal state cannot be restarted by stale/repeated requests.
    in.sequence.startRequested = true;
    out = tick(c, in);
    assert(out.state == COORDINATOR_ABORTED && !out.injectionPermitted);

    // STOP dominates the sequence before any injection request can reach adapter.
    {
        Controller stopped; initialize(stopped);
        Inputs x = safeStart();
        tick(stopped, x);
        x.sequence.startRequested = false;
        x.sequence.stopRequested = true;
        Output y = tick(stopped, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.reason == REASON_POLICY_ABORT);
        assert(y.sequenceState == WindingMeasurement::ABORTED);
        assert(y.forceOutputsOff && !y.injectionPermitted);
        assert(!y.physicalOutputsOffConfirmed && !y.requestWasRefused);
    }
    // Loss of independent current-limit confirmation aborts in SETTLE.
    {
        Controller noLimit; initialize(noLimit);
        Inputs x = safeStart();
        tick(noLimit, x);
        x.sequence.startRequested = false;
        x.sequence.motorSettled = true;
        x.sequence.hardwareCurrentLimitConfirmed = false;
        x.handshake.hardwareCurrentLimitConfirmed = false;
        Output y = tick(noLimit, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.reason == REASON_POLICY_ABORT);
        assert(y.forceOutputsOff && !y.injectionPermitted && !y.requestWasRefused);
    }
    // ARM loss also aborts before the disabled adapter is asked to inject.
    {
        Controller unarmed; initialize(unarmed);
        Inputs x = safeStart();
        tick(unarmed, x);
        x.sequence.startRequested = false;
        x.sequence.armed = false;
        x.handshake.armed = false;
        Output y = tick(unarmed, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.forceOutputsOff && !y.injectionPermitted && !y.requestWasRefused);
    }
    // A move request is not allowed to bypass a missing production move adapter.
    {
        Controller move; initialize(move);
        move.sequence.state = WindingMeasurement::MOVE;
        move.sequence.measurementValid = true;
        move.handshake.state = WindingHandshake::READY_MOVE;
        Inputs x = safeStart();
        x.sequence.startRequested = false;
        x.sequence.moveComplete = false;
        Output y = tick(move, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.reason == REASON_ADAPTER_REFUSED);
        assert(y.forceOutputsOff && !y.injectionPermitted);
    }
    // Early sampleReady must not advance the sequence while the pulse is
    // still active. It is accepted only after injectionFinished and physical
    // outputs-OFF readback have moved the handshake to READY_SAMPLE.
    {
        Controller sampling; initialize(sampling);
        sampling.state = COORDINATOR_RUNNING;
        sampling.sequence.state = WindingMeasurement::SAMPLE;
        sampling.handshake.state = WindingHandshake::INJECTION_ACTIVE;
        sampling.handshake.injectionRequestIssued = true;
        sampling.handshake.injectionRequestAtMs = 10;
        Inputs x = {};
        x.sequence.armed = true;
        x.sequence.hardwareCurrentLimitConfirmed = true;
        x.sequence.sampleReady = true;
        x.sequence.sampleValid = true;
        x.handshake.armed = true;
        x.handshake.hardwareCurrentLimitConfirmed = true;
        x.handshake.injectionActive = true;
        x.handshake.outputsOffConfirmed = false;
        x.handshake.nowMs = 15;
        Output y = tick(sampling, x);
        assert(y.state == COORDINATOR_RUNNING);
        assert(y.sequenceState == WindingMeasurement::SAMPLE);
        assert(!y.physicalOutputsOffConfirmed);

        x.handshake.injectionActive = false;
        x.handshake.injectionFinished = true;
        x.handshake.outputsOffConfirmed = true;
        x.handshake.nowMs = 20;
        y = tick(sampling, x);
        assert(y.sequenceState == WindingMeasurement::SAMPLE);
        assert(sampling.handshake.state == WindingHandshake::READY_SAMPLE);

        y = tick(sampling, x);
        assert(y.state == COORDINATOR_RUNNING);
        assert(y.sequenceState == WindingMeasurement::OFF);
        assert(sampling.handshake.state == WindingHandshake::READY_MOVE);
        assert(!y.injectionPermitted);
    }
    return 0;
}
