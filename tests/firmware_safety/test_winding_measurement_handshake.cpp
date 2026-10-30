#include <assert.h>
#include "../../firmware/motor/WindingMeasurementHandshake.h"
using namespace WindingHandshake;
static Inputs safeInputs() {
    Inputs in = {};
    in.injectionStartTimeoutMs = 25;
    in.armed = true; in.hardwareCurrentLimitConfirmed = true; in.outputsOffConfirmed = true;
    return in;
}
int main() {
    Controller c; initialize(c);
    Inputs in = safeInputs();
    in.startRequested = true; in.outputsOffConfirmed = false;
    Output out = tick(c, in);
    assert(out.state == ABORTED && out.forceOutputsOff && out.reason == REASON_OUTPUTS_NOT_OFF);

    // A request is emitted once only; missing start acknowledgement times out.
    initialize(c); in = safeInputs(); in.startRequested = true;
    out = tick(c, in); assert(out.state == READY_INJECTION);
    in.startRequested = false; in.injectionRequested = true; in.nowMs = 100;
    out = tick(c, in); assert(out.allowInjection);
    in.injectionRequested = false; in.nowMs = 124;
    out = tick(c, in); assert(!out.allowInjection && out.state == READY_INJECTION);
    in.nowMs = 125; out = tick(c, in);
    assert(out.state == ABORTED && out.reason == REASON_INJECTION_START_TIMEOUT && out.forceOutputsOff);

    // Normal handshake: one request -> active pulse -> confirmed OFF -> sample.
    initialize(c); in = safeInputs(); in.startRequested = true;
    out = tick(c, in); assert(out.state == READY_INJECTION);
    in.startRequested = false; in.injectionRequested = true;
    out = tick(c, in); assert(out.allowInjection);
    in.injectionRequested = false; in.injectionActive = true; in.outputsOffConfirmed = false;
    out = tick(c, in); assert(out.state == INJECTION_ACTIVE && out.allowSample);
    in.injectionActive = false; out = tick(c, in);
    assert(out.state == INJECTION_ACTIVE && !out.allowSample && out.forceOutputsOff);
    in.injectionFinished = true; out = tick(c, in);
    assert(out.state == INJECTION_ACTIVE && !out.allowSample);
    in.outputsOffConfirmed = true; out = tick(c, in);
    assert(out.state == READY_SAMPLE && out.allowSample && out.forceOutputsOff);
    in.injectionFinished = false; in.sampleReady = true; in.sampleValid = true;
    out = tick(c, in); assert(out.state == READY_MOVE && out.forceOutputsOff);

    // Movement is never allowed without physical OFF readback.
    in.sampleReady = false; in.moveRequested = true; in.outputsOffConfirmed = false;
    out = tick(c, in); assert(out.state == ABORTED && !out.allowMove && out.forceOutputsOff);

    // STOP and lost current-limit confirmation revoke active pulse permissions.
    initialize(c); in = safeInputs(); in.startRequested = true; tick(c, in);
    in.startRequested = false; in.injectionRequested = true; tick(c, in);
    in.injectionRequested = false; in.injectionActive = true; in.outputsOffConfirmed = false; tick(c, in);
    in.stopRequested = true; out = tick(c, in);
    assert(out.state == ABORTED && !out.allowInjection && !out.allowSample && !out.allowMove && out.forceOutputsOff);
    assert(out.reason == REASON_STOP);

    initialize(c); in = safeInputs(); in.startRequested = true; tick(c, in);
    in.startRequested = false; in.injectionRequested = true; tick(c, in);
    in.injectionRequested = false; in.injectionActive = true; in.outputsOffConfirmed = false; tick(c, in);
    in.hardwareCurrentLimitConfirmed = false; out = tick(c, in);
    assert(out.state == ABORTED && out.forceOutputsOff && out.reason == REASON_CURRENT_LIMIT);
    return 0;
}
