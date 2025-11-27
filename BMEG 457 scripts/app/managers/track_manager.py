"""Track manager for initializing and managing EMG tracks."""

from PyQt5 import QtWidgets
import numpy as np
from app.core.track import Track


class TrackManager:
    """Manages initialization and organization of EMG signal tracks."""
    
    def __init__(self, device, plot_time, scroll_layout, hdsemg_scroll_layout, feature_scroll_layout):
        self.device = device
        self.plot_time = plot_time
        self.scroll_layout = scroll_layout
        self.hdsemg_scroll_layout = hdsemg_scroll_layout
        self.feature_scroll_layout = feature_scroll_layout
        
        # Track storage
        self.tracks = []
        self.track_containers = []
        self.hdsemg_track = None
        self.hd_channel_tracks = []
        self.hd_channel_containers = []
        self.hd_average_track = None
        self.hd_average_channels = []
        self.feature_track = None
        self.feature_containers = []
        self.feature_tracks = []
        
        self._initialize_tracks()
    
    def _initialize_tracks(self):
        """Initialize all tracks based on device configuration."""
        if self.device.nchannels == 72:
            track_info = [
                ("HDsEMG 64 channels", 64, 0, 0.001, 0.000000286),
                ("AUX 1", 1, 64, 1, 0.00014648),
                ("AUX 2", 1, 65, 1, 0.00014648),
                ("Quaternions", 4, 66, 1, 1),
                ("Buffer", 1, 70, 1, 1),
                ("Ramp", 1, 71, 1, 1),
            ]
        elif self.device.nchannels == 40:  # 64 bio channels in MODE=1
            track_info = [
                ('HDsEMG 32 channels', 32, 0, 0.001, 0.000000286),
                ('AUX 1', 1, 32, 1, 0.00014648),
                ('AUX 2', 1, 33, 1, 0.00014648),
                ('Quaternions', 4, 34, 1, 1),
                ('Buffer', 1, 38, 1, 1),
                ('Ramp', 1, 39, 1, 1),
            ]
        else:
            # Calculate main channels (total - 8 accessory channels)
            main = max(4, self.device.nchannels - 8)
            track_info = [
                (f"HDsEMG {main} channels", main, 0, 0.001, 0.000000286),
                ("AUX 1", 1, main, 1, 0.00014648),
                ("AUX 2", 1, main + 1, 1, 0.00014648),
            ]
            # Only add other channels if we have enough total channels
            if self.device.nchannels >= main + 8:
                track_info.extend([
                    ('Quaternions', 4, main + 2, 1, 1),
                    ('Buffer', 1, main + 6, 1, 1),
                    ('Ramp', 1, main + 7, 1, 1),
                ])
        
        for title, n, idx, offset, conv in track_info:
            track_container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(track_container)

            track = Track(title, self.device.frequency, n, offset, conv, self.plot_time)
            self.tracks.append(track)

            track.plot_widget.setMinimumHeight(300)
            layout.addWidget(track.plot_widget)
            self.scroll_layout.addWidget(track_container)
            self.track_containers.append((title, track_container))

            # Store reference to HDsEMG main track and create per-channel tracks
            if "HDsEMG" in title:
                self.hdsemg_track = track
                # create averaged-track container (shows the mean across selected channels)
                self.hd_average_channels = list(range(n))
                self.hd_average_track = Track("HD Average", self.device.frequency, 1, 0, conv, self.plot_time)
                self.hd_average_track.plot_widget.setMinimumHeight(300)
                hd_avg_container = QtWidgets.QWidget()
                hd_avg_layout = QtWidgets.QVBoxLayout(hd_avg_container)
                hd_avg_layout.addWidget(self.hd_average_track.plot_widget)
                # add average plot (only) to HDsEMG tab
                self.hdsemg_scroll_layout.addWidget(hd_avg_container)

            if "Features" in title.lower():
                # add to features tab instead
                self.feature_scroll_layout.addWidget(track_container)
                self.feature_track = Track("Feature", self.device.frequency, 1, 0, conv, self.plot_time)
                self.feature_track.plot_widget.setMinimumHeight(300)
                feature_container = QtWidgets.QWidget()
                feature_layout = QtWidgets.QVBoxLayout(feature_container)
                feature_layout.addWidget(self.feature_track.plot_widget)
                self.feature_scroll_layout.addWidget(feature_container)
        
        self.scroll_layout.addStretch()
        self.hdsemg_scroll_layout.addStretch()
    
    def change_plot_time(self, new_time):
        """Change plot time window for all tracks.
        
        Args:
            new_time: New time window in seconds
        """
        for track in self.tracks:
            new_buf = np.zeros((track.num_channels, int(new_time * track.frequency)))

            copy = min(new_buf.shape[1], track.buffer.shape[1])
            new_buf[:, -copy:] = track.buffer[:, -copy:]

            track.plot_time = new_time
            track.buffer = new_buf
            track.buffer_index = min(track.buffer_index, new_buf.shape[1])
            track.time_array = np.linspace(0, new_time, new_buf.shape[1])
            track.plot_widget.setXRange(0, new_time)

        # also resize per-channel HDsEMG tracks if present
        if self.hd_channel_tracks:
            for ch_track in self.hd_channel_tracks:
                new_buf = np.zeros((ch_track.num_channels, int(new_time * ch_track.frequency)))
                copy = min(new_buf.shape[1], ch_track.buffer.shape[1])
                new_buf[:, -copy:] = ch_track.buffer[:, -copy:]
                ch_track.plot_time = new_time
                ch_track.buffer = new_buf
                ch_track.buffer_index = min(ch_track.buffer_index, new_buf.shape[1])
                ch_track.time_array = np.linspace(0, new_time, new_buf.shape[1])
                ch_track.plot_widget.setXRange(0, new_time)
    
    def update_hd_average(self):
        """Update the HD average track with mean of selected channels."""
        if self.hd_average_track is None or not self.hd_average_channels or self.hdsemg_track is None:
            return
        
        try:
            buf = self.hdsemg_track.buffer
            # guard indices
            sel = [i for i in self.hd_average_channels if 0 <= i < buf.shape[0]]
            if sel:
                avg = np.mean(buf[sel, :], axis=0)
                # copy into average track buffer
                if self.hd_average_track.buffer.shape[1] == avg.shape[0]:
                    self.hd_average_track.buffer[0, :] = avg
                else:
                    # resize if needed (shouldn't normally happen)
                    new_buf = np.zeros((1, avg.shape[0]))
                    new_buf[0, -avg.shape[0]:] = avg
                    self.hd_average_track.buffer = new_buf
                self.hd_average_track.buffer_index = self.hdsemg_track.buffer_index
                self.hd_average_track.time_array = self.hdsemg_track.time_array
            self.hd_average_track.draw()
        except Exception:
            pass
    
    def update_hd_channel_tracks(self):
        """Update per-channel HD tracks from main HDsEMG buffer."""
        if not self.hd_channel_tracks or self.hdsemg_track is None:
            return
        
        for idx, ch_track in enumerate(self.hd_channel_tracks):
            try:
                # copy the corresponding row from main HDsEMG buffer into the 1-channel track
                if idx < self.hdsemg_track.buffer.shape[0]:
                    ch_track.buffer[0, :] = self.hdsemg_track.buffer[idx, :]
                    ch_track.buffer_index = self.hdsemg_track.buffer_index
                    ch_track.time_array = self.hdsemg_track.time_array
            except Exception:
                pass
            ch_track.draw()
    
    def draw_all_tracks(self):
        """Draw all tracks."""
        for track in self.tracks:
            track.draw()
    
    def get_track_titles(self):
        """Get list of all track titles."""
        return [title for title, _ in self.track_containers]
    
    def set_track_visibility(self, selected_titles):
        """Set which tracks are visible.
        
        Args:
            selected_titles: List of track titles to show
        """
        for title, widget in self.track_containers:
            widget.setVisible(title in selected_titles)
    
    def get_visible_track_titles(self):
        """Get list of currently visible track titles."""
        return [title for title, widget in self.track_containers if widget.isVisible()]
