#include "../../firmware/motor/WindingPulseAuthorizationGuard.h"
#include <assert.h>

using namespace WindingPulseGuard;

static Inputs safe(uint32_t now) {
    Inputs in = {now, false, false, true, false, true, 10};
    return in;
}

int main() {
    Guard g;
    initialize(g);

    Inputs in = safe(100);
    in.startRequested = true;
    Output out = tick(g, in);
    assert(out.state == ACTIVE && out.outputEnable);

    in = safe(105);
    out = tick(g, in);
    assert(out.state == ACTIVE && out.outputEnable);

    in = safe(110);
    out = tick(g, in);
    assert(out.state == COMPLETE && !out.outputEnable);

    initialize(g);
    in = safe(200);
    in.startRequested = true;
    in.armed = false;
    out = tick(g, in);
    assert(out.state == ABORTED && out.reason == REASON_NOT_ARMED && !out.outputEnable);

    initialize(g);
    in = safe(300);
    in.startRequested = true;
    in.hardwareCurrentLimitConfirmed = false;
    out = tick(g, in);
    assert(out.state == ABORTED && !out.outputEnable);

    initialize(g);
    in = safe(400);
    in.startRequested = true;
    in.requestedDurationMs = MAX_PULSE_DURATION_MS + 1;
    out = tick(g, in);
    assert(out.state == ABORTED && out.reason == REASON_BAD_DURATION);

    initialize(g);
    in = safe(500);
    in.startRequested = true;
    out = tick(g, in);
    assert(out.outputEnable);
    in = safe(501);
    in.stopRequested = true;
    out = tick(g, in);
    assert(out.state == ABORTED && out.reason == REASON_STOP && !out.outputEnable);

    initialize(g);
    in = safe(600);
    in.startRequested = true;
    out = tick(g, in);
    in = safe(601);
    in.normalDriveActive = true;
    out = tick(g, in);
    assert(out.state == ABORTED && out.reason == REASON_DRIVE_ACTIVE && !out.outputEnable);

    // millis() rollover: start near UINT32_MAX, expire after 10 ms.
    initialize(g);
    in = safe(0xFFFFFFFCu);
    in.startRequested = true;
    in.requestedDurationMs = 10;
    out = tick(g, in);
    assert(out.outputEnable);
    in = safe(5);
    out = tick(g, in);
    assert(out.state == ACTIVE && out.outputEnable);
    in = safe(6);
    out = tick(g, in);
    assert(out.state == COMPLETE && !out.outputEnable);

    return 0;
}
