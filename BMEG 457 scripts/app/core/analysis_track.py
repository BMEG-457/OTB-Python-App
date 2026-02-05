"""Track class for static data analysis - displays preprocessed data with view window."""

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore
from scipy import signal
from scipy.ndimage import uniform_filter1d


class AnalysisTrack:
    """Single track for displaying EMG data with selectable channels and processing."""

    # Colors for the two channels
    CHANNEL_COLORS = [
        (255, 100, 100),  # Red-ish for channel 1
        (100, 100, 255),  # Blue-ish for channel 2
    ]

    def __init__(self, title, num_channels, timestamps, data, sample_rate=2000):
        """
        Args:
            title: Track title
            num_channels: Total number of channels available
            timestamps: Timestamp array
            data: Data array (channels, samples)
            sample_rate: Sample rate in Hz
        """
        self.title = title
        self.num_channels = num_channels
        self.timestamps = timestamps
        self.raw_data = data  # Store original data
        self.data = data      # Processed data (may be modified)
        self.sample_rate = sample_rate

        # Processing settings
        self.rectify = False
        self.envelope_type = 'none'  # 'none', 'rms', 'lowpass'
        self.rms_window = 50         # samples
        self.lowpass_cutoff = 10     # Hz

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

        # Onset markers (vertical lines) and threshold lines (horizontal)
        self.onset_markers = []
        self.threshold_lines = []

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
                label = f"Channel {ch_num}"
                self.legend.removeItem(curve)
                curve.opts['name'] = label
                self.legend.addItem(curve, label)
            else:
                curve.hide()

        self.draw()

    def get_selected_channels(self) -> list:
        return list(self.selected_channels)

    def set_processing(self, rectify: bool, envelope_type: str,
                       rms_window: int = 50, lowpass_cutoff: float = 10):
        """Set processing options and recompute processed data.

        Args:
            rectify: Whether to apply full-wave rectification
            envelope_type: 'none', 'rms', or 'lowpass'
            rms_window: Window size in samples for RMS envelope
            lowpass_cutoff: Cutoff frequency in Hz for lowpass filter
        """
        self.rectify = rectify
        self.envelope_type = envelope_type
        self.rms_window = rms_window
        self.lowpass_cutoff = lowpass_cutoff

        self._apply_processing()
        self.draw()

    def _apply_processing(self):
        """Apply current processing settings to raw data."""
        if self.raw_data is None:
            return

        data = self.raw_data.copy()

        # Step 1: Rectification (if enabled)
        if self.rectify:
            data = np.abs(data)

        # Step 2: Envelope (if selected)
        if self.envelope_type == 'rms':
            data = self._compute_rms_envelope(data, self.rms_window)
        elif self.envelope_type == 'lowpass':
            data = self._compute_lowpass_envelope(data, self.lowpass_cutoff)

        self.data = data

    def _compute_rms_envelope(self, data, window_size):
        """Compute RMS envelope."""
        result = np.zeros_like(data)
        for ch in range(data.shape[0]):
            squared = data[ch, :] ** 2
            mean_squared = uniform_filter1d(squared, size=window_size, mode='nearest')
            result[ch, :] = np.sqrt(mean_squared)
        return result

    def _compute_lowpass_envelope(self, data, cutoff_hz):
        """Apply lowpass filter for envelope detection."""
        if self.sample_rate <= 0:
            return data.copy()

        nyquist = self.sample_rate / 2
        if cutoff_hz >= nyquist:
            return data.copy()

        try:
            b, a = signal.butter(4, cutoff_hz / nyquist, btype='low')
            result = np.zeros_like(data)
            for ch in range(data.shape[0]):
                result[ch, :] = signal.filtfilt(b, a, data[ch, :])
            return result
        except Exception as e:
            print(f"Warning: Lowpass filter failed: {e}")
            return data.copy()

    def add_onset_markers(self, onset_times: np.ndarray, base_time: float):
        """Add vertical line markers at detected onset times.

        Args:
            onset_times: Array of absolute onset timestamps
            base_time: Base timestamp (timestamps[0]) for converting to relative time
        """
        self.clear_markers()
        for t in onset_times:
            relative_t = t - base_time
            line = pg.InfiniteLine(
                pos=relative_t,
                angle=90,
                pen=pg.mkPen(color=(255, 0, 0), width=2, style=QtCore.Qt.DashLine),
            )
            self.plot_widget.addItem(line)
            self.onset_markers.append(line)

    def add_threshold_lines(self, detection_threshold: float, backtrack_threshold: float):
        """Add horizontal threshold lines.

        Args:
            detection_threshold: Main detection threshold value
            backtrack_threshold: Lower backtrack threshold value
        """
        det_line = pg.InfiniteLine(
            pos=detection_threshold,
            angle=0,
            pen=pg.mkPen(color=(255, 165, 0), width=1.5, style=QtCore.Qt.SolidLine),
        )
        self.plot_widget.addItem(det_line)
        self.threshold_lines.append(det_line)

        bt_line = pg.InfiniteLine(
            pos=backtrack_threshold,
            angle=0,
            pen=pg.mkPen(color=(255, 255, 0), width=1, style=QtCore.Qt.DashLine),
        )
        self.plot_widget.addItem(bt_line)
        self.threshold_lines.append(bt_line)

    def clear_markers(self):
        """Remove all onset markers and threshold lines."""
        for line in self.onset_markers:
            self.plot_widget.removeItem(line)
        self.onset_markers.clear()

        for line in self.threshold_lines:
            self.plot_widget.removeItem(line)
        self.threshold_lines.clear()
