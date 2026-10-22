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

    // Every drive/restart command is rejected after STOP until explicit ARM,
    // and untagged/stale commands remain rejected even after a new ARM.
    processCommand("START");
    processCommand("FWD");
    processCommand("REV");
    processCommand("RESUME");
    processCommand("PWM=80");
    assert(!runtime.running);
    assert(runtime.pwm == 0);
    assert(mock_analog_write[PIN_PWM] == 0);

    processCommand("ARM=AB12CD34");
    assert(driveArmed);
    processCommand("FWD");
    assert(!runtime.running);
    assert(runtime.pwm == 0);
    processCommand("FWD@DEADBEEF");
    assert(!runtime.running);
    processCommand("FWD@AB12CD34");
    assert(runtime.running);
    assert(runtime.direction == DIR_FORWARD);

    // STOP revokes the token. Old-token commands cannot restart the motor.
    processCommand("STOP");
    assert(!driveArmed);
    assert(!runtime.running);
    assert(runtime.pwm == 0);
    processCommand("PWM=100@AB12CD34");
    assert(!runtime.running);
    assert(runtime.pwm == 0);

    // A fresh ARM permits the next intentionally authorized run.
    processCommand("ARM=1122AABB");
    assert(driveArmed);
    processCommand("REV@1122AABB");
    assert(runtime.running);
    assert(runtime.direction == DIR_REVERSE);
    processCommand("STOP");
    assert(!driveArmed);
    assert(!runtime.running);

    // Nonce-correlated safety commands are accepted without an ARM token.
    // PWM=0 preserves RUN state but forces the output low; correlated STOP
    // then stops the runtime and revokes the arm token.
    processCommand("ARM=ABCDEF12");
    processCommand("FWD@ABCDEF12");
    assert(runtime.running);
    runtime.pwm = 80;
    mock_analog_write[PIN_PWM] = 80;
    processCommand("PWM=0#TESTNONCE");
    assert(runtime.running);
    assert(runtime.pwm == 0);
    assert(mock_analog_write[PIN_PWM] == 0);
    processCommand("STOP#TESTNONCE");
    assert(runtime.state == STATE_STOP);
    assert(!runtime.running);
    assert(!driveArmed);
    assert(runtime.pwm == 0);
    assert(mock_analog_write[PIN_PWM] == 0);

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
