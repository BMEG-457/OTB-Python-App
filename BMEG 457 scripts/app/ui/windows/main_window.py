"""Main window for EMG data visualization and control - Refactored version."""

from PyQt5 import QtWidgets, QtCore
import numpy as np
from datetime import datetime
import csv
import os

from app.core.config import Config
from app.core.paths import get_data_dir
from app.data.data_receiver import DataReceiverThread
from app.processing import filters, transforms
from app.processing.pipeline import get_pipeline
from app.ui.dialogs.dialogs import CalibrationDialog, ChannelSelectorDialog, TrackVisibilityDialog, FeatureControlsDialog
from app.ui.tabs.tab_implementations import AllTracksTab, AccessoryTab, HeatmapTab, IndividualChannelsTab, FeaturesTab
from app.processing.features import median_frequency_window
from app.core.track import Track
from app.managers.recording_manager import RecordingManager
from app.managers.streaming_controller import StreamingController
from app.managers.track_manager import TrackManager
from app.processing.realtime_detector import ContractionDetector


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

        # Contraction detection
        self.contraction_detector = None
        
        # Load previous session data if available
        self.load_session_data()

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
        self.connect_button = QtWidgets.QPushButton("Connect to Device")
        self.calibrate_button = QtWidgets.QPushButton("Calibrate")
        self.stream_button = QtWidgets.QPushButton("Start Live Stream")
        self.record_button = QtWidgets.QPushButton("Start Recording")

        top_bar_layout.addWidget(self.connect_button)
        top_bar_layout.addWidget(self.calibrate_button)
        top_bar_layout.addWidget(self.stream_button)
        top_bar_layout.addWidget(self.record_button)

        # Status label
        self.status_label = QtWidgets.QLabel("Ready")
        top_bar_layout.addWidget(self.status_label)

        # Contraction indicator
        top_bar_layout.addSpacing(20)
        self.contraction_led = QtWidgets.QLabel("●")
        self.contraction_led.setStyleSheet(f"color: {Config.COLOR_LED_INACTIVE}; font-size: 22px;")
        self.contraction_status_label = QtWidgets.QLabel("Not Calibrated")
        top_bar_layout.addWidget(self.contraction_led)
        top_bar_layout.addWidget(self.contraction_status_label)

        # Battery indicator
        top_bar_layout.addSpacing(20)
        self.battery_label = QtWidgets.QLabel("Battery: N/A")
        self.battery_label.setStyleSheet("font-size: 13px; font-weight: bold; color: gray;")
        top_bar_layout.addWidget(self.battery_label)

        top_bar_layout.addStretch()

        # If previous session had calibration, initialize indicator to ready state
        if self.is_calibrated:
            self.contraction_detector = ContractionDetector()
            self._update_contraction_indicator(False)

        self.main_layout.addWidget(top_bar)

    def _create_tabs(self):
        """Create all visualization tabs. Add or remove tabs by editing this list."""
        self.tabs = QtWidgets.QTabWidget()
        self.tab_list = [
            AllTracksTab(),
            IndividualChannelsTab(),
            FeaturesTab(),
            AccessoryTab(),
            HeatmapTab(),
        ]
        for tab in self.tab_list:
            self.tabs.addTab(tab, tab.get_tab_name())

    def _get_tab(self, tab_class):
        """Get a tab instance by its class type, or None if not present."""
        for tab in self.tab_list:
            if isinstance(tab, tab_class):
                return tab
        return None

    def _initialize_managers(self):
        """Initialize manager components."""
        # Timer for plot updates (started by streaming controller)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        # Don't start timer yet - let streaming controller manage it
        # self.timer.start(Config.UPDATE_RATE)

        # Track Manager
        accessory_tab = self._get_tab(AccessoryTab)
        individual_tab = self._get_tab(IndividualChannelsTab)
        self.track_manager = TrackManager(
            self.device,
            Config.DEFAULT_PLOT_TIME,
            self._get_tab(AllTracksTab).scroll_layout,
            accessory_scroll_layout=accessory_tab.accessory_scroll_layout if accessory_tab else None,
            individual_channels_scroll_layout=individual_tab.individual_scroll_layout if individual_tab else None,
        )

        # Get tracks reference for compatibility
        self.tracks = self.track_manager.tracks
        self.hdsemg_track = self.track_manager.hdsemg_track

        # Feature tracks
        _FEATURE_RATE = Config.FEATURE_RATE
        _FEATURE_PLOT_TIME = Config.FEATURE_PLOT_TIME
        self.feature_window_ms = Config.FEATURE_WINDOW_MS
        self._contraction_times = []
        features_tab = self._get_tab(FeaturesTab)
        if features_tab is not None:
            feature_layout = features_tab.feature_scroll_layout
            self.rms_feature_track = Track("Mean RMS (µV)", _FEATURE_RATE, 1, 0, 1.0, _FEATURE_PLOT_TIME)
            self.mf_feature_track = Track("Median Frequency (Hz)", _FEATURE_RATE, 1, 0, 1.0, _FEATURE_PLOT_TIME)
            self.rate_feature_track = Track("Contraction Rate (per min)", _FEATURE_RATE, 1, 0, 1.0, _FEATURE_PLOT_TIME)
            for _ft in (self.rms_feature_track, self.mf_feature_track, self.rate_feature_track):
                _ft.plot_widget.setMinimumHeight(Config.FEATURE_PLOT_MIN_HEIGHT)
                _c = QtWidgets.QWidget()
                QtWidgets.QVBoxLayout(_c).addWidget(_ft.plot_widget)
                feature_layout.addWidget(_c)
            feature_layout.addStretch()
        else:
            self.rms_feature_track = None
            self.mf_feature_track = None
            self.rate_feature_track = None

        # Recording Manager
        self.recording_manager = RecordingManager()
        self.recording_manager.overflow_stop_requested.connect(self.handle_recording_overflow)
        self.recording_manager.status_update.connect(self.update_status)

        # Streaming Controller (will be initialized when receiver is ready)
        self.streaming_controller = None
        
        # Verify heatmap readiness after full initialization
        QtCore.QTimer.singleShot(Config.INIT_DELAY_MS, self.verify_heatmap_readiness)

    def _connect_signals(self):
        """Connect all UI signals to handlers. Note: calibrate/stream/record buttons are wired in main.py."""
        # Let each tab wire its own buttons
        for tab in self.tab_list:
            tab.connect_signals(self)

    def _configure_pipelines(self):
        """Configure processing pipelines."""
        # FFT pipeline
        get_pipeline('fft').add_stage(transforms.fft_transform)
        
        # Filtered pipeline - use lambda to provide required parameters
        get_pipeline('filtered').add_stage(lambda data: filters.butter_bandpass(data, low=Config.BANDPASS_LOW, high=Config.BANDPASS_HIGH, fs=self.device.frequency))
        get_pipeline('filtered').add_stage(lambda data: filters.notch(data, freq=Config.NOTCH_FREQ, fs=self.device.frequency))
        
        # Rectified pipeline
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
        if checked:
            self.timer.stop()
        else:
            self.timer.start(Config.UPDATE_RATE)

    def update_status(self, msg):
        """Update status label."""
        self.status_label.setText(msg)
    
    def show_error(self, message):
        """Display error message dialog."""
        QtWidgets.QMessageBox.critical(self, "Error", message)
    
    def update_heatmap(self):
        """Update the 8x8 heatmap with current RMS values normalized to MVC."""
        if not self.is_calibrated or self.mvc_rms is None or self.hdsemg_track is None:
            return

        try:
            buf = self.hdsemg_track.buffer
            window_size = min(100, buf.shape[1])
            recent_data = buf[:, -window_size:]

            # Compute RMS per channel with saturation filtering
            current_rms = np.zeros(recent_data.shape[0])
            for ch_idx in range(recent_data.shape[0]):
                channel_data = recent_data[ch_idx]
                non_saturated = channel_data[
                    (channel_data > Config.SATURATION_LOW) &
                    (channel_data < Config.SATURATION_HIGH)
                ]

                if len(non_saturated) > 0:
                    current_rms[ch_idx] = np.sqrt(np.mean(non_saturated**2))
                else:
                    current_rms[ch_idx] = 0.0

            n = Config.EMG_CHANNELS
            if len(current_rms) >= n and len(self.mvc_rms) >= n:
                normalized_rms = current_rms[:n] / (self.mvc_rms[:n] + 1e-10)
                normalized_rms = np.clip(normalized_rms, 0, 1)
                heatmap_tab = self._get_tab(HeatmapTab)
                if heatmap_tab:
                    heatmap_tab.update_heatmap(normalized_rms)
                if self.contraction_detector is not None:
                    changed = self.contraction_detector.update(normalized_rms)
                    if changed and self.contraction_detector.is_contracting:
                        import time as _time
                        self._contraction_times.append(_time.monotonic())
                    self._update_contraction_indicator(self.contraction_detector.is_contracting)
        except Exception:
            pass

    def _update_contraction_indicator(self, is_contracting: bool):
        """Update the LED and label to reflect current contraction state."""
        if not self.is_calibrated:
            self.contraction_led.setStyleSheet(f"color: {Config.COLOR_LED_INACTIVE}; font-size: 22px;")
            self.contraction_status_label.setText("Not Calibrated")
        elif is_contracting:
            self.contraction_led.setStyleSheet(f"color: {Config.COLOR_LED_CONTRACTING}; font-size: 22px;")
            self.contraction_status_label.setText("Contracting!")
        else:
            self.contraction_led.setStyleSheet(f"color: {Config.COLOR_LED_RELAXED}; font-size: 22px;")
            self.contraction_status_label.setText("Relaxed")

    def update_battery_display(self, level):
        """Update battery percentage label with color coding."""
        if level is None:
            self.battery_label.setText("Battery: --")
            self.battery_label.setStyleSheet("font-size: 13px; font-weight: bold; color: gray;")
        else:
            if level <= 20:
                color = Config.COLOR_LED_CONTRACTING   # red
            elif level <= 50:
                color = "#FFA500"                      # orange
            else:
                color = Config.COLOR_LED_RELAXED       # green
            self.battery_label.setText(f"Battery: {level}%")
            self.battery_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

    def change_group_preset(self, preset):
        """Switch the HDsEMG group average preset shown in AllTracksTab."""
        self.track_manager.set_group_preset(preset)

    def update_plot(self):
        """Main plot update loop - draws whenever timer is running."""
        if not self.is_paused:
            current_tab = self.tabs.currentWidget()
            self.track_manager.draw_all_tracks(active_tab=current_tab)
            if isinstance(current_tab, AllTracksTab):
                self.track_manager.update_group_averages()
            if isinstance(current_tab, HeatmapTab):
                self.update_heatmap()
            if isinstance(current_tab, FeaturesTab):
                self.update_features()

    def toggle_streaming(self):
        """Toggle streaming on/off."""
        # Streaming controller should already be initialized by button handler in main.py
        if self.streaming_controller is None:
            self.update_status("ERROR: Streaming controller not initialized. This should not happen.")
            print("ERROR: streaming_controller is None in toggle_streaming - check main.py button handlers")
            return
        
        if self.streaming_controller.is_streaming:
            self.streaming_controller.stop_streaming()
            self.stream_button.setText("Start Live Stream")
            if self.contraction_detector is not None:
                self.contraction_detector.reset()
                self._update_contraction_indicator(False)
            self._contraction_times.clear()
        else:
            self.streaming_controller.start_streaming()
            self.stream_button.setText("Stop Live Stream")

    def toggle_recording(self):
        """Toggle recording on/off."""
        if self.recording_manager.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start recording data."""
        print("[MAIN] start_recording() called")
        self.recording_manager.start_recording()
        self.record_button.setText("Stop Recording")
        self.update_status("Recording...")
        
        # Ensure streaming is active
        if not self.streaming_controller.is_streaming:
            print("[MAIN] Streaming not active, starting it now...")
            self.streaming_controller.start_streaming()
        else:
            print(f"[MAIN] Streaming already active (running={self.receiver_thread.running})")

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
        # Stop streaming and recording
        if self.streaming_controller and self.streaming_controller.is_streaming:
            self.streaming_controller.stop_streaming()
        if self.recording_manager.is_recording:
            self.stop_recording()
        
        # Stop receiver thread
        if self.receiver_thread is not None:
            try:
                self.receiver_thread.stop()
                self.receiver_thread.wait(Config.RECEIVER_WAIT_MS)
            except Exception as e:
                print(f"Error stopping receiver thread: {e}")
        
        # Close socket
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
        
        # Stop device server
        if hasattr(self, 'device') and self.device is not None:
            try:
                self.device.stop_server()
            except Exception as e:
                print(f"Error stopping device server: {e}")
        
        event.accept()

    def set_client_socket(self, socket):
        """Set the client socket."""
        self.client_socket = socket

    def initialize_receiver(self):
        """Initialize data receiver thread (but don't start it yet - streaming_controller will do that)."""
        print(f"[INIT] Creating receiver thread for device with {self.device.nchannels} channels at {self.device.frequency}Hz")
        self.receiver_thread = DataReceiverThread(
            self.device,
            self.client_socket,
            self.tracks
        )
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.error_signal.connect(self.show_error)
        self.receiver_thread.stage_output.connect(self.recording_manager.on_data_for_recording)
        self.receiver_thread.finished.connect(self.on_receiver_finished)
        print("[INIT] Receiver thread created but not started yet")

        # Initialize streaming controller now that receiver is ready
        self.streaming_controller = StreamingController(self.timer, self.receiver_thread)
        self.streaming_controller.status_update.connect(self.update_status)
        print("[INIT] Streaming controller initialized")

    def on_receiver_finished(self):
        # Called when the receiver thread exits. Only act if the thread died while
        # streaming was active (unexpected exit); normal stop sets is_streaming=False first.
        if self.streaming_controller and self.streaming_controller.is_streaming:
            self.streaming_controller.is_streaming = False
            self.streaming_controller.is_paused = True
            self.timer.stop()
            self.stream_button.setText("Start Live Stream")
            if self.contraction_detector is not None:
                self.contraction_detector.reset()
                self._update_contraction_indicator(False)
            self.update_status("Connection lost. Click 'Start Live Stream' to reconnect.")

    def reinitialize_receiver(self):
        # Stop old thread cleanly if still alive (e.g. slow exit after error).
        if self.receiver_thread is not None and self.receiver_thread.isRunning():
            self.receiver_thread.stop()
            self.receiver_thread.wait(Config.RECEIVER_WAIT_MS)

        # Create fresh thread with updated socket (set_client_socket called before this).
        self.receiver_thread = DataReceiverThread(self.device, self.client_socket, self.tracks)
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.error_signal.connect(self.show_error)
        self.receiver_thread.stage_output.connect(self.recording_manager.on_data_for_recording)
        self.receiver_thread.finished.connect(self.on_receiver_finished)

        if self.streaming_controller is not None:
            self.streaming_controller.receiver_thread = self.receiver_thread

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

    def open_feature_controls(self):
        """Open dialog to configure feature computation window size."""
        dlg = FeatureControlsDialog(self, self.feature_window_ms)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.feature_window_ms = dlg.selected_window_ms()

    def update_features(self):
        """Compute RMS, median frequency, and contraction rate; feed into feature tracks."""
        if self.rms_feature_track is None or self.hdsemg_track is None:
            return
        import time as _time
        window_samples = int(self.feature_window_ms * self.device.frequency / 1000)
        buf = self.hdsemg_track.buffer
        if buf.shape[1] < window_samples:
            return

        # Filter saturated channels before computing
        window = buf[:, -window_samples:]
        mask = np.all(np.abs(window) < Config.SATURATION_HIGH, axis=1)
        if not mask.any():
            return
        clean = window[mask, :]

        # Mean RMS in µV
        raw_rms = float(np.sqrt(np.mean(clean ** 2)))
        rms_uv = raw_rms * self.hdsemg_track.conv_fact * 1e6
        self.rms_feature_track.feed(np.array([[rms_uv]]))
        self.rms_feature_track.draw()

        # Median frequency (minimum 500ms window for frequency resolution)
        if self.mf_feature_track is not None:
            mf_samples = max(window_samples, int(0.5 * self.device.frequency))
            if buf.shape[1] >= mf_samples:
                mf_window = buf[:, -mf_samples:]
                signal_mean = np.mean(mf_window[mask, :], axis=0)
                mf_hz = median_frequency_window(signal_mean, self.device.frequency)
                self.mf_feature_track.feed(np.array([[mf_hz]]))
                self.mf_feature_track.draw()

        # Contraction rate (contractions per minute in the last 60 seconds)
        if self.rate_feature_track is not None:
            now = _time.monotonic()
            self._contraction_times = [t for t in self._contraction_times if now - t <= Config.CONTRACTION_RATE_WINDOW]
            rate = float(len(self._contraction_times))
            self.rate_feature_track.feed(np.array([[rate]]))
            self.rate_feature_track.draw()

    def open_calibration_dialog(self):
        """Open calibration dialog. This method should be overridden/wrapped in main.py to handle receiver initialization."""
        if self.receiver_thread is None:
            QtWidgets.QMessageBox.warning(self, "Not Ready", 
                                         "Device not connected. Please connect device first.")
            return
        
        dlg = CalibrationDialog(self, self.receiver_thread, rest_duration=Config.REST_DURATION, contraction_duration=Config.CONTRACTION_DURATION)
        dlg.calibration_complete.connect(self.on_calibration_complete)
        dlg.exec_()
    
    def on_calibration_complete(self, baseline_rms, threshold, mvc_rms):
        """Handle successful calibration."""
        self.baseline_rms = baseline_rms
        self.threshold = threshold
        self.mvc_rms = mvc_rms
        self.is_calibrated = True

        # Initialize (or reset) contraction detector with new calibration
        self.contraction_detector = ContractionDetector()
        self._update_contraction_indicator(False)

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
        
        # Save session data immediately after successful calibration
        print("[SESSION] Saving calibration data...")
        self.save_session_data()
    
    def load_session_data(self):
        """Load configuration and calibrated values from previous session CSV file."""
        try:
            # Get path to CSV file
            data_dir = get_data_dir()
            csv_path = os.path.join(data_dir, 'previous_session.csv')

            if not os.path.exists(csv_path):
                print("[SESSION] No previous session file found")
                return
            
            # Read the CSV file
            with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                session_data = next(reader, None)
                
                if session_data is None:
                    print("[SESSION] No data found in previous session file")
                    return
                
                # Load calibration data if available
                if session_data.get('is_calibrated', '').lower() == 'true':
                    try:
                        # Parse comma-separated values back to numpy arrays
                        baseline_values = session_data.get('baseline_rms_values', '')
                        threshold_values = session_data.get('threshold_values', '')
                        mvc_values = session_data.get('mvc_rms_values', '')
                        
                        if baseline_values and threshold_values and mvc_values:
                            self.baseline_rms = np.array([float(x) for x in baseline_values.split(',') if x.strip()])
                            self.threshold = np.array([float(x) for x in threshold_values.split(',') if x.strip()])
                            self.mvc_rms = np.array([float(x) for x in mvc_values.split(',') if x.strip()])
                            self.is_calibrated = True
                            
                            num_channels = len(self.baseline_rms)
                            mean_baseline = np.mean(self.baseline_rms)
                            mean_threshold = np.mean(self.threshold)
                            mean_mvc = np.mean(self.mvc_rms)
                            
                            print(f"[SESSION] Loaded previous calibration: {num_channels} channels")
                            print(f"[SESSION] Baseline: {mean_baseline:.6f}, Threshold: {mean_threshold:.6f}, MVC: {mean_mvc:.6f}")
                            
                            # Update status
                            self.status_label.setText(f"Loaded previous calibration - Channels: {num_channels}, "
                                                    f"Baseline: {mean_baseline:.4f}, Threshold: {mean_threshold:.4f}, MVC: {mean_mvc:.4f}")
                            
                            # Verify heatmap readiness
                            if self.hdsemg_track is not None:
                                print("[SESSION] ✅ Heatmap ready - calibration loaded and tracks initialized")
                            else:
                                print("[SESSION] ⚠️  Heatmap not ready - tracks not yet initialized")
                        
                    except (ValueError, IndexError) as e:
                        print(f"[SESSION] Error parsing calibration data: {e}")
                        self.is_calibrated = False
                else:
                    print("[SESSION] Previous session was not calibrated")
                
                # Load timestamp info
                timestamp = session_data.get('timestamp', '')
                if timestamp:
                    print(f"[SESSION] Previous session timestamp: {timestamp}")
                    
        except Exception as e:
            print(f"[SESSION] Error loading previous session data: {e}")
    
    def create_initial_session_file(self):
        """Create initial session file with current configuration values (no calibration data)."""
        print("[SESSION] Creating initial session file with default configuration...")
        
        # Temporarily set calibration status to ensure we save config-only data
        original_calibrated = self.is_calibrated
        self.is_calibrated = False  # This will cause save_session_data to use empty calibration placeholders
        
        # Save the session data
        self.save_session_data()
        
        # Restore original calibration status
        self.is_calibrated = original_calibrated
        
        print("[SESSION] Initial session file created with configuration data")
    
    def verify_heatmap_readiness(self):
        """Verify and report if heatmap is ready to display."""
        conditions = {
            'is_calibrated': self.is_calibrated,
            'mvc_rms_available': self.mvc_rms is not None,
            'hdsemg_track_available': self.hdsemg_track is not None
        }
        
        all_ready = all(conditions.values())
        
        print(f"[HEATMAP] Readiness check:")
        for condition, status in conditions.items():
            status_symbol = "✅" if status else "❌"
            print(f"[HEATMAP]   {condition}: {status_symbol}")
        
        if all_ready:
            num_channels = len(self.mvc_rms) if self.mvc_rms is not None else 0
            print(f"[HEATMAP] ✅ Heatmap fully ready with {num_channels} channels")
            return True
        else:
            print("[HEATMAP] ❌ Heatmap not ready - missing conditions above")
            return False
    
    def save_session_data(self):
        """Save configuration and calibrated values to CSV file."""
        try:
            # Ensure data directory exists
            data_dir = get_data_dir()
            os.makedirs(data_dir, exist_ok=True)
            
            csv_path = os.path.join(data_dir, 'previous_session.csv')
            
            # Prepare session data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Configuration values
            config_data = {
                'timestamp': timestamp,
                'default_plot_time': Config.DEFAULT_PLOT_TIME,
                'update_rate': Config.UPDATE_RATE,
                'plot_height': Config.PLOT_HEIGHT,
                'window_width': Config.WINDOW_SIZE[0],
                'window_height': Config.WINDOW_SIZE[1],
                'is_calibrated': str(self.is_calibrated)
            }
            
            # Add calibration data if available
            if self.is_calibrated and self.baseline_rms is not None:
                # Convert numpy arrays to comma-separated strings
                config_data.update({
                    'baseline_rms_mean': f"{np.mean(self.baseline_rms):.6f}",
                    'baseline_rms_std': f"{np.std(self.baseline_rms):.6f}",
                    'threshold_mean': f"{np.mean(self.threshold):.6f}", 
                    'threshold_std': f"{np.std(self.threshold):.6f}",
                    'mvc_rms_mean': f"{np.mean(self.mvc_rms):.6f}",
                    'mvc_rms_std': f"{np.std(self.mvc_rms):.6f}",
                    'num_channels': str(len(self.baseline_rms)),
                    'baseline_rms_values': ','.join([f"{val:.6f}" for val in self.baseline_rms]),
                    'threshold_values': ','.join([f"{val:.6f}" for val in self.threshold]),
                    'mvc_rms_values': ','.join([f"{val:.6f}" for val in self.mvc_rms])
                })
            else:
                # Add empty placeholders for calibration data
                config_data.update({
                    'baseline_rms_mean': '',
                    'baseline_rms_std': '',
                    'threshold_mean': '',
                    'threshold_std': '',
                    'mvc_rms_mean': '',
                    'mvc_rms_std': '',
                    'num_channels': '',
                    'baseline_rms_values': '',
                    'threshold_values': '',
                    'mvc_rms_values': ''
                })
            
            # Write to CSV file
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(config_data.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(config_data)
            
            print(f"[SESSION] Session data saved to {csv_path}")
            
        except Exception as e:
            print(f"[SESSION] Error saving session data: {e}")
    
    def closeEvent(self, event):
        """Handle window close event - save session data before closing."""
        print("[SESSION] Saving session data before closing...")
        self.save_session_data()
        
        # Stop streaming if active
        if self.streaming_controller and self.streaming_controller.is_streaming:
            self.streaming_controller.stop_streaming()
        
        # Stop recording if active  
        if self.recording_manager.is_recording:
            self.stop_recording()
        
        # Accept the close event
        event.accept()
