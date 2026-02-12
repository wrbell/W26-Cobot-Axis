"""
W26 Cobot Axis -- CSV Data Logger

Logs timestamped bridge telemetry (commanded vs actual rates, latency,
TMC status) for Phase 4 test/reporting and post-hoc analysis.

Features:
- CSV format with fixed column order
- File rotation by size
- Buffered writes with periodic flush
- Event annotations (ESTOP, RECONNECT, etc.)
- Decimation (log every Nth tick)

Reference: docs/design/bridge_enhancements.md, Section 3.
"""

import csv
import logging
import os
import time

from . import config

log = logging.getLogger(__name__)

# Column order for CSV output
CSV_COLUMNS = [
    "timestamp",
    "wall_clock",
    "tick_number",
    "loop_dt_ms",
    "mode",
    "enable",
    "commanded_rate",
    "tcp_speed",
    "actual_rate",
    "status",
    "error_code",
    "stepper_enabled",
    "tmc_sg_result",
    "tmc_standstill",
    "rtde_read_us",
    "klipper_cmd_us",
    "notes",
]


class DataLogger:
    """CSV data logger with file rotation and buffered writes."""

    def __init__(self, log_dir: str = config.LOG_DIR,
                 prefix: str = config.LOG_FILE_PREFIX,
                 max_size_mb: int = config.LOG_MAX_SIZE_MB,
                 max_files: int = config.LOG_MAX_FILES,
                 flush_interval: float = config.LOG_FLUSH_INTERVAL,
                 decimation: int = config.LOG_DECIMATION):
        self._log_dir = log_dir
        self._prefix = prefix
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._max_files = max_files
        self._flush_interval = flush_interval
        self._decimation = max(1, decimation)

        self._file = None
        self._writer = None
        self._filepath = None
        self._tick_counter = 0
        self._last_flush_time = 0.0
        self._consecutive_errors = 0
        self._disabled = False
        self._pending_note = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create log directory and open the initial CSV file."""
        if self._disabled:
            return
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            self._open_new_file()
            log.info("Data logger started: %s (decimation=%d)",
                     self._filepath, self._decimation)
        except OSError as exc:
            log.error("Failed to start data logger: %s", exc)
            self._disabled = True

    def stop(self) -> None:
        """Flush and close the current log file."""
        self._close_file()
        log.info("Data logger stopped")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def log_tick(self, data: dict) -> None:
        """
        Write one row of telemetry data to the CSV log.

        Called from the main bridge loop each tick. Respects decimation
        (only writes every Nth tick).

        Args:
            data: dict with keys matching CSV_COLUMNS (missing keys become "").
        """
        if self._disabled or self._file is None:
            return

        self._tick_counter += 1
        if self._tick_counter % self._decimation != 0:
            return

        # Attach any pending annotation
        if self._pending_note:
            data["notes"] = self._pending_note
            self._pending_note = ""

        try:
            row = [data.get(col, "") for col in CSV_COLUMNS]
            self._writer.writerow(row)
            self._consecutive_errors = 0

            # Periodic flush
            now = time.monotonic()
            if now - self._last_flush_time >= self._flush_interval:
                self._file.flush()
                self._last_flush_time = now

            # Check for rotation
            self._maybe_rotate()

        except OSError as exc:
            self._consecutive_errors += 1
            log.warning("Data logger write error: %s (consecutive=%d)",
                        exc, self._consecutive_errors)
            if self._consecutive_errors >= 10:
                log.error("Data logger disabled after %d consecutive errors",
                          self._consecutive_errors)
                self._disabled = True
                self._close_file()

    def annotate(self, note: str) -> None:
        """
        Attach an event annotation to the next logged row.

        Multiple annotations before the next log_tick are concatenated
        with semicolons.
        """
        if self._pending_note:
            self._pending_note += "; " + note
        else:
            self._pending_note = note

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _open_new_file(self) -> None:
        """Open a new CSV file with timestamp in the filename."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{self._prefix}_{timestamp}.csv"
        self._filepath = os.path.join(self._log_dir, filename)
        self._file = open(self._filepath, "w", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        self._writer.writerow(CSV_COLUMNS)
        self._last_flush_time = time.monotonic()

    def _close_file(self) -> None:
        """Flush and close the current file."""
        if self._file is not None:
            try:
                self._file.flush()
                self._file.close()
            except OSError:
                pass
            self._file = None
            self._writer = None

    def _maybe_rotate(self) -> None:
        """Rotate the log file if it exceeds the size limit."""
        if self._filepath is None:
            return
        try:
            size = os.path.getsize(self._filepath)
        except OSError:
            return

        if size < self._max_size_bytes:
            return

        log.info("Rotating log file (size=%d bytes, limit=%d)",
                 size, self._max_size_bytes)
        self._close_file()
        self._cleanup_old_files()
        self._open_new_file()

    def _cleanup_old_files(self) -> None:
        """Remove oldest log files if count exceeds max_files."""
        try:
            files = sorted([
                os.path.join(self._log_dir, f)
                for f in os.listdir(self._log_dir)
                if f.startswith(self._prefix) and f.endswith(".csv")
            ])
            # Keep max_files - 1 (we are about to create a new one)
            while len(files) >= self._max_files:
                oldest = files.pop(0)
                os.remove(oldest)
                log.debug("Removed old log file: %s", oldest)
        except OSError as exc:
            log.warning("Log file cleanup failed: %s", exc)
