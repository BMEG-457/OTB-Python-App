import numpy as np
import pandas as pd

# Parameters
sampling_rate = 1000  # Hz
duration = 60  # seconds
n_samples = sampling_rate * duration
n_channels = 64  # 8x8 array
adc_range = (0, 1024)

# Generate timestamp column (in seconds)
timestamps = np.arange(n_samples) / sampling_rate

# Create contraction periods (simulate muscle activation)
# Let's have 5 contraction periods of varying lengths
contraction_periods = [
    (5, 10),    # 5-10 seconds
    (15, 20),   # 15-20 seconds
    (25, 32),   # 25-32 seconds
    (38, 43),   # 38-43 seconds
    (50, 55)    # 50-55 seconds
]

# Initialize data matrix
emg_data = np.zeros((n_samples, n_channels))

# Generate baseline noise for all channels (resting state)
baseline_mean = 512  # Middle of ADC range
baseline_std = 15    # Small noise during rest

for ch in range(n_channels):
    emg_data[:, ch] = np.random.normal(baseline_mean, baseline_std, n_samples)

# Add contraction signals
for start, end in contraction_periods:
    start_idx = int(start * sampling_rate)
    end_idx = int(end * sampling_rate)
    
    # Generate realistic EMG during contraction
    for ch in range(n_channels):
        # Each channel has slightly different activation patterns
        amplitude = np.random.uniform(80, 150)  # Variation across channels
        
        # Generate EMG-like signal with multiple frequency components
        t = np.arange(end_idx - start_idx) / sampling_rate
        
        # Mix of frequencies typical for EMG (20-500 Hz)
        signal = 0
        for freq in [50, 80, 120, 150, 200]:
            phase = np.random.uniform(0, 2*np.pi)
            weight = np.random.uniform(0.5, 1.5)
            signal += weight * np.sin(2 * np.pi * freq * t + phase)
        
        # Normalize and scale
        signal = signal / np.max(np.abs(signal)) * amplitude
        
        # Add to baseline with smooth ramp up/down
        ramp_samples = int(0.2 * sampling_rate)  # 200ms ramp
        ramp_up = np.linspace(0, 1, ramp_samples)
        ramp_down = np.linspace(1, 0, ramp_samples)
        
        envelope = np.ones(end_idx - start_idx)
        envelope[:ramp_samples] = ramp_up
        envelope[-ramp_samples:] = ramp_down
        
        emg_data[start_idx:end_idx, ch] += signal * envelope

# Clip to ADC range and convert to integers
emg_data = np.clip(emg_data, adc_range[0], adc_range[1])
emg_data = emg_data.astype(int)

# Create DataFrame
columns = ['Timestamp'] + [f'Ch{i+1:02d}' for i in range(n_channels)]
df = pd.DataFrame(np.column_stack([timestamps, emg_data]), columns=columns)

# Save to CSV
output_file = 'data/mock_emg_data.csv'
df.to_csv(output_file, index=False, float_format='%.6f')

print(f"Generated mock EMG data:")
print(f"  - Duration: {duration} seconds")
print(f"  - Sampling rate: {sampling_rate} Hz")
print(f"  - Total samples: {n_samples}")
print(f"  - Channels: {n_channels} (8x8 array)")
print(f"  - Contraction periods: {len(contraction_periods)}")
print(f"  - File saved as: {output_file}")
print(f"\nFirst few rows:")
print(df.head())
print(f"\nData shape: {df.shape}")
