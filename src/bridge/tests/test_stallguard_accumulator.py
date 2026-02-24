"""
Unit tests for StallGuard batch accumulator.

Tests the Pi-side in-memory ring buffer that stores StallGuard samples
from KlipperStatusPoller. Covers NamedTuple fields, capacity, overflow,
thread safety, statistics, and integration with poller and bridge.
"""

import csv
import threading
import time

import pytest
from unittest.mock import MagicMock

from bridge import config
from bridge.stallguard_accumulator import StallGuardSample, StallGuardAccumulator
from bridge.klipper_status import KlipperStatusPoller
from bridge.bridge_daemon import Bridge


# ===================================================================
# 1. StallGuardSample NamedTuple
# ===================================================================

class TestStallGuardSample:

    def test_fields_present(self):
        s = StallGuardSample(
            timestamp=1.0, wall_clock="2026-02-24T12:00:00",
            sg_result=150, stall_active=False, stall_count=0,
            last_stall_ticks=0,
        )
        assert s.timestamp == 1.0
        assert s.wall_clock == "2026-02-24T12:00:00"
        assert s.sg_result == 150
        assert s.stall_active is False
        assert s.stall_count == 0
        assert s.last_stall_ticks == 0

    def test_immutable(self):
        s = StallGuardSample(1.0, "x", 100, False, 0, 0)
        with pytest.raises(AttributeError):
            s.sg_result = 200  # type: ignore[misc]


# ===================================================================
# 2. Accumulator init
# ===================================================================

class TestAccumulatorInit:

    def test_default_capacity(self):
        acc = StallGuardAccumulator()
        expected = int(config.SG_ACCUMULATOR_DURATION_S * config.SG_ACCUMULATOR_SAMPLE_RATE_HZ)
        assert acc.capacity == expected

    def test_custom_capacity(self):
        acc = StallGuardAccumulator(max_duration_s=10.0, sample_rate_hz=2.0)
        assert acc.capacity == 20

    def test_empty_on_creation(self):
        acc = StallGuardAccumulator()
        assert acc.sample_count == 0
        assert acc.get_history() == []


# ===================================================================
# 3. Recording
# ===================================================================

class TestAccumulatorRecord:

    def test_single_record(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=100, stall_active=False, stall_count=0, last_stall_ticks=0)
        assert acc.sample_count == 1

    def test_fills_to_capacity(self):
        acc = StallGuardAccumulator(max_duration_s=1.0, sample_rate_hz=4.0)
        assert acc.capacity == 4
        for i in range(4):
            acc.record(sg_result=i, stall_active=False, stall_count=0, last_stall_ticks=0)
        assert acc.sample_count == 4

    def test_overflow_evicts_oldest(self):
        acc = StallGuardAccumulator(max_duration_s=1.0, sample_rate_hz=2.0)
        assert acc.capacity == 2
        acc.record(sg_result=10, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=20, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=30, stall_active=False, stall_count=0, last_stall_ticks=0)
        assert acc.sample_count == 2
        history = acc.get_history()
        assert history[0].sg_result == 20
        assert history[1].sg_result == 30

    def test_missing_sg_result_negative_one(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=-1, stall_active=False, stall_count=0, last_stall_ticks=0)
        assert acc.get_history()[0].sg_result == -1

    def test_thread_safety(self):
        """Multiple threads recording concurrently should not corrupt buffer."""
        acc = StallGuardAccumulator(max_duration_s=100.0, sample_rate_hz=10.0)
        errors = []

        def writer(start_val):
            try:
                for i in range(100):
                    acc.record(sg_result=start_val + i, stall_active=False,
                               stall_count=0, last_stall_ticks=0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 1000,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert acc.sample_count == 400


# ===================================================================
# 4. get_history
# ===================================================================

class TestAccumulatorGetHistory:

    def test_empty_history(self):
        acc = StallGuardAccumulator()
        assert acc.get_history() == []

    def test_returns_list_copy(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=50, stall_active=False, stall_count=0, last_stall_ticks=0)
        h1 = acc.get_history()
        h2 = acc.get_history()
        assert h1 == h2
        assert h1 is not h2

    def test_order_preserved(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=10, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=20, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=30, stall_active=False, stall_count=0, last_stall_ticks=0)
        history = acc.get_history()
        assert [s.sg_result for s in history] == [10, 20, 30]

    def test_after_overflow(self):
        acc = StallGuardAccumulator(max_duration_s=1.0, sample_rate_hz=2.0)
        for v in [1, 2, 3, 4, 5]:
            acc.record(sg_result=v, stall_active=False, stall_count=0, last_stall_ticks=0)
        history = acc.get_history()
        assert len(history) == 2
        assert [s.sg_result for s in history] == [4, 5]


# ===================================================================
# 5. get_summary
# ===================================================================

class TestAccumulatorGetSummary:

    def test_empty_summary(self):
        acc = StallGuardAccumulator()
        s = acc.get_summary()
        assert s["sample_count"] == 0
        assert s["duration_s"] == 0.0
        assert s["sg_min"] is None
        assert s["sg_max"] is None
        assert s["sg_mean"] is None
        assert s["stall_event_count"] == 0
        assert s["stall_active_now"] is False

    def test_stats_calculation(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=100, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=200, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=150, stall_active=True, stall_count=2, last_stall_ticks=999)
        s = acc.get_summary()
        assert s["sample_count"] == 3
        assert s["sg_min"] == 100
        assert s["sg_max"] == 200
        assert s["sg_mean"] == 150.0
        assert s["stall_event_count"] == 2
        assert s["stall_active_now"] is True

    def test_negative_sg_ignored_in_stats(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=-1, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=100, stall_active=False, stall_count=0, last_stall_ticks=0)
        s = acc.get_summary()
        assert s["sg_min"] == 100
        assert s["sg_max"] == 100
        assert s["sg_mean"] == 100.0

    def test_all_negative_sg(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=-1, stall_active=False, stall_count=0, last_stall_ticks=0)
        s = acc.get_summary()
        assert s["sg_min"] is None
        assert s["sg_mean"] is None

    def test_duration_increases(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=50, stall_active=False, stall_count=0, last_stall_ticks=0)
        time.sleep(0.05)
        acc.record(sg_result=60, stall_active=False, stall_count=0, last_stall_ticks=0)
        s = acc.get_summary()
        assert s["duration_s"] >= 0.04


# ===================================================================
# 6. clear
# ===================================================================

class TestAccumulatorClear:

    def test_empties_buffer(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=50, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=60, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.clear()
        assert acc.sample_count == 0
        assert acc.get_history() == []

    def test_allows_reuse_after_clear(self):
        acc = StallGuardAccumulator()
        acc.record(sg_result=50, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.clear()
        acc.record(sg_result=70, stall_active=False, stall_count=0, last_stall_ticks=0)
        assert acc.sample_count == 1
        assert acc.get_history()[0].sg_result == 70


# ===================================================================
# 7. Poller integration
# ===================================================================

class TestPollerIntegration:

    @pytest.fixture
    def poller_with_acc(self):
        kc = MagicMock()
        poller = KlipperStatusPoller(klipper_client=kc)
        acc = StallGuardAccumulator()
        poller.set_accumulator(acc)
        return poller, acc

    def test_set_accumulator_stores_reference(self, poller_with_acc):
        poller, acc = poller_with_acc
        assert poller._sg_accumulator is acc

    def test_poll_once_feeds_accumulator(self, poller_with_acc):
        poller, acc = poller_with_acc
        poller._klipper.query_status.return_value = {
            "status": {
                "stepper_enable": {"steppers": {}},
                "tmc2209 manual_stepper pump": {
                    "drv_status": {"sg_result": 175}
                },
                "stallguard_monitor": {
                    "stall_active": True,
                    "stall_count": 3,
                    "last_stall_ticks": 12345,
                },
            }
        }
        poller._poll_once()
        assert acc.sample_count == 1
        sample = acc.get_history()[0]
        assert sample.sg_result == 175
        assert sample.stall_active is True
        assert sample.stall_count == 3
        assert sample.last_stall_ticks == 12345

    def test_poll_once_without_accumulator(self):
        """_poll_once() works normally when no accumulator is set."""
        kc = MagicMock()
        poller = KlipperStatusPoller(klipper_client=kc)
        poller._klipper.query_status.return_value = {
            "status": {
                "stepper_enable": {"steppers": {}},
                "tmc2209 manual_stepper pump": {},
                "stallguard_monitor": {},
            }
        }
        poller._poll_once()  # should not raise

    def test_accumulator_gets_negative_one_when_no_tmc(self, poller_with_acc):
        """sg_result defaults to -1 when TMC data is empty."""
        poller, acc = poller_with_acc
        poller._klipper.query_status.return_value = {
            "status": {
                "stepper_enable": {"steppers": {}},
                "tmc2209 manual_stepper pump": {},
                "stallguard_monitor": {
                    "stall_active": False,
                    "stall_count": 0,
                    "last_stall_ticks": 0,
                },
            }
        }
        poller._poll_once()
        sample = acc.get_history()[0]
        assert sample.sg_result == -1


# ===================================================================
# 8. Bridge wiring
# ===================================================================

class TestBridgeWiring:

    def test_accumulator_created_by_default(self):
        b = Bridge(ur_host="127.0.0.1", dry_run=True)
        assert b.sg_accumulator is not None
        assert isinstance(b.sg_accumulator, StallGuardAccumulator)

    def test_accumulator_disabled_flag(self):
        b = Bridge(ur_host="127.0.0.1", dry_run=True,
                   enable_sg_accumulator=False)
        assert b.sg_accumulator is None

    def test_no_accumulator_when_no_poller(self):
        b = Bridge(ur_host="127.0.0.1", dry_run=True,
                   enable_status_poll=False)
        assert b.sg_accumulator is None

    def test_accumulator_wired_to_poller(self):
        b = Bridge(ur_host="127.0.0.1", dry_run=True)
        assert b.status_poller is not None
        assert b.status_poller._sg_accumulator is b.sg_accumulator

    def test_shutdown_logs_summary(self):
        """stop() logs the accumulator summary (no crash even if empty)."""
        b = Bridge(ur_host="127.0.0.1", dry_run=True)
        b.rtde = MagicMock()
        b.klipper = MagicMock()
        b.rtde.connected = True
        b.klipper.connected = True
        b.stop()  # should not raise


# ===================================================================
# 9. dump_to_csv
# ===================================================================

class TestAccumulatorDumpCSV:

    def test_dump_csv_empty(self, tmp_path):
        """Empty buffer writes headers only, returns 0."""
        acc = StallGuardAccumulator()
        csv_file = str(tmp_path / "empty.csv")
        count = acc.dump_to_csv(csv_file)
        assert count == 0
        with open(csv_file, newline="") as f:
            reader = list(csv.reader(f))
        assert len(reader) == 1  # header only

    def test_dump_csv_writes_data(self, tmp_path):
        """Records some samples, dumps, reads back and verifies content."""
        acc = StallGuardAccumulator()
        acc.record(sg_result=120, stall_active=False, stall_count=0, last_stall_ticks=0)
        acc.record(sg_result=200, stall_active=True, stall_count=1, last_stall_ticks=5000)
        acc.record(sg_result=-1, stall_active=False, stall_count=1, last_stall_ticks=5000)

        csv_file = str(tmp_path / "data.csv")
        count = acc.dump_to_csv(csv_file)
        assert count == 3

        with open(csv_file, newline="") as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 3
        assert reader[0]["sg_result"] == "120"
        assert reader[1]["stall_active"] == "True"
        assert reader[1]["stall_count"] == "1"
        assert reader[2]["sg_result"] == "-1"

    def test_dump_csv_headers(self, tmp_path):
        """Verify the header row matches StallGuardSample field names."""
        acc = StallGuardAccumulator()
        csv_file = str(tmp_path / "headers.csv")
        acc.dump_to_csv(csv_file)
        with open(csv_file, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
        expected = list(StallGuardSample._fields)
        assert header == expected

    def test_dump_csv_returns_count(self, tmp_path):
        """Verify return value equals sample count."""
        acc = StallGuardAccumulator()
        csv_file = str(tmp_path / "count.csv")
        assert acc.dump_to_csv(csv_file) == 0

        for i in range(5):
            acc.record(sg_result=i * 10, stall_active=False,
                       stall_count=0, last_stall_ticks=0)
        assert acc.dump_to_csv(csv_file) == 5
