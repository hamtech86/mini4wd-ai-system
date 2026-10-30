#include <assert.h>
#include "../../firmware/motor/WindingTimestampedPairer.h"

using namespace WindingTimestampedPairer;

int main() {
    Collector c;
    Pair p;
    initialize(c);

    // Pair only within the caller-supplied skew tolerance.
    assert(pushVoltage(c, 0.20f, 1000, 50, p) == NO_PAIR);
    assert(pushCurrent(c, 0.10f, 1040, 50, p) == PAIR_READY);
    assert(p.sample.voltageV == 0.20f && p.sample.currentA == 0.10f);
    assert(p.skewUs == 40 && c.pairedCount == 1);
    assert(!c.hasVoltage && !c.hasCurrent);

    // A stale older reading is dropped; the newer side remains pending.
    assert(pushVoltage(c, 0.21f, 2000, 20, p) == NO_PAIR);
    assert(pushCurrent(c, 0.11f, 2050, 20, p) == DROPPED_OLDER_VOLTAGE);
    assert(!c.hasVoltage && c.hasCurrent);
    assert(c.rejectedCount == 1);

    // A subsequent voltage can pair with the retained current.
    assert(pushVoltage(c, 0.22f, 2060, 20, p) == PAIR_READY);
    assert(p.skewUs == 10 && c.pairedCount == 2);

    // Replacing an unmatched same-kind reading is explicit and counted.
    assert(pushCurrent(c, 0.12f, 3000, 20, p) == NO_PAIR);
    assert(pushCurrent(c, 0.13f, 3010, 20, p) == REPLACED_PENDING_CURRENT);
    assert(c.rejectedCount == 2);

    // micros() wraparound: timestamps 20us apart across UINT32_MAX still pair.
    initialize(c);
    assert(pushVoltage(c, 0.20f, 0xfffffff0UL, 30, p) == NO_PAIR);
    assert(pushCurrent(c, 0.10f, 0x00000004UL, 30, p) == PAIR_READY);
    assert(p.skewUs == 20);

    // Exact configured boundary is accepted; one microsecond over is not.
    initialize(c);
    assert(pushVoltage(c, 0.20f, 100, 25, p) == NO_PAIR);
    assert(pushCurrent(c, 0.10f, 125, 25, p) == PAIR_READY);
    assert(pushVoltage(c, 0.20f, 200, 25, p) == NO_PAIR);
    assert(pushCurrent(c, 0.10f, 226, 25, p) == DROPPED_OLDER_VOLTAGE);

    return 0;
}
