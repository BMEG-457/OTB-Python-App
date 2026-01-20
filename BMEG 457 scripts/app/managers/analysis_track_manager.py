"""Track manager for data analysis mode."""

from PyQt5 import QtWidgets
import numpy as np
from app.core.analysis_track import AnalysisTrack


class AnalysisTrackManager:
    """Manages tracks for data analysis mode - creates HDsEMG track from CSV data."""

    def __init__(self, scroll_layout):
        self.scroll_layout = scroll_layout

        # Track storage - only HDsEMG track
        self.hdsemg_track = None
        self.track_container = None

        # CSV data reference
        self.csv_loader = None

        # Current view settings
        self.view_start = 0.0
        self.view_duration = 1.0

    def initialize_tracks_from_csv(self, csv_loader):
        """Create HDsEMG track from loaded CSV data.

        Args:
            csv_loader: CSVDataLoader instance with loaded data
        """
        self.csv_loader = csv_loader
        self._clear_tracks()

        num_channels = csv_loader.get_channel_count()
        timestamps = csv_loader.timestamps
        data = csv_loader.data

        # Use first 64 channels (or all if fewer)
        hdsemg_channels = min(64, num_channels)
        track_data = data[:hdsemg_channels, :]

        # Create track container
        self.track_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.track_container)

        # Create HDsEMG track - plots raw values, no offset
        self.hdsemg_track = AnalysisTrack(
            f"HDsEMG {hdsemg_channels} channels",
            hdsemg_channels,
            timestamps,
            track_data
        )

        self.hdsemg_track.plot_widget.setMinimumHeight(400)
        layout.addWidget(self.hdsemg_track.plot_widget)
        self.scroll_layout.addWidget(self.track_container)

        self.scroll_layout.addStretch()

        # Apply initial view
        self.set_view_window(self.view_start, self.view_duration)

    def _clear_tracks(self):
        """Clear existing track and container."""
        if self.track_container is not None:
            self.track_container.setParent(None)
            self.track_container.deleteLater()

        self.hdsemg_track = None
        self.track_container = None

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

        if self.hdsemg_track:
            self.hdsemg_track.set_view_window(start_time, duration)

    def draw_all_tracks(self):
        """Draw the track with current view settings."""
        if self.hdsemg_track:
            self.hdsemg_track.draw()

    def get_hdsemg_channel_count(self):
        """Get number of channels in HDsEMG track."""
        if self.hdsemg_track:
            return self.hdsemg_track.num_channels
        return 0

    def get_total_duration(self):
        """Get total duration of loaded data."""
        if self.csv_loader:
            return self.csv_loader.get_duration()
        return 0.0

    def set_visible_channels(self, channels):
        """Set which channels are visible on the HDsEMG track.

        Args:
            channels: List of channel indices to show
        """
        if self.hdsemg_track:
            self.hdsemg_track.set_visible_channels(channels)

    def get_visible_channels(self):
        """Get list of currently visible channel indices."""
        if self.hdsemg_track:
            return self.hdsemg_track.get_visible_channels()
        return []
