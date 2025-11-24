"""Main window for EMG data visualization and control - Refactored version."""

from PyQt5 import QtWidgets, QtCore
import numpy as np
import pyqtgraph as pg

from app.core.config import Config
from app.data.data_receiver import DataReceiverThread
from app.processing import filters, features, transforms
from app.processing.pipeline import get_pipeline
from app.ui.dialogs.dialogs import CalibrationDialog, ChannelSelectorDialog, TrackVisibilityDialog
from app.managers.recording_manager import RecordingManager
from app.managers.streaming_controller import StreamingController
from app.managers.track_manager import TrackManager


class SoundtrackWindow(QtWidgets.QWidget):
    """Main application window for EMG data visualization."""
    
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.client_socket = None
        self.is_paused = False
        
        # Calibration state
        self.is_calibrated = False
        self.baseline_rms = None
        self.threshold = None
        self.mvc_rms = None

        self.setWindowTitle("Sessantaquattro+ Viewer")
        self.setGeometry(100, 100, *Config.WINDOW_SIZE)

        self.main_layout = QtWidgets.QVBoxLayout(self)

        # -------- Back Button Row --------
        back_row = QtWidgets.QWidget()
        back_layout = QtWidgets.QHBoxLayout(back_row)
        self.back_button = QtWidgets.QPushButton("← Back")
        self.back_button.setMaximumWidth(100)
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        self.main_layout.addWidget(back_row)

        # -------- Top Control Bar --------
        self._create_top_control_bar()

        # -------- Tabs for different views --------
        self._create_tabs()
        
        self.main_layout.addWidget(self.tabs)

        # Initialize managers and controllers
        self._initialize_managers()
        
        # Wire up signals
        self._connect_signals()

        # Initialize receiver thread placeholder
        self.receiver_thread = None

        # Configure processing pipelines
        self._configure_pipelines()

    def _create_top_control_bar(self):
        """Create the top control bar with main buttons."""
        top_bar = QtWidgets.QWidget()
        top_bar_layout = QtWidgets.QHBoxLayout(top_bar)

        # Left side: Plot time selector
        top_bar_layout.addWidget(QtWidgets.QLabel("Plot Time:"))
        self.time_selector = QtWidgets.QComboBox()
        self.time_selector.addItems(["100ms", "250ms", "500ms", "1s", "5s", "10s"])
        self.time_selector.setCurrentText("1s")
        self.time_selector.currentTextChanged.connect(self.change_plot_time)
        top_bar_layout.addWidget(self.time_selector)

        # Add separator
        top_bar_layout.addSpacing(20)

        # Main control buttons
        self.calibrate_button = QtWidgets.QPushButton("Calibrate")
        self.stream_button = QtWidgets.QPushButton("Start Live Stream")
        self.record_button = QtWidgets.QPushButton("Start Recording")
        self.record_button.setEnabled(False)  # Disabled until calibration
        
        top_bar_layout.addWidget(self.calibrate_button)
        top_bar_layout.addWidget(self.stream_button)
        top_bar_layout.addWidget(self.record_button)

        # Add separator
        top_bar_layout.addSpacing(20)

        # Pause button
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.toggle_pause)
        top_bar_layout.addWidget(self.pause_button)

        # Status label
        self.status_label = QtWidgets.QLabel("Ready")
        top_bar_layout.addWidget(self.status_label)
        top_bar_layout.addStretch()

        self.main_layout.addWidget(top_bar)

    def _create_tabs(self):
        """Create all visualization tabs."""
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: All Tracks
        all_tracks_content = QtWidgets.QWidget()
        all_tracks_layout = QtWidgets.QHBoxLayout(all_tracks_content)

        # Scroll Area for all Tracks
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        all_tracks_layout.addWidget(self.scroll_area, stretch=3)

        # Right-side control panel
        control_panel = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(control_panel)
        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        self.select_tracks_button = QtWidgets.QPushButton("Select Tracks")
        ctrl_layout.addWidget(self.select_channels_button)
        ctrl_layout.addWidget(self.select_tracks_button)
        ctrl_layout.addStretch()
        all_tracks_layout.addWidget(control_panel, stretch=0)
        
        self.tabs.addTab(all_tracks_content, "All Tracks")

        # Tab 2: HDsEMG
        self._create_hdsemg_tab()

        # Tab 3: Features
        self._create_features_tab()
        
        # Tab 4: Heatmap
        self._create_heatmap_tab()

    def _create_hdsemg_tab(self):
        """Create the HDsEMG tab."""
        hdsemg_content = QtWidgets.QWidget()
        hdsemg_layout = QtWidgets.QHBoxLayout(hdsemg_content)

        self.hdsemg_scroll_area = QtWidgets.QScrollArea()
        self.hdsemg_scroll_area.setWidgetResizable(True)
        self.hdsemg_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.hdsemg_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.hdsemg_scroll_widget = QtWidgets.QWidget()
        self.hdsemg_scroll_layout = QtWidgets.QVBoxLayout(self.hdsemg_scroll_widget)
        self.hdsemg_scroll_area.setWidget(self.hdsemg_scroll_widget)
        hdsemg_layout.addWidget(self.hdsemg_scroll_area, stretch=3)

        # Right-side control panel
        hdsemg_control_panel = QtWidgets.QWidget()
        hdsemg_ctrl_layout = QtWidgets.QVBoxLayout(hdsemg_control_panel)
        self.hd_average_select_button = QtWidgets.QPushButton("Select Avg Channels")
        hdsemg_ctrl_layout.addWidget(self.hd_average_select_button)
        hdsemg_ctrl_layout.addStretch()
        hdsemg_layout.addWidget(hdsemg_control_panel, stretch=0)
        
        self.tabs.addTab(hdsemg_content, "HDsEMG")

    def _create_features_tab(self):
        """Create the Features tab."""
        feature_content = QtWidgets.QWidget()
        feature_layout = QtWidgets.QHBoxLayout(feature_content)

        self.feature_scroll_area = QtWidgets.QScrollArea()
        self.feature_scroll_area.setWidgetResizable(True)
        self.feature_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.feature_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.feature_scroll_widget = QtWidgets.QWidget()
        self.feature_scroll_layout = QtWidgets.QVBoxLayout(self.feature_scroll_widget)
        self.feature_scroll_area.setWidget(self.feature_scroll_widget)
        feature_layout.addWidget(self.feature_scroll_area, stretch=3)

        # Right-side control panel
        feature_control_panel = QtWidgets.QWidget()
        feature_ctrl_layout = QtWidgets.QVBoxLayout(feature_control_panel)
        self.feature_controls_button = QtWidgets.QPushButton("Feature Controls")
        feature_ctrl_layout.addWidget(self.feature_controls_button)
        feature_ctrl_layout.addStretch()
        feature_layout.addWidget(feature_control_panel, stretch=0)
        
        self.tabs.addTab(feature_content, "Features")

    def _create_heatmap_tab(self):
        """Create the Heatmap tab."""
        heatmap_content = QtWidgets.QWidget()
        heatmap_layout = QtWidgets.QHBoxLayout(heatmap_content)
        
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
                channel_num = col * 8 + (7 - row) + 1
                text = pg.TextItem(str(channel_num), color='w', anchor=(0.5, 0.5))
                text.setPos(col + 0.5, row + 0.5)
                self.heatmap_plot.addItem(text)
                self.heatmap_labels.append(text)
        
        heatmap_layout.addWidget(self.heatmap_view, stretch=3)

        # Right-side control panel
        heatmap_control_panel = QtWidgets.QWidget()
        heatmap_ctrl_layout = QtWidgets.QVBoxLayout(heatmap_control_panel)
        heatmap_ctrl_layout.addStretch()
        heatmap_layout.addWidget(heatmap_control_panel, stretch=0)
        
        self.tabs.addTab(heatmap_content, "Heatmap")

    def _initialize_managers(self):
        """Initialize manager components."""
        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(Config.UPDATE_RATE)

        # Track Manager
        self.track_manager = TrackManager(
            self.device,
            Config.DEFAULT_PLOT_TIME,
            self.scroll_layout,
            self.hdsemg_scroll_layout,
            self.feature_scroll_layout
        )
        
        # Get tracks reference for compatibility
        self.tracks = self.track_manager.tracks
        self.hdsemg_track = self.track_manager.hdsemg_track
        self.hd_average_track = self.track_manager.hd_average_track
        self.hd_average_channels = self.track_manager.hd_average_channels

        # Recording Manager
        self.recording_manager = RecordingManager(max_samples=1000000)
        self.recording_manager.overflow_stop_requested.connect(self.handle_recording_overflow)
        self.recording_manager.status_update.connect(self.update_status)

        # Streaming Controller (will be initialized when receiver is ready)
        self.streaming_controller = None

    def _connect_signals(self):
        """Connect all UI signals to handlers."""
        self.calibrate_button.clicked.connect(self.open_calibration_dialog)
        self.stream_button.clicked.connect(self.toggle_streaming)
        self.record_button.clicked.connect(self.toggle_recording)
        self.select_channels_button.clicked.connect(self.open_channel_selector)
        self.select_tracks_button.clicked.connect(self.open_track_selector)
        self.hd_average_select_button.clicked.connect(self.open_hd_average_selector)

    def _configure_pipelines(self):
        """Configure processing pipelines."""
        get_pipeline('fft').add_stage(transforms.fft_transform)
        get_pipeline('filtered').add_stage(filters.butter_bandpass)
        get_pipeline('filtered').add_stage(filters.notch)
        get_pipeline('rectified').add_stage(filters.rectify)

    def change_plot_time(self, text):
        """Change plot time window."""
        if text.endswith("ms"):
            new_time = float(text[:-2]) / 1000
        else:
            new_time = float(text[:-1])

        self.track_manager.change_plot_time(new_time)

    def toggle_pause(self, checked):
        """Toggle pause state."""
        self.is_paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        if checked:
            self.timer.stop()
        else:
            self.timer.start(Config.UPDATE_RATE)

    def update_status(self, msg):
        """Update status label."""
        self.status_label.setText(msg)
    
    def update_heatmap(self):
        """Update the 8x8 heatmap with current RMS values normalized to MVC."""
        if not self.is_calibrated or self.mvc_rms is None or self.hdsemg_track is None:
            return
        
        try:
            buf = self.hdsemg_track.buffer
            window_size = min(100, buf.shape[1])
            recent_data = buf[:, -window_size:]
            current_rms = np.sqrt(np.mean(recent_data**2, axis=1))
            
            if len(current_rms) >= 64 and len(self.mvc_rms) >= 64:
                normalized_rms = current_rms[:64] / (self.mvc_rms[:64] + 1e-10)
                normalized_rms = np.clip(normalized_rms, 0, 1)
                
                for col in range(8):
                    for row in range(8):
                        channel_idx = col * 8 + (7 - row)
                        if channel_idx < len(normalized_rms):
                            self.heatmap_data[row, col] = normalized_rms[channel_idx]
                
                self.heatmap_img.setImage(self.heatmap_data.T, levels=(0, 1))
        except Exception:
            pass

    def update_plot(self):
        """Main plot update loop."""
        if not self.is_paused:
            self.track_manager.draw_all_tracks()
            self.track_manager.update_hd_channel_tracks()
            self.track_manager.update_hd_average()
            self.update_heatmap()

    def toggle_streaming(self):
        """Toggle streaming on/off."""
        if self.streaming_controller is None:
            self.update_status("Receiver not initialized")
            return
        
        if self.streaming_controller.is_streaming:
            self.streaming_controller.stop_streaming()
            self.stream_button.setText("Start Live Stream")
        else:
            self.streaming_controller.start_streaming()
            self.stream_button.setText("Stop Live Stream")

    def toggle_recording(self):
        """Toggle recording on/off."""
        if not self.is_calibrated:
            QtWidgets.QMessageBox.warning(self, "Not Calibrated",
                                         "Please complete calibration before recording.")
            return
        
        if self.recording_manager.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start recording data."""
        self.recording_manager.start_recording()
        self.record_button.setText("Stop Recording")
        self.update_status("Recording...")
        
        # Ensure streaming is active
        if not self.streaming_controller.is_streaming:
            self.streaming_controller.start_streaming()

    def stop_recording(self):
        """Stop recording and save data."""
        self.recording_manager.stop_recording()
        
        # Save to CSV
        success, message, filename = self.recording_manager.save_recording_to_csv()
        self.update_status(message)
        
        if not success and filename is None:
            if message != "No data recorded":
                QtWidgets.QMessageBox.critical(self, "Save Error", message)
        
        self.record_button.setText("Start Recording")

    @QtCore.pyqtSlot()
    def handle_recording_overflow(self):
        """Handle recording overflow."""
        QtWidgets.QMessageBox.warning(self, "Recording Limit Reached",
                                    f"Maximum recording length reached. Recording stopped automatically.")
        self.stop_recording()

    def closeEvent(self, event):
        """Handle window close event."""
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

    def set_client_socket(self, socket):
        """Set the client socket."""
        self.client_socket = socket

    def initialize_receiver(self):
        """Initialize data receiver thread."""
        self.receiver_thread = DataReceiverThread(
            self.device,
            self.client_socket,
            self.tracks
        )
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.stage_output.connect(self.recording_manager.on_data_for_recording)
        self.receiver_thread.start()

        # Initialize streaming controller now that receiver is ready
        self.streaming_controller = StreamingController(self.timer, self.receiver_thread)
        self.streaming_controller.status_update.connect(self.update_status)

    def open_channel_selector(self):
        """Open channel selector dialog."""
        if not self.tracks:
            return
        track = self.tracks[0]
        num = track.num_channels
        current = getattr(track, 'visible_channels', list(range(num)))
        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            track.set_visible_channels(sel)

    def open_track_selector(self):
        """Open track visibility selector dialog."""
        titles = self.track_manager.get_track_titles()
        current = self.track_manager.get_visible_track_titles()
        dlg = TrackVisibilityDialog(self, titles, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_titles()
            self.track_manager.set_track_visibility(sel)

    def open_hd_average_selector(self):
        """Open HD average channel selector dialog."""
        if self.hdsemg_track is None:
            return
        num = self.hdsemg_track.num_channels
        current = self.hd_average_channels
        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            self.track_manager.hd_average_channels = sorted(sel)

    def open_calibration_dialog(self):
        """Open calibration dialog."""
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
        
        # Display summary
        mean_baseline = np.mean(baseline_rms)
        mean_threshold = np.mean(threshold)
        mean_mvc = np.mean(mvc_rms)
        num_channels = len(baseline_rms)
        QtWidgets.QMessageBox.information(self, "Calibration Success",
                                         f"Channels: {num_channels}\n"
                                         f"Rest Baseline RMS: {mean_baseline:.6f}\n"
                                         f"Threshold: {mean_threshold:.6f}\n"
                                         f"MVC (Max Contraction): {mean_mvc:.6f}")
