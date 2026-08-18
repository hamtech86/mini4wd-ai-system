# Battery DB operator UI

The main application exposes `BATTERY DATABASE / INSTANCE & RESULT REGISTRATION`.

## Instance registration

Select a Battery Model and enter an Instance ID such as `BAT0001`, plus optional serial/nickname/notes. This is the physical Battery master/instance record used by later measurement sessions.

## Benchmark result registration

Select a completed Measurement Session and Battery Instance, enter the observed Benchmark result values, then explicitly confirm measurement quality and operator approval before pressing `REGISTER CONFIRMED BENCHMARK RESULT`.

ERROR/CANCEL/incomplete sessions cannot be registered through this UI. The UI writes only the confirmed derived result; it does not modify raw Measurement rows and does not alter the verified 5A Arduino firmware.
