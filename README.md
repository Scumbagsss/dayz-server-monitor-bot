# DayZ Server Monitor Bot

> **Portfolio showcase — production source is private and this repository is intentionally non-runnable.**

DayZ server status monitor with online/queue tracking, historical statistics and activity graphs.

## What it demonstrates

- Server availability checks
- Online/max player tracking
- Queue tracking
- Historical snapshots
- Daily/hourly activity reports
- Auto-updating status message

## Technology

Python • discord.py • aiosqlite • matplotlib • Steam server query

## High-level workflow

1. Query game server
2. Normalize status snapshot
3. Persist time-series data
4. Render public status summary
5. Generate historical report on demand

## Public interface preview

The public skeleton exposes only the architectural surface:

- `query_server(...)`
- `store_snapshot(...)`
- `render_status(...)`
- `build_activity_report(...)`

The production implementations behind these methods are withheld. See [`NOTICE.md`](NOTICE.md).

## Repository contents

- `src/public_interface.py` — non-runnable interface skeleton;
- `docs/ARCHITECTURE.md` — high-level design;
- `examples/config.example.jsonc` — sanitized configuration shape;
- `LICENSE` — explicit all-rights-reserved notice.

## Status

Production-tested private project / portfolio edition.
