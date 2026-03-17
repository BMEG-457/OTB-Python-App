"""Tests for app/data/csv_loader.py"""

import os
import tempfile
import numpy as np
import pytest
from app.data.csv_loader import CSVDataLoader


def _write_csv(path, n_channels=3, n_samples=10, fs=1000.0):
    """Write a minimal valid CSV to `path` and return (timestamps, data) arrays."""
    timestamps = np.arange(n_samples) / fs
    rng = np.random.default_rng(0)
    data = rng.standard_normal((n_channels, n_samples))

    with open(path, 'w', newline='') as f:
        header = "Timestamp," + ",".join(f"Channel_{i+1}" for i in range(n_channels))
        f.write(header + "\n")
        for j in range(n_samples):
            row = f"{timestamps[j]}"
            for ch in range(n_channels):
                row += f",{data[ch, j]}"
            f.write(row + "\n")

    return timestamps, data


class TestCSVDataLoaderLoad:
    def test_load_valid_file_returns_true(self, tmp_path):
        fpath = str(tmp_path / "test.csv")
        _write_csv(fpath)
        loader = CSVDataLoader()
        assert loader.load_file(fpath) is True

    def test_load_nonexistent_file_returns_false(self):
        loader = CSVDataLoader()
        assert loader.load_file("/nonexistent/path/file.csv") is False

    def test_load_sets_data_shape(self, tmp_path):
        fpath = str(tmp_path / "test.csv")
        n_ch, n_samp = 4, 20
        _write_csv(fpath, n_channels=n_ch, n_samples=n_samp)
        loader = CSVDataLoader()
        loader.load_file(fpath)
        assert loader.data.shape == (n_ch, n_samp)

    def test_load_sets_timestamps_length(self, tmp_path):
        fpath = str(tmp_path / "test.csv")
        _, _ = _write_csv(fpath, n_samples=15)
        loader = CSVDataLoader()
        loader.load_file(fpath)
        assert len(loader.timestamps) == 15

    def test_load_sets_channel_names(self, tmp_path):
        fpath = str(tmp_path / "test.csv")
        _write_csv(fpath, n_channels=3)
        loader = CSVDataLoader()
        loader.load_file(fpath)
        assert loader.channel_names == ["Channel_1", "Channel_2", "Channel_3"]

    def test_failed_load_clears_state(self):
        loader = CSVDataLoader()
        loader.load_file("/bad/path.csv")
        assert loader.data is None
        assert loader.timestamps is None
        assert loader.channel_names == []
        assert loader.sample_rate is None

    def test_load_skips_short_rows(self, tmp_path):
        fpath = str(tmp_path / "sparse.csv")
        with open(fpath, 'w') as f:
            f.write("Timestamp,Channel_1\n")
            f.write("0.0,1.0\n")
            f.write("\n")           # empty row — should be skipped
            f.write("0.001,2.0\n")
        loader = CSVDataLoader()
        loader.load_file(fpath)
        assert loader.get_sample_count() == 2


class TestCSVDataLoaderAccessors:
    @pytest.fixture
    def loaded_loader(self, tmp_path):
        fpath = str(tmp_path / "data.csv")
        _write_csv(fpath, n_channels=3, n_samples=100, fs=500.0)
        loader = CSVDataLoader()
        loader.load_file(fpath)
        return loader

    def test_get_channel_count(self, loaded_loader):
        assert loaded_loader.get_channel_count() == 3

    def test_get_sample_count(self, loaded_loader):
        assert loaded_loader.get_sample_count() == 100

    def test_get_duration(self, loaded_loader):
        # 100 samples at 500 Hz → 99/500 = 0.198 s
        assert abs(loaded_loader.get_duration() - 99 / 500.0) < 1e-6

    def test_estimate_sample_rate(self, loaded_loader):
        assert abs(loaded_loader.sample_rate - 500.0) < 1.0

    def test_is_loaded_true_after_load(self, loaded_loader):
        assert loaded_loader.is_loaded() is True

    def test_is_loaded_false_before_load(self):
        loader = CSVDataLoader()
        assert loader.is_loaded() is False

    def test_get_channel_count_before_load(self):
        assert CSVDataLoader().get_channel_count() == 0

    def test_get_sample_count_before_load(self):
        assert CSVDataLoader().get_sample_count() == 0

    def test_get_duration_before_load(self):
        assert CSVDataLoader().get_duration() == 0.0
