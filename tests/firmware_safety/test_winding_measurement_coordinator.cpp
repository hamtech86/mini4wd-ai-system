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
    return 0;
}
