"""Tests for app/processing/realtime_detector.py"""

import numpy as np
import pytest
from app.processing.realtime_detector import ContractionDetector


ON = ContractionDetector.ON_THRESHOLD
OFF = ContractionDetector.OFF_THRESHOLD


def _uniform(value, n=64):
    """Return an array of `n` identical values."""
    return np.full(n, value)


class TestContractionDetectorInit:
    def test_starts_not_contracting(self):
        d = ContractionDetector()
        assert d.is_contracting is False


class TestContractionDetectorUpdate:
    def test_triggers_on_above_threshold(self):
        d = ContractionDetector()
        changed = d.update(_uniform(ON + 0.01))
        assert d.is_contracting is True
        assert changed is True

    def test_no_trigger_at_threshold(self):
        # Exactly at ON threshold — strict greater-than required.
        d = ContractionDetector()
        changed = d.update(_uniform(ON))
        assert d.is_contracting is False
        assert changed is False

    def test_stays_on_in_deadband(self):
        d = ContractionDetector()
        d.update(_uniform(ON + 0.01))  # turn on
        # Value between OFF and ON — should stay on.
        changed = d.update(_uniform((ON + OFF) / 2))
        assert d.is_contracting is True
        assert changed is False

    def test_turns_off_below_off_threshold(self):
        d = ContractionDetector()
        d.update(_uniform(ON + 0.01))          # turn on
        changed = d.update(_uniform(OFF - 0.01))  # turn off
        assert d.is_contracting is False
        assert changed is True

    def test_no_change_when_already_off_and_below_on(self):
        d = ContractionDetector()
        changed = d.update(_uniform(OFF - 0.01))
        assert d.is_contracting is False
        assert changed is False

    def test_no_change_returned_when_state_unchanged(self):
        d = ContractionDetector()
        d.update(_uniform(ON + 0.01))   # turn on → changed
        changed = d.update(_uniform(ON + 0.01))  # stays on → no change
        assert changed is False

    def test_multiple_channels_uses_mean(self):
        # Mix of high and low values — mean determines state.
        d = ContractionDetector()
        values = np.zeros(64)
        values[:32] = ON + 0.1   # top half above threshold
        values[32:] = 0.0        # bottom half at 0
        mean = float(np.mean(values))
        d.update(values)
        # mean = (ON + 0.1) / 2 ≈ 0.125 — just below ON (0.15); detector stays off.
        assert d.is_contracting == (mean > ON)


class TestContractionDetectorReset:
    def test_reset_clears_contracting_state(self):
        d = ContractionDetector()
        d.update(_uniform(ON + 0.01))
        assert d.is_contracting is True
        d.reset()
        assert d.is_contracting is False

    def test_reset_allows_re_trigger(self):
        d = ContractionDetector()
        d.update(_uniform(ON + 0.01))
        d.reset()
        changed = d.update(_uniform(ON + 0.01))
        assert d.is_contracting is True
        assert changed is True
