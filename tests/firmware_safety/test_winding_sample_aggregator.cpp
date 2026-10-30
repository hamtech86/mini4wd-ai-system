#include <assert.h>
#include <math.h>
#include "../../firmware/motor/WindingSampleAggregator.h"

using namespace WindingSampleAggregator;
using namespace WindingResistance;

static const Config config = {
    0.01f, 2.0f, 0.05f, 2.0f, 0.08f, 0.01f, 10.0f
};

int main() {
    Collector c;
    initialize(c);

    // Empty aggregation is invalid, not a fabricated zero-ohm result.
    Summary s = summarize(c, false);
    assert(!s.valid && s.count == 0);

    // Accepted synchronous pairs produce median/min/max.
    assert(add(c, Sample{0.20f, 0.10f}, config) == ADD_ACCEPTED);
    assert(add(c, Sample{0.30f, 0.10f}, config) == ADD_ACCEPTED);
    assert(add(c, Sample{0.25f, 0.10f}, config) == ADD_ACCEPTED);
    s = summarize(c, true);
    assert(s.valid && s.count == 3);
    assert(fabs(s.medianOhm - 2.5f) < 0.001f);
    assert(fabs(s.minOhm - 2.0f) < 0.001f);
    assert(fabs(s.maxOhm - 3.0f) < 0.001f);

    // Invalid pair is retained as a reason and cannot be silently counted.
    initialize(c);
    assert(add(c, Sample{0.2f, -0.1f}, config) == ADD_REJECTED_INVALID);
    s = summarize(c, false);
    assert(!s.valid && s.reason == INVALID_POLARITY);
    assert(add(c, Sample{0.2f, 0.1f}, config) == ADD_ACCEPTED);
    s = summarize(c, true);
    assert(!s.valid && s.reason == INVALID_POLARITY);
    s = summarize(c, false);
    assert(s.valid && s.count == 1);

    // Bound is fixed; the 33rd accepted sample is refused.
    initialize(c);
    for (uint8_t i = 0; i < MAX_POINTS; ++i) {
        assert(add(c, Sample{0.2f, 0.1f}, config) == ADD_ACCEPTED);
    }
    assert(add(c, Sample{0.2f, 0.1f}, config) == ADD_REJECTED_FULL);
    s = summarize(c, true);
    assert(!s.valid && s.reason == INVALID_SAMPLE_COUNT);

    // Range and resolution rejection are surfaced with their exact cause.
    initialize(c);
    assert(add(c, Sample{0.001f, 0.1f}, config) == ADD_REJECTED_INVALID);
    assert(c.firstInvalidReason == INVALID_VOLTAGE_RANGE);
    initialize(c);
    assert(add(c, Sample{0.2f, 0.06f}, config) == ADD_REJECTED_INVALID);
    assert(c.firstInvalidReason == INVALID_CURRENT_RESOLUTION);

    return 0;
}
