"""
MOTOR_BREAKIN_V3
Hardware communication test utility

Purpose:
- Verify SerialManager connection path before real break-in
- Check START / PWM / STOP command sequence

This script does not execute a full break-in recipe.
"""

import time

try:
    from communication.serial_manager import SerialManager
except ImportError:
    SerialManager = None


PORT = "/dev/ttyACM0"
BAUDRATE = 57600


def main():

    if SerialManager is None:
        print("SerialManager import failed")
        return

    serial = SerialManager(
        port=PORT,
        baudrate=BAUDRATE
    )

    print("Connecting Arduino...")

    serial.connect()

    print("Forward test")
    serial.forward()

    time.sleep(1)

    print("PWM test 80")
    serial.set_pwm(80)

    time.sleep(3)

    print("PWM stop")
    serial.set_pwm(0)

    serial.stop_breakin()

    print("Test complete")


if __name__ == "__main__":
    main()
