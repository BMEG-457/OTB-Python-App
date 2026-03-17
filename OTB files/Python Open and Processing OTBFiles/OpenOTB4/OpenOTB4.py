import os
import shutil
import numpy as np
import xmltodict
import tkinter as tk
from tkinter import filedialog
import tarfile
import sys
from PyQt5 import QtWidgets
import pyqtgraph as pg

def show_graph(time, data, title="Signal", shift=0.5):
    win = QtWidgets.QMainWindow()
    win.setWindowTitle(title)

    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout()
    central_widget.setLayout(layout)

    tabs = QtWidgets.QTabWidget()
    layout.addWidget(tabs)

    n_channels = data.shape[0]
    maximus = np.max(np.abs(data))

    # --- Tab 1: Normalized Data ---
    normalized_widget = pg.PlotWidget(title="Normalized Data")
    for ch in range(n_channels):
        color = pg.intColor(ch, hues=n_channels)
        y = data[ch, :] / 2 / maximus - ch
        normalized_widget.plot(time, y, pen=pg.mkPen(color=color, width=1))
    tabs.addTab(normalized_widget, "Normalized Data")

    # --- Tab 2: Raw Data ---
    shifted_widget = pg.PlotWidget(title="Raw Data")
    for ch in range(n_channels):
        color = pg.intColor(ch, hues=n_channels)
        y = data[ch, :] - ch * shift
        shifted_widget.plot(time, y, pen=pg.mkPen(color=color, width=1))
    tabs.addTab(shifted_widget, "Raw Data")

    win.setCentralWidget(central_widget)
    win.resize(1000, 600)
    win.show()
    return win

# --- GUI File Selection ---
tk.Tk().withdraw()
filetypes = [("OTB4 files", "*.otb4"), ("Zip files", "*.zip"), ("TAR files", "*.tar")]
file_path = filedialog.askopenfilename(filetypes=filetypes)

if not file_path:
    print("No file selected.")
    sys.exit()

# --- File Handling ---
tmp_dir = 'tmpopen'
if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)
os.mkdir(tmp_dir)

# --- Extract tar ---
with tarfile.open(file_path, 'r') as tar:
    tar.extractall(tmp_dir)

# --- Parse XML ---
xml_file = [f for f in os.listdir(tmp_dir) if f.endswith('Tracks_000.xml')][0]
with open(os.path.join(tmp_dir, xml_file)) as fd:
    abs_xml = xmltodict.parse(fd.read())

track_info = abs_xml['ArrayOfTrackInfo']['TrackInfo']
if not isinstance(track_info, list):
    track_info = [track_info]

device = track_info[0]['Device'].split(';')[0]

# --- Read Parameters ---
Gains, nADBit, PowerSupply, Fsample, Path = [], [], [], [], []
nChannel, startIndex = [0], []

for track in track_info:
    Gains.append(float(track['Gain']))
    nADBit.append(int(track['ADC_Nbits']))
    PowerSupply.append(float(track['ADC_Range']))
    Fsample.append(int(track['SamplingFrequency']))
    Path.append(track['SignalStreamPath'])
    nChannel.append(int(track['NumberOfChannels']))
    startIndex.append(int(track['AcquisitionChannel']))

TotCh = sum(nChannel)

# --- Read .sig files ---
signals = sorted([f for f in os.listdir(tmp_dir) if f.endswith('.sig')])
if not signals:
    raise FileNotFoundError("No file .sig found.")

Data = []
windows = []
app = QtWidgets.QApplication(sys.argv)

if device == 'Novecento+':
    for sig_name in signals[1:]: 
        matching_blocks = [j for j, p in enumerate(Path) if p == sig_name]
        if not matching_blocks:
            print(f"No block found for {sig_name}")
            continue

        nCh = sum([nChannel[j + 1] for j in matching_blocks])
        file_path = os.path.join(tmp_dir, sig_name)

        # --- Read Binary Data ---
        with open(file_path, 'rb') as f:
            raw_data = np.fromfile(f, dtype=np.int32)
            try:
                data = raw_data.reshape((nCh, -1), order='F').astype(np.float32)
            except ValueError:
                print(f"Error in reshape of {sig_name}")
                continue

        current_ch = 0
        for j in matching_blocks:
            n_ch_block = nChannel[j + 1]
            psup = PowerSupply[j]
            adbit = nADBit[j]
            gain = Gains[j]
            for ch in range(current_ch, current_ch + n_ch_block):
                data[ch, :] = data[ch, :] * psup / (2 ** adbit) * 1000 / gain
            current_ch += n_ch_block

        Data.append(data)
        Fs = Fsample[matching_blocks[0]]
        # --- Plotting ---
        t = np.arange(data.shape[1]) / Fs
        windows.append(show_graph(t, data, title=f"Signal: {sig_name}", shift=0.5))

else:
    sig_name = signals[0]
    file_path = os.path.join(tmp_dir, sig_name)

    # --- Read Binary Data ---
    with open(file_path, 'rb') as f:
        raw_data = np.fromfile(f, dtype=np.int16)
        if raw_data.size % TotCh != 0:
            print("Error in reshape of signal.")
            sys.exit()
        data = raw_data.reshape((TotCh, -1), order='F').astype(np.float32)

    idx = [nChannel[0]]
    for val in nChannel[1:]:
        idx.append(idx[-1] + val)

    for ntype in range(1, len(track_info) + 1):
        for ch in range(idx[ntype - 1], idx[ntype]):
            data[ch, :] = data[ch, :] * PowerSupply[ntype - 1] / (2 ** nADBit[ntype - 1]) * 1000 / Gains[ntype - 1]

    Data.append(data)
    Fs = Fsample[0]
    # --- Plotting ---
    t = np.arange(data.shape[1]) / Fs
    windows.append(show_graph(t, data, title="Signal", shift=0.5))

sys.exit(app.exec_())