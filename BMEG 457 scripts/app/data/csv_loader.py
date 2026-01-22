"""CSV data loader for EMG recording files with multi-resolution preprocessing."""

import numpy as np
import csv
from scipy import signal


class CSVDataLoader:
    """Loads and parses EMG recording CSV files with multi-resolution preprocessing."""

    # Resolution levels: name -> target sample rate
    RESOLUTION_LEVELS = {
        'Raw': None,      # Original sample rate
        'L1': 500,        # 500 Hz
        'L2': 200,        # 200 Hz
        'L3': 50,         # 50 Hz
    }

    def __init__(self):
        self.data = None           # numpy array (channels, samples) - raw data
        self.timestamps = None     # numpy array of timestamps - raw
        self.channel_names = []    # list of channel names from header
        self.sample_rate = None    # estimated sample rate
        self.file_path = None

        # Multi-resolution data storage
        self.resolution_data = {}      # {level_name: (timestamps, data)}

    def load_file(self, file_path: str) -> bool:
        """Load a CSV file and parse into numpy arrays.

        Args:
            file_path: Path to the CSV file

        Returns:
            True on success, False on error
        """
        try:
            self.file_path = file_path

            # Read CSV file
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)

                # Parse header
                header = next(reader)
                # Expected format: Timestamp, Channel_1, Channel_2, ..., Channel_N
                self.channel_names = header[1:]  # Skip 'Timestamp'

                # Read all data rows
                timestamps_list = []
                data_list = []

                for row in reader:
                    if len(row) < 2:
                        continue
                    timestamps_list.append(float(row[0]))
                    data_list.append([float(x) for x in row[1:]])

            # Convert to numpy arrays
            self.timestamps = np.array(timestamps_list)
            # Transpose so shape is (channels, samples)
            self.data = np.array(data_list).T

            # Estimate sample rate
            self.sample_rate = self.estimate_sample_rate()

            print(f"[CSV] Loaded {self.file_path}")
            print(f"[CSV] Channels: {self.get_channel_count()}, Samples: {self.get_sample_count()}")
            print(f"[CSV] Duration: {self.get_duration():.2f}s, Sample rate: {self.sample_rate:.1f} Hz")

            # Precompute multi-resolution data
            self._precompute_resolutions()

            return True

        except Exception as e:
            print(f"[CSV] Error loading file: {e}")
            self.data = None
            self.timestamps = None
            self.channel_names = []
            self.sample_rate = None
            self.resolution_data = {}
            return False

    def _precompute_resolutions(self):
        """Precompute rectified and enveloped data at multiple resolutions."""
        if self.data is None or self.sample_rate is None:
            return

        print("[CSV] Precomputing multi-resolution data...")

        # First rectify the raw signal (full-wave rectification)
        rectified = np.abs(self.data)

        # Store raw resolution
        self.resolution_data['Raw'] = (self.timestamps.copy(), rectified.copy())
        print(f"[CSV]   Raw: {self.sample_rate:.0f} Hz, {rectified.shape[1]} samples")

        # Compute downsampled versions with envelope detection
        for level_name, target_rate in self.RESOLUTION_LEVELS.items():
            if target_rate is None:  # Skip raw
                continue

            if target_rate >= self.sample_rate:
                # Target rate is same or higher than source, just copy raw
                self.resolution_data[level_name] = (self.timestamps.copy(), rectified.copy())
                print(f"[CSV]   {level_name}: {self.sample_rate:.0f} Hz (no downsampling needed)")
                continue

            # Calculate decimation factor
            decimate_factor = int(self.sample_rate / target_rate)

            # Apply lowpass filter for anti-aliasing and envelope detection
            # Use a lowpass filter at half the target rate (Nyquist)
            nyquist = self.sample_rate / 2
            cutoff = target_rate / 2

            # Design lowpass filter
            try:
                b, a = signal.butter(4, cutoff / nyquist, btype='low')

                # Apply filter (envelope detection via lowpass of rectified signal)
                envelope = np.zeros_like(rectified)
                for ch in range(rectified.shape[0]):
                    envelope[ch, :] = signal.filtfilt(b, a, rectified[ch, :])

                # Decimate
                downsampled_data = envelope[:, ::decimate_factor]
                downsampled_timestamps = self.timestamps[::decimate_factor]

                self.resolution_data[level_name] = (downsampled_timestamps, downsampled_data)
                actual_rate = 1.0 / np.mean(np.diff(downsampled_timestamps)) if len(downsampled_timestamps) > 1 else 0
                print(f"[CSV]   {level_name}: {actual_rate:.0f} Hz, {downsampled_data.shape[1]} samples")

            except Exception as e:
                print(f"[CSV]   {level_name}: Error computing - {e}")
                # Fallback to simple decimation
                self.resolution_data[level_name] = (
                    self.timestamps[::decimate_factor],
                    rectified[:, ::decimate_factor]
                )

        print("[CSV] Multi-resolution preprocessing complete")

    def get_resolution_data(self, level: str):
        """Get preprocessed data at a specific resolution level.

        Args:
            level: Resolution level name ('Raw', 'L1', 'L2', 'L3')

        Returns:
            tuple: (timestamps, data) or (None, None) if not available
        """
        if level in self.resolution_data:
            return self.resolution_data[level]
        return None, None

    def get_available_resolutions(self):
        """Get list of available resolution levels."""
        return list(self.resolution_data.keys())

    def get_channel_count(self) -> int:
        """Return number of channels in loaded data."""
        if self.data is None:
            return 0
        return self.data.shape[0]

    def get_sample_count(self) -> int:
        """Return total number of samples."""
        if self.data is None:
            return 0
        return self.data.shape[1]

    def get_duration(self) -> float:
        """Return total duration in seconds."""
        if self.timestamps is None or len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    def estimate_sample_rate(self) -> float:
        """Estimate sample rate from timestamp differences."""
        if self.timestamps is None or len(self.timestamps) < 2:
            return 0.0

        # Calculate mean time difference between samples
        time_diffs = np.diff(self.timestamps)
        mean_diff = np.mean(time_diffs)

        if mean_diff > 0:
            return 1.0 / mean_diff
        return 0.0

    def is_loaded(self) -> bool:
        """Check if data has been loaded."""
        return self.data is not None and self.timestamps is not None
