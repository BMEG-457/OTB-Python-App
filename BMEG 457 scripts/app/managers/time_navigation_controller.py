"""Time navigation controller for data analysis mode."""

from PyQt5 import QtCore


class TimeNavigationController(QtCore.QObject):
    """Controls time navigation for data analysis."""

    # Signal emitted when view window changes: (start_time, duration)
    view_changed = QtCore.pyqtSignal(float, float)

    def __init__(self, total_duration: float = 0.0, initial_window: float = 1.0):
        super().__init__()
        self.total_duration = total_duration
        self.current_start = 0.0
        self.current_duration = initial_window

    def set_total_duration(self, duration: float):
        """Set the total duration of the data.

        Args:
            duration: Total duration in seconds
        """
        self.total_duration = duration
        # Clamp current position if needed
        self._clamp_position()
        self._emit_change()

    def set_window_duration(self, duration: float):
        """Set the view window duration (zoom level).

        Args:
            duration: Window duration in seconds
        """
        if duration <= 0:
            return

        # Keep center position when changing duration
        center = self.current_start + self.current_duration / 2
        self.current_duration = min(duration, self.total_duration) if self.total_duration > 0 else duration
        self.current_start = center - self.current_duration / 2
        self._clamp_position()
        self._emit_change()

    def seek_to(self, time: float):
        """Jump to a specific time position.

        Args:
            time: Absolute time position in seconds
        """
        self.current_start = time
        self._clamp_position()
        self._emit_change()

    def scroll_by(self, delta: float):
        """Scroll by a time delta.

        Args:
            delta: Time to scroll (positive = forward, negative = backward)
        """
        self.current_start += delta
        self._clamp_position()
        self._emit_change()

    def scroll_left(self):
        """Scroll left by 10% of window duration."""
        self.scroll_by(-self.current_duration * 0.1)

    def scroll_right(self):
        """Scroll right by 10% of window duration."""
        self.scroll_by(self.current_duration * 0.1)

    def zoom_in(self):
        """Decrease window duration (zoom in on time axis)."""
        new_duration = self.current_duration / 2
        if new_duration >= 0.05:  # Minimum 50ms window
            self.set_window_duration(new_duration)

    def zoom_out(self):
        """Increase window duration (zoom out on time axis)."""
        new_duration = self.current_duration * 2
        self.set_window_duration(new_duration)

    def go_to_start(self):
        """Jump to beginning of recording."""
        self.current_start = 0.0
        self._emit_change()

    def go_to_end(self):
        """Jump to end of recording."""
        self.current_start = max(0, self.total_duration - self.current_duration)
        self._emit_change()

    def get_normalized_position(self) -> float:
        """Get current position as fraction of total duration (0.0-1.0)."""
        if self.total_duration <= 0:
            return 0.0
        # Use center of view window for position
        center = self.current_start + self.current_duration / 2
        return min(1.0, max(0.0, center / self.total_duration))

    def set_normalized_position(self, pos: float):
        """Set position from normalized value (for slider).

        Args:
            pos: Position as fraction (0.0-1.0)
        """
        if self.total_duration <= 0:
            return
        # Map to center of view window
        center = pos * self.total_duration
        self.current_start = center - self.current_duration / 2
        self._clamp_position()
        self._emit_change()

    def get_current_start(self) -> float:
        """Get current view start time."""
        return self.current_start

    def get_current_duration(self) -> float:
        """Get current view duration."""
        return self.current_duration

    def _clamp_position(self):
        """Clamp position to valid range."""
        if self.total_duration <= 0:
            self.current_start = 0.0
            return

        # Ensure we don't go past the end
        max_start = max(0, self.total_duration - self.current_duration)
        self.current_start = max(0, min(self.current_start, max_start))

    def _emit_change(self):
        """Emit the view_changed signal."""
        self.view_changed.emit(self.current_start, self.current_duration)

    def reset(self, total_duration: float, window_duration: float = 1.0):
        """Reset controller for new data.

        Args:
            total_duration: Total duration of new data
            window_duration: Initial view window duration
        """
        self.total_duration = total_duration
        self.current_start = 0.0
        self.current_duration = min(window_duration, total_duration) if total_duration > 0 else window_duration
        self._emit_change()
