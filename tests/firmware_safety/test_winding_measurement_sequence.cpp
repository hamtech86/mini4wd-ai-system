#include <assert.h>
#include "../../firmware/motor/WindingMeasurementSequence.h"

using namespace WindingMeasurement;

static Inputs idleInputs() {
    Inputs in = {false, false, true, false, false, false,
                 false, false, false, false, false};
    return in;
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

    // Reset and walk through a fully permitted policy path (no hardware is driven).
    initialize(c);
    in = idleInputs();
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.motorSettled = true;
    in.hardwareCurrentLimitConfirmed = true;
    out = tick(c, in);
    assert(out.state == INJECT);
    out = tick(c, in);
    assert(out.state == SAMPLE && (out.actions & ACTION_REQUEST_INJECTION));
    in.sampleReady = true;
    in.sampleValid = true;
    out = tick(c, in);
    assert(out.state == OFF && (out.actions & ACTION_FORCE_OUTPUTS_OFF));
    in.morePositionsRequired = false;
    out = tick(c, in);
    assert(out.state == AGGREGATE && (out.actions & ACTION_FORCE_OUTPUTS_OFF));
    out = tick(c, in);
    assert(out.state == COMPLETE && (out.actions & ACTION_REPORT_RESULT));

    // STOP from an active sample phase dominates and requests immediate OFF.
    initialize(c);
    in = idleInputs();
    in.startRequested = true;
    tick(c, in);
    in.startRequested = false;
    in.motorSettled = true;
    in.hardwareCurrentLimitConfirmed = true;
    tick(c, in); // INJECT
    tick(c, in); // SAMPLE
    in.stopRequested = true;
    out = tick(c, in);
    assert(out.state == ABORTED);
    assert(out.reason == REASON_STOP);
    assert(out.actions & ACTION_FORCE_OUTPUTS_OFF);
    assert(out.actions & ACTION_REPORT_INVALID);

    return 0;
}
