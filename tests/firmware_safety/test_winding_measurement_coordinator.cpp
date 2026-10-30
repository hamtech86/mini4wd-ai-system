#include <assert.h>
#include "../../firmware/motor/WindingMeasurementCoordinator.h"
using namespace WindingCoordinator;
int main() {
    Controller c; initialize(c);
    Inputs in = {};
    in.pulseDurationMs = 20;
    in.handshake.injectionStartTimeoutMs = 25;
    in.handshake.armed = true;
    in.handshake.hardwareCurrentLimitConfirmed = true;
    in.handshake.outputsOffConfirmed = true;
    in.handshake.startRequested = true;
    Output out = tick(c, in);
    assert(out.state == COORDINATOR_RUNNING);
    assert(!out.injectionPermitted && !out.requestWasRefused);

    in.handshake.startRequested = false;
    in.handshake.injectionRequested = true;
    out = tick(c, in);
    // The policy and pulse guard may authorize a bounded request, but the
    // production adapter stub must refuse it and cannot claim OFF readback.
    assert(out.state == COORDINATOR_ABORTED);
    assert(out.reason == REASON_ADAPTER_REFUSED);
    assert(out.requestWasRefused);
    assert(out.forceOutputsOff);
    assert(!out.physicalOutputsOffConfirmed);
    assert(!out.injectionPermitted);

    // Terminal state cannot be restarted by stale/repeated requests.
    in.handshake.startRequested = true;
    out = tick(c, in);
    assert(out.state == COORDINATOR_ABORTED && !out.injectionPermitted);

    // STOP dominates a pending injection request.
    {
        Controller stopped; initialize(stopped);
        Inputs x = {};
        x.pulseDurationMs = 20;
        x.handshake.injectionStartTimeoutMs = 25;
        x.handshake.armed = true;
        x.handshake.hardwareCurrentLimitConfirmed = true;
        x.handshake.outputsOffConfirmed = true;
        x.handshake.startRequested = true;
        tick(stopped, x);
        x.handshake.startRequested = false;
        x.handshake.stopRequested = true;
        Output y = tick(stopped, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.reason == REASON_POLICY_ABORT);
        assert(y.forceOutputsOff && !y.injectionPermitted);
        assert(!y.physicalOutputsOffConfirmed);
    }
    // Loss of independent current-limit confirmation aborts before injection.
    {
        Controller noLimit; initialize(noLimit);
        Inputs x = {};
        x.pulseDurationMs = 20;
        x.handshake.injectionStartTimeoutMs = 25;
        x.handshake.armed = true;
        x.handshake.hardwareCurrentLimitConfirmed = true;
        x.handshake.outputsOffConfirmed = true;
        x.handshake.startRequested = true;
        tick(noLimit, x);
        x.handshake.startRequested = false;
        x.handshake.hardwareCurrentLimitConfirmed = false;
        x.handshake.injectionRequested = true;
        Output y = tick(noLimit, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.reason == REASON_POLICY_ABORT);
        assert(y.forceOutputsOff && !y.injectionPermitted);
        assert(!y.requestWasRefused);
    }
    // ARM loss also aborts before the disabled adapter is asked to inject.
    {
        Controller unarmed; initialize(unarmed);
        Inputs x = {};
        x.pulseDurationMs = 20;
        x.handshake.injectionStartTimeoutMs = 25;
        x.handshake.armed = true;
        x.handshake.hardwareCurrentLimitConfirmed = true;
        x.handshake.outputsOffConfirmed = true;
        x.handshake.startRequested = true;
        tick(unarmed, x);
        x.handshake.startRequested = false;
        x.handshake.armed = false;
        x.handshake.injectionRequested = true;
        Output y = tick(unarmed, x);
        assert(y.state == COORDINATOR_ABORTED);
        assert(y.forceOutputsOff && !y.injectionPermitted);
        assert(!y.requestWasRefused);
    }
    return 0;
}
