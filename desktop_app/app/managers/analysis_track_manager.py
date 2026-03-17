"""Track manager for data analysis mode."""

import numpy as np
import pyqtgraph as pg
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

        # Feature tracks
        self.feature_tracks = []
        self.feature_containers = []

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
        self.remove_feature_tracks()

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

        for ft in self.feature_tracks:
            ft.set_view_window(start_time, duration)

    def draw_all_tracks(self):
        """Draw all tracks with current view settings."""
        if self.track:
            self.track.draw()
        for ft in self.feature_tracks:
            ft.draw()

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

    def set_processing(self, bandpass: bool, notch: bool, rectify: bool,
                       envelope_type: str, rms_window: int = 50,
                       lowpass_cutoff: float = 10):
        """Set processing options for the track.

        Args:
            bandpass: Apply bandpass filter
            notch: Apply notch filter
            rectify: Whether to apply full-wave rectification
            envelope_type: 'none', 'rms', or 'lowpass'
            rms_window: Window size in samples for RMS envelope
            lowpass_cutoff: Cutoff frequency in Hz for lowpass filter
        """
        if self.track:
            self.track.set_processing(bandpass, notch, rectify, envelope_type, rms_window, lowpass_cutoff)

    def add_feature_track(self, title: str, timestamps: np.ndarray,
                          data_1d: np.ndarray, sample_rate: float,
                          onset_times: np.ndarray = None,
                          detection_threshold: float = None,
                          backtrack_threshold: float = None) -> AnalysisTrack:
        """Add a new feature track to the scroll layout.

        Args:
            title: Track title
            timestamps: Timestamp array for the feature data
            data_1d: 1D array of feature values
            sample_rate: Sample rate of the feature data
            onset_times: Optional onset times for vertical markers
            detection_threshold: Optional detection threshold for horizontal line
            backtrack_threshold: Optional backtrack threshold for horizontal line

        Returns:
            The created AnalysisTrack instance
        """
        data_2d = data_1d.reshape(1, -1)

        feature_track = AnalysisTrack(
            title=title,
            num_channels=1,
            timestamps=timestamps,
            data=data_2d,
            sample_rate=sample_rate,
        )

        # Auto-select the single channel and set green curve color
        feature_track.set_selected_channels([0])
        feature_track.curves[0].setPen(pg.mkPen(color=(0, 200, 100), width=2))

        # Add onset markers if provided
        if onset_times is not None and len(onset_times) > 0:
            base_time = timestamps[0]
            feature_track.add_onset_markers(onset_times, base_time)

        # Add threshold lines if provided
        if detection_threshold is not None and backtrack_threshold is not None:
            feature_track.add_threshold_lines(detection_threshold, backtrack_threshold)

        # Apply current view window
        feature_track.set_view_window(self.view_start, self.view_duration)

        # Create container widget
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 5)
        feature_track.plot_widget.setMinimumHeight(300)
        layout.addWidget(feature_track.plot_widget)

        # Insert before trailing stretch
        self._remove_trailing_stretch()
        self.scroll_layout.addWidget(container)
        self.scroll_layout.addStretch()

        self.feature_tracks.append(feature_track)
        self.feature_containers.append(container)

        feature_track.draw()
        return feature_track

    def remove_feature_tracks(self):
        """Remove all feature tracks."""
        for container in self.feature_containers:
            container.setParent(None)
            container.deleteLater()
        self.feature_tracks.clear()
        self.feature_containers.clear()

    def _remove_trailing_stretch(self):
        """Remove the trailing stretch item from the scroll layout."""
        count = self.scroll_layout.count()
        if count > 0:
            last_item = self.scroll_layout.itemAt(count - 1)
            if last_item and last_item.widget() is None:
                self.scroll_layout.removeItem(last_item)
