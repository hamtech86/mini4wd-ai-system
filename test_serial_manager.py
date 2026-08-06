from communication.serial_manager import SerialManager
import time


def main():

    print("=== SerialManager Test Start ===")

    manager = SerialManager()

    print("Connecting...")

    if not manager.connect("/dev/ttyACM0"):
        print("Connection failed")
        return

    print("Connected")


    time.sleep(2)


    print("FORWARD")
    manager.forward()

    time.sleep(2)


    print("PWM 50")
    manager.set_pwm(50)

    time.sleep(5)


    print("STOP")
    manager.stop_breakin()

    time.sleep(2)


    manager.disconnect()

    print("Test Complete")


if __name__ == "__main__":
    main()

