#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define F(value) value
#define INPUT 0
#define OUTPUT 1
#define LOW 0
#define HIGH 1
#define A0 14
#define A1 15
#define A2 16
#define A3 17
#define A4 18
#define A5 19

class MockSerial {
public:
    void begin(unsigned long) {}
    int available() { return 0; }
    int read() { return -1; }
    template <typename T> void print(T) {}
    template <typename T> void print(T, int) {}
    void print(const char*) {}
    void println() {}
    template <typename T> void println(T) {}
    template <typename T> void println(T, int) {}
    void println(const char*) {}
};

extern MockSerial Serial;
extern int mock_analog_write[32];
extern int mock_digital_write[32];

inline void pinMode(uint8_t, uint8_t) {}
inline int analogRead(uint8_t) { return 512; }
inline void analogWrite(uint8_t pin, int value) {
    if (pin < 32) mock_analog_write[pin] = value;
}
inline void digitalWrite(uint8_t pin, uint8_t value) {
    if (pin < 32) mock_digital_write[pin] = value;
}
inline unsigned long millis() { return 1000UL; }
inline unsigned long micros() { return 1000000UL; }
inline void delay(unsigned long) {}
