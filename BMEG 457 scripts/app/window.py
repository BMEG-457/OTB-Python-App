from PyQt5 import QtWidgets, QtCore
import numpy as np

from app.config import Config
from app.track import Track
from app.data_receiver import DataReceiverThread


class ChannelSelectorDialog(QtWidgets.QDialog):
    def __init__(self, parent, num_channels, selected=None):
        super().__init__(parent)
        self.setWindowTitle("Select Channels")
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)

        grid = QtWidgets.QGridLayout()
        self.checkboxes = []
        cols = 8
        for i in range(num_channels):
            cb = QtWidgets.QCheckBox(f"{i+1}")
            cb.setChecked(True if selected is None else (i in selected))
            self.checkboxes.append(cb)
            row = i // cols
            col = i % cols
            grid.addWidget(cb, row, col)

        layout.addLayout(grid)

        btn_layout = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("All")
        select_none = QtWidgets.QPushButton("None")
        btn_layout.addWidget(select_all)
        btn_layout.addWidget(select_none)
        btn_layout.addStretch()

        ok = QtWidgets.QPushButton("OK")
        cancel = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(ok)
        btn_layout.addWidget(cancel)

        layout.addLayout(btn_layout)

        select_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self.checkboxes])
        select_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self.checkboxes])
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def selected_indices(self):
        return [i for i, cb in enumerate(self.checkboxes) if cb.isChecked()]


class TrackVisibilityDialog(QtWidgets.QDialog):
    def __init__(self, parent, track_titles, selected=None):
        super().__init__(parent)
        self.setWindowTitle("Select Tracks")
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)

        self.checkboxes = []
        for title in track_titles:
            cb = QtWidgets.QCheckBox(title)
            cb.setChecked(True if selected is None else (title in selected))
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        btn_layout = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("All")
        select_none = QtWidgets.QPushButton("None")
        btn_layout.addWidget(select_all)
        btn_layout.addWidget(select_none)
        btn_layout.addStretch()

        ok = QtWidgets.QPushButton("OK")
        cancel = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(ok)
        btn_layout.addWidget(cancel)

        layout.addLayout(btn_layout)

        select_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self.checkboxes])
        select_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self.checkboxes])
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def selected_titles(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

# window for plots
class SoundtrackWindow(QtWidgets.QWidget):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.client_socket = None
        self.tracks = []
        self.plot_time = Config.DEFAULT_PLOT_TIME
        self.is_paused = False

        self.setWindowTitle("Sessantaquattro+ Viewer")
        self.setGeometry(100, 100, *Config.WINDOW_SIZE)

        self.main_layout = QtWidgets.QVBoxLayout(self)

        # -------- Menu Bar --------
        menu = QtWidgets.QWidget()
        menu_layout = QtWidgets.QHBoxLayout(menu)

        self.time_selector = QtWidgets.QComboBox()
        self.time_selector.addItems(["100ms", "250ms", "500ms", "1s", "5s", "10s"])
        self.time_selector.setCurrentText("1s")
        self.time_selector.currentTextChanged.connect(self.change_plot_time)

        menu_layout.addWidget(QtWidgets.QLabel("Plot Time:"))
        menu_layout.addWidget(self.time_selector)

        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.toggle_pause)
        menu_layout.addWidget(self.pause_button)

        self.status_label = QtWidgets.QLabel("Ready")
        menu_layout.addWidget(self.status_label)
        menu_layout.addStretch()

        self.main_layout.addWidget(menu)

        # Content area: left = plots (scroll area), right = controls
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content)

        # -------- Scroll Area for Tracks (plots) --------
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)

        self.scroll_area.setWidget(self.scroll_widget)
        content_layout.addWidget(self.scroll_area, stretch=3)

        # -------- Right-side control panel --------
        self.control_panel = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(self.control_panel)

        self.start_button = QtWidgets.QPushButton("Start Recording")
        self.stop_button = QtWidgets.QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        self.select_tracks_button = QtWidgets.QPushButton("Select Tracks")

        ctrl_layout.addWidget(self.start_button)
        ctrl_layout.addWidget(self.stop_button)
        ctrl_layout.addWidget(self.select_channels_button)
        ctrl_layout.addWidget(self.select_tracks_button)
        ctrl_layout.addStretch()

        # Add control panel to the content area
        content_layout.addWidget(self.control_panel, stretch=0)

        # Add the content area to the main layout
        self.main_layout.addWidget(content)

        self.init_tracks()

        # wire the select channels button to the main HDsEMG track (first track)
        self.select_channels_button.clicked.connect(self.open_channel_selector)
        # wire the select tracks button to toggle visibility of whole tracks
        self.select_tracks_button.clicked.connect(self.open_track_selector)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(Config.UPDATE_RATE)
        self.receiver_thread = None
        #self.receiver_thread = DataReceiverThread(self.device, self.client_socket, self.tracks)

        ''' Processor stages here
        self.receiver_thread.processor.add_stage(lambda d: d * 0.001)
        self.receiver_thread.processor.add_stage(filters.butter_bandpass_lowpass)
        self.receiver_thread.processor.add_stage(features.rms)
        self.receiver_thread.processor.add_stage(transforms.fft_transform)
        '''

        #self.receiver_thread.status_update.connect(self.update_status)
        #self.receiver_thread.start()

    def init_tracks(self):
        if self.device.nchannels == 72:
            track_info = [
                ("HDsEMG 64 channels", 64, 0, 0.001, 0.000000286),
                ("AUX 1", 1, 64, 1, 0.00014648),
                ("AUX 2", 1, 65, 1, 0.00014648),
                ("Quaternions", 4, 66, 1, 1),
                ("Buffer", 1, 70, 1, 1),
                ("Ramp", 1, 71, 1, 1),
            ]
        else:
            main = self.device.nchannels - 8
            track_info = [
                (f"HDsEMG {main} channels", main, 0, 0.001, 0.000000286),
                ("AUX 1", 1, main, 1, 0.00014648),
                ("AUX 2", 1, main + 1, 1, 0.00014648),
            ]

        # store containers so we can show/hide whole tracks later
        self.track_containers = []
        for title, n, idx, offset, conv in track_info:
            track_container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(track_container)

            track = Track(title, self.device.frequency, n, offset, conv, self.plot_time)
            self.tracks.append(track)

            track.plot_widget.setMinimumHeight(300)
            layout.addWidget(track.plot_widget)
            self.scroll_layout.addWidget(track_container)
            self.track_containers.append((title, track_container))

        self.scroll_layout.addStretch()

    def change_plot_time(self, text):
        if text.endswith("ms"):
            new_time = float(text[:-2]) / 1000
        else:
            new_time = float(text[:-1])

        for track in self.tracks:
            new_buf = np.zeros((track.num_channels, int(new_time * track.frequency)))

            copy = min(new_buf.shape[1], track.buffer.shape[1])
            new_buf[:, -copy:] = track.buffer[:, -copy:]

            track.plot_time = new_time
            track.buffer = new_buf
            track.buffer_index = min(track.buffer_index, new_buf.shape[1])
            track.time_array = np.linspace(0, new_time, new_buf.shape[1])
            track.plot_widget.setXRange(0, new_time)

    def toggle_pause(self, checked):
        self.is_paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        if checked:
            self.timer.stop()
        else:
            self.timer.start(Config.UPDATE_RATE)

    def update_status(self, msg):
        self.status_label.setText(msg)

    def update_plot(self):
        if not self.is_paused:
            for track in self.tracks:
                track.draw()

    def closeEvent(self, event):
        if self.receiver_thread is not None:
            try:
                self.receiver_thread.stop()
                self.receiver_thread.wait()
            except Exception:
                pass
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception:
                pass
        event.accept()

    def start_recording(self):
        print("Recording started")
        self.is_paused = False
        self.timer.start()
        self.receiver_thread.running = True

    def stop_recording(self):
        print("Recording stopped")
        self.is_paused = True
        self.timer.stop()
        self.receiver_thread.running = False

    def set_client_socket(self, socket):
        self.client_socket = socket

    def initialize_receiver(self):
        self.receiver_thread = DataReceiverThread(
            self.device,
            self.client_socket,
            self.tracks
        )
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.start()

    def open_channel_selector(self):
        # target the main HDsEMG track (assumed to be first)
        if not self.tracks:
            return
        track = self.tracks[0]
        num = track.num_channels
        current = getattr(track, 'visible_channels', list(range(num)))
        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            # apply selection to the track
            track.set_visible_channels(sel)

    def open_track_selector(self):
        # open dialog showing track titles to choose which whole tracks to show
        if not hasattr(self, 'track_containers') or not self.track_containers:
            return
        titles = [t for t, _ in self.track_containers]
        # current visible titles
        current = [t for t, w in self.track_containers if w.isVisible()]
        dlg = TrackVisibilityDialog(self, titles, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_titles()
            # show/hide containers based on selection
            for title, widget in self.track_containers:
                widget.setVisible(title in sel)


