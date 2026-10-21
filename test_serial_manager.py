"""Legacy direct motor test intentionally disabled.

This script used SerialManager directly and could issue FWD/PWM without the
verified INFO identity gate used by the integrated application. Use the
integrated UI only after Issue #98 explicitly re-authorizes physical testing.
"""


def main():
    print(
        "BLOCKED: direct SerialManager motor test is disabled because this path "
        "does not verify MOTOR_BREAKIN_V3 INFO identity."
    )
    print(
        "No serial port was opened and no motor command was sent. "
        "Use the integrated application only after Issue #98 re-authorizes testing."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
