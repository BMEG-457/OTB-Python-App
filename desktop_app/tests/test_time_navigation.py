"""Tests for app/managers/time_navigation_controller.py"""

import pytest
from app.managers.time_navigation_controller import TimeNavigationController


@pytest.fixture
def ctrl(qapp):
    """Controller with 10-second total duration and 1-second window."""
    return TimeNavigationController(total_duration=10.0, initial_window=1.0)


class TestInit:
    def test_initial_start_is_zero(self, qapp):
        c = TimeNavigationController(total_duration=10.0, initial_window=1.0)
        assert c.get_current_start() == 0.0

    def test_initial_duration_matches_argument(self, qapp):
        c = TimeNavigationController(total_duration=10.0, initial_window=2.0)
        assert c.get_current_duration() == 2.0

    def test_zero_duration_uses_window(self, qapp):
        c = TimeNavigationController(total_duration=0.0, initial_window=5.0)
        assert c.get_current_duration() == 5.0


class TestSeekTo:
    def test_seek_to_middle(self, ctrl):
        ctrl.seek_to(5.0)
        assert ctrl.get_current_start() == 5.0

    def test_seek_clamped_to_zero(self, ctrl):
        ctrl.seek_to(-2.0)
        assert ctrl.get_current_start() == 0.0

    def test_seek_clamped_to_max(self, ctrl):
        # Max start = total_duration - window_duration = 10 - 1 = 9
        ctrl.seek_to(100.0)
        assert ctrl.get_current_start() == 9.0

    def test_seek_to_start(self, ctrl):
        ctrl.seek_to(5.0)
        ctrl.seek_to(0.0)
        assert ctrl.get_current_start() == 0.0


class TestScrollBy:
    def test_scroll_forward(self, ctrl):
        ctrl.scroll_by(2.0)
        assert abs(ctrl.get_current_start() - 2.0) < 1e-9

    def test_scroll_backward(self, ctrl):
        ctrl.seek_to(5.0)
        ctrl.scroll_by(-2.0)
        assert abs(ctrl.get_current_start() - 3.0) < 1e-9

    def test_scroll_clamped_at_zero(self, ctrl):
        ctrl.scroll_by(-100.0)
        assert ctrl.get_current_start() == 0.0

    def test_scroll_clamped_at_max(self, ctrl):
        ctrl.scroll_by(100.0)
        assert ctrl.get_current_start() == 9.0


class TestScrollLeftRight:
    def test_scroll_right_moves_forward(self, ctrl):
        ctrl.scroll_right()
        assert ctrl.get_current_start() > 0.0

    def test_scroll_left_at_start_stays_zero(self, ctrl):
        ctrl.scroll_left()
        assert ctrl.get_current_start() == 0.0

    def test_scroll_right_then_left_returns_to_origin(self, ctrl):
        ctrl.scroll_right()
        moved = ctrl.get_current_start()
        ctrl.scroll_left()
        assert abs(ctrl.get_current_start() - 0.0) < 1e-9

    def test_scroll_step_is_10_percent_of_window(self, ctrl):
        # window = 1.0s → 10% step = 0.1s
        ctrl.scroll_right()
        assert abs(ctrl.get_current_start() - 0.1) < 1e-9


class TestZoom:
    def test_zoom_in_halves_duration(self, ctrl):
        ctrl.seek_to(5.0)
        ctrl.zoom_in()
        assert abs(ctrl.get_current_duration() - 0.5) < 1e-9

    def test_zoom_out_doubles_duration(self, ctrl):
        ctrl.zoom_out()
        assert abs(ctrl.get_current_duration() - 2.0) < 1e-9

    def test_zoom_in_min_window_50ms(self, ctrl):
        # Zoom in many times — should never go below 50ms (0.05s).
        for _ in range(20):
            ctrl.zoom_in()
        assert ctrl.get_current_duration() >= 0.05

    def test_zoom_out_capped_at_total_duration(self, ctrl):
        # Window cannot exceed total duration.
        for _ in range(10):
            ctrl.zoom_out()
        assert ctrl.get_current_duration() <= 10.0

    def test_zoom_preserves_center(self, ctrl):
        ctrl.seek_to(4.0)  # center at 4.5 (start=4, window=1 → center=4.5)
        center_before = ctrl.get_current_start() + ctrl.get_current_duration() / 2
        ctrl.zoom_in()
        center_after = ctrl.get_current_start() + ctrl.get_current_duration() / 2
        assert abs(center_before - center_after) < 1e-9


class TestGoToStartEnd:
    def test_go_to_start(self, ctrl):
        ctrl.seek_to(7.0)
        ctrl.go_to_start()
        assert ctrl.get_current_start() == 0.0

    def test_go_to_end(self, ctrl):
        ctrl.go_to_end()
        assert ctrl.get_current_start() == 9.0  # 10 - 1 = 9


class TestNormalizedPosition:
    def test_at_start_normalized_is_based_on_center(self, ctrl):
        # start=0, window=1 → center=0.5 → normalized=0.5/10=0.05
        pos = ctrl.get_normalized_position()
        assert abs(pos - 0.05) < 1e-9

    def test_at_end_normalized_near_one(self, ctrl):
        ctrl.go_to_end()
        pos = ctrl.get_normalized_position()
        # start=9, window=1 → center=9.5 → normalized=9.5/10=0.95
        assert abs(pos - 0.95) < 1e-9

    def test_set_normalized_position(self, ctrl):
        ctrl.set_normalized_position(0.5)
        # center = 0.5 * 10 = 5.0 → start = 5 - 0.5 = 4.5
        assert abs(ctrl.get_current_start() - 4.5) < 1e-9

    def test_zero_total_duration_returns_zero(self, qapp):
        c = TimeNavigationController(total_duration=0.0, initial_window=1.0)
        assert c.get_normalized_position() == 0.0


class TestReset:
    def test_reset_restores_start_to_zero(self, ctrl):
        ctrl.seek_to(5.0)
        ctrl.reset(total_duration=20.0, window_duration=2.0)
        assert ctrl.get_current_start() == 0.0

    def test_reset_updates_total_duration(self, ctrl):
        ctrl.reset(total_duration=30.0, window_duration=3.0)
        assert ctrl.total_duration == 30.0

    def test_reset_window_capped_at_total_duration(self, ctrl):
        ctrl.reset(total_duration=1.0, window_duration=5.0)
        assert ctrl.get_current_duration() == 1.0
