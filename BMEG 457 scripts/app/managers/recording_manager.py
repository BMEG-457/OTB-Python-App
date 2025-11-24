"""Recording manager for handling EMG data recording and CSV export."""

from PyQt5 import QtWidgets, QtCore
import csv
from datetime import datetime
import os
import time


class RecordingManager(QtCore.QObject):
    """Manages recording state and CSV export for EMG data."""
    
    # Signal emitted when recording should stop due to overflow
    overflow_stop_requested = QtCore.pyqtSignal()
    # Signal emitted when recording status changes
    status_update = QtCore.pyqtSignal(str)
    
    def __init__(self, max_samples=1000000):
        super().__init__()
        self.recording_data = []  # List of (timestamp, channel_data) tuples
        self.recording_start_time = None
        self.max_recording_samples = max_samples
        self.is_recording = False
    
    def start_recording(self):
        """Start recording data."""
        self.recording_data = []
        self.recording_start_time = time.time()
        self.is_recording = True
        print("Recording started")
        return True
    
    def stop_recording(self):
        """Stop recording data."""
        print("Recording stopped")
        self.is_recording = False
        return True
    
    def on_data_for_recording(self, stage_name, data):
        """Capture data from the receiver thread for recording.
        
        Args:
            stage_name: Name of the processing stage (should be 'final')
            data: numpy array of shape (channels, samples)
        """
        # Only record 'final' stage data (the processed data that goes to tracks)
        if stage_name != 'final' or not self.is_recording:
            return
        
        try:
            # Check for overflow protection
            if len(self.recording_data) >= self.max_recording_samples:
                # Stop recording and warn user
                self.overflow_stop_requested.emit()
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
                    self.overflow_stop_requested.emit()
                    break
                    
        except Exception as e:
            print(f"Error collecting recording data: {e}")
    
    def save_recording_to_csv(self):
        """Save recorded data to CSV file.
        
        Returns:
            tuple: (success: bool, message: str, filename: str or None)
        """
        if not self.recording_data:
            return False, "No data recorded", None
        
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
            message = f"Recording saved: {filename} ({num_samples} samples)"
            print(message)
            
            # Clear recording data to free memory
            self.recording_data = []
            self.recording_start_time = None
            
            return True, message, filename
            
        except Exception as e:
            error_msg = f"Error saving recording: {e}"
            print(error_msg)
            return False, error_msg, None
    
    def clear_recording_data(self):
        """Clear all recorded data from memory."""
        self.recording_data = []
        self.recording_start_time = None
    
    def get_recording_info(self):
        """Get information about current recording.
        
        Returns:
            dict: Information about recording (num_samples, duration, is_recording)
        """
        num_samples = len(self.recording_data)
        duration = None
        if self.recording_start_time is not None:
            duration = time.time() - self.recording_start_time
        
        return {
            'num_samples': num_samples,
            'duration': duration,
            'is_recording': self.is_recording,
            'max_samples': self.max_recording_samples
        }
