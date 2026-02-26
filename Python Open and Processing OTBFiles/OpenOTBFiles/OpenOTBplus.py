import os
import shutil
import tarfile
import tkinter as tk
from tkinter import filedialog
import numpy as np
from PyQt5 import QtWidgets
import pyqtgraph as pg
import sys
import xmltodict

def show_graph(time, data, shift=0.05):
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Signals")

    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout()
    central_widget.setLayout(layout)

    tabs = QtWidgets.QTabWidget()
    layout.addWidget(tabs)

    n_channels = data.shape[0]
    maximus = np.max(np.abs(data))

    # --- Tab 1: Normalized Data ---
    normalized_widget = pg.PlotWidget(title="Normalized Data")
    for i in range(n_channels):
        ch = i 
        color = pg.intColor(i, hues=n_channels)
        y = data[ch, :] / 2 / maximus - i 
        normalized_widget.plot(time, y, pen=pg.mkPen(color=color, width=1))
    tabs.addTab(normalized_widget, "Normalized Data")

    # --- Tab 2: Raw Data ---
    shifted_widget = pg.PlotWidget(title="Raw Data")
    for i in range(n_channels):
        ch = i
        color = pg.intColor(i, hues=n_channels)
        y = data[ch, :] - i * shift 
        shifted_widget.plot(time, y, pen=pg.mkPen(color=color, width=1))
    tabs.addTab(shifted_widget, "Raw Data")

    win.setCentralWidget(central_widget)
    win.resize(1000, 600)
    win.show()
    sys.exit(app.exec_())

# --- GUI File Selection ---
tk.Tk().withdraw()
filetypes = [("OTB+ files", "*.otb+"), ("OTB files", "*.otb"), ("ZIP files", "*.zip")]
file_path = filedialog.askopenfilename(title="titolo", filetypes=filetypes)

if not file_path:
    raise SystemExit("No file selected.")


# --- File Handling ---
tmp_dir = 'tmpopen'
if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)
os.mkdir(tmp_dir)

# --- Extract tar or zip ---
if file_path.endswith(".zip"):
    shutil.unpack_archive(file_path, tmp_dir)
else:
    with tarfile.open(file_path, 'r') as tar:
        tar.extractall(path=tmp_dir)

# --- Read .sig files ---
signals = [f for f in os.listdir(tmp_dir) if f.endswith('.sig')]
if not signals:
    raise FileNotFoundError("No file .sig found.")

nSig = 0
sig_file = signals[nSig]
abstract_file = sig_file.replace('.sig', '.xml')
xml_path = os.path.join(tmp_dir, abstract_file)

# --- Parse XML ---
with open(xml_path) as f:
    abs_xml = xmltodict.parse(f.read())

device_name = abs_xml['Device']['@Name']
sample_freq = float(abs_xml['Device']['@SampleFrequency'])
ad_bits = int(abs_xml['Device']['@ad_bits'])
adapters = abs_xml['Device']['Channels']['Adapter']
if not isinstance(adapters, list):
    adapters = [adapters]

n_channels = 0
gains = []

for adapter in adapters:
    gain = float(adapter['@Gain'])
    start_index = int(adapter['@ChannelStartIndex'])
    channels = adapter['Channel']
    if not isinstance(channels, list):
        channels = [channels]
    for ch in channels:
        idx = int(ch['@Index'])
        pos = start_index + idx
        if len(gains) <= pos:
            gains.extend([0] * (pos - len(gains) + 1))
        gains[pos] = gain
        n_channels += 1

# --- Read Binary Data ---
with open(os.path.join(tmp_dir, sig_file), 'rb') as f:
    dtype = np.int16 if ad_bits == 16 else np.int32
    raw_data = np.fromfile(f, dtype=dtype)
    data = raw_data.reshape((n_channels, -1), order='F').astype(np.float64)

# --- Apply Gains and Scaling ---
nCh = 0
gain_array = np.array(gains)

for nad, adapter in enumerate(adapters):
    adapter_id = adapter['@ID']
    channels = adapter['Channel']
    if not isinstance(channels, list):
        channels = [channels]
    for _ in channels:
        if device_name in ['QUATTROCENTO', 'QUATTRO']:
            if adapter_id == 'Direct connection':
                data[nCh, :] *= 0.1526
            elif adapter_id == 'AdapterControl':
                pass
            else:
                data[nCh, :] *= 0.00050863
        elif device_name in ['DUE+', 'QUATTRO+']:
            if adapter_id in ['AdapterControl', 'AdapterQuaternions']:
                pass
            else:
                data[nCh, :] *= 0.00024928
        elif device_name == 'DUE':
            if adapter_id in ['AdapterControl', 'AdapterQuaternions']:
                pass
            else:
                data[nCh, :] *= 0.00025177
        elif device_name in ['SESSANTAQUATTRO', 'SESSANTAQUATTRO+']:
            if adapter_id in ['AdapterControl', 'AdapterQuaternions']:
                pass
            elif adapter_id == 'Direct connection to Auxiliary Input':
                data[nCh, :] *= 0.00014648 if ad_bits == 16 else 0.00000057220
            else:
                gain_val = gain_array[nCh]
                if ad_bits == 16:
                    gain_val = {256: 1, 128: 0.5, 64: 0.75}.get(gain_val, gain_val)
                elif ad_bits == 24:
                    gain_val = {1: 1, 0.5: 2, 0.25: 3, 0.125: 4}.get(gain_val, gain_val)
                data[nCh, :] *= (4.8 / (2 ** 24) * 1000 / gain_val)
        elif device_name == 'SYNCSTATION':
            if adapter_id in ['Due+', 'Quattro+']:
                data[nCh, :] *= 0.00024928
            elif adapter_id == 'Direct connection to Syncstation Input':
                data[nCh, :] *= 0.1526
            elif adapter_id == 'AdapterLoadCell':
                data[nCh, :] *= 0.00037217
            elif adapter_id in ['AdapterControl', 'AdapterQuaternions']:
                pass
            else:
                data[nCh, :] *= 0.00028610
        else:
            if adapter_id == 'Direct connection to Auxiliary Input':
                data[nCh, :] *= 0.00000057220
            elif adapter_id in ['AdapterControl', 'AdapterQuaternions']:
                pass
            else:
                data[nCh, :] *= (4.8 / (2 ** 24) * 1000 / gain_array[nCh])
        nCh += 1

# --- Plotting ---
time = np.arange(data.shape[1]) / sample_freq
show_graph(time, data, shift=0.05)

# --- Cleaning ---
shutil.rmtree(tmp_dir)