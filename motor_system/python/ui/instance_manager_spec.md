# Motor Instance Manager Completion Scope

## Role

Motor Instance Manager manages individual motor identity, lifecycle, history and comparison. It does not execute break-in recipes or control hardware.

## Fixed integration keys

- Motor Instance ID (`instance_id`)
- Measurement Session ID (`session_id`)
- Break-in Result
- Benchmark RPM (optional confirmed result)

## Required views

### Instance list

Show identity/lifecycle fields and latest session status.

### Instance detail

Show identity, lifecycle, measurement sessions, break-in history and latest available results.

### Comparison

Allow multiple instances to be selected and compare the latest compatible results. Missing values must remain blank/NA.

## Data integrity

- Raw measurement logs are immutable from the UI.
- Motor Instance deletion is logical/soft deletion.
- Benchmark RPM is not stored by overwriting `breakin_log.measured_rpm`.
- Historical sessions remain associated with their original instance.

## Main.py boundary

Main.py supplies benchmark execution and confirmation. Instance Manager consumes the persisted result. Instance Manager must not modify Main.py's break-in control flow.

## Completion criteria

- Register an individual motor.
- Edit an individual motor.
- Retire/delete without losing history.
- Open individual history.
- Show latest benchmark/break-in result.
- Select and compare multiple motors.
- Preserve missing/NA values safely.
- Keep the Main.py integration contract explicit.
