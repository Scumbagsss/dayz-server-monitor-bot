"""Synthetic data tests; never uses live game-server records."""
import json
from pathlib import Path
import tempfile
import unittest

from monitor_demo import MonitorStore, Snapshot, SnapshotError, ingest_jsonl

GOOD = {
    "server": "demo-01",
    "timestamp": "2026-11-01T09:00:00Z",
    "online": 12,
    "capacity": 80,
    "queue": 2,
    "available": True,
}


class SnapshotTests(unittest.TestCase):
    def test_valid_snapshot(self):
        self.assertEqual(Snapshot.from_mapping(GOOD).online, 12)

    def test_normalizes_offset_to_utc(self):
        value = {**GOOD, "timestamp": "2026-11-01T12:00:00+03:00"}
        self.assertEqual(Snapshot.from_mapping(value).timestamp, "2026-11-01T09:00:00+00:00")

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "timestamp": "2026-11-01T09:00:00"})

    def test_invalid_timestamp_rejected(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "timestamp": "not-a-date"})

    def test_invalid_server(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "server": " "})

    def test_bool_not_accepted_as_player_count(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "online": True})

    def test_negative_queue(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "queue": -1})

    def test_online_above_capacity(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "online": 81})

    def test_offline_with_players_rejected(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "available": False})

    def test_offline_zero_players_accepted(self):
        value = {**GOOD, "online": 0, "queue": 0, "available": False}
        self.assertFalse(Snapshot.from_mapping(value).available)

    def test_invalid_availability(self):
        with self.assertRaises(SnapshotError):
            Snapshot.from_mapping({**GOOD, "available": 1})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.store = MonitorStore(self.db)

    def test_record_and_latest(self):
        self.store.record(GOOD)
        self.assertEqual(self.store.latest("demo-01")["online"], 12)

    def test_available_bool_after_read(self):
        self.store.record(GOOD)
        self.assertIs(self.store.latest("demo-01")["available"], True)

    def test_missing_server_returns_none(self):
        self.assertIsNone(self.store.latest("missing"))

    def test_persists_across_instance(self):
        self.store.record(GOOD)
        self.assertEqual(MonitorStore(self.db).latest("demo-01")["online"], 12)

    def test_retry_does_not_duplicate_sample(self):
        self.store.record(GOOD)
        self.store.record(GOOD)
        self.assertEqual(self.store.daily_summary("demo-01", "2026-11-01")["samples"], 1)

    def test_newer_duplicate_replaces_existing(self):
        self.store.record(GOOD)
        self.store.record({**GOOD, "online": 19})
        self.assertEqual(self.store.latest("demo-01")["online"], 19)
        self.assertEqual(self.store.daily_summary("demo-01", "2026-11-01")["samples"], 1)

    def test_latest_uses_utc_timestamp_order(self):
        self.store.record({**GOOD, "timestamp": "2026-11-01T10:00:00Z", "online": 23})
        self.store.record(GOOD)
        self.assertEqual(self.store.latest("demo-01")["online"], 23)

    def test_daily_aggregate(self):
        self.store.record(GOOD)
        self.store.record({**GOOD, "timestamp": "2026-11-01T10:00:00Z", "online": 0, "queue": 0, "available": False})
        summary = self.store.daily_summary("demo-01", "2026-11-01")
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["availability_percent"], 50.0)
        self.assertEqual(summary["average_players"], 6.0)
        self.assertEqual(summary["peak_queue"], 2)

    def test_separate_servers(self):
        self.store.record(GOOD)
        self.store.record({**GOOD, "server": "demo-02", "online": 5})
        self.assertEqual(self.store.daily_summary("demo-01", "2026-11-01")["samples"], 1)

    def test_no_samples_summary(self):
        self.assertIsNone(self.store.daily_summary("demo-01", "2026-11-01"))

    def test_bad_day(self):
        with self.assertRaises(SnapshotError):
            self.store.daily_summary("demo-01", "nonsense")

    def test_sql_injection_treated_as_server_name(self):
        unsafe = "'; DROP TABLE snapshots; --"
        self.store.record({**GOOD, "server": unsafe})
        self.assertEqual(self.store.latest(unsafe)["server"], unsafe)
        self.assertIsNone(self.store.latest("demo-01"))

    def test_import_jsonl(self):
        p = Path(self.temp.name) / "samples.jsonl"
        p.write_text(json.dumps(GOOD) + "\n" + json.dumps({**GOOD, "online": 1}) + "\n")
        self.assertEqual(ingest_jsonl(self.store, p), 2)
        self.assertEqual(self.store.latest("demo-01")["online"], 1)

    def test_import_invalid_line_has_number(self):
        p = Path(self.temp.name) / "bad.jsonl"
        p.write_text(json.dumps(GOOD) + "\nnot json\n")
        with self.assertRaisesRegex(SnapshotError, "Line 2"):
            ingest_jsonl(self.store, p)

    def test_invalid_batch_does_not_partially_import(self):
        p = Path(self.temp.name) / "atomic.jsonl"
        p.write_text(json.dumps(GOOD) + "\nnot json\n", encoding="utf-8")
        with self.assertRaisesRegex(SnapshotError, "Line 2"):
            ingest_jsonl(self.store, p)
        self.assertIsNone(self.store.latest("demo-01"))

    def test_invalid_data_does_not_modify_existing_snapshot(self):
        self.store.record(GOOD)
        p = Path(self.temp.name) / "batch.jsonl"
        p.write_text(
            json.dumps({**GOOD, "online": 30}) + "\n" +
            json.dumps({**GOOD, "online": 999}) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SnapshotError, "Line 2"):
            ingest_jsonl(self.store, p)
        self.assertEqual(self.store.latest("demo-01")["online"], 12)

    def test_in_memory_not_supported(self):
        with self.assertRaises(ValueError):
            MonitorStore(":memory:")


if __name__ == "__main__":
    unittest.main()
