#include <assert.h>
#include "../../firmware/motor/WindingMeasurementSequence.h"

using namespace WindingMeasurement;

static Inputs idleInputs() {
    Inputs in = {false, false, true, false, false, false,
                 false, false, false, false, false};
    return in;
}

static void enterSample(Controller &c, Inputs &in) {
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.motorSettled = true;
    in.hardwareCurrentLimitConfirmed = true;
    tick(c, in); // SETTLE -> INJECT
    tick(c, in); // INJECT -> SAMPLE
}

int main() {
    Controller c;
    initialize(c);
    Inputs in = idleInputs();

    // Start only enters a de-energized settle state.
    in.startRequested = true;
    Output out = tick(c, in);
    assert(out.state == SETTLE);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(!(out.actions & ACTION_REQUEST_INJECTION));

    // Settled but without independently confirmed hardware limiting: fail closed.
    in.startRequested = false;
    in.motorSettled = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_CURRENT_LIMIT_UNCONFIRMED);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(!(out.actions & ACTION_REQUEST_INJECTION));

    // DRIVE activation after starting must abort from SETTLE.
    initialize(c);
    in = idleInputs();
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.normalDriveActive = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_DRIVE_ACTIVE);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(!(out.actions & ACTION_REQUEST_INJECTION));

    // DRIVE activation while sampling must also abort synchronously.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.normalDriveActive = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_DRIVE_ACTIVE);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);

    // Normal policy path; this test does not drive physical hardware.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    out = tick(c, in); // Wait for synchronized sample
    assert(out.state == SAMPLE && (out.actions & ACTION_REQUEST_SAMPLE));
    in.sampleReady = true;
    in.sampleValid = true;
    out = tick(c, in);
    assert(out.state == OFF && (out.actions & ACTION_FORCE_OUTPUTS_OFF));
    in.morePositionsRequired = false;
    out = tick(c, in);
    assert(out.state == AGGREGATE && (out.actions & ACTION_FORCE_OUTPUTS_OFF));
    out = tick(c, in);
    assert(out.state == COMPLETE && (out.actions & ACTION_REPORT_RESULT));

    // Invalid sample must abort without requesting a position move.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.sampleReady = true;
    in.sampleValid = false;
    in.morePositionsRequired = true;
    out = tick(c, in);
    assert(out.state == OFF);
    assert(out.actions & ACTION_REPORT_INVALID);
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(!(out.actions & ACTION_REQUEST_MOVE));

    // A completed valid position can request movement, then settle again.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.sampleReady = true;
    in.sampleValid = true;
    in.morePositionsRequired = true;
    out = tick(c, in); // SAMPLE -> OFF
    assert(out.state == OFF);
    out = tick(c, in); // OFF -> MOVE
    assert(out.state == MOVE);
    in.moveComplete = false;
    out = tick(c, in);
    assert(out.actions & ACTION_REQUEST_MOVE);
    in.moveComplete = true;
    out = tick(c, in);
    assert(out.state == SETTLE);
    in.moveComplete = false;
    out = tick(c, in);
    assert(out.state == INJECT);

    // STOP from an active sample phase dominates and requests immediate OFF.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.stopRequested = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_STOP);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(out.actions & ACTION_REPORT_INVALID);

    // Timeout also fails closed from a measurement state.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.timedOut = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_TIMEOUT);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(out.actions & ACTION_REPORT_INVALID);

    // Losing ARM/current-limit confirmation during SAMPLE immediately aborts.
    initialize(c);
    in = idleInputs();
    enterSample(c, in);
    in.armed = false;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(out.actions & ACTION_REPORT_INVALID);

    return 0;
}
