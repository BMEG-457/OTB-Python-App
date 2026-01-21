"""
Script to plot EMG data from CSV recording file.
Plots every 8 channels in separate subplots.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

def plot_emg_channels_by_rows(csv_file, max_channels=64):
    """
    Plot EMG data from CSV file, showing all 8 rows of the 8x8 grid.
    Each subplot shows all 8 channels in that row.
    
    Parameters:
    - csv_file: path to the CSV file
    - max_channels: maximum number of channels (default: 64 for HDsEMG)
    """
    # Read CSV file
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Get channel columns (ch_1 to ch_64 for HDsEMG)
    all_channel_cols = [col for col in df.columns if col.startswith('ch_')]
    all_channel_cols = all_channel_cols[:max_channels]
    
    print(f"Found {len(all_channel_cols)} total channels")
    print(f"Plotting all 8 rows of the 8x8 grid")
    
    # Create time array
    if 'timestamp' in df.columns:
        time = df['timestamp'].values - df['timestamp'].values[0]
    else:
        time = np.arange(len(df))
    
    
    # Create figure with 8 subplots (one per row)
    fig, axes = plt.subplots(8, 1, figsize=(14, 16), sharex=True, sharey=True)
    
    # Calculate global y-axis limits
    all_data = []
    for ch_name in all_channel_cols:
        all_data.extend(df[ch_name].values)
    y_min, y_max = np.min(all_data), np.max(all_data)
    y_margin = (y_max - y_min) * 0.1
    
    # Plot each row
    for row in range(8):
        ax = axes[row]
        
        # Get all channels in this row (channels 1-8, 9-16, 17-24, etc.)
        row_start = row * 8
        row_end = row_start + 8
        
        # Plot all 8 channels in this row with offset
        offset = 0
        offset_step = (y_max - y_min) * 0.3
        
        for col in range(8):
            ch_idx = row_start + col
            if ch_idx < len(all_channel_cols):
                ch_name = all_channel_cols[ch_idx]
                data = df[ch_name].values + offset
                ch_num = int(ch_name.split('_')[1])
                ax.plot(time, data, label=f'Ch {ch_num}', linewidth=0.6, alpha=0.8)
                offset -= offset_step
        
        # Formatting
        ax.set_ylabel(f'Row {row}', fontsize=10, fontweight='bold')
        ax.legend(loc='right', fontsize=7, ncol=1)
        ax.grid(True, alpha=0.3)
        
        if row == 7:
            ax.set_xlabel('Time (seconds)' if 'timestamp' in df.columns else 'Sample')
        else:
            ax.set_xticklabels([])
    
    plt.suptitle('EMG Data by Rows (8x8 Grid)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    # Save figure
    output_file = csv_file.replace('.csv', '_rows_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Rows plot saved to: {output_file}")
    
    plt.show()


def plot_emg_channels_by_columns(csv_file, max_channels=64):
    """
    Plot EMG data from CSV file, showing all 8 columns of the 8x8 grid.
    Each subplot shows all 8 channels in that column.
    
    Parameters:
    - csv_file: path to the CSV file
    - max_channels: maximum number of channels (default: 64 for HDsEMG)
    """
    # Read CSV file
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Get channel columns
    all_channel_cols = [col for col in df.columns if col.startswith('ch_')]
    all_channel_cols = all_channel_cols[:max_channels]
    
    print(f"Found {len(all_channel_cols)} total channels")
    print(f"Plotting all 8 columns of the 8x8 grid")
    
    # Create time array
    if 'timestamp' in df.columns:
        time = df['timestamp'].values - df['timestamp'].values[0]
    else:
        time = np.arange(len(df))
    
    # Create figure with 8 subplots (one per column)
    fig, axes = plt.subplots(8, 1, figsize=(14, 16), sharex=True, sharey=True)
    
    # Calculate global y-axis limits
    all_data = []
    for ch_name in all_channel_cols:
        all_data.extend(df[ch_name].values)
    y_min, y_max = np.min(all_data), np.max(all_data)
    y_margin = (y_max - y_min) * 0.1
    
    # Plot each column
    for col in range(8):
        ax = axes[col]
        
        # Get all channels in this column (ch_1, ch_9, ch_17... or ch_2, ch_10, ch_18...)
        offset = 0
        offset_step = (y_max - y_min) * 0.3
        
        for row in range(8):
            ch_idx = row * 8 + col
            if ch_idx < len(all_channel_cols):
                ch_name = all_channel_cols[ch_idx]
                data = df[ch_name].values + offset
                ch_num = int(ch_name.split('_')[1])
                ax.plot(time, data, label=f'Ch {ch_num}', linewidth=0.6, alpha=0.8)
                offset -= offset_step
        
        # Formatting
        ax.set_ylabel(f'Col {col}', fontsize=10, fontweight='bold')
        ax.legend(loc='right', fontsize=7, ncol=1)
        ax.grid(True, alpha=0.3)
        
        if col == 7:
            ax.set_xlabel('Time (seconds)' if 'timestamp' in df.columns else 'Sample')
        else:
            ax.set_xticklabels([])
    
    plt.suptitle('EMG Data by Columns (8x8 Grid)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    # Save figure
    output_file = csv_file.replace('.csv', '_columns_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Columns plot saved to: {output_file}")
    
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
    
    # Plot by rows (each subplot shows one row of 8 channels)
    print("\n=== Creating plot by rows (8 subplots, each showing 8 channels) ===")
    plot_emg_channels_by_rows(csv_file, max_channels=64)
    
    # Plot by columns (each subplot shows one column of 8 channels)
    print("\n=== Creating plot by columns (8 subplots, each showing 8 channels) ===")
    plot_emg_channels_by_columns(csv_file, max_channels=64)
    
    # Alternative: Grid plot (each channel separate) - uncomment to use
    # print("\n=== Creating grid plot (each channel separate) ===")
    # plot_emg_channels_separate(csv_file, channels_per_row=8, max_channels=64)
