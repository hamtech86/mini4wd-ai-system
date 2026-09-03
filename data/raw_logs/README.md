# Raw Log Library

This directory is the data boundary for original Motor/Battery measurement logs.

## Rules

- `log_id` is the unique logical identifier used by analysis and downstream tools.
- Raw log bodies are immutable after registration.
- Management tags are stored separately from the raw body.
- Management tags include, at minimum: individual ID, nickname, session number, acquisition date/time, and optional memo.
- `Instance ID` is the formal individual identifier; `Nickname` is display/management information only.
- Firmware elapsed time and externally recorded acquisition date/time are distinct values.
- Parser, feature extraction, evaluation, diagnosis, prediction, and learning outputs must not be written into the raw body.
- Adding raw data must not require a source/specification branch.
- Code/specification changes must not be mixed with raw-data commits.

## Storage layout

```text
data/raw_logs/
  README.md
  index.csv
  motor/
    MOTOR-xxxxxx/
      LOG-xxxxxx.<original-extension>
      metadata.json
  battery/
    BATTERY-xxxxxx/
      LOG-xxxxxx.<original-extension>
      metadata.json
```

`metadata.json` is an editable management-tag store for the individual directory and is keyed by `log_id`, allowing multiple sessions/logs for one individual without modifying any raw body.

`index.csv` is the library index for fast discovery. It duplicates management metadata for indexing; the per-individual `metadata.json` remains the editable tag store.

## Boundary with GitHub

GitHub may currently hold the raw-log data for operational efficiency. Git-managed source code, current specifications, and the library management mechanism remain development assets. Growth of raw logs must not branch or fork those development systems.

Analysis must resolve a log by `log_id`, not by a GitHub path. This permits future migration of raw storage to local storage, a database, or another large-file backend without changing the analysis contract.

## Existing logs

Existing Motor logs are to be imported without rewriting their original bodies. When the original binary/text source is not present in this repository, registration must wait for the original source rather than reconstructing or normalizing it. Existing source-reference documents are metadata/documentation, not substitutes for the immutable raw body.
