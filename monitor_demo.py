"""Standalone synthetic server monitoring data pipeline.

This code is independent of any commercial DayZ system. Requires Python 3.11+.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Mapping


class SnapshotError(ValueError):
    """Invalid input snapshot or query."""


@dataclass(frozen=True)
class Snapshot:
    server: str
    timestamp: str
    online: int
    capacity: int
    queue: int
    available: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "Snapshot":
        if not isinstance(data, dict):
            raise SnapshotError("Snapshot must be a JSON object")
        server = data.get("server")
        if not isinstance(server, str) or not 1 <= len(server.strip()) <= 80:
            raise SnapshotError("server must be a nonempty name of at most 80 characters")
        timestamp = data.get("timestamp")
        if not isinstance(timestamp, str):
            raise SnapshotError("timestamp must be an ISO 8601 string")
        try:
            instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SnapshotError("timestamp must be a valid ISO 8601 string") from exc
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise SnapshotError("timestamp must include a timezone")
        instant = instant.astimezone(timezone.utc)

        numbers: dict[str, int] = {}
        for field in ("online", "capacity", "queue"):
            value = data.get(field)
            if type(value) is not int or value < 0:
                raise SnapshotError(f"{field} must be a nonnegative integer")
            numbers[field] = value
        available = data.get("available")
        if type(available) is not bool:
            raise SnapshotError("available must be a boolean")
        if numbers["online"] > numbers["capacity"]:
            raise SnapshotError("online cannot exceed capacity")
        if not available and (numbers["online"] or numbers["queue"]):
            raise SnapshotError("offline server cannot have online players or a queue")
        return cls(
            server=server.strip(),
            timestamp=instant.isoformat(timespec="seconds"),
            available=available,
            **numbers,
        )


class MonitorStore:
    """File-backed SQLite snapshot repository (no live network integration)."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("Use a file-backed database for this demo")
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    server TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    online INTEGER NOT NULL CHECK (online >= 0),
                    capacity INTEGER NOT NULL CHECK (capacity >= 0),
                    queue INTEGER NOT NULL CHECK (queue >= 0),
                    available INTEGER NOT NULL CHECK (available IN (0, 1)),
                    PRIMARY KEY (server, timestamp)
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(timestamp)"
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record(self, payload: Mapping[str, object]) -> Snapshot:
        snapshot = Snapshot.from_mapping(payload)
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO snapshots(server, timestamp, online, capacity, queue, available)
                VALUES (:server, :timestamp, :online, :capacity, :queue, :available)
                ON CONFLICT(server, timestamp) DO UPDATE SET
                    online=excluded.online,
                    capacity=excluded.capacity,
                    queue=excluded.queue,
                    available=excluded.available
            """, asdict(snapshot))
        return snapshot

    def latest(self, server: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE server=? ORDER BY timestamp DESC LIMIT 1",
                (server,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["available"] = bool(result["available"])
        return result

    def daily_summary(self, server: str, day: str) -> dict | None:
        try:
            target = date.fromisoformat(day)
        except ValueError as exc:
            raise SnapshotError("day must be YYYY-MM-DD") from exc
        with self._connection() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS samples,
                       SUM(available) AS available_samples,
                       ROUND(AVG(online), 2) AS average_players,
                       MAX(online) AS peak_players,
                       MAX(queue) AS peak_queue
                  FROM snapshots
                 WHERE server=? AND substr(timestamp, 1, 10)=?
            """, (server, target.isoformat())).fetchone()
        if row["samples"] == 0:
            return None
        samples = row["samples"]
        return {
            "server": server,
            "day": target.isoformat(),
            "samples": samples,
            "available_samples": row["available_samples"],
            "availability_percent": round(100 * row["available_samples"] / samples, 2),
            "average_players": row["average_players"],
            "peak_players": row["peak_players"],
            "peak_queue": row["peak_queue"],
        }


def ingest_jsonl(store: MonitorStore, path: str | Path) -> int:
    """Import synthetic JSON Lines data. Invalid input fails with a line number."""
    count = 0
    for line_no, text in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            data = json.loads(text)
            store.record(data)
        except (json.JSONDecodeError, SnapshotError) as exc:
            raise SnapshotError(f"Line {line_no}: {exc}") from exc
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic server-monitoring data pipeline")
    parser.add_argument("--db", default="demo-monitor.sqlite3")
    parser.add_argument("--file", default="fixtures/demo_snapshots.jsonl")
    parser.add_argument("--server", default="demo-dayz-01")
    parser.add_argument("--day", default="2026-11-01")
    args = parser.parse_args()
    store = MonitorStore(args.db)
    imported = ingest_jsonl(store, args.file)
    print(json.dumps({
        "imported": imported,
        "latest": store.latest(args.server),
        "summary": store.daily_summary(args.server, args.day),
    }, indent=2))


if __name__ == "__main__":
    main()
