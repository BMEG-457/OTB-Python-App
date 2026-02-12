"""Main window for EMG data visualization and control - Refactored version."""

from PyQt5 import QtWidgets, QtCore
import numpy as np
from datetime import datetime
import csv
import os

from app.core.config import Config
from app.data.data_receiver import DataReceiverThread
from app.processing import filters, transforms
from app.processing.pipeline import get_pipeline
from app.ui.dialogs.dialogs import CalibrationDialog, ChannelSelectorDialog, TrackVisibilityDialog
from app.ui.tabs.tab_implementations import AllTracksTab, HeatmapTab
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
        self.calibrate_button = QtWidgets.QPushButton("Calibrate")
        self.stream_button = QtWidgets.QPushButton("Start Live Stream")
        self.record_button = QtWidgets.QPushButton("Start Recording")
        
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
        """Create all visualization tabs. Add or remove tabs by editing this list."""
        self.tabs = QtWidgets.QTabWidget()
        self.tab_list = [
            AllTracksTab(),
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
        self.track_manager = TrackManager(
            self.device,
            Config.DEFAULT_PLOT_TIME,
            self._get_tab(AllTracksTab).scroll_layout
        )

        # Get tracks reference for compatibility
        self.tracks = self.track_manager.tracks
        self.hdsemg_track = self.track_manager.hdsemg_track

        # Recording Manager
        self.recording_manager = RecordingManager(max_samples=1000000)
        self.recording_manager.overflow_stop_requested.connect(self.handle_recording_overflow)
        self.recording_manager.status_update.connect(self.update_status)

        # Streaming Controller (will be initialized when receiver is ready)
        self.streaming_controller = None
        
        # Verify heatmap readiness after full initialization
        QtCore.QTimer.singleShot(100, self.verify_heatmap_readiness)  # Delay to ensure all initialization is complete

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
        get_pipeline('filtered').add_stage(lambda data: filters.butter_bandpass(data, low=20, high=450, fs=self.device.frequency))
        get_pipeline('filtered').add_stage(lambda data: filters.notch(data, freq=60, fs=self.device.frequency))
        
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
        self.pause_button.setText("Resume" if checked else "Pause")
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

            # Filter out saturated values before computing RMS
            saturation_threshold_low = -32760  # Close to -32768 (int16 min)
            saturation_threshold_high = 32760   # Close to 32767 (int16 max)

            # Compute RMS per channel with saturation filtering
            current_rms = np.zeros(recent_data.shape[0])
            for ch_idx in range(recent_data.shape[0]):
                channel_data = recent_data[ch_idx]
                # Filter out saturated values
                non_saturated = channel_data[
                    (channel_data > saturation_threshold_low) &
                    (channel_data < saturation_threshold_high)
                ]

                if len(non_saturated) > 0:
                    current_rms[ch_idx] = np.sqrt(np.mean(non_saturated**2))
                else:
                    current_rms[ch_idx] = 0.0

            if len(current_rms) >= 64 and len(self.mvc_rms) >= 64:
                normalized_rms = current_rms[:64] / (self.mvc_rms[:64] + 1e-10)
                normalized_rms = np.clip(normalized_rms, 0, 1)
                heatmap_tab = self._get_tab(HeatmapTab)
                if heatmap_tab:
                    heatmap_tab.update_heatmap(normalized_rms)
        except Exception:
            pass

    def update_plot(self):
        """Main plot update loop - draws whenever timer is running."""
        # Simplified logic: if timer is running, draw plots
        # Timer is controlled by streaming_controller, so this implicitly respects streaming state
        if not self.is_paused:  # Only respect manual pause button
            self.track_manager.draw_all_tracks()
            self.update_heatmap()

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
                self.receiver_thread.wait(2000)  # Wait max 2 seconds
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
        print("[INIT] stage_output signal connected to recording_manager.on_data_for_recording")
        # DON'T start thread here - let streaming controller manage it
        print("[INIT] Receiver thread created but not started yet")

        # Initialize streaming controller now that receiver is ready
        self.streaming_controller = StreamingController(self.timer, self.receiver_thread)
        self.streaming_controller.status_update.connect(self.update_status)
        print("[INIT] Streaming controller initialized")

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

    def open_calibration_dialog(self):
        """Open calibration dialog. This method should be overridden/wrapped in main.py to handle receiver initialization."""
        if self.receiver_thread is None:
            QtWidgets.QMessageBox.warning(self, "Not Ready", 
                                         "Device not connected. Please connect device first.")
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
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
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
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
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
