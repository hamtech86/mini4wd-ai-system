#include <assert.h>
#include <string.h>
#include "Arduino.h"

MockSerial Serial;
int mock_analog_write[32] = {};
int mock_digital_write[32] = {};

#include "../../firmware/motor/MotoreRev.ino"

int main() {
    initializeVariables();
    initializePins();
    stopMotor();
    setState(STATE_READY);

    // STOP is authoritative: internal PWM, motor output, direction and
    // legacy voltage control are all disabled.
    runtime.state = STATE_RUN;
    runtime.running = true;
    runtime.pwm = 120;
    voltageControl.enabled = true;
    mock_analog_write[PIN_PWM] = 120;
    processCommand("STOP");
    assert(runtime.state == STATE_STOP);
    assert(!runtime.running);
    assert(runtime.pwm == 0);
    assert(!voltageControl.enabled);
    assert(mock_analog_write[PIN_PWM] == 0);
    assert(mock_digital_write[PIN_IN3] == LOW);
    assert(mock_digital_write[PIN_IN4] == LOW);

    // A periodic legacy update must not restore PWM after STOP.
    runtime.state = STATE_STOP;
    runtime.running = false;
    runtime.pwm = 0;
    voltageControl.enabled = true;  // simulate stale/corrupt legacy flag
    voltageControl.targetVoltage = 3.0f;
    sensor.motorVoltage = 0.0f;
    mock_analog_write[PIN_PWM] = 0;
    voltageControlUpdate();
    assert(mock_analog_write[PIN_PWM] == 0);
    assert(runtime.pwm == 0);

    // Host-owned voltage control commands are rejected.
    voltageControl.enabled = false;
    const float originalTarget = voltageControl.targetVoltage;
    processCommand("VCTRL=ON");
    assert(!voltageControl.enabled);
    processCommand("TARGET=3.00");
    assert(voltageControl.targetVoltage == originalTarget);

    // PAUSE clears both the hardware output and internal PWM state.
    runtime.state = STATE_RUN;
    runtime.running = true;
    runtime.paused = false;
    runtime.pwm = 90;
    mock_analog_write[PIN_PWM] = 90;
    processCommand("PAUSE");
    assert(runtime.state == STATE_PAUSE);
    assert(runtime.pwm == 0);
    assert(mock_analog_write[PIN_PWM] == 0);

    return 0;
}
