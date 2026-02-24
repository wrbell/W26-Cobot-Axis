"""
W26 Cobot Axis -- StallGuard Batch Accumulator

Pi-side in-memory buffer for StallGuard data history. Stores up to
5 minutes (default) of samples from KlipperStatusPoller at 4 Hz in a
thread-safe deque. Queryable for full history or summary statistics.

Zero MCU changes -- purely additive to the existing live RTDE path.

Reference: todo.md "Stretch: Batch StallGuard Data Reporting"
"""

import csv
import statistics
import threading
import time
from collections import deque
from typing import NamedTuple

from . import config


class StallGuardSample(NamedTuple):
    """Single StallGuard measurement from one poller cycle."""
    timestamp: float        # time.monotonic()
    wall_clock: str         # ISO-8601
    sg_result: int          # TMC2209 UART (0-255), -1 if unavailable
    stall_active: bool      # core1 DIAG pin state
    stall_count: int        # cumulative stall events
    last_stall_ticks: int   # MCU timer ticks at last stall


class StallGuardAccumulator:
    """Thread-safe ring buffer of StallGuard samples on the Pi.

    Owns its own lock -- never nested with poller's lock. The poller
    calls record() AFTER its own ``with self._lock:`` block exits.

    Memory: ~144 KB for 1200 samples (5 min @ 4 Hz).
    """

    def __init__(
        self,
        max_duration_s: float = config.SG_ACCUMULATOR_DURATION_S,
        sample_rate_hz: float = config.SG_ACCUMULATOR_SAMPLE_RATE_HZ,
    ):
        max_samples = int(max_duration_s * sample_rate_hz)
        self._buffer: deque[StallGuardSample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        sg_result: int,
        stall_active: bool,
        stall_count: int,
        last_stall_ticks: int,
    ) -> None:
        """Append a new sample (called from poller thread)."""
        sample = StallGuardSample(
            timestamp=time.monotonic(),
            wall_clock=time.strftime("%Y-%m-%dT%H:%M:%S"),
            sg_result=sg_result,
            stall_active=stall_active,
            stall_count=stall_count,
            last_stall_ticks=last_stall_ticks,
        )
        with self._lock:
            self._buffer.append(sample)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_history(self) -> list[StallGuardSample]:
        """Return a snapshot of the full buffer as a list (oldest first)."""
        with self._lock:
            return list(self._buffer)

    def get_summary(self) -> dict:
        """Return aggregate statistics over the current buffer.

        Returns dict with keys: sample_count, duration_s, sg_min, sg_max,
        sg_mean, stall_event_count, stall_active_now.
        """
        with self._lock:
            samples = list(self._buffer)

        if not samples:
            return {
                "sample_count": 0,
                "duration_s": 0.0,
                "sg_min": None,
                "sg_max": None,
                "sg_mean": None,
                "stall_event_count": 0,
                "stall_active_now": False,
            }

        valid_sg = [s.sg_result for s in samples if s.sg_result >= 0]
        duration = samples[-1].timestamp - samples[0].timestamp

        return {
            "sample_count": len(samples),
            "duration_s": round(duration, 3),
            "sg_min": min(valid_sg) if valid_sg else None,
            "sg_max": max(valid_sg) if valid_sg else None,
            "sg_mean": round(statistics.mean(valid_sg), 1) if valid_sg else None,
            "stall_event_count": samples[-1].stall_count,
            "stall_active_now": samples[-1].stall_active,
        }

    def clear(self) -> None:
        """Discard all buffered samples."""
        with self._lock:
            self._buffer.clear()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def dump_to_csv(self, path: str) -> int:
        """Write all buffered samples to a CSV file.

        Acquires the lock only to copy the buffer, then writes outside
        the lock to avoid holding it during I/O.

        Args:
            path: Filesystem path for the output CSV file.

        Returns:
            Number of data rows written (excludes header).
        """
        with self._lock:
            samples = list(self._buffer)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(StallGuardSample._fields)
            for s in samples:
                writer.writerow(s)

        return len(samples)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sample_count(self) -> int:
        """Number of samples currently in the buffer."""
        with self._lock:
            return len(self._buffer)

    @property
    def capacity(self) -> int:
        """Maximum number of samples the buffer can hold."""
        return self._buffer.maxlen  # type: ignore[return-value]
