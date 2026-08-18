# Battery manual result registration

Battery 5A measurement data is not automatically promoted to the official Battery evaluation history.

## Flow

1. Perform the physically verified Battery 5A measurement.
2. Keep the resulting Measurement/Session and provisional Benchmark result.
3. Review the result manually.
4. Register the result to the official Battery history only when:
   - session result is `COMPLETE`;
   - measurement quality is acceptable;
   - an operator explicitly confirms the result.

`ERROR` and `CANCEL` sessions are not eligible for official registration.

## Instance/channel rule

Battery Instance and channel are independent concepts. The same Instance may be measured on CH1 in one session and CH2 in another. During one simultaneous `STARTALL`, the same Instance may not be assigned to both channels.

The verified Arduino 5A firmware remains outside this workflow's modification scope.
