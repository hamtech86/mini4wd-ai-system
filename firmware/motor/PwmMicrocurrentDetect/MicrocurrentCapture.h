#ifndef MICROCURRENT_CAPTURE_H
#define MICROCURRENT_CAPTURE_H
#include <Arduino.h>
namespace MicrocurrentCapture {
struct Reading { uint8_t channel; uint16_t raw; uint32_t timestampUs; };
struct Frame { Reading reading[4]; uint8_t count; };
inline uint16_t readAdc(uint8_t channel) { return (uint16_t)analogRead(channel); }
inline uint32_t readMicros() { return micros(); }
inline bool capture(Frame &f, const uint8_t channels[4]) {
  f.count = 0;
  for (uint8_t i = 0; i < 4; ++i) {
    const uint32_t before = readMicros();
    const uint16_t raw = readAdc(channels[i]);
    const uint32_t after = readMicros();
    f.reading[i] = {channels[i], raw, before + (after - before) / 2UL};
    ++f.count;
  }
  return true;
}
}
#endif
