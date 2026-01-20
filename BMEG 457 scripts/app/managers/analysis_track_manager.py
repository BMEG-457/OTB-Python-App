"""Track manager for data analysis mode."""

from PyQt5 import QtWidgets
from app.core.analysis_track import AnalysisTrack


class AnalysisTrackManager:
    """Manages track for data analysis mode - creates track from CSV data."""

    def __init__(self, scroll_layout):
        self.scroll_layout = scroll_layout

        # Track storage - single track for HDsEMG
        self.track = None
        self.track_container = None

        # CSV data reference
        self.csv_loader = None

        # Current view settings
        self.view_start = 0.0
        self.view_duration = 1.0

    def initialize_tracks_from_csv(self, csv_loader):
        """Create track from loaded CSV data with multi-resolution support.

        Args:
            csv_loader: CSVDataLoader instance with loaded and preprocessed data
        """
        self.csv_loader = csv_loader
        self._clear_tracks()

        num_channels = min(64, csv_loader.get_channel_count())

        # Get resolution data from loader
        resolution_data = csv_loader.resolution_data

        # Create track container
        self.track_container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.track_container)

        # Create track with multi-resolution data
        self.track = AnalysisTrack(
            f"HDsEMG {num_channels} channels",
            num_channels,
            resolution_data
        )

        self.track.plot_widget.setMinimumHeight(500)
        layout.addWidget(self.track.plot_widget)
        self.scroll_layout.addWidget(self.track_container)

        self.scroll_layout.addStretch()

        # Apply initial view (full duration)
        duration = csv_loader.get_duration()
        self.set_view_window(0, duration)

    def _clear_tracks(self):
        """Clear existing track and container."""
        if self.track_container is not None:
            self.track_container.setParent(None)
            self.track_container.deleteLater()

        self.track = None
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

        if self.track:
            self.track.set_view_window(start_time, duration)

    def draw_all_tracks(self):
        """Draw the track with current view settings."""
        if self.track:
            self.track.draw()

    def set_resolution(self, level: str):
        """Set resolution level for display.

        Args:
            level: Resolution level name ('Raw', 'L1', 'L2', 'L3')
        """
        if self.track:
            self.track.set_resolution(level)

    def get_current_resolution(self) -> str:
        """Get current resolution level."""
        if self.track:
            return self.track.get_current_resolution()
        return 'L2'

    def get_available_resolutions(self) -> list:
        """Get list of available resolution levels."""
        if self.csv_loader:
            return self.csv_loader.get_available_resolutions()
        return []

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
