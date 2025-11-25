"""
Script to plot EMG data from CSV recording file.
Plots every 8 channels in separate subplots.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

def plot_emg_channels(csv_file, channels_per_plot=8, max_channels=64):
    """
    Plot EMG data from CSV file, showing every 8th channel (1, 9, 17, 25, etc.).
    
    Parameters:
    - csv_file: path to the CSV file
    - channels_per_plot: number of channels to show per plot (default: 8)
    - max_channels: maximum number of channels to plot (default: 64 for HDsEMG)
    """
    # Read CSV file
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Get channel columns (ch_1 to ch_64 for HDsEMG)
    all_channel_cols = [col for col in df.columns if col.startswith('ch_')]
    all_channel_cols = all_channel_cols[:max_channels]  # Limit to max_channels
    
    # For an 8x8 grid, select representative channels:
    # Channels: 1, 8, 20, 23, 28, 29, 36, 37, 44, 47, 57, 64
    # This provides a good spatial distribution across the electrode array
    representative_indices = [0, 7, 18, 21, 27, 28, 35, 36, 42, 45, 56, 63]
    channel_cols = [all_channel_cols[i] for i in representative_indices if i < len(all_channel_cols)]
    
    print(f"Found {len(all_channel_cols)} total channels")
    print(f"Plotting {len(channel_cols)} representative channels from 8x8 grid:")
    for ch in channel_cols:
        ch_num = int(ch.split('_')[1])
        row = (ch_num - 1) // 8
        col = (ch_num - 1) % 8
        print(f"  {ch} (row {row}, col {col})")
    print(f"Total samples: {len(df)}")
    
    # Create time array (use timestamp if available, otherwise sample index)
    if 'timestamp' in df.columns:
        time = df['timestamp'].values - df['timestamp'].values[0]  # Start from 0
    else:
        time = np.arange(len(df))
    
    # Create one subplot per channel
    num_plots = len(channel_cols)
    
    # Create figure with subplots (shared y-axis)
    fig, axes = plt.subplots(num_plots, 1, figsize=(14, 2*num_plots), sharex=True, sharey=True)
    
    # Handle single subplot case
    if num_plots == 1:
        axes = [axes]
    
    # Calculate global y-axis limits for all channels
    all_data = []
    for ch_name in channel_cols:
        all_data.extend(df[ch_name].values)
    y_min, y_max = np.min(all_data), np.max(all_data)
    y_margin = (y_max - y_min) * 0.1
    
    # Plot each channel in its own subplot
    for idx, ch_name in enumerate(channel_cols):
        ax = axes[idx]
        
        # Get channel data
        data = df[ch_name].values
        ch_num = int(ch_name.split('_')[1])
        
        # Plot channel
        ax.plot(time, data, linewidth=0.8, color='blue', alpha=0.8)
        
        # Formatting
        ax.set_ylabel(f'Ch {ch_num}', fontsize=10)
        ax.set_ylim(y_min - y_margin, y_max + y_margin)
        ax.grid(True, alpha=0.3)
        
        # Only show x-label on bottom plot
        if idx == len(channel_cols) - 1:
            ax.set_xlabel('Time (seconds)' if 'timestamp' in df.columns else 'Sample')
        else:
            ax.set_xticklabels([])
    
    plt.tight_layout()
    
    # Save figure
    output_file = csv_file.replace('.csv', '_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
    # Show plot
    plt.show()


def plot_emg_channels_separate(csv_file, channels_per_row=8, max_channels=64):
    """
    Alternative plotting: each channel in its own subplot arranged in a grid.
    Plots every 8th channel (1, 9, 17, 25, etc.).
    
    Parameters:
    - csv_file: path to the CSV file
    - channels_per_row: number of subplots per row (default: 8)
    - max_channels: maximum number of channels to plot (default: 64)
    """
    # Read CSV file
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Get channel columns
    all_channel_cols = [col for col in df.columns if col.startswith('ch_')]
    all_channel_cols = all_channel_cols[:max_channels]
    
    # Select every 8th channel: ch_1, ch_9, ch_17, ch_25, etc.
    channel_cols = [all_channel_cols[i] for i in range(0, len(all_channel_cols), 8)]
    
    print(f"Found {len(channel_cols)} channels")
    
    # Create time array
    if 'timestamp' in df.columns:
        time = df['timestamp'].values - df['timestamp'].values[0]
    else:
        time = np.arange(len(df))
    
    # Calculate grid dimensions
    num_rows = int(np.ceil(len(channel_cols) / channels_per_row))
    
    # Create figure with grid of subplots
    fig, axes = plt.subplots(num_rows, channels_per_row, 
                            figsize=(channels_per_row*2.5, num_rows*2))
    
    # Flatten axes array for easier iteration
    if num_rows == 1:
        axes = axes.reshape(1, -1)
    axes_flat = axes.flatten()
    
    # Plot each channel
    for idx, ch_name in enumerate(channel_cols):
        ax = axes_flat[idx]
        data = df[ch_name].values
        ch_num = int(ch_name.split('_')[1])
        
        ax.plot(time, data, linewidth=0.5, color='blue')
        ax.set_title(f'Ch {ch_num}', fontsize=8)
        ax.set_xlabel('Time (s)', fontsize=7)
        ax.set_ylabel('Amp', fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, alpha=0.3)
    
    # Hide unused subplots
    for idx in range(len(channel_cols), len(axes_flat)):
        axes_flat[idx].set_visible(False)
    
    plt.tight_layout()
    
    # Save figure
    output_file = csv_file.replace('.csv', '_grid_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Grid plot saved to: {output_file}")
    
    plt.show()


if __name__ == "__main__":
    # Default file or from command line argument
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "emg_recording_20251124_103921.csv"
    
    # Choose plotting style:
    # Option 1: Stacked plot (8 channels per subplot with offset)
    print("\n=== Creating stacked plot (8 channels per subplot) ===")
    plot_emg_channels(csv_file, channels_per_plot=8, max_channels=64)
    
    # Option 2: Grid plot (each channel separate) - uncomment to use
    # print("\n=== Creating grid plot (each channel separate) ===")
    # plot_emg_channels_separate(csv_file, channels_per_row=8, max_channels=64)
