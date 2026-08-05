"""
MOTOR_BREAKIN_V3
Arduino Command Sender
"""


class CommandSender:
    def __init__(self, serial_controller):
        self.serial = serial_controller

    def send(self, command: str):
        self.serial.send(command)

    def start(self):
        self.send("START")

    def stop(self):
        self.send("STOP")

    def pwm(self, value: int):
        self.send(f"PWM,{value}")

    def direction(self, value: str):
        self.send(f"DIR,{value}")
