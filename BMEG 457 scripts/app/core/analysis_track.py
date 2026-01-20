"""Track class for static data analysis - displays preprocessed data with view window."""

import numpy as np
import pyqtgraph as pg


class AnalysisTrack:
    """Track for data analysis - supports multi-resolution display, limited to 2 channels."""

    # Maximum number of channels that can be displayed simultaneously
    MAX_CHANNELS = 2

    # Colors for the two channels
    CHANNEL_COLORS = [
        (255, 100, 100),  # Red-ish for channel 1
        (100, 100, 255),  # Blue-ish for channel 2
    ]

    def __init__(self, title, num_channels, resolution_data):
        """
        Args:
            title: Track title
            num_channels: Total number of channels available
            resolution_data: Dict of {level_name: (timestamps, data)} from CSVDataLoader
        """
        self.title = title
        self.num_channels = num_channels
        self.resolution_data = resolution_data

        # Current resolution level
        self.current_resolution = 'L2'  # Default to L2 (200 Hz) for good balance

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
        self.plot_widget.setLabel("left", "Amplitude (Rectified Envelope)")
        self.plot_widget.setLabel("bottom", "Time", units="s")

        # Add legend
        self.legend = self.plot_widget.addLegend()

        # Create plot curves for 2 channels (line plots for envelope)
        self.curves = []
        for i in range(self.MAX_CHANNELS):
            pen = pg.mkPen(color=self.CHANNEL_COLORS[i], width=2)
            curve = self.plot_widget.plot(pen=pen, name=f"Channel ?")
            curve.hide()  # Hidden until channel is selected
            self.curves.append(curve)

    def set_resolution(self, level: str):
        """Set the resolution level for display.

        Args:
            level: Resolution level name ('Raw', 'L1', 'L2', 'L3')
        """
        if level in self.resolution_data:
            self.current_resolution = level
            self.draw()

    def get_current_resolution(self) -> str:
        """Get current resolution level."""
        return self.current_resolution

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
        """Draw the current view window with selected channels."""
        # Get data at current resolution
        if self.current_resolution not in self.resolution_data:
            return

        timestamps, data = self.resolution_data[self.current_resolution]

        if data is None or len(data) == 0:
            return
        if timestamps is None or len(timestamps) == 0:
            return

        # Get base time for relative timestamps
        base_time = timestamps[0]

        # Find indices for current view
        abs_start = base_time + self.view_start
        abs_end = abs_start + self.view_duration

        start_idx = np.searchsorted(timestamps, abs_start)
        end_idx = np.searchsorted(timestamps, abs_end)

        # Clamp indices
        start_idx = max(0, start_idx)
        end_idx = min(len(timestamps), end_idx)

        if start_idx >= end_idx:
            # No data in window, clear curves
            for curve in self.curves:
                curve.setData([], [])
            return

        # Get view data
        view_timestamps = timestamps[start_idx:end_idx] - base_time
        view_data = data[:, start_idx:end_idx]

        # Update curves for selected channels
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
        """Set which channels to display (max 2).

        Args:
            channels: List of channel indices to display (only first 2 will be used)
        """
        # Limit to MAX_CHANNELS
        valid_channels = [ch for ch in channels if 0 <= ch < self.num_channels]
        self.selected_channels = valid_channels[:self.MAX_CHANNELS]

        # Update legend names
        for curve_idx, curve in enumerate(self.curves):
            if curve_idx < len(self.selected_channels):
                ch_num = self.selected_channels[curve_idx] + 1  # 1-based for display
                curve.setData(name=f"Channel {ch_num}")
            else:
                curve.hide()

        # Redraw
        self.draw()

    def get_selected_channels(self) -> list:
        """Get list of currently selected channel indices."""
        return list(self.selected_channels)

    def get_data_duration(self) -> float:
        """Get total duration of loaded data in seconds."""
        # Use raw resolution for duration calculation
        if 'Raw' in self.resolution_data:
            timestamps, _ = self.resolution_data['Raw']
            if timestamps is not None and len(timestamps) >= 2:
                return timestamps[-1] - timestamps[0]
        return 0.0
