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
    return 0;
}
