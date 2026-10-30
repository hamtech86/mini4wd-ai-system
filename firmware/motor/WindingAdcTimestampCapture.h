#ifndef MINI4WD_WINDING_ADC_TIMESTAMP_CAPTURE_H
#define MINI4WD_WINDING_ADC_TIMESTAMP_CAPTURE_H

#include <stdint.h>

// Hardware-neutral capture wrapper. Channel order and physical meaning are
// supplied by the caller; this module never assumes ACS/voltage pin mapping.
namespace WindingAdcTimestampCapture {

typedef uint16_t (*ReadAdcFn)(uint8_t channel);
typedef uint32_t (*MicrosFn)();

struct Reading {
    uint8_t channel;
    uint16_t rawAdc;
    uint32_t timestampUs;
    uint32_t conversionDurationUs;
};

struct Frame {
    Reading readings[4];
    uint8_t count;
};

inline void initialize(Frame &frame) {
    frame.count = 0;
}

inline bool captureFour(Frame &frame, const uint8_t channels[4],
                        ReadAdcFn readAdc, MicrosFn microsNow) {
    if (channels == 0 || readAdc == 0 || microsNow == 0) {
        frame.count = 0;
        return false;
    }

    frame.count = 0;
    for (uint8_t i = 0; i < 4; ++i) {
        const uint32_t before = microsNow();
        const uint16_t raw = readAdc(channels[i]);
        const uint32_t after = microsNow();
        const uint32_t duration = after - before;
        frame.readings[i] = Reading{
            channels[i], raw, before + duration / 2U, duration
        };
        ++frame.count;
    }
    return true;
}

} // namespace WindingAdcTimestampCapture

#endif
