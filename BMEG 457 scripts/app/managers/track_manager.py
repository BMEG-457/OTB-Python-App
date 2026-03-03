"""Track manager for initializing and managing EMG tracks."""

from PyQt5 import QtWidgets
import numpy as np
from app.core.track import Track
from app.core.config import Config


def _make_group_preset(preset):
    """Return (groups, labels) for a given preset name.

    groups: list of lists of channel indices (0-indexed, column-major 8x8)
    labels: list of display strings, one per group

    Channel mapping: index = col * 8 + row  (col, row both 0-indexed)
    """
    if preset == '2x2_blocks':
        groups, labels = [], []
        for br in range(4):
            for bc in range(4):
                indices = [(2*bc + dc)*8 + (2*br + dr) for dc in range(2) for dr in range(2)]
                groups.append(indices)
                labels.append(f"B{br*4+bc+1} R{2*br+1}-{2*br+2}/C{2*bc+1}-{2*bc+2}")
        return groups, labels
    elif preset == 'rows':
        groups = [[r + c*8 for c in range(8)] for r in range(8)]
        labels = [f"Row {r+1}" for r in range(8)]
        return groups, labels
    elif preset == 'columns':
        groups = [[c*8 + r for r in range(8)] for c in range(8)]
        labels = [f"Column {c+1}" for c in range(8)]
        return groups, labels
    return [], []


class TrackManager:
    """Manages initialization and organization of EMG signal tracks."""

    def __init__(self, device, plot_time, scroll_layout, hdsemg_scroll_layout=None, feature_scroll_layout=None, accessory_scroll_layout=None, individual_channels_scroll_layout=None):
        self.device = device
        self.plot_time = plot_time
        self.scroll_layout = scroll_layout
        self.hdsemg_scroll_layout = hdsemg_scroll_layout
        self.feature_scroll_layout = feature_scroll_layout
        self.accessory_scroll_layout = accessory_scroll_layout
        self.individual_channels_scroll_layout = individual_channels_scroll_layout

        # Track storage
        self.tracks = []
        self.track_containers = []
        self.accessory_containers = []
        self.hdsemg_track = None
        self.hdsemg_track_container = None  # container for raw 64-ch track; hidden by default
        self.hd_channel_tracks = []
        self.hd_channel_containers = []
        self.hd_average_track = None
        self.hd_average_channels = []
        self.feature_track = None
        self.feature_containers = []
        self.feature_tracks = []

        # Group average preset state
        self.active_preset = '2x2_blocks'
        self.group_tracks = {}      # preset -> list of Track
        self.group_containers = {}  # preset -> list of QWidget
        self._group_channel_map = {}  # preset -> list of channel index lists

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

            track.plot_widget.setMinimumHeight(Config.TRACK_MIN_HEIGHT)
            layout.addWidget(track.plot_widget)

            is_accessory = "HDsEMG" not in title
            if is_accessory and self.accessory_scroll_layout is not None:
                self.accessory_scroll_layout.addWidget(track_container)
                self.accessory_containers.append((title, track_container))
            elif "HDsEMG" in title and self.individual_channels_scroll_layout is not None:
                # Raw 64-ch track lives in the dedicated Channels tab
                self.individual_channels_scroll_layout.addWidget(track_container)
            else:
                self.scroll_layout.addWidget(track_container)
                self.track_containers.append((title, track_container))

            # Store reference to HDsEMG main track
            if "HDsEMG" in title:
                self.hdsemg_track = track
                self.hdsemg_track_container = track_container
                if self.individual_channels_scroll_layout is None:
                    # No dedicated tab — hide until 'all' preset is selected
                    track_container.hide()
                self.hd_average_channels = list(range(n))
                # Only create the average track widget if an HDsEMG tab layout is provided
                if self.hdsemg_scroll_layout is not None:
                    self.hd_average_track = Track("HD Average", self.device.frequency, 1, 0, conv, self.plot_time)
                    self.hd_average_track.plot_widget.setMinimumHeight(Config.TRACK_MIN_HEIGHT)
                    hd_avg_container = QtWidgets.QWidget()
                    hd_avg_layout = QtWidgets.QVBoxLayout(hd_avg_container)
                    hd_avg_layout.addWidget(self.hd_average_track.plot_widget)
                    self.hdsemg_scroll_layout.addWidget(hd_avg_container)

            if "Features" in title.lower() and self.feature_scroll_layout is not None:
                self.feature_scroll_layout.addWidget(track_container)
                self.feature_track = Track("Feature", self.device.frequency, 1, 0, conv, self.plot_time)
                self.feature_track.plot_widget.setMinimumHeight(Config.TRACK_MIN_HEIGHT)
                feature_container = QtWidgets.QWidget()
                feature_layout = QtWidgets.QVBoxLayout(feature_container)
                feature_layout.addWidget(self.feature_track.plot_widget)
                self.feature_scroll_layout.addWidget(feature_container)

        # Build group average tracks for all presets before adding stretch
        if self.hdsemg_track is not None:
            self._init_group_tracks()

        self.scroll_layout.addStretch()
        if self.hdsemg_scroll_layout is not None:
            self.hdsemg_scroll_layout.addStretch()
        if self.accessory_scroll_layout is not None:
            self.accessory_scroll_layout.addStretch()
        if self.individual_channels_scroll_layout is not None:
            self.individual_channels_scroll_layout.addStretch()

    def _init_group_tracks(self):
        """Create Track objects for all group presets and add to scroll_layout.

        Only the active_preset's containers are visible; others are hidden.
        """
        conv = self.hdsemg_track.conv_fact
        for preset in ('2x2_blocks', 'rows', 'columns'):
            groups, labels = _make_group_preset(preset)
            tracks, containers = [], []
            for label in labels:
                track = Track(label, self.device.frequency, 1, 0, conv, self.plot_time)
                track.plot_widget.setMinimumHeight(Config.GROUP_TRACK_MIN_HEIGHT)
                container = QtWidgets.QWidget()
                QtWidgets.QVBoxLayout(container).addWidget(track.plot_widget)
                self.scroll_layout.addWidget(container)
                container.setVisible(preset == self.active_preset)
                tracks.append(track)
                containers.append(container)
            self.group_tracks[preset] = tracks
            self.group_containers[preset] = containers
            self._group_channel_map[preset] = groups

    def update_group_averages(self):
        """Compute and draw group average traces for the active preset.

        Called each frame from update_plot(). No-op when preset is 'all'.
        """
        if self.active_preset == 'all' or self.hdsemg_track is None:
            return
        if self.active_preset not in self.group_tracks:
            return
        buf = self.hdsemg_track.buffer
        tracks = self.group_tracks[self.active_preset]
        groups = self._group_channel_map[self.active_preset]
        for track, indices in zip(tracks, groups):
            valid = [i for i in indices if i < buf.shape[0]]
            if not valid:
                continue
            avg = np.mean(buf[valid, :], axis=0)
            track.buffer[0, :] = avg
            track.buffer_index = self.hdsemg_track.buffer_index
            track.time_array = self.hdsemg_track.time_array
            track.draw()

    def set_group_preset(self, preset):
        """Switch the active group preset, showing the appropriate track containers."""
        for c in self.group_containers.get(self.active_preset, []):
            c.hide()
        self.active_preset = preset
        for c in self.group_containers.get(preset, []):
            c.show()

    def change_plot_time(self, new_time):
        """Change plot time window for all tracks."""
        for track in self.tracks:
            new_buf = np.zeros((track.num_channels, int(new_time * track.frequency)))
            copy = min(new_buf.shape[1], track.buffer.shape[1])
            new_buf[:, -copy:] = track.buffer[:, -copy:]
            track.plot_time = new_time
            track.buffer = new_buf
            track.buffer_index = min(track.buffer_index, new_buf.shape[1])
            track.time_array = np.linspace(0, new_time, new_buf.shape[1])
            track.plot_widget.setXRange(0, new_time)

        # Resize per-channel HDsEMG tracks if present
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

        # Resize all group average tracks
        for track_list in self.group_tracks.values():
            for track in track_list:
                new_buf = np.zeros((1, int(new_time * track.frequency)))
                copy = min(new_buf.shape[1], track.buffer.shape[1])
                new_buf[:, -copy:] = track.buffer[:, -copy:]
                track.plot_time = new_time
                track.buffer = new_buf
                track.buffer_index = min(track.buffer_index, new_buf.shape[1])
                track.time_array = np.linspace(0, new_time, new_buf.shape[1])
                track.plot_widget.setXRange(0, new_time)

    def update_hd_average(self):
        """Update the HD average track with mean of selected channels."""
        if self.hd_average_track is None or not self.hd_average_channels or self.hdsemg_track is None:
            return

        try:
            buf = self.hdsemg_track.buffer
            sel = [i for i in self.hd_average_channels if 0 <= i < buf.shape[0]]
            if sel:
                avg = np.mean(buf[sel, :], axis=0)
                if self.hd_average_track.buffer.shape[1] == avg.shape[0]:
                    self.hd_average_track.buffer[0, :] = avg
                else:
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

    def _all_containers(self):
        """Get all track containers (main + accessory)."""
        return self.track_containers + self.accessory_containers

    def get_track_titles(self):
        """Get list of all track titles."""
        return [title for title, _ in self._all_containers()]

    def set_track_visibility(self, selected_titles):
        """Set which tracks are visible."""
        for title, widget in self._all_containers():
            widget.setVisible(title in selected_titles)

    def get_visible_track_titles(self):
        """Get list of currently visible track titles."""
        return [title for title, widget in self._all_containers() if widget.isVisible()]
