"""
Unit tests for W26 bridge watchdog timer.

Tests timeout detection, feed/reset, stale timestamp logic, disabled mode,
and edge cases around trigger/clear transitions.
"""

import time

from bridge.watchdog import Watchdog


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------

class TestWatchdogInit:
    def test_default_timeout(self):
        wd = Watchdog()
        assert wd._timeout == 0.5
        assert wd._enabled is True

    def test_custom_timeout(self):
        wd = Watchdog(timeout=2.0)
        assert wd._timeout == 2.0

    def test_disabled(self):
        wd = Watchdog(enabled=False)
        assert wd._enabled is False

    def test_not_triggered_initially(self):
        wd = Watchdog()
        assert wd.is_triggered is False


# ---------------------------------------------------------------------------
# Feed behaviour
# ---------------------------------------------------------------------------

class TestFeed:
    def test_first_feed_initialises(self):
        wd = Watchdog()
        wd.feed({"timestamp": 1.0})
        assert wd._last_timestamp == 1.0
        assert wd.is_triggered is False

    def test_changing_timestamp_stays_fresh(self):
        wd = Watchdog(timeout=0.1)
        wd.feed({"timestamp": 1.0})
        wd.feed({"timestamp": 2.0})
        wd.feed({"timestamp": 3.0})
        assert wd.is_triggered is False

    def test_missing_timestamp_key_ignored(self):
        wd = Watchdog()
        wd.feed({"no_timestamp": 1.0})
        assert wd._last_timestamp is None
        assert wd.is_triggered is False

    def test_none_timestamp_ignored(self):
        wd = Watchdog()
        wd.feed({"timestamp": None})
        assert wd._last_timestamp is None

    def test_disabled_watchdog_ignores_feed(self):
        wd = Watchdog(enabled=False)
        wd.feed({"timestamp": 1.0})
        assert wd._last_timestamp is None


# ---------------------------------------------------------------------------
# Trigger logic
# ---------------------------------------------------------------------------

class TestTrigger:
    def test_stale_data_triggers(self):
        wd = Watchdog(timeout=0.05)
        wd.feed({"timestamp": 1.0})
        # Simulate time passing with same timestamp
        wd._last_feed_time = time.monotonic() - 0.1
        wd.feed({"timestamp": 1.0})
        assert wd.is_triggered is True

    def test_fresh_data_clears_trigger(self):
        wd = Watchdog(timeout=0.05)
        wd.feed({"timestamp": 1.0})
        wd._last_feed_time = time.monotonic() - 0.1
        wd.feed({"timestamp": 1.0})
        assert wd.is_triggered is True
        # New timestamp clears
        wd.feed({"timestamp": 2.0})
        assert wd.is_triggered is False

    def test_trigger_only_fires_once(self):
        """Repeated stale feeds after trigger don't re-log."""
        wd = Watchdog(timeout=0.05)
        wd.feed({"timestamp": 1.0})
        wd._last_feed_time = time.monotonic() - 0.1
        wd.feed({"timestamp": 1.0})
        assert wd.is_triggered is True
        # Feed again — still triggered, no state change
        wd.feed({"timestamp": 1.0})
        assert wd.is_triggered is True

    def test_not_triggered_before_timeout(self):
        wd = Watchdog(timeout=10.0)
        wd.feed({"timestamp": 1.0})
        wd.feed({"timestamp": 1.0})  # same, but timeout is 10s
        assert wd.is_triggered is False


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_trigger(self):
        wd = Watchdog(timeout=0.05)
        wd.feed({"timestamp": 1.0})
        wd._last_feed_time = time.monotonic() - 0.1
        wd.feed({"timestamp": 1.0})
        assert wd.is_triggered is True
        wd.reset()
        assert wd.is_triggered is False
        assert wd._last_timestamp is None

    def test_reset_allows_reinitialisation(self):
        wd = Watchdog()
        wd.feed({"timestamp": 1.0})
        wd.reset()
        wd.feed({"timestamp": 5.0})
        assert wd._last_timestamp == 5.0
        assert wd.is_triggered is False
