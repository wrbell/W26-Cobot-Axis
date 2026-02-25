"""
Unit tests for W26 bridge CSV data logger.

Tests CSV output, decimation, file rotation, annotations, error handling,
lifecycle, disabled state, and write error recovery.
"""

import csv
import os
from unittest.mock import MagicMock

from bridge.data_logger import DataLogger, CSV_COLUMNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv(filepath):
    """Read a CSV file and return (header, rows)."""
    with open(filepath, "r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    return header, rows


def _sample_data(**overrides):
    """Build a sample data dict with defaults for all columns."""
    data = {col: "" for col in CSV_COLUMNS}
    data["timestamp"] = 1000.0
    data["wall_clock"] = "2026-02-24T12:00:00"
    data["tick_number"] = 1
    data["mode"] = 1
    data["commanded_rate"] = 10.0
    data["status"] = 1
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_start_creates_directory(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        dl = DataLogger(log_dir=log_dir)
        dl.start()
        assert os.path.isdir(log_dir)
        dl.stop()

    def test_start_creates_csv_with_header(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        assert len(files) == 1
        header, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert header == CSV_COLUMNS
        assert len(rows) == 0

    def test_stop_flushes(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.log_tick(_sample_data())
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 1

    def test_double_stop_safe(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.stop()
        dl.stop()  # should not raise


# ---------------------------------------------------------------------------
# log_tick
# ---------------------------------------------------------------------------

class TestLogTick:
    def test_writes_one_row(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.log_tick(_sample_data(commanded_rate=25.0))
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 1
        # commanded_rate is column index 6
        rate_idx = CSV_COLUMNS.index("commanded_rate")
        assert rows[0][rate_idx] == "25.0"

    def test_missing_keys_become_empty(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.log_tick({"timestamp": 1.0})  # most keys missing
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 1

    def test_log_tick_before_start_ignored(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.log_tick(_sample_data())  # no crash
        # No files created
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        assert len(files) == 0


# ---------------------------------------------------------------------------
# Decimation
# ---------------------------------------------------------------------------

class TestDecimation:
    def test_decimation_1_logs_every_tick(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path), decimation=1)
        dl.start()
        for i in range(5):
            dl.log_tick(_sample_data(tick_number=i))
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 5

    def test_decimation_5_logs_every_5th(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path), decimation=5)
        dl.start()
        for i in range(10):
            dl.log_tick(_sample_data(tick_number=i))
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 2  # ticks 5 and 10

    def test_decimation_0_treated_as_1(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path), decimation=0)
        assert dl._decimation == 1


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

class TestAnnotations:
    def test_annotate_attaches_to_next_row(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.annotate("ESTOP")
        dl.log_tick(_sample_data())
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        notes_idx = CSV_COLUMNS.index("notes")
        assert rows[0][notes_idx] == "ESTOP"

    def test_multiple_annotations_concatenated(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.annotate("ESTOP")
        dl.annotate("RECONNECT")
        dl.log_tick(_sample_data())
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        notes_idx = CSV_COLUMNS.index("notes")
        assert "ESTOP" in rows[0][notes_idx]
        assert "RECONNECT" in rows[0][notes_idx]

    def test_annotation_cleared_after_consumption(self, tmp_path):
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl.annotate("EVENT")
        dl.log_tick(_sample_data())
        dl.log_tick(_sample_data())
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        notes_idx = CSV_COLUMNS.index("notes")
        assert rows[0][notes_idx] == "EVENT"
        assert rows[1][notes_idx] == ""


# ---------------------------------------------------------------------------
# File rotation
# ---------------------------------------------------------------------------

class TestRotation:
    @staticmethod
    def _patch_unique_timestamps(monkeypatch):
        """Patch time.strftime so each rotated file gets a unique name."""
        import bridge.data_logger as dl_mod
        counter = [0]
        def unique_strftime(fmt, *args):
            counter[0] += 1
            return f"20260224_{counter[0]:06d}"
        monkeypatch.setattr(dl_mod.time, "strftime", unique_strftime)

    def test_rotates_when_size_exceeded(self, tmp_path, monkeypatch):
        self._patch_unique_timestamps(monkeypatch)
        # Tiny max size to force rotation
        dl = DataLogger(log_dir=str(tmp_path), max_size_mb=0,
                        max_files=5)
        # Override to 100 bytes — header alone exceeds this, so every
        # log_tick triggers a rotation.
        dl._max_size_bytes = 100
        dl.start()
        for i in range(50):
            dl.log_tick(_sample_data(tick_number=i))
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        assert len(files) >= 2  # at least one rotation happened

    def test_cleanup_respects_max_files(self, tmp_path, monkeypatch):
        self._patch_unique_timestamps(monkeypatch)
        dl = DataLogger(log_dir=str(tmp_path), max_files=2)
        dl._max_size_bytes = 50  # force frequent rotation
        dl.start()
        for i in range(200):
            dl.log_tick(_sample_data(tick_number=i))
        dl.stop()
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        assert len(files) <= 2


# ---------------------------------------------------------------------------
# CSV column order
# ---------------------------------------------------------------------------

class TestCSVColumns:
    def test_column_count(self):
        assert len(CSV_COLUMNS) == 17

    def test_expected_columns_present(self):
        for col in ["timestamp", "mode", "commanded_rate", "actual_rate",
                     "status", "notes", "tmc_sg_result"]:
            assert col in CSV_COLUMNS


# ---------------------------------------------------------------------------
# Disabled state
# ---------------------------------------------------------------------------

class TestDisabledState:
    def test_start_when_disabled(self, tmp_path):
        """start() does nothing when logger is disabled."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl._disabled = True
        dl.start()
        assert dl._file is None

    def test_log_tick_when_disabled(self, tmp_path):
        """log_tick() does nothing when logger is disabled."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl._disabled = True
        dl.log_tick(_sample_data())  # should not raise

    def test_start_with_bad_directory_disables(self):
        """start() disables logger if directory creation fails."""
        dl = DataLogger(log_dir="/proc/nonexistent/impossible")
        dl.start()
        assert dl._disabled is True


# ---------------------------------------------------------------------------
# Write error handling
# ---------------------------------------------------------------------------

class TestWriteErrors:
    def test_consecutive_write_errors_disable_logger(self, tmp_path):
        """10 consecutive write errors disable the logger."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()

        # Force write errors by making the writer raise
        mock_writer = MagicMock()
        mock_writer.writerow.side_effect = OSError("disk full")
        dl._writer = mock_writer

        for i in range(10):
            dl.log_tick(_sample_data(tick_number=i))

        assert dl._disabled is True
        assert dl._file is None

    def test_successful_write_resets_error_count(self, tmp_path):
        """Successful write resets consecutive error counter."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        dl._consecutive_errors = 5

        dl.log_tick(_sample_data())

        assert dl._consecutive_errors == 0
        dl.stop()

    def test_flush_on_interval(self, tmp_path):
        """File is flushed when flush interval elapses."""
        dl = DataLogger(log_dir=str(tmp_path), flush_interval=0.0)
        dl.start()

        # With interval=0, every log_tick should trigger flush
        dl.log_tick(_sample_data())
        dl.stop()

        # Just verify no crash — the file was flushed and data is there
        files = [f for f in os.listdir(tmp_path) if f.endswith(".csv")]
        _, rows = _read_csv(os.path.join(tmp_path, files[0]))
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# File rotation internals
# ---------------------------------------------------------------------------

class TestRotationInternals:
    def test_maybe_rotate_no_filepath(self, tmp_path):
        """_maybe_rotate does nothing when filepath is None."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl._filepath = None
        dl._maybe_rotate()  # should not raise

    def test_maybe_rotate_no_rotate_when_small(self, tmp_path):
        """_maybe_rotate does nothing when file is under size limit."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        original_filepath = dl._filepath

        dl.log_tick(_sample_data())
        dl._maybe_rotate()

        assert dl._filepath == original_filepath
        dl.stop()

    def test_close_file_when_none(self, tmp_path):
        """_close_file does nothing when no file is open."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl._close_file()  # should not raise

    def test_cleanup_handles_oserror(self, tmp_path):
        """_cleanup_old_files handles OSError gracefully."""
        dl = DataLogger(log_dir="/proc/nonexistent")
        dl._cleanup_old_files()  # should not raise

    def test_close_file_oserror(self, tmp_path):
        """_close_file handles OSError from flush/close."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()

        # Replace file with one that raises on flush
        dl._file = MagicMock()
        dl._file.flush.side_effect = OSError("disk full")

        dl._close_file()  # should not raise
        assert dl._file is None

    def test_maybe_rotate_getsize_oserror(self, tmp_path):
        """_maybe_rotate handles OSError from getsize."""
        dl = DataLogger(log_dir=str(tmp_path))
        dl.start()
        original_filepath = dl._filepath

        # Point to a non-existent file path for getsize to fail
        dl._filepath = "/nonexistent/file.csv"
        dl._maybe_rotate()

        # Restore so stop() doesn't crash
        dl._filepath = original_filepath
        dl.stop()
