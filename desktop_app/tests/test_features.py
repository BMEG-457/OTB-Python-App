"""Tests for app/processing/features.py"""

import numpy as np
import pytest
from app.processing.features import (
    rms, mav, integrated_emg,
    compute_tkeo_activation_timing,
    compute_burst_duration,
    compute_bilateral_symmetry,
    compute_fatigue,
    compute_centroid_shift,
    compute_spatial_nonuniformity,
)
from app.core.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FS = 2000  # Hz — device default


def _timestamps(n, fs=FS):
    return np.arange(n, dtype=float) / fs


def _synthetic_emg(n=4000, fs=FS, burst_start=0.7, burst_end=1.3, seed=42):
    """Quiet-then-burst-then-quiet synthetic EMG, shape (n,)."""
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n) * 100.0
    t = _timestamps(n, fs)
    burst_mask = (t >= burst_start) & (t <= burst_end)
    noise[burst_mask] += rng.standard_normal(np.sum(burst_mask)) * 2000.0
    return noise


# ---------------------------------------------------------------------------
# Basic features
# ---------------------------------------------------------------------------

class TestRms:
    def test_known_value(self):
        # rms([[3, 4]]) = sqrt((9+16)/2) = sqrt(12.5)
        data = np.array([[3.0, 4.0]])
        result = rms(data)
        np.testing.assert_allclose(result, np.sqrt(12.5), rtol=1e-9)

    def test_output_shape_keepdims(self):
        data = np.random.randn(5, 100)
        result = rms(data)
        assert result.shape == (5, 1)

    def test_zeros_return_zero(self):
        data = np.zeros((3, 50))
        assert np.all(rms(data) == 0.0)

    def test_uniform_signal(self):
        # rms of constant c = c
        data = np.full((2, 200), 3.0)
        np.testing.assert_allclose(rms(data), 3.0)


class TestMav:
    def test_known_value(self):
        # mav([[-3, 4]]) = (3+4)/2 = 3.5
        data = np.array([[-3.0, 4.0]])
        np.testing.assert_allclose(mav(data), 3.5)

    def test_output_shape_keepdims(self):
        data = np.random.randn(4, 100)
        assert mav(data).shape == (4, 1)

    def test_zeros(self):
        assert np.all(mav(np.zeros((2, 50))) == 0.0)


class TestIntegratedEmg:
    def test_known_value(self):
        # iemg([[-3, 4]]) = 3 + 4 = 7
        data = np.array([[-3.0, 4.0]])
        np.testing.assert_allclose(integrated_emg(data), 7.0)

    def test_output_shape_keepdims(self):
        data = np.random.randn(3, 100)
        assert integrated_emg(data).shape == (3, 1)


# ---------------------------------------------------------------------------
# TKEO activation timing
# ---------------------------------------------------------------------------

class TestTKEOActivationTiming:
    def test_too_few_samples_returns_none(self):
        n = Config.TKEO_MIN_DATA_LEN - 1
        result = compute_tkeo_activation_timing(
            np.random.randn(n), _timestamps(n), FS
        )
        assert result is None

    def test_valid_signal_returns_result(self):
        signal = _synthetic_emg()
        ts = _timestamps(len(signal))
        result = compute_tkeo_activation_timing(signal, ts, FS)
        assert result is not None

    def test_result_has_expected_fields(self):
        signal = _synthetic_emg()
        ts = _timestamps(len(signal))
        result = compute_tkeo_activation_timing(signal, ts, FS)
        assert result is not None
        assert len(result.timestamps) > 0
        assert len(result.tkeo_envelope) == len(result.timestamps)
        assert result.detection_threshold > 0

    def test_onset_detected_in_burst_region(self):
        signal = _synthetic_emg(burst_start=0.7, burst_end=1.3)
        ts = _timestamps(len(signal))
        result = compute_tkeo_activation_timing(signal, ts, FS)
        assert result is not None
        if len(result.onset_times) > 0:
            # At least one onset should fall within or just before the burst.
            assert any(0.5 <= t <= 1.5 for t in result.onset_times)

    def test_nan_timestamps_handled(self):
        signal = _synthetic_emg()
        ts = _timestamps(len(signal))
        ts[5] = np.nan
        signal[5] = np.nan
        result = compute_tkeo_activation_timing(signal, ts, FS)
        # Should not crash; may return result or None depending on remaining data.
        # Just verify no exception is raised and type is correct.
        assert result is None or hasattr(result, 'timestamps')


# ---------------------------------------------------------------------------
# Burst duration
# ---------------------------------------------------------------------------

class TestBurstDuration:
    def test_too_few_samples_returns_none(self):
        n = Config.TKEO_MIN_DATA_LEN - 1
        result = compute_burst_duration(np.random.randn(n), _timestamps(n), FS)
        assert result is None

    def test_valid_signal_returns_result(self):
        signal = _synthetic_emg()
        result = compute_burst_duration(signal, _timestamps(len(signal)), FS)
        assert result is not None

    def test_burst_count_non_negative(self):
        signal = _synthetic_emg()
        result = compute_burst_duration(signal, _timestamps(len(signal)), FS)
        assert result is not None
        assert result.num_bursts >= 0

    def test_avg_duration_non_negative(self):
        signal = _synthetic_emg()
        result = compute_burst_duration(signal, _timestamps(len(signal)), FS)
        assert result is not None
        assert result.avg_duration >= 0.0


# ---------------------------------------------------------------------------
# Bilateral symmetry
# ---------------------------------------------------------------------------

class TestBilateralSymmetry:
    def _make_pair(self, amp1=1.0, amp2=1.0, n=2000, fs=200.0, seed=0):
        rng = np.random.default_rng(seed)
        ts = np.arange(n) / fs
        s1 = rng.standard_normal(n) * amp1
        s2 = rng.standard_normal(n) * amp2
        return s1, ts, fs, s2, ts.copy(), fs

    def test_equal_amplitude_near_zero_mean_si(self):
        s1, ts1, fs1, s2, ts2, fs2 = self._make_pair(amp1=1.0, amp2=1.0, n=4000)
        result = compute_bilateral_symmetry(s1, ts1, fs1, s2, ts2, fs2)
        assert result is not None
        assert abs(result.mean_si) < 0.2  # statistical; should be small

    def test_asymmetric_signals_positive_si(self):
        # Signal 1 has much higher amplitude → SI should be clearly positive.
        s1, ts1, fs1, s2, ts2, fs2 = self._make_pair(amp1=10.0, amp2=1.0, n=4000)
        result = compute_bilateral_symmetry(s1, ts1, fs1, s2, ts2, fs2)
        assert result is not None
        assert result.mean_si > 0.5

    def test_si_range(self):
        s1, ts1, fs1, s2, ts2, fs2 = self._make_pair(amp1=3.0, amp2=1.0, n=2000)
        result = compute_bilateral_symmetry(s1, ts1, fs1, s2, ts2, fs2)
        assert result is not None
        assert np.all(np.abs(result.symmetry_index) <= 1.0)

    def test_overlap_duration_is_min_of_two(self):
        n1, n2 = 2000, 1000
        fs = 200.0
        rng = np.random.default_rng(1)
        s1 = rng.standard_normal(n1)
        ts1 = np.arange(n1) / fs
        s2 = rng.standard_normal(n2)
        ts2 = np.arange(n2) / fs
        result = compute_bilateral_symmetry(s1, ts1, fs, s2, ts2, fs)
        assert result is not None
        expected_overlap = min(ts1[-1], ts2[-1])
        assert abs(result.overlap_duration - expected_overlap) < 0.1


# ---------------------------------------------------------------------------
# Fatigue
# ---------------------------------------------------------------------------

class TestFatigue:
    def _make_signal(self, n=6000, fs=FS):
        rng = np.random.default_rng(7)
        return rng.standard_normal(n) * 500.0, _timestamps(n, fs)

    def test_valid_signal_returns_result(self):
        sig, ts = self._make_signal()
        result = compute_fatigue(sig, ts, FS)
        assert result is not None

    def test_too_few_samples_returns_none(self):
        sig = np.random.randn(10)
        ts = _timestamps(10)
        result = compute_fatigue(sig, ts, FS)
        assert result is None

    def test_result_has_rms_and_mf_arrays(self):
        sig, ts = self._make_signal()
        result = compute_fatigue(sig, ts, FS)
        assert result is not None
        assert len(result.rms_values) > 0
        assert len(result.mf_values) > 0
        assert len(result.rms_times) == len(result.rms_values)
        assert len(result.mf_times) == len(result.mf_values)

    def test_baseline_rms_non_negative(self):
        sig, ts = self._make_signal()
        result = compute_fatigue(sig, ts, FS)
        assert result is not None
        assert result.baseline_rms >= 0.0


# ---------------------------------------------------------------------------
# Centroid shift
# ---------------------------------------------------------------------------

class TestCentroidShift:
    def _make_64ch(self, n=4000, fs=FS):
        rng = np.random.default_rng(3)
        data = rng.standard_normal((64, n)) * 500.0
        ts = _timestamps(n, fs)
        return data, ts

    def test_wrong_channel_count_returns_none(self):
        rng = np.random.default_rng(0)
        data = rng.standard_normal((32, 4000))
        ts = _timestamps(4000)
        assert compute_centroid_shift(data, ts, FS) is None

    def test_valid_data_returns_result(self):
        data, ts = self._make_64ch()
        result = compute_centroid_shift(data, ts, FS)
        assert result is not None

    def test_displacement_starts_at_zero(self):
        data, ts = self._make_64ch()
        result = compute_centroid_shift(data, ts, FS)
        assert result is not None
        assert result.displacement[0] == pytest.approx(0.0, abs=1e-10)

    def test_centroid_within_grid_bounds(self):
        data, ts = self._make_64ch()
        result = compute_centroid_shift(data, ts, FS)
        assert result is not None
        assert np.all(result.centroid_x >= 0) and np.all(result.centroid_x <= 7)
        assert np.all(result.centroid_y >= 0) and np.all(result.centroid_y <= 7)

    def test_too_few_samples_returns_none(self):
        data = np.random.randn(64, 10)
        ts = _timestamps(10)
        assert compute_centroid_shift(data, ts, FS) is None


# ---------------------------------------------------------------------------
# Spatial non-uniformity
# ---------------------------------------------------------------------------

class TestSpatialNonUniformity:
    def _make_64ch(self, n=4000, fs=FS):
        rng = np.random.default_rng(5)
        data = np.abs(rng.standard_normal((64, n))) * 500.0
        ts = _timestamps(n, fs)
        return data, ts

    def test_wrong_channel_count_returns_none(self):
        data = np.random.randn(32, 4000)
        ts = _timestamps(4000)
        assert compute_spatial_nonuniformity(data, ts, FS) is None

    def test_valid_data_returns_result(self):
        data, ts = self._make_64ch()
        result = compute_spatial_nonuniformity(data, ts, FS)
        assert result is not None

    def test_cv_non_negative(self):
        data, ts = self._make_64ch()
        result = compute_spatial_nonuniformity(data, ts, FS)
        assert result is not None
        assert np.all(result.cv >= 0)

    def test_entropy_non_negative(self):
        data, ts = self._make_64ch()
        result = compute_spatial_nonuniformity(data, ts, FS)
        assert result is not None
        assert np.all(result.entropy >= 0)

    def test_activation_fraction_between_0_and_1(self):
        data, ts = self._make_64ch()
        result = compute_spatial_nonuniformity(data, ts, FS)
        assert result is not None
        assert np.all(result.activation_fraction >= 0)
        assert np.all(result.activation_fraction <= 1)

    def test_threshold_source_auto_when_no_calibration(self):
        data, ts = self._make_64ch()
        result = compute_spatial_nonuniformity(data, ts, FS)
        assert result is not None
        assert result.threshold_source == 'auto'

    def test_threshold_source_calibration_when_provided(self):
        data, ts = self._make_64ch()
        thresholds = np.ones(64) * 100.0
        result = compute_spatial_nonuniformity(data, ts, FS,
                                               threshold_per_channel=thresholds)
        assert result is not None
        assert result.threshold_source == 'calibration'

    def test_uniform_activation_higher_entropy(self):
        # Uniform activation (all channels equal) should give higher entropy
        # than highly concentrated activation (one channel dominant).
        n = 4000
        ts = _timestamps(n)

        uniform = np.ones((64, n)) * 500.0
        concentrated = np.zeros((64, n))
        concentrated[0, :] = 5000.0  # one channel dominates

        r_uniform = compute_spatial_nonuniformity(uniform, ts, FS)
        r_concentrated = compute_spatial_nonuniformity(concentrated, ts, FS)

        if r_uniform is not None and r_concentrated is not None:
            assert np.mean(r_uniform.entropy) > np.mean(r_concentrated.entropy)
