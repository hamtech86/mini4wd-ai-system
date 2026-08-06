import serial
import time


PORT = "/dev/ttyACM0"
BAUD = 57600


ser = serial.Serial(
    PORT,
    BAUD,
    timeout=1
)

time.sleep(2)  # Arduinoリセット待ち


print("=== Arduino Receive Test ===")


while True:

    if ser.in_waiting:

        line = ser.readline().decode(
            errors="ignore"
        ).strip()

        print(line)

