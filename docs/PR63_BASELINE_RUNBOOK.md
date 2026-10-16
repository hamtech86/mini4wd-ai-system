# PR #63-era runnable baseline

## Purpose
Keep the complete project snapshot used as the integration safety baseline, without replacing or changing `main`.

## Pinned source
- Snapshot commit: `872ae01545d9a4aff5d076914a68a6793beea653`
- Safety branch: `safety/pr63-runnable-baseline-20261016`
- Preserved entry-point copy: `app/main_pr63_baseline.py`
- The copy was made from `app/main.py` at the pinned snapshot; it is not a reimplementation.

## Running
From the repository root, install the dependencies listed in `requirements.txt`, then run either:
- `python -m app.main` (original snapshot entry point)
- `python app/main_pr63_baseline.py` (preserved named entry point)

The runtime launch has **not yet been executed in this environment**. Treat this as a preserved runnable candidate, not as a passed launch test. Before using hardware, verify the selected serial ports and database path.

## Database safety constraint
Do not use a branch-local copy of the database as a new source of truth. Before integrating or switching operational execution between worktrees, set every worktree to the same explicitly chosen canonical database file. The existing code has inconsistent path construction:
- `ui/main_window.py` resolves `<project-root>/database/mini4wd.db`.
- `app/config.py` resolves `<project-root>/app/database/mini4wd.db`.
- `database/manager/database_manager.py` defaults to the relative path `database/mini4wd.db`.

Do not silently choose or migrate a database until the operator's currently used data file has been identified. Unify all connection paths behind one canonical configuration, preserve a backup, and test schema compatibility before enabling a shared writable SQLite database. A shared database does not mean each branch may run independent schema migrations against it without coordination.
