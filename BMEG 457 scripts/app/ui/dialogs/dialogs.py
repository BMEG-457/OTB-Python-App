"""Dialog classes for EMG calibration and channel/track selection."""

from PyQt5 import QtWidgets, QtCore
import numpy as np


class CalibrationDialog(QtWidgets.QDialog):
    """Modal dialog that collects RMS data during rest and contraction phases."""
    calibration_complete = QtCore.pyqtSignal(object, object, object)  # emits (baseline_rms, threshold, mvc_rms) as numpy arrays
    
    def __init__(self, parent, receiver_thread, rest_duration=5, contraction_duration=5):
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
    
    def _fix_low_channels_spatial(self, mvc_rms):
        """Fix unreasonably low channels by averaging neighbors in 8x8 grid.
        
        Assumes first 64 channels are arranged in 8x8 grid (HDsEMG channels).
        Channel mapping: channel_idx = col * 8 + (7 - row)
        where row, col are in range [0, 7]
        
        Args:
            mvc_rms: numpy array of MVC values per channel
        
        Returns:
            Fixed mvc_rms array with interpolated values for low channels
        """
        if len(mvc_rms) < 64:
            # Not enough channels for 8x8 grid, return as-is
            return mvc_rms
        
        # Only process first 64 channels (8x8 HDsEMG grid)
        grid_channels = mvc_rms[:64].copy()
        
        # Define threshold for "unreasonably low" - use median of all channels
        median_mvc = np.median(grid_channels)
        low_threshold = median_mvc * 0.1  # Channels below 10% of median are considered bad
        
        print(f"[CALIBRATION] MVC median: {median_mvc:.6f}, low threshold: {low_threshold:.6f}")
        
        # Reshape to 8x8 grid for spatial operations
        # Note: Channel mapping is col * 8 + (7 - row), so we need to reshape carefully
        grid = np.zeros((8, 8))
        for col in range(8):
            for row in range(8):
                channel_idx = col * 8 + (7 - row)
                grid[row, col] = grid_channels[channel_idx]
        
        # Find and fix low channels
        low_channels = []
        for col in range(8):
            for row in range(8):
                if grid[row, col] < low_threshold:
                    channel_idx = col * 8 + (7 - row)
                    low_channels.append(channel_idx)
                    
                    # Get neighbors in 3x3 window (excluding center)
                    neighbors = []
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue  # Skip center
                            nr, nc = row + dr, col + dc
                            if 0 <= nr < 8 and 0 <= nc < 8:
                                neighbor_val = grid[nr, nc]
                                # Only use neighbors that are above threshold
                                if neighbor_val >= low_threshold:
                                    neighbors.append(neighbor_val)
                    
                    # Replace with average of valid neighbors
                    if neighbors:
                        avg_neighbor = np.mean(neighbors)
                        grid[row, col] = avg_neighbor
                        print(f"[CALIBRATION] Fixed channel {channel_idx+1}: {grid_channels[channel_idx]:.6f} -> {avg_neighbor:.6f} (avg of {len(neighbors)} neighbors)")
                    else:
                        # No valid neighbors, use median of all channels
                        grid[row, col] = median_mvc
                        print(f"[CALIBRATION] Fixed channel {channel_idx+1}: {grid_channels[channel_idx]:.6f} -> {median_mvc:.6f} (no valid neighbors, using median)")
        
        if low_channels:
            print(f"[CALIBRATION] Fixed {len(low_channels)} low channels: {[ch+1 for ch in low_channels]}")
        else:
            print("[CALIBRATION] No low channels detected")
        
        # Convert grid back to channel array
        for col in range(8):
            for row in range(8):
                channel_idx = col * 8 + (7 - row)
                grid_channels[channel_idx] = grid[row, col]
        
        # Update mvc_rms with fixed values
        mvc_rms[:64] = grid_channels
        return mvc_rms

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
        """Collect RMS from filtered signal."""
        if stage_name == 'filtered' and self.countdown_timer.isActive():
            # Filter out saturated values before computing RMS
            # Saturation indicates hanging/disconnected electrodes
            saturation_threshold_low = -32760  # Close to -32768 (int16 min)
            saturation_threshold_high = 32760   # Close to 32767 (int16 max)
            
            # Create mask for non-saturated values
            non_saturated_mask = (data > saturation_threshold_low) & (data < saturation_threshold_high)
            
            # Compute RMS per channel (shape: channels x samples)
            # data shape is (channels, samples)
            rms_per_channel = np.zeros(data.shape[0])
            
            for ch_idx in range(data.shape[0]):
                channel_data = data[ch_idx]
                channel_mask = non_saturated_mask[ch_idx]
                
                # Only compute RMS from non-saturated samples
                valid_samples = channel_data[channel_mask]
                
                if len(valid_samples) > 0:
                    rms_per_channel[ch_idx] = np.sqrt(np.mean(valid_samples**2))
                else:
                    # All samples saturated - set to 0 (will be handled later)
                    rms_per_channel[ch_idx] = 0.0
            
            if self.current_phase == 'rest':
                self.rest_rms_values.append(rms_per_channel)
                if len(self.rest_rms_values) == 1:
                    print(f"[CALIBRATION] First rest sample collected (shape: {rms_per_channel.shape})")
            elif self.current_phase == 'contraction':
                self.contraction_rms_values.append(rms_per_channel)
                if len(self.contraction_rms_values) == 1:
                    print(f"[CALIBRATION] First contraction sample collected (shape: {rms_per_channel.shape})")
    
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
        # Debug: Show how much data was collected
        print(f"[CALIBRATION] Rest samples collected: {len(self.rest_rms_values)}")
        print(f"[CALIBRATION] Contraction samples collected: {len(self.contraction_rms_values)}")
        
        # Check if we have any data (adjust minimum required samples here)
        min_samples_required = 1  # Lower this if you want to allow calibration with less data
        
        if len(self.rest_rms_values) < min_samples_required or len(self.contraction_rms_values) < min_samples_required:
            QtWidgets.QMessageBox.warning(self, "Calibration Failed", 
                                         f"Insufficient data collected.\n"
                                         f"Rest: {len(self.rest_rms_values)} samples\n"
                                         f"Contraction: {len(self.contraction_rms_values)} samples\n"
                                         f"Required: {min_samples_required} samples each\n\n"
                                         f"Make sure streaming is active before calibration!")
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
        
        # Filter out saturation values (-32768, 32767) before calculating MVC
        # These values indicate hanging/disconnected electrodes
        mvc_rms = np.zeros(contraction_array.shape[1])  # One value per channel
        saturation_threshold_low = -32760  # Close to -32768 (int16 min)
        saturation_threshold_high = 32760   # Close to 32767 (int16 max)
        
        for ch_idx in range(contraction_array.shape[1]):
            channel_data = contraction_array[:, ch_idx]
            
            # Filter out saturated values
            non_saturated = channel_data[
                (channel_data > saturation_threshold_low) & 
                (channel_data < saturation_threshold_high)
            ]
            
            if len(non_saturated) > 0:
                # Use 99th percentile of non-saturated values as MVC
                # This is more robust than max and avoids outliers
                mvc_rms[ch_idx] = np.percentile(non_saturated, 99)
                
                # Log if we filtered out saturated values
                if len(non_saturated) < len(channel_data):
                    print(f"[CALIBRATION] Channel {ch_idx+1}: Filtered {len(channel_data) - len(non_saturated)} saturated values, "
                          f"using 99th percentile = {mvc_rms[ch_idx]:.6f}")
            else:
                # All values are saturated - this channel is likely disconnected
                # Use a very small value that will be fixed by spatial interpolation
                mvc_rms[ch_idx] = 0.0
                print(f"[CALIBRATION] Channel {ch_idx+1}: ALL VALUES SATURATED - marking for spatial interpolation")
        
        # Fix unreasonably low MVC values by spatial interpolation (8x8 grid)
        mvc_rms = self._fix_low_channels_spatial(mvc_rms)
        
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
