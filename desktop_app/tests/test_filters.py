"""Tests for app/processing/filters.py"""

import numpy as np
import pytest
from app.processing.filters import butter_bandpass, notch, rectify
from app.core.config import Config


FS = 2000  # Hz — matches device default


class TestRectify:
    def test_positive_values_unchanged(self):
        data = np.array([[1.0, 2.0, 3.0]])
        np.testing.assert_array_equal(rectify(data), data)

    def test_negative_values_become_positive(self):
        data = np.array([[-1.0, -2.0, -3.0]])
        expected = np.array([[1.0, 2.0, 3.0]])
        np.testing.assert_array_equal(rectify(data), expected)

    def test_mixed_values(self):
        data = np.array([[-3.0, 0.0, 4.0]])
        expected = np.array([[3.0, 0.0, 4.0]])
        np.testing.assert_array_equal(rectify(data), expected)

    def test_multichannel(self):
        data = np.array([[-1.0, 2.0], [3.0, -4.0]])
        result = rectify(data)
        assert np.all(result >= 0)
        assert result.shape == data.shape


class TestButterbandpass:
    def _sine(self, freq, n=4000):
        """Generate a single-row 1D sine wave at `freq` Hz."""
        t = np.arange(n) / FS
        return np.array([np.sin(2 * np.pi * freq * t)])

    def test_passband_signal_preserved(self):
        # 100 Hz is inside 20-450 Hz band — amplitude should not drop significantly.
        data = self._sine(100)
        filtered = butter_bandpass(data, 20, 450, FS)
        # Steady-state amplitude should stay close to 1 (ignoring edge transients).
        mid = filtered[0, 500:-500]
        assert np.max(np.abs(mid)) > 0.8

    def test_stopband_signal_attenuated(self):
        # 5 Hz is below the 20 Hz cutoff — should be heavily attenuated.
        data = self._sine(5)
        filtered = butter_bandpass(data, 20, 450, FS)
        assert np.max(np.abs(filtered)) < 0.5

    def test_output_shape_preserved(self):
        data = np.random.randn(4, 4000)
        filtered = butter_bandpass(data, 20, 450, FS)
        assert filtered.shape == data.shape

    def test_very_small_data_passthrough(self):
        # Fewer than FILTER_MIN_SAMPLES — data returned unchanged.
        data = np.ones((1, Config.FILTER_MIN_SAMPLES - 1))
        result = butter_bandpass(data, 20, 450, FS)
        np.testing.assert_array_equal(result, data)

    def test_small_data_reduced_order(self):
        # Data length just meets FILTER_MIN_SAMPLES — should use order 1 and not raise.
        n = Config.FILTER_MIN_SAMPLES + 5
        data = np.random.randn(1, n)
        result = butter_bandpass(data, 20, 450, FS)
        assert result.shape == data.shape


class TestNotch:
    def _sine(self, freq, n=4000):
        t = np.arange(n) / FS
        return np.array([np.sin(2 * np.pi * freq * t)])

    def test_notch_attenuates_target_frequency(self):
        # 60 Hz powerline tone should be suppressed.
        data = self._sine(60)
        result = notch(data, 60, FS)
        mid = result[0, 500:-500]
        assert np.max(np.abs(mid)) < 0.5

    def test_non_notch_frequency_preserved(self):
        # 100 Hz should pass through a 60 Hz notch mostly intact.
        data = self._sine(100)
        result = notch(data, 60, FS)
        mid = result[0, 500:-500]
        assert np.max(np.abs(mid)) > 0.8

    def test_output_shape_preserved(self):
        data = np.random.randn(2, 4000)
        result = notch(data, 60, FS)
        assert result.shape == data.shape

    def test_small_data_passthrough(self):
        # Fewer than NOTCH_MIN_SAMPLES — data returned unchanged.
        data = np.ones((1, Config.NOTCH_MIN_SAMPLES - 1))
        result = notch(data, 60, FS)
        np.testing.assert_array_equal(result, data)
