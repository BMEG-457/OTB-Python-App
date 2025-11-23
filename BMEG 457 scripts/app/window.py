from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
import pyqtgraph as pg
import csv
from datetime import datetime
import os
import time

from app.config import Config
from app.track import Track
from app.data_receiver import DataReceiverThread
from app.processing import filters, features, transforms
from app.processing.pipeline import get_pipeline


class CalibrationDialog(QtWidgets.QDialog):
    """Modal dialog that collects RMS data during rest and contraction phases."""
    calibration_complete = QtCore.pyqtSignal(object, object, object)  # emits (baseline_rms, threshold, mvc_rms) as numpy arrays
    
    def __init__(self, parent, receiver_thread, rest_duration=3, contraction_duration=3):
        super().__init__(parent)
        self.setWindowTitle("EMG Calibration")
        self.setModal(True)
        self.setGeometry(200, 200, 400, 250)
        
        self.receiver_thread = receiver_thread
        self.rest_duration = rest_duration
        self.contraction_duration = contraction_duration
        
        # Data collection
        self.rest_rms_values = []
        self.contraction_rms_values = []
        self.remaining_time = 0
        self.current_phase = None  # 'rest' or 'contraction'
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Phase label
        self.phase_label = QtWidgets.QLabel("Phase: Waiting")
        self.phase_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.phase_label)
        
        # Instructions
        self.instruction_label = QtWidgets.QLabel("Click Start to begin calibration")
        self.instruction_label.setStyleSheet("font-size: 14px;")
        self.instruction_label.setWordWrap(True)
        layout.addWidget(self.instruction_label)
        
        # Countdown timer display
        self.timer_label = QtWidgets.QLabel("--")
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
        """Start the calibration with rest phase."""
        self.rest_rms_values = []
        self.contraction_rms_values = []
        self.start_button.setEnabled(False)
        
        # Connect to rectified signal to collect RMS during window
        if not self.subscription_connected and self.receiver_thread is not None:
            self.receiver_thread.stage_output.connect(self.on_stage_output)
            self.subscription_connected = True
        
        # Start rest phase
        self.start_rest_phase()
    
    def start_rest_phase(self):
        """Begin the rest phase (no contraction)."""
        self.current_phase = 'rest'
        self.remaining_time = self.rest_duration
        self.phase_label.setText("Phase 1: REST")
        self.phase_label.setStyleSheet("font-size: 16px; font-weight: bold; color: blue;")
        self.instruction_label.setText("Relax your muscles - stay still and relaxed")
        self.status_label.setText("Collecting rest baseline data...")
        
        # Start countdown
        self.countdown_timer.start(1000)  # Update every 1 second
        self.tick_countdown()  # Immediate first tick
    
    def start_contraction_phase(self):
        """Begin the contraction phase (maximum voluntary contraction)."""
        self.current_phase = 'contraction'
        self.remaining_time = self.contraction_duration
        self.phase_label.setText("Phase 2: CONTRACTION")
        self.phase_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        self.instruction_label.setText("Contract your muscle as hard as you can!")
        self.status_label.setText("Collecting maximum contraction data...")
        
        # Start countdown
        self.countdown_timer.start(1000)  # Update every 1 second
        self.tick_countdown()  # Immediate first tick
    
    def on_stage_output(self, stage_name, data):
        """Collect RMS from rectified signal."""
        if stage_name == 'rectified' and self.countdown_timer.isActive():
            # Compute RMS per channel (shape: channels x samples)
            # data shape is (channels, samples)
            rms_per_channel = np.sqrt(np.mean(data**2, axis=1))  # RMS across samples for each channel
            
            if self.current_phase == 'rest':
                self.rest_rms_values.append(rms_per_channel)
            elif self.current_phase == 'contraction':
                self.contraction_rms_values.append(rms_per_channel)
    
    def tick_countdown(self):
        """Update countdown display and check if phase is complete."""
        self.timer_label.setText(f"{self.remaining_time}s")
        self.remaining_time -= 1
        
        if self.remaining_time < 0:
            # Phase complete
            self.countdown_timer.stop()
            
            if self.current_phase == 'rest':
                # Move to contraction phase
                self.start_contraction_phase()
            elif self.current_phase == 'contraction':
                # Calibration complete
                self.compute_threshold_and_close()
    
    def compute_threshold_and_close(self):
        """Compute baseline, threshold, and MVC from collected data."""
        if not self.rest_rms_values or not self.contraction_rms_values:
            QtWidgets.QMessageBox.warning(self, "Calibration Failed", 
                                         "Insufficient data collected. Please try again.")
            self.start_button.setEnabled(True)
            self.status_label.setText("Ready. Click Start to begin.")
            self.current_phase = None
            return
        
        # Calculate rest baseline per channel
        # rest_array shape: (time_points, channels)
        rest_array = np.array(self.rest_rms_values)
        baseline_rms = np.mean(rest_array, axis=0)  # Mean rest RMS for each channel
        baseline_std = np.std(rest_array, axis=0)   # Std of rest RMS for each channel
        
        # Calculate MVC (Maximum Voluntary Contraction) from contraction phase
        contraction_array = np.array(self.contraction_rms_values)
        mvc_rms = np.max(contraction_array, axis=0)  # Max contraction RMS for each channel
        
        # Threshold = baseline_mean + 3*std (based on rest baseline)
        threshold = baseline_rms + 3.0 * baseline_std
        
        # Display summary statistics
        mean_baseline = np.mean(baseline_rms)
        mean_threshold = np.mean(threshold)
        mean_mvc = np.mean(mvc_rms)
        self.status_label.setText(f"Calibration complete. Baseline: {mean_baseline:.4f}, Threshold: {mean_threshold:.4f}, MVC: {mean_mvc:.4f}")
        
        # Disconnect receiver signal
        if self.subscription_connected:
            self.receiver_thread.stage_output.disconnect(self.on_stage_output)
            self.subscription_connected = False
        
        # Emit calibration values and accept
        self.calibration_complete.emit(baseline_rms, threshold, mvc_rms)
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
        self.baseline_rms = None  # Will be numpy array of per-channel rest baselines
        self.threshold = None      # Will be numpy array of per-channel thresholds (baseline + 3*std)
        self.mvc_rms = None        # Will be numpy array of per-channel MVC (maximum voluntary contraction)

        # Streaming and Recording state
        self.is_streaming = False
        self.is_recording = False
        self.recording_data = []  # List of (timestamp, channel_data) tuples
        self.recording_start_time = None
        self.max_recording_samples = 1000000  # Limit to prevent overflow (~1M samples)

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
        self.stream_button = QtWidgets.QPushButton("Start Live Stream")
        self.record_button = QtWidgets.QPushButton("Start Recording")
        self.record_button.setEnabled(False)  # Disabled until calibration
        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        self.select_tracks_button = QtWidgets.QPushButton("Select Tracks")

        ctrl_layout.addWidget(self.calibrate_button)
        ctrl_layout.addWidget(self.stream_button)
        ctrl_layout.addWidget(self.record_button)
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
        
        # Tab 4: Heatmap
        heatmap_content = QtWidgets.QWidget()
        heatmap_layout = QtWidgets.QVBoxLayout(heatmap_content)
        
        # Heatmap view
        self.heatmap_view = pg.GraphicsLayoutWidget()
        self.heatmap_plot = self.heatmap_view.addPlot()
        self.heatmap_plot.setAspectLocked(True)
        self.heatmap_plot.hideAxis('bottom')
        self.heatmap_plot.hideAxis('left')
        self.heatmap_plot.setTitle("HD-EMG Array Heatmap (Normalized to MVC)")
        
        # Create 8x8 ImageItem for heatmap
        self.heatmap_img = pg.ImageItem()
        self.heatmap_plot.addItem(self.heatmap_img)
        
        # Initialize with zeros
        self.heatmap_data = np.zeros((8, 8))
        self.heatmap_img.setImage(self.heatmap_data.T, levels=(0, 1))
        
        # Set colormap
        colormap = pg.colormap.get('viridis')
        self.heatmap_img.setColorMap(colormap)
        
        # Add colorbar
        colorbar = pg.ColorBarItem(values=(0, 1), colorMap=colormap)
        colorbar.setImageItem(self.heatmap_img)
        
        # Add text labels for channel numbers
        self.heatmap_labels = []
        for row in range(8):
            for col in range(8):
                # Channel number: bottom-left is 1, going up by column
                channel_num = col * 8 + (7 - row) + 1
                text = pg.TextItem(str(channel_num), color='w', anchor=(0.5, 0.5))
                text.setPos(col + 0.5, row + 0.5)
                self.heatmap_plot.addItem(text)
                self.heatmap_labels.append(text)
        
        heatmap_layout.addWidget(self.heatmap_view)
        self.tabs.addTab(heatmap_content, "Heatmap")
        
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
    
    def update_heatmap(self):
        """Update the 8x8 heatmap with current RMS values normalized to MVC."""
        if not self.is_calibrated or self.mvc_rms is None:
            return
        
        if self.hdsemg_track is None:
            return
        
        try:
            # Get current buffer data
            buf = self.hdsemg_track.buffer  # shape: (channels, samples)
            
            # Calculate RMS for recent window (last 100ms or so)
            window_size = min(100, buf.shape[1])
            recent_data = buf[:, -window_size:]
            
            # Compute RMS per channel
            current_rms = np.sqrt(np.mean(recent_data**2, axis=1))
            
            # Normalize to MVC (0 to 1 scale, clamped)
            # Ensure we have the right number of channels (64 for 8x8)
            if len(current_rms) >= 64 and len(self.mvc_rms) >= 64:
                normalized_rms = current_rms[:64] / (self.mvc_rms[:64] + 1e-10)  # Avoid division by zero
                normalized_rms = np.clip(normalized_rms, 0, 1)
                
                # Reshape to 8x8 grid
                # Channel 1 at bottom-left, incrementing upward by column
                for col in range(8):
                    for row in range(8):
                        channel_idx = col * 8 + (7 - row)  # 0-indexed
                        if channel_idx < len(normalized_rms):
                            self.heatmap_data[row, col] = normalized_rms[channel_idx]
                
                # Update the image
                self.heatmap_img.setImage(self.heatmap_data.T, levels=(0, 1))
        except Exception as e:
            pass  # Silent fail to avoid disrupting main update loop
    
    def on_data_for_recording(self, stage_name, data):
        """Capture data from the receiver thread for recording."""
        # Only record 'final' stage data (the processed data that goes to tracks)
        if stage_name != 'final' or not self.is_recording:
            return
        
        try:
            # Check for overflow protection
            if len(self.recording_data) >= self.max_recording_samples:
                # Stop recording and warn user
                QtCore.QMetaObject.invokeMethod(self, "stop_recording_overflow",
                                               QtCore.Qt.QueuedConnection)
                return
            
            # data shape: (channels, samples)
            # Store each sample with timestamp
            num_samples = data.shape[1]
            current_time = time.time()
            
            for sample_idx in range(num_samples):
                # Calculate relative timestamp (seconds since recording start)
                timestamp = current_time - self.recording_start_time
                
                # Get all channels for this sample
                sample_data = data[:, sample_idx].copy()
                
                # Store as tuple: (timestamp, channel_data_array)
                self.recording_data.append((timestamp, sample_data))
                
                # Re-check overflow for each sample
                if len(self.recording_data) >= self.max_recording_samples:
                    QtCore.QMetaObject.invokeMethod(self, "stop_recording_overflow",
                                                   QtCore.Qt.QueuedConnection)
                    break
                    
        except Exception as e:
            print(f"Error collecting recording data: {e}")
    
    @QtCore.pyqtSlot()
    def stop_recording_overflow(self):
        """Stop recording due to overflow (called from receiver thread)."""
        QtWidgets.QMessageBox.warning(self, "Recording Limit Reached",
                                    f"Maximum recording length ({self.max_recording_samples} samples) reached. "
                                    "Recording stopped automatically.")
        self.stop_recording()
    
    def save_recording_to_csv(self):
        """Save recorded data to CSV file."""
        if not self.recording_data:
            return
        
        try:
            # Create recordings directory if it doesn't exist
            recordings_dir = "recordings"
            if not os.path.exists(recordings_dir):
                os.makedirs(recordings_dir)
            
            # Generate filename with timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(recordings_dir, f"recording_{timestamp_str}.csv")
            
            # Determine number of channels from first sample
            num_channels = len(self.recording_data[0][1])
            
            # Write CSV file
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header: Timestamp, Channel_1, Channel_2, ..., Channel_N
                header = ['Timestamp'] + [f'Channel_{i+1}' for i in range(num_channels)]
                writer.writerow(header)
                
                # Write data rows
                for timestamp, channel_data in self.recording_data:
                    row = [timestamp] + channel_data.tolist()
                    writer.writerow(row)
            
            num_samples = len(self.recording_data)
            self.status_label.setText(f"Recording saved: {filename} ({num_samples} samples)")
            print(f"Recording saved: {filename} with {num_samples} samples")
            
        except Exception as e:
            error_msg = f"Error saving recording: {e}"
            self.status_label.setText(error_msg)
            print(error_msg)
            QtWidgets.QMessageBox.critical(self, "Save Error", error_msg)
    
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
            
            # Update heatmap
            self.update_heatmap()

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

    def start_streaming(self):
        """Start live streaming without recording."""
        self.is_streaming = True
        self.is_paused = False
        self.timer.start()
        self.receiver_thread.running = True
        self.status_label.setText("Streaming...")
        
        # Change button to "Stop Live Stream"
        self.stream_button.setText("Stop Live Stream")
        print("Live streaming started")
    
    def stop_streaming(self):
        """Stop live streaming."""
        self.is_streaming = False
        self.is_paused = True
        self.timer.stop()
        self.receiver_thread.running = False
        self.status_label.setText("Stream stopped")
        
        # Change button back to "Start Live Stream"
        self.stream_button.setText("Start Live Stream")
        print("Live streaming stopped")
    
    def start_recording(self):
        if not self.is_calibrated:
            QtWidgets.QMessageBox.warning(self, "Not Calibrated",
                                         "Please complete calibration before starting recording.")
            return
        
        # Clear previous recording data to prevent overflow
        self.recording_data = []
        self.recording_start_time = time.time()
        self.is_recording = True
        self.is_streaming = True  # Recording also enables streaming
        
        print("Recording started")
        self.is_paused = False
        self.timer.start()
        self.receiver_thread.running = True
        self.status_label.setText("Recording...")
        
        # Change button to "Stop Recording"
        self.record_button.setText("Stop Recording")

    def stop_recording(self):
        print("Recording stopped")
        self.is_recording = False
        
        # Save recording data to CSV
        if self.recording_data:
            self.save_recording_to_csv()
        else:
            self.status_label.setText("No data recorded")
        
        # Clear recording data to free memory
        self.recording_data = []
        self.recording_start_time = None
        
        # Change button back to "Start Recording"
        self.record_button.setText("Start Recording")
        
        # Keep streaming unless user explicitly stops it
        # If not already in pure streaming mode, continue streaming
        if not self.is_streaming:
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
        self.receiver_thread.stage_output.connect(self.on_data_for_recording)
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
        
        dlg = CalibrationDialog(self, self.receiver_thread, rest_duration=3, contraction_duration=3)
        dlg.calibration_complete.connect(self.on_calibration_complete)
        dlg.exec_()
    
    def on_calibration_complete(self, baseline_rms, threshold, mvc_rms):
        """Handle successful calibration."""
        self.baseline_rms = baseline_rms
        self.threshold = threshold
        self.mvc_rms = mvc_rms
        self.is_calibrated = True
        self.record_button.setEnabled(True)
        
        # Display summary statistics
        mean_baseline = np.mean(baseline_rms)
        mean_threshold = np.mean(threshold)
        mean_mvc = np.mean(mvc_rms)
        num_channels = len(baseline_rms)
        QtWidgets.QMessageBox.information(self, "Calibration Success",
                                         f"Channels: {num_channels}\n"
                                         f"Rest Baseline RMS: {mean_baseline:.6f}\n"
                                         f"Threshold: {mean_threshold:.6f}\n"
                                         f"MVC (Max Contraction): {mean_mvc:.6f}")



