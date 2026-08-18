# Battery Result Commit Policy

Battery measurement data and official Battery evaluation history are intentionally separated.

1. A real-device run produces a Measurement Session and raw Measurements.
2. Benchmark Analysis produces a provisional Result for operator review.
3. The operator checks the Result and error/quality state.
4. Only after explicit human confirmation is the Result committed as an official Battery evaluation record.
5. Failed, cancelled, or suspicious runs are not promoted to official evaluation history.

The Battery Instance is not permanently tied to a channel. The same instance may be measured on CH1 in one session and CH2 in another. For a simultaneous STARTALL operation, the two channels must use different Battery Instances.

Analysis never mutates raw Measurement data.
