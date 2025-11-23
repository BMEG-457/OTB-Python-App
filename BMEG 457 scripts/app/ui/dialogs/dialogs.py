"""Dialog classes for EMG calibration and channel/track selection."""

from PyQt5 import QtWidgets, QtCore
import numpy as np


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
    """Dialog for selecting which channels to display."""
    
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
        """Return list of selected channel indices (0-based)."""
        return [i for i, cb in enumerate(self.checkboxes) if cb.isChecked()]


class TrackVisibilityDialog(QtWidgets.QDialog):
    """Dialog for selecting which tracks to display."""
    
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
        """Return list of selected track titles."""
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]
