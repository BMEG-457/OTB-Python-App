"""Track manager for data analysis mode."""

from PyQt5 import QtWidgets
from app.core.analysis_track import AnalysisTrack


class AnalysisTrackManager:
    """Manages a single track for data analysis mode."""

    def __init__(self, scroll_layout):
        self.scroll_layout = scroll_layout

        # Single track
        self.track = None
        self.track_container = None

        # CSV data reference
        self.csv_loader = None

        # Current view settings
        self.view_start = 0.0
        self.view_duration = 1.0

    def initialize_tracks_from_csv(self, csv_loader):
        """Create a single track from loaded CSV data.

        Args:
            csv_loader: CSVDataLoader instance with loaded data
        """
        self.csv_loader = csv_loader
        self._clear_tracks()

        num_channels = min(64, csv_loader.get_channel_count())
        timestamps = csv_loader.timestamps
        raw_data = csv_loader.data[:num_channels, :]
        sample_rate = csv_loader.sample_rate

        # Create single track
        self.track = AnalysisTrack(
            "EMG Data",
            num_channels,
            timestamps,
            raw_data,
            sample_rate
        )

        # Add track to the scroll layout
        self.track_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.track_container)
        layout.setContentsMargins(0, 0, 0, 5)

        self.track.plot_widget.setMinimumHeight(400)
        layout.addWidget(self.track.plot_widget)

        self.scroll_layout.addWidget(self.track_container)
        self.scroll_layout.addStretch()

        # Apply initial view (full duration)
        duration = csv_loader.get_duration()
        self.set_view_window(0, duration)

    def _clear_tracks(self):
        """Clear existing track and container."""
        if self.track_container:
            self.track_container.setParent(None)
            self.track_container.deleteLater()

        self.track_container = None
        self.track = None

        # Clear stretch items from layout
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_view_window(self, start_time: float, duration: float):
        """Update view window for the track.

        Args:
            start_time: Start time in seconds
            duration: Window duration in seconds
        """
        self.view_start = start_time
        self.view_duration = duration

        if self.track:
            self.track.set_view_window(start_time, duration)

    def draw_all_tracks(self):
        """Draw the track with current view settings."""
        if self.track:
            self.track.draw()

    def get_channel_count(self):
        """Get number of channels available."""
        if self.track:
            return self.track.num_channels
        return 0

    def get_total_duration(self):
        """Get total duration of loaded data."""
        if self.csv_loader:
            return self.csv_loader.get_duration()
        return 0.0

    def set_selected_channels(self, channels: list):
        """Set which channels to display (max 2).

        Args:
            channels: List of channel indices to display
        """
        if self.track:
            self.track.set_selected_channels(channels)

    def get_selected_channels(self) -> list:
        """Get list of currently selected channel indices."""
        if self.track:
            return self.track.get_selected_channels()
        return []

    def set_processing(self, rectify: bool, envelope_type: str,
                       rms_window: int = 50, lowpass_cutoff: float = 10):
        """Set processing options for the track.

        Args:
            rectify: Whether to apply full-wave rectification
            envelope_type: 'none', 'rms', or 'lowpass'
            rms_window: Window size in samples for RMS envelope
            lowpass_cutoff: Cutoff frequency in Hz for lowpass filter
        """
        if self.track:
            self.track.set_processing(rectify, envelope_type, rms_window, lowpass_cutoff)
