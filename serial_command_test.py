import serial
import time


ser = serial.Serial(
    "/dev/ttyACM0",
    57600,
    timeout=1
)

time.sleep(2)


while True:

    cmd = input("CMD> ")

    ser.write(
        (cmd + "\n").encode()
    )

    time.sleep(0.2)

    while ser.in_waiting:

        print(
            ser.readline()
            .decode(errors="ignore")
            .strip()
        )

