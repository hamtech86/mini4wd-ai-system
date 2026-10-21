"""Legacy direct motor test intentionally disabled.

The former utility bypassed the integrated application's verified INFO identity
gate and emergency-stop latch. It must not be used for physical testing.
"""


def main():
    print(
        "BLOCKED: legacy hardware test is disabled because direct SerialManager "
        "commands do not verify MOTOR_BREAKIN_V3 INFO identity."
    )
    print(
        "No serial port was opened and no motor command was sent. "
        "Use the integrated application only after Issue #98 re-authorizes testing."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
