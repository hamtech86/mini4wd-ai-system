# Battery 5A `STARTALL` semantics

The verified standalone firmware implements `STARTALL` by calling `startChannel(ch1)` and `startChannel(ch2)`. The channels remain independent and the loop emits one `DATA` frame for CH1 and one for CH2 on each cycle.

Therefore the application model is:

- `START1` -> independent CH1 measurement/session
- `START2` -> independent CH2 measurement/session
- `STARTALL` -> start both independent measurements/sessions at the same control event
- `STOP1` / `STOP2` -> stop only that channel
- `STOPALL` -> stop both channels

`ALL` is a control command, not a Measurement channel. Benchmark analysis must never combine CH1 and CH2 into a single battery result merely because `STARTALL` was used.
