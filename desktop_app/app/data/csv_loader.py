"""CSV data loader for EMG recording files."""

import numpy as np
import csv


class CSVDataLoader:
    """Loads and parses EMG recording CSV files."""

    def __init__(self):
        self.data = None           # numpy array (channels, samples) - raw data
        self.timestamps = None     # numpy array of timestamps - raw
        self.channel_names = []    # list of channel names from header
        self.sample_rate = None    # estimated sample rate
        self.file_path = None

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

            return True

        except Exception as e:
            print(f"[CSV] Error loading file: {e}")
            self.data = None
            self.timestamps = None
            self.channel_names = []
            self.sample_rate = None
            return False

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
