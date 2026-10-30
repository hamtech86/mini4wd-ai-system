#include <assert.h>
#include "../../firmware/motor/WindingMeasurementHandshake.h"
using namespace WindingHandshake;

static Inputs safeInputs() {
    Inputs in = {};
    in.armed = true;
    in.hardwareCurrentLimitConfirmed = true;
    in.outputsOffConfirmed = true;
    return in;
}

int main() {
    Controller c;
    initialize(c);
    Inputs in = safeInputs();

    // Cannot start unless physical OFF readback is confirmed.
    in.startRequested = true;
    in.outputsOffConfirmed = false;
    Output out = tick(c, in);
    assert(out.state == ABORTED && out.forceOutputsOff);
    assert(out.reason == REASON_OUTPUTS_NOT_OFF);

    // Normal handshake: request -> active pulse/sample -> confirmed OFF -> sample.
    initialize(c);
    in = safeInputs();
    in.startRequested = true;
    out = tick(c, in);
    assert(out.state == READY_INJECTION && out.forceOutputsOff);
    in.startRequested = false;
    in.injectionRequested = true;
    out = tick(c, in);
    assert(out.allowInjection && !out.allowSample);
    in.injectionRequested = false;
    in.injectionActive = true;
    in.outputsOffConfirmed = false;
    out = tick(c, in);
    assert(out.state == INJECTION_ACTIVE && out.allowSample);

    // Pulse-active status may fall before OFF readback and completion arrive.
    in.injectionActive = false;
    out = tick(c, in);
    assert(out.state == INJECTION_ACTIVE && !out.allowSample && out.forceOutputsOff);
    in.injectionFinished = true;
    out = tick(c, in);
    assert(out.state == INJECTION_ACTIVE && !out.allowSample && out.forceOutputsOff);
    in.outputsOffConfirmed = true;
    out = tick(c, in);
    assert(out.state == READY_SAMPLE && out.allowSample && out.forceOutputsOff);

    in.injectionFinished = false;
    in.sampleReady = true;
    in.sampleValid = true;
    out = tick(c, in);
    assert(out.state == READY_MOVE && out.forceOutputsOff);

    // Movement is never allowed without confirmed physical OFF.
    in.sampleReady = false;
    in.moveRequested = true;
    in.outputsOffConfirmed = false;
    out = tick(c, in);
    assert(out.state == ABORTED && !out.allowMove && out.forceOutputsOff);

    // A stop during a pulse immediately revokes all permissions.
    initialize(c);
    in = safeInputs();
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.injectionRequested = true;
    tick(c, in);
    in.injectionRequested = false;
    in.injectionActive = true;
    in.outputsOffConfirmed = false;
    tick(c, in);
    in.stopRequested = true;
    out = tick(c, in);
    assert(out.state == ABORTED && !out.allowInjection &&
           !out.allowSample && !out.allowMove && out.forceOutputsOff);
    assert(out.reason == REASON_STOP);

    // Lost current-limit confirmation revokes an active pulse.
    initialize(c);
    in = safeInputs();
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.injectionRequested = true;
    tick(c, in);
    in.injectionRequested = false;
    in.injectionActive = true;
    in.outputsOffConfirmed = false;
    tick(c, in);
    in.hardwareCurrentLimitConfirmed = false;
    out = tick(c, in);
    assert(out.state == ABORTED && out.forceOutputsOff);
    assert(out.reason == REASON_CURRENT_LIMIT);
    return 0;
}
