#include <assert.h>
#include <stdint.h>
#include "../../firmware/motor/WindingAdcTimestampCapture.h"

using namespace WindingAdcTimestampCapture;

static uint32_t fakeTime = 1000;
static uint8_t expectedChannels[4] = {0, 1, 4, 5};
static uint8_t readIndex = 0;

static uint32_t fakeMicros() {
    const uint32_t value = fakeTime;
    fakeTime += 2;
    return value;
}

static uint16_t fakeRead(uint8_t channel) {
    assert(channel == expectedChannels[readIndex]);
    ++readIndex;
    fakeTime += 8; // simulated ADC conversion time
    return (uint16_t)(100 + channel);
}

int main() {
    Frame frame;
    initialize(frame);
    assert(frame.count == 0);
    readIndex = 0;
    fakeTime = 1000;
    assert(captureFour(frame, expectedChannels, fakeRead, fakeMicros));
    assert(frame.count == 4);
    for (uint8_t i = 0; i < 4; ++i) {
        assert(frame.readings[i].channel == expectedChannels[i]);
        assert(frame.readings[i].rawAdc == 100 + expectedChannels[i]);
        assert(frame.readings[i].conversionDurationUs == 8);
        assert(frame.readings[i].timestampUs >= 1000);
    }

    initialize(frame);
    assert(!captureFour(frame, expectedChannels, 0, fakeMicros));
    assert(frame.count == 0);
    assert(!captureFour(frame, expectedChannels, fakeRead, 0));
    assert(frame.count == 0);

    // Unsigned elapsed arithmetic remains valid across micros() rollover.
    fakeTime = 0xfffffff8UL;
    readIndex = 0;
    assert(captureFour(frame, expectedChannels, fakeRead, fakeMicros));
    assert(frame.count == 4);
    assert(frame.readings[0].conversionDurationUs == 8);
    return 0;
}
