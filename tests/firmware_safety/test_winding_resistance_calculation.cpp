#include <assert.h>
#include "../../firmware/motor/WindingResistance.h"

int main() {
    using namespace WindingResistance;
    const Config config = {
        0.01f, 2.0f, 0.05f, 2.0f, 0.08f, 0.01f, 10.0f
    };
    const Sample samples[] = {
        {0.20f, 0.10f}, {0.30f, 0.10f}, {0.25f, 0.10f}
    };
    Result result = calculate(samples, 3, config);
    assert(result.valid);
    assert(result.validCount == 3);
    assert(fabs(result.medianOhm - 2.5f) < 0.001f);
    assert(fabs(result.minOhm - 2.0f) < 0.001f);
    assert(fabs(result.maxOhm - 3.0f) < 0.001f);

    const Sample polarityMismatch[] = {{0.20f, -0.10f}};
    result = calculate(polarityMismatch, 1, config);
    assert(!result.valid && result.reason == INVALID_POLARITY);

    const Sample belowCurrentRange[] = {{0.20f, 0.04f}};
    result = calculate(belowCurrentRange, 1, config);
    assert(!result.valid && result.reason == INVALID_CURRENT_RANGE);

    return 0;
}
