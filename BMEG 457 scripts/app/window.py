from PyQt5 import QtWidgets, QtCore
import numpy as np

from app.config import Config
from app.track import Track
from app.data_receiver import DataReceiverThread
from app.processing import filters, features, transforms
from app.processing.pipeline import get_pipeline


class CalibrationDialog(QtWidgets.QDialog):
    """Modal dialog that collects RMS data during a timed calibration window."""
    calibration_complete = QtCore.pyqtSignal(float, float)  # emits (baseline_rms, threshold)
    
    def __init__(self, parent, receiver_thread, calibration_duration=3):
        super().__init__(parent)
        self.setWindowTitle("EMG Calibration")
        self.setModal(True)
        self.setGeometry(200, 200, 400, 200)
        
        self.receiver_thread = receiver_thread
        self.calibration_duration = calibration_duration
        self.rms_values = []
        self.remaining_time = calibration_duration
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Instructions
        instruction_label = QtWidgets.QLabel("Contract your muscle during countdown")
        instruction_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(instruction_label)
        
        # Countdown timer display
        self.timer_label = QtWidgets.QLabel(f"{self.calibration_duration}s")
        self.timer_label.setStyleSheet("font-size: 32px; text-align: center; color: red;")
        self.timer_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.timer_label)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Ready. Click Start to begin.")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Start")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # Connect buttons
        self.start_button.clicked.connect(self.start_calibration)
        self.cancel_button.clicked.connect(self.reject)
        
        # Countdown timer
        self.countdown_timer = QtCore.QTimer()
        self.countdown_timer.timeout.connect(self.tick_countdown)
        
        # Connection to receiver for RMS collection
        self.subscription_connected = False

    def start_calibration(self):
        """Start the calibration countdown and begin collecting RMS data."""
        self.rms_values = []
        self.remaining_time = self.calibration_duration
        self.start_button.setEnabled(False)
        self.status_label.setText("Collecting data...")
        
        # Connect to rectified signal to collect RMS during window
        if not self.subscription_connected and self.receiver_thread is not None:
            self.receiver_thread.stage_output.connect(self.on_stage_output)
            self.subscription_connected = True
        
        # Start countdown
        self.countdown_timer.start(1000)  # Update every 1 second
        self.tick_countdown()  # Immediate first tick
    
    def on_stage_output(self, stage_name, data):
        """Collect RMS from rectified signal."""
        if stage_name == 'rectified' and self.countdown_timer.isActive():
            # Compute RMS across all channels and samples
            rms_val = np.sqrt(np.mean(data**2))
            self.rms_values.append(rms_val)
    
    def tick_countdown(self):
        """Update countdown display and check if calibration is complete."""
        self.timer_label.setText(f"{self.remaining_time}s")
        self.remaining_time -= 1
        
        if self.remaining_time < 0:
            # Calibration complete
            self.countdown_timer.stop()
            self.compute_threshold_and_close()
    
    def compute_threshold_and_close(self):
        """Compute baseline RMS and threshold from collected data."""
        if not self.rms_values:
            QtWidgets.QMessageBox.warning(self, "Calibration Failed", 
                                         "No RMS data collected. Please try again.")
            self.start_button.setEnabled(True)
            self.status_label.setText("Ready. Click Start to begin.")
            return
        
        # Calculate baseline and threshold
        rms_array = np.array(self.rms_values)
        baseline_rms = np.mean(rms_array)
        baseline_std = np.std(rms_array)
        
        # Threshold = baseline_mean + 2*std (typical for contraction detection)
        threshold = baseline_rms + 2.0 * baseline_std
        
        self.status_label.setText(f"Calibration complete. Baseline: {baseline_rms:.4f}, Threshold: {threshold:.4f}")
        
        # Disconnect receiver signal
        if self.subscription_connected:
            self.receiver_thread.stage_output.disconnect(self.on_stage_output)
            self.subscription_connected = False
        
        # Emit calibration values and accept
        self.calibration_complete.emit(baseline_rms, threshold)
        self.accept()


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
        
        # Calibration state
        self.is_calibrated = False
        self.baseline_rms = None
        self.threshold = None

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

        # -------- Tabs for different views --------
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: All Tracks
        all_tracks_content = QtWidgets.QWidget()
        all_tracks_layout = QtWidgets.QHBoxLayout(all_tracks_content)

        # Scroll Area for all Tracks (plots)
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)

        self.scroll_area.setWidget(self.scroll_widget)
        all_tracks_layout.addWidget(self.scroll_area, stretch=3)

        # Right-side control panel
        self.control_panel = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(self.control_panel)

        self.calibrate_button = QtWidgets.QPushButton("Calibrate")
        self.start_button = QtWidgets.QPushButton("Start Recording")
        self.stop_button = QtWidgets.QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(False)  # Disabled until calibration
        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        self.select_tracks_button = QtWidgets.QPushButton("Select Tracks")

        ctrl_layout.addWidget(self.calibrate_button)
        ctrl_layout.addWidget(self.start_button)
        ctrl_layout.addWidget(self.stop_button)
        ctrl_layout.addWidget(self.select_channels_button)
        ctrl_layout.addWidget(self.select_tracks_button)
        ctrl_layout.addStretch()

        all_tracks_layout.addWidget(self.control_panel, stretch=0)
        self.tabs.addTab(all_tracks_content, "All Tracks")

        # Tab 2: HDsEMG Only
        hdsemg_content = QtWidgets.QWidget()
        hdsemg_layout = QtWidgets.QVBoxLayout(hdsemg_content)

        # Controls for HDsEMG tab (channel selector)
        hd_controls = QtWidgets.QWidget()
        hd_ctrl_layout = QtWidgets.QHBoxLayout(hd_controls)
        # button to select channels to include in the averaged plot
        self.hd_average_select_button = QtWidgets.QPushButton("Select Avg Channels")
        hd_ctrl_layout.addWidget(self.hd_average_select_button)
        hd_ctrl_layout.addStretch()
        hdsemg_layout.addWidget(hd_controls)

        self.hdsemg_scroll_area = QtWidgets.QScrollArea()
        self.hdsemg_scroll_area.setWidgetResizable(True)
        self.hdsemg_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.hdsemg_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.hdsemg_scroll_widget = QtWidgets.QWidget()
        self.hdsemg_scroll_layout = QtWidgets.QVBoxLayout(self.hdsemg_scroll_widget)

        self.hdsemg_scroll_area.setWidget(self.hdsemg_scroll_widget)
        hdsemg_layout.addWidget(self.hdsemg_scroll_area)
        self.tabs.addTab(hdsemg_content, "HDsEMG")

        # Tab 3: Features tab
        feature_content = QtWidgets.QWidget()
        feature_layout = QtWidgets.QVBoxLayout(feature_content)

        feature_controls = QtWidgets.QWidget()
        feature_ctrl_layout = QtWidgets.QHBoxLayout(feature_controls)
        self.feature_controls_button = QtWidgets.QPushButton("Feature Controls")
        feature_ctrl_layout.addWidget(self.feature_controls_button)
        feature_ctrl_layout.addStretch()
        feature_layout.addWidget(feature_controls)

        self.feature_scroll_area = QtWidgets.QScrollArea()
        self.feature_scroll_area.setWidgetResizable(True)
        self.feature_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.feature_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.feature_scroll_widget = QtWidgets.QWidget()
        self.feature_scroll_layout = QtWidgets.QVBoxLayout(self.feature_scroll_widget)

        self.feature_scroll_area.setWidget(self.feature_scroll_widget)
        feature_layout.addWidget(self.feature_scroll_area)
        self.tabs.addTab(feature_content, "Features") 
        
        
        self.main_layout.addWidget(self.tabs)

        self.init_tracks()

        

        

        # wire the calibrate button to open the calibration dialog
        self.calibrate_button.clicked.connect(self.open_calibration_dialog)
        # wire the select channels button to the main HDsEMG track (first track)
        self.select_channels_button.clicked.connect(self.open_channel_selector)
        # wire average channels selector
        self.hd_average_select_button.clicked.connect(self.open_hd_average_selector)
        # wire the select tracks button to toggle visibility of whole tracks
        self.select_tracks_button.clicked.connect(self.open_track_selector)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(Config.UPDATE_RATE)
        self.receiver_thread = None
        #self.receiver_thread = DataReceiverThread(self.device, self.client_socket, self.tracks)

        # Processor stages here (Option 3 - named pipelines)
        # Preconfigure named pipelines BEFORE creating/starting the receiver.
        # These pipelines are independent; you can add stages to e.g. 'filtered',
        # 'rectified', 'fft', and 'final' and DataReceiverThread will compute
        # each branch and emit intermediate outputs.
        get_pipeline('fft').add_stage(transforms.fft_transform)
        get_pipeline('filtered').add_stage(filters.butter_bandpass)
        get_pipeline('filtered').add_stage(filters.notch)
        get_pipeline('rectified').add_stage(filters.rectify)
        # features (e.g. rms) should be applied on the appropriate pipeline when
        # you want a reduced output; by default do not add `features.rms` to
        # 'final' because it changes array shape expected by tracks.
        # Example (optional): get_pipeline('features').add_stage(features.rms)

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
        self.hdsemg_track = None
        # lists for per-channel tracks (on HDsEMG tab)
        self.hd_channel_tracks = []
        self.hd_channel_containers = [] 


        # feature tracks
        self.feature_track = None 
        self.feature_containers = []
        self.feature_tracks = []

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
        # ensure hdsemg layout also gets a stretch
        self.hdsemg_scroll_layout.addStretch()

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

        # also resize per-channel HDsEMG tracks if present
        if hasattr(self, 'hd_channel_tracks') and self.hd_channel_tracks:
            for ch_track in self.hd_channel_tracks:
                new_buf = np.zeros((ch_track.num_channels, int(new_time * ch_track.frequency)))
                copy = min(new_buf.shape[1], ch_track.buffer.shape[1])
                new_buf[:, -copy:] = ch_track.buffer[:, -copy:]
                ch_track.plot_time = new_time
                ch_track.buffer = new_buf
                ch_track.buffer_index = min(ch_track.buffer_index, new_buf.shape[1])
                ch_track.time_array = np.linspace(0, new_time, new_buf.shape[1])
                ch_track.plot_widget.setXRange(0, new_time)

    def toggle_pause(self, checked):
        self.is_paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        if checked:
            self.timer.stop()
        else:
            self.timer.start(Config.UPDATE_RATE)

    def update_status(self, msg):
        self.status_label.setText(msg)
    
    # access track data here
    def update_plot(self):
        if not self.is_paused:
            for track in self.tracks:
                track.draw()
            # update per-channel HDsEMG tracks from the main HDsEMG buffer and draw them
            if hasattr(self, 'hd_channel_tracks') and self.hd_channel_tracks and self.hdsemg_track is not None:
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

            # update average plot (if present)
            try:
                if getattr(self, 'hd_average_track', None) is not None and getattr(self, 'hd_average_channels', None) is not None and self.hdsemg_track is not None:
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
        if not self.is_calibrated:
            QtWidgets.QMessageBox.warning(self, "Not Calibrated",
                                         "Please complete calibration before starting recording.")
            return
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

    def open_hd_channel_selector(self):
        # open dialog to control visibility of individual HD channels on the HDsEMG tab
        if not hasattr(self, 'hd_channel_containers') or not self.hd_channel_containers:
            return
        num = len(self.hd_channel_containers)
        current = [i for i, (_, w) in enumerate(self.hd_channel_containers) if w.isVisible()]
        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            sel_set = set(sel)
            for i, (_, widget) in enumerate(self.hd_channel_containers):
                widget.setVisible(i in sel_set)

    def open_hd_average_selector(self):
        # open dialog to choose channels to include in the averaged plot
        if not hasattr(self, 'hdsemg_track') or self.hdsemg_track is None:
            return
        num = self.hdsemg_track.num_channels
        current = getattr(self, 'hd_average_channels', list(range(num)))
        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            # store zero-based indices
            self.hd_average_channels = sorted(sel)

    def open_calibration_dialog(self):
        """Open calibration dialog if receiver is running."""
        if self.receiver_thread is None:
            QtWidgets.QMessageBox.warning(self, "Not Ready", 
                                         "Data receiver not started. Initialize receiver first.")
            return
        
        dlg = CalibrationDialog(self, self.receiver_thread, calibration_duration=3)
        dlg.calibration_complete.connect(self.on_calibration_complete)
        dlg.exec_()
    
    def on_calibration_complete(self, baseline_rms, threshold):
        """Handle successful calibration."""
        self.baseline_rms = baseline_rms
        self.threshold = threshold
        self.is_calibrated = True
        self.start_button.setEnabled(True)
        QtWidgets.QMessageBox.information(self, "Calibration Success",
                                         f"Baseline RMS: {baseline_rms:.6f}\nThreshold: {threshold:.6f}")



