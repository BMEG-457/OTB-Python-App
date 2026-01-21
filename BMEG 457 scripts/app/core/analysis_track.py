"""Track class for static data analysis - displays preprocessed data with view window."""

import numpy as np
import pyqtgraph as pg


class AnalysisTrack:
    """Single track for displaying EMG data with selectable channels."""

    # Colors for the two channels
    CHANNEL_COLORS = [
        (255, 100, 100),  # Red-ish for channel 1
        (100, 100, 255),  # Blue-ish for channel 2
    ]

    def __init__(self, title, num_channels, timestamps, data):
        """
        Args:
            title: Track title
            num_channels: Total number of channels available
            timestamps: Timestamp array
            data: Data array (channels, samples)
        """
        self.title = title
        self.num_channels = num_channels
        self.timestamps = timestamps
        self.data = data

        # Current view window
        self.view_start = 0.0
        self.view_duration = 1.0

        # Selected channels (max 2)
        self.selected_channels = []

        # Setup plot widget
        self.plot_widget = pg.PlotWidget(title=self.title)
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getViewBox().setBackgroundColor((30, 30, 30))
        self.plot_widget.setAntialiasing(True)
        self.plot_widget.enableAutoRange(axis='y')

        # Add labels
        self.plot_widget.setLabel("left", "Amplitude")
        self.plot_widget.setLabel("bottom", "Time", units="s")

        # Add legend
        self.legend = self.plot_widget.addLegend()

        # Create plot curves for 2 channels
        self.curves = []
        for i in range(2):
            pen = pg.mkPen(color=self.CHANNEL_COLORS[i], width=2)
            curve = self.plot_widget.plot(pen=pen, name=f"Channel ?")
            curve.hide()
            self.curves.append(curve)

    def set_view_window(self, start_time: float, duration: float):
        """Set the current view window."""
        self.view_start = start_time
        self.view_duration = duration
        self.plot_widget.setXRange(start_time, start_time + duration, padding=0)

    def draw(self):
        """Draw the current view window with selected channels."""
        if self.data is None or len(self.data) == 0:
            return
        if self.timestamps is None or len(self.timestamps) == 0:
            return

        base_time = self.timestamps[0]
        abs_start = base_time + self.view_start
        abs_end = abs_start + self.view_duration

        start_idx = np.searchsorted(self.timestamps, abs_start)
        end_idx = np.searchsorted(self.timestamps, abs_end)

        start_idx = max(0, start_idx)
        end_idx = min(len(self.timestamps), end_idx)

        if start_idx >= end_idx:
            for curve in self.curves:
                curve.setData([], [])
            return

        view_timestamps = self.timestamps[start_idx:end_idx] - base_time
        view_data = self.data[:, start_idx:end_idx]

        for curve_idx, curve in enumerate(self.curves):
            if curve_idx < len(self.selected_channels):
                ch_idx = self.selected_channels[curve_idx]
                if ch_idx < view_data.shape[0]:
                    curve.setData(view_timestamps, view_data[ch_idx, :])
                    curve.show()
                else:
                    curve.setData([], [])
                    curve.hide()
            else:
                curve.setData([], [])
                curve.hide()

    def set_selected_channels(self, channels: list):
        """Set which channels to display (max 2)."""
        valid_channels = [ch for ch in channels if 0 <= ch < self.num_channels]
        self.selected_channels = valid_channels[:2]

        for curve_idx, curve in enumerate(self.curves):
            if curve_idx < len(self.selected_channels):
                ch_num = self.selected_channels[curve_idx] + 1
                curve.setData(name=f"Channel {ch_num}")
            else:
                curve.hide()

        self.draw()

    def get_selected_channels(self) -> list:
        return list(self.selected_channels)
