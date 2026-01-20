"""Track class for static data analysis - displays full dataset with view window."""

import numpy as np
import pyqtgraph as pg


class AnalysisTrack:
    """Track optimized for static data analysis - full data buffer, configurable view window."""

    def __init__(self, title, num_channels, timestamps, data):
        """
        Args:
            title: Track title
            num_channels: Number of channels
            timestamps: Full timestamp array
            data: Full data array (channels, samples)
        """
        self.title = title
        self.num_channels = num_channels

        # Store full dataset
        self.full_timestamps = timestamps
        self.full_data = data

        # Current view window
        self.view_start = 0.0
        self.view_duration = 1.0

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

        # Create scatter plots for each channel - all channels plotted centered at 0
        self.curves = []
        for i in range(num_channels):
            # Use different colors for each channel - scatter plot (no line)
            color = pg.intColor(i, hues=num_channels)
            scatter = pg.ScatterPlotItem(pen=None, brush=color, size=3)
            self.plot_widget.addItem(scatter)
            self.curves.append(scatter)

        # By default no channels are visible - user must select
        self.visible_channels = []
        # Hide all curves initially
        for curve in self.curves:
            curve.hide()

    def set_view_window(self, start_time: float, duration: float):
        """Set the current view window - what portion of data to display.

        Args:
            start_time: Start time in seconds (relative to data start)
            duration: Window duration in seconds
        """
        self.view_start = start_time
        self.view_duration = duration

        # Update X range
        self.plot_widget.setXRange(start_time, start_time + duration, padding=0)

    def draw(self):
        """Draw the current view window."""
        if self.full_data is None or len(self.full_data) == 0:
            return

        if self.full_timestamps is None or len(self.full_timestamps) == 0:
            return

        # Get base time for relative timestamps
        base_time = self.full_timestamps[0]

        # Find indices for current view
        abs_start = base_time + self.view_start
        abs_end = abs_start + self.view_duration

        start_idx = np.searchsorted(self.full_timestamps, abs_start)
        end_idx = np.searchsorted(self.full_timestamps, abs_end)

        # Clamp indices
        start_idx = max(0, start_idx)
        end_idx = min(len(self.full_timestamps), end_idx)

        if start_idx >= end_idx:
            # No data in window, clear scatter plots
            for scatter in self.curves:
                scatter.setData(x=[], y=[])
            return

        # Get view data
        view_timestamps = self.full_timestamps[start_idx:end_idx] - base_time
        view_data = self.full_data[:, start_idx:end_idx]

        # Update scatter plots - plot raw values centered at 0 (no offset)
        for i, scatter in enumerate(self.curves):
            if i < view_data.shape[0]:
                scatter.setData(x=view_timestamps, y=view_data[i, :])
            else:
                scatter.setData(x=[], y=[])

    def set_visible_channels(self, channels):
        """
        Show only the channels listed in `channels` (iterable of channel indices).
        Channels not listed will be hidden.
        """
        channels_set = set(int(c) for c in channels)
        self.visible_channels = sorted([c for c in channels_set if 0 <= c < self.num_channels])

        for ch_idx, curve in enumerate(self.curves):
            if ch_idx in channels_set:
                try:
                    curve.show()
                except Exception:
                    pass
            else:
                try:
                    curve.hide()
                except Exception:
                    pass

    def get_visible_channels(self):
        """Get list of currently visible channel indices."""
        return list(self.visible_channels)

    def get_data_duration(self) -> float:
        """Get total duration of loaded data in seconds."""
        if self.full_timestamps is None or len(self.full_timestamps) < 2:
            return 0.0
        return self.full_timestamps[-1] - self.full_timestamps[0]
