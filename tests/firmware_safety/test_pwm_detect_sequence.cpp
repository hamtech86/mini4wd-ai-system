#include <assert.h>
#include <stdint.h>
#include "../../firmware/motor/PwmDetectSequence.h"

using namespace PwmDetectSequence;

int main() {
    Sequence sequence;
    assert(sequence.state() == IDLE);
    assert(sequence.begin(100));
    assert(!sequence.begin(200));

    Snapshot s = sequence.snapshot(100);
    assert(s.state == RUNNING && s.stage_index == 0 && s.pwm == 0);

    // Each PWM value is held for a full 10 seconds.
    for (uint8_t pwm = 0; pwm < 30; ++pwm) {
        const uint32_t start = 100UL + (uint32_t)pwm * STAGE_DURATION_MS;
        assert(!sequence.update(start + STAGE_DURATION_MS - 1));
        assert(sequence.update(start + STAGE_DURATION_MS));
        s = sequence.snapshot(start + STAGE_DURATION_MS);
        assert(s.state == RUNNING);
        assert(s.stage_index == (uint8_t)(pwm + 1));
        assert(s.pwm == (uint8_t)(pwm + 1));
    }

    const uint32_t last_start = 100UL + 30UL * STAGE_DURATION_MS;
    assert(!sequence.update(last_start + STAGE_DURATION_MS - 1));
    assert(sequence.update(last_start + STAGE_DURATION_MS));
    assert(sequence.state() == COMPLETE);
    assert(sequence.snapshot(last_start + STAGE_DURATION_MS).pwm == 0);

    // STOP aborts a run and cannot be mistaken for completion.
    assert(sequence.begin(500000));
    assert(sequence.stop());
    assert(sequence.state() == ABORTED);
    assert(!sequence.update(600000));
    assert(!sequence.stop());

    // Unsigned millis() subtraction handles wraparound.
    const uint32_t wrap_start = 0xfffffff0UL;
    assert(sequence.begin(wrap_start));
    assert(!sequence.update((uint32_t)(wrap_start + 9999UL)));
    assert(sequence.update((uint32_t)(wrap_start + 10000UL)));
    assert(sequence.snapshot((uint32_t)(wrap_start + 10000UL)).pwm == 1);

    // A delayed loop advances only one stage, never skipping PWM values.
    assert(sequence.update((uint32_t)(wrap_start + 30000UL)));
    assert(sequence.snapshot((uint32_t)(wrap_start + 30000UL)).pwm == 2);
    return 0;
}
