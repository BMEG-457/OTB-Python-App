import socket
import sys
import time
import signal
from PyQt5 import QtWidgets, QtCore, QtGui
import struct
import numpy as np
import pyqtgraph as pg


class Config:
    DEFAULT_PLOT_TIME = 1      # seconds
    UPDATE_RATE = 16           # milliseconds (~60 FPS)
    PLOT_HEIGHT = 600          # pixels
    WINDOW_SIZE = (1200, 800)  # width, height


class Track:
    def __init__(self, title, frequency, num_channels, offset, conv_fact, plot_time=1, channel_names=None):
        self.title = title
        self.frequency = frequency
        self.num_channels = num_channels
        self.offset = offset
        self.conv_fact = conv_fact
        self.plot_time = plot_time
        self.buffer = np.zeros((num_channels, int(plot_time * frequency)))
        self.buffer_index = 0
        self.time_array = np.linspace(0, self.plot_time, self.buffer.shape[1])
        self.channel_names = channel_names if channel_names else [f"Ch {i+1}" for i in range(num_channels)]

        # Create PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumHeight(350)
        self.plot_widget.setBackground('#1e1e1e')
        self.plot_widget.setTitle(self.title, color='w', size='10pt')
        self.plot_widget.setLabel('bottom', 'Time (s)', color='w')
        
        # Set ylabel based on track type
        if 'HDsEMG' in title:
            self.plot_widget.setLabel('left', 'Amplitude (V)', color='w')
        else:
            self.plot_widget.setLabel('left', 'Amplitude (A.U.)', color='w')
        
        self.plot_widget.setXRange(0, self.plot_time)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Define colors (tab10 colormap equivalent)
        colors = [
            (31, 119, 180),   # Blue
            (255, 127, 14),   # Orange
            (44, 160, 44),    # Green
            (214, 39, 40),    # Red
            (148, 103, 189),  # Purple
            (140, 86, 75),    # Brown
            (227, 119, 194),  # Pink
            (127, 127, 127),  # Gray
            (188, 189, 34),   # Olive
            (23, 190, 207)    # Cyan
        ]
        
        # Create line objects with different colors
        self.curves = []
        for i in range(num_channels):
            color = colors[i % 10]
            pen = pg.mkPen(color=color, width=1.5)
            curve = self.plot_widget.plot(self.time_array, np.zeros_like(self.time_array), 
                                         pen=pen, name=self.channel_names[i])
            self.curves.append(curve)
        
        # Add legend if 8 or fewer channels
        if num_channels <= 8:
            legend = self.plot_widget.addLegend(offset=(10, 10))
            legend.setParentItem(self.plot_widget.getPlotItem())

    def feed(self, packet):
        packet_size = packet.shape[1]
        # Use buffer management
        if self.buffer_index + packet_size > self.buffer.shape[1]:
            # Calculate exactly how much data fits at the end
            end_space = self.buffer.shape[1] - self.buffer_index
            if end_space > 0:
                self.buffer[:, self.buffer_index:] = packet[:, :end_space]
            self.buffer[:, :packet_size-end_space] = packet[:, end_space:]
            self.buffer_index = packet_size - end_space
        else:
            self.buffer[:, self.buffer_index:self.buffer_index + packet_size] = packet
            self.buffer_index = (self.buffer_index + packet_size) % self.buffer.shape[1]

    def draw(self):
        # Update curve data
        for index, curve in enumerate(self.curves):
            curve.setData(self.time_array, self.buffer[index, :] * self.conv_fact)

    def update_plot_time(self, new_time):
        """Update the plot time window."""
        # Create new buffer with new size
        new_buffer = np.zeros((self.num_channels, int(new_time * self.frequency)))
        
        # Copy existing data if possible
        if self.buffer_index > 0:
            # Calculate how much data to copy
            copy_size = min(new_buffer.shape[1], self.buffer.shape[1])
            new_buffer[:, -copy_size:] = self.buffer[:, -copy_size:]
        
        # Update track properties
        self.plot_time = new_time
        self.buffer = new_buffer
        self.buffer_index = min(self.buffer_index, new_buffer.shape[1])
        self.time_array = np.linspace(0, self.plot_time, self.buffer.shape[1])
        
        # Update plot x-axis and curve data
        self.plot_widget.setXRange(0, new_time)
        for curve in self.curves:
            curve.setData(self.time_array, np.zeros_like(self.time_array))


class DataReceiverThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(np.ndarray)
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, device, client_socket, tracks):
        super().__init__()
        self.device = device
        self.client_socket = client_socket
        self.tracks = tracks
        self.running = True
        self.packet_count = 0
        self.last_time = time.time()
        self.fps = 0
        
        # Recording state
        self.is_recording = False
        self.recording_data = []
        self.recording_start_time = None

    def run(self):
        while self.running:
            try:
                data = self.client_socket.recv(self.device.nchannels * 2 * (self.device.frequency // 16))
                if not data:
                    print("No data received, connection may be closed")
                    break

                unpacked_data = struct.unpack(f'>{len(data) // 2}h', data)
                reshaped_data = np.array(unpacked_data).reshape((-1, self.device.nchannels)).T

                # Feed data to tracks based on their channel_indices mapping
                for track in self.tracks:
                    if hasattr(track, 'channel_indices'):
                        track_data = reshaped_data[track.channel_indices, :]
                        track.feed(track_data)
                    else:
                        print(f"Warning: Track {track.title} has no channel_indices")

                self.data_received.emit(reshaped_data)
                
                # Record data if recording is active (only HDsEMG 64 channels)
                if self.is_recording:
                    hdemg_data = reshaped_data[:64, :]
                    current_time = time.time()
                    
                    for sample_idx in range(hdemg_data.shape[1]):
                        timestamp = current_time - self.recording_start_time
                        sample_data = hdemg_data[:, sample_idx]
                        self.recording_data.append((timestamp, sample_data))
                
                # Calculate FPS every 100 packets
                self.packet_count += 1
                if self.packet_count % 100 == 0:
                    current_time = time.time()
                    elapsed = current_time - self.last_time
                    self.fps = 100 / elapsed if elapsed > 0 else 0
                    self.last_time = current_time
                    self.status_update.emit(f"Data rate: {self.fps:.1f} packets/second")
                    
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def stop(self):
        print("Stopping data receiver thread")
        self.running = False
    
    def start_recording(self):
        """Start recording HDsEMG data."""
        self.recording_data = []
        self.recording_start_time = time.time()
        self.is_recording = True
        print("Recording started")
    
    def stop_recording(self):
        """Stop recording and return collected data."""
        self.is_recording = False
        print(f"Recording stopped. Collected {len(self.recording_data)} samples")
        return self.recording_data


class Soundtrack(QtWidgets.QWidget):
    def __init__(self, device, client_socket):
        super().__init__()
        self.device = device
        self.client_socket = client_socket
        self.tracks = []
        self.plot_time = Config.DEFAULT_PLOT_TIME
        self.is_paused = False

        self.setWindowTitle("Sessantaquattro+ Data Visualization")
        self.setGeometry(100, 100, *Config.WINDOW_SIZE)

        # Create main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Create menu bar widget
        self.menu_widget = QtWidgets.QWidget()
        self.menu_layout = QtWidgets.QHBoxLayout(self.menu_widget)

        # Create and setup the combo box for plot time
        self.time_selector = QtWidgets.QComboBox()
        self.time_selector.addItems(['100ms', '250ms', '500ms', '1s', '5s', '10s'])
        self.time_selector.setCurrentText(f"{Config.DEFAULT_PLOT_TIME}s")
        self.time_selector.currentTextChanged.connect(self.change_plot_time)

        # Add label and combo box to menu layout
        self.menu_layout.addWidget(QtWidgets.QLabel("Plot Time:"))
        self.menu_layout.addWidget(self.time_selector)
        
        # Add pause button
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.toggle_pause)
        self.menu_layout.addWidget(self.pause_button)
        
        # Add record button
        self.record_button = QtWidgets.QPushButton("Start Recording")
        self.record_button.setCheckable(True)
        self.record_button.toggled.connect(self.toggle_recording)
        self.menu_layout.addWidget(self.record_button)

        # Add status label
        self.status_label = QtWidgets.QLabel("Ready")
        self.menu_layout.addWidget(self.status_label)
        
        # Add stretch to push widgets to the left
        self.menu_layout.addStretch()  
        
        # Add menu widget to main layout
        self.main_layout.addWidget(self.menu_widget)
        
        # Create scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create widget to hold plots
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        
        # Add scroll area to main layout
        self.main_layout.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.init_tracks()

        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(Config.UPDATE_RATE)

        self.receiver_thread = DataReceiverThread(self.device, self.client_socket, self.tracks)
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.start()

    def init_tracks(self):
        """Initialize tracks with 8x8 HDsEMG grid displayed as rows and columns."""
        # Store mapping from channel index to (row, col) for the 8x8 grid
        self.hdemg_grid_channels = np.zeros((8, 8), dtype=int)
        for col in range(8):
            for row in range(8):
                channel_idx = col * 8 + (7 - row)
                self.hdemg_grid_channels[row, col] = channel_idx
        
        conv_fact = 0.000000286  # Conversion factor for HDsEMG
        
        # Create 8 row tracks
        for row in range(8):
            channel_list = self.hdemg_grid_channels[row, :].tolist()
            channel_str = ', '.join([str(ch + 1) for ch in channel_list])
            title = f'HDsEMG Row {row + 1} (Ch: {channel_str})'
            
            # Create channel names for the legend
            channel_names = [f"Ch {ch + 1}" for ch in channel_list]
            
            track = Track(title, self.device.frequency, 8, offset=0, conv_fact=conv_fact, 
                         plot_time=self.plot_time, channel_names=channel_names)
            
            # Store which channels this track should display
            track.grid_type = 'row'
            track.grid_index = row
            track.channel_indices = channel_list
            
            self.tracks.append(track)
            self.scroll_layout.addWidget(track.plot_widget)
        
        # Create 8 column tracks
        for col in range(8):
            channel_list = self.hdemg_grid_channels[:, col].tolist()
            channel_str = ', '.join([str(ch + 1) for ch in channel_list])
            title = f'HDsEMG Column {col + 1} (Ch: {channel_str})'
            
            # Create channel names for the legend
            channel_names = [f"Ch {ch + 1}" for ch in channel_list]
            
            track = Track(title, self.device.frequency, 8, offset=0, conv_fact=conv_fact, 
                         plot_time=self.plot_time, channel_names=channel_names)
            
            # Store which channels this track should display
            track.grid_type = 'column'
            track.grid_index = col
            track.channel_indices = channel_list
            
            self.tracks.append(track)
            self.scroll_layout.addWidget(track.plot_widget)
        
        # Don't add stretch - let plots take their natural size for better scrolling
        # self.scroll_layout.addStretch()

    def change_plot_time(self, time_str):
        # Convert string time to seconds
        if time_str.endswith('ms'):
            new_time = float(time_str[:-2]) / 1000
        else:
            new_time = float(time_str[:-1])
        
        print(f"Changing plot time to {new_time} seconds")
        
        # Update plot time for all tracks
        for track in self.tracks:
            track.update_plot_time(new_time)

    def toggle_pause(self, checked):
        self.is_paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        if checked:
            self.timer.stop()
            print("Visualization paused")
        else:
            self.timer.start(Config.UPDATE_RATE)
            print("Visualization resumed")
    
    def toggle_recording(self, checked):
        """Toggle recording on/off."""
        if checked:
            self.receiver_thread.start_recording()
            self.record_button.setText("Stop Recording")
            self.status_label.setText("Recording...")
        else:
            recording_data = self.receiver_thread.stop_recording()
            self.record_button.setText("Start Recording")
            self.save_recording_to_csv(recording_data)

    def save_recording_to_csv(self, recording_data):
        """Save recorded HDsEMG data to CSV file."""
        if not recording_data:
            self.status_label.setText("No data to save")
            QtWidgets.QMessageBox.warning(self, "No Data", "No data was recorded.")
            return
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hdemg_recording_{timestamp}.csv"
        
        try:
            import csv
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                header = ['Timestamp'] + [f'Channel_{i+1}' for i in range(64)]
                writer.writerow(header)
                
                for timestamp, channel_data in recording_data:
                    row = [timestamp] + channel_data.tolist()
                    writer.writerow(row)
            
            message = f"Saved {len(recording_data)} samples to {filename}"
            print(message)
            self.status_label.setText(message)
            QtWidgets.QMessageBox.information(self, "Recording Saved", message)
            
        except Exception as e:
            error_msg = f"Error saving recording: {e}"
            print(error_msg)
            self.status_label.setText("Save failed")
            QtWidgets.QMessageBox.critical(self, "Save Error", error_msg)

    def update_status(self, message):
        self.status_label.setText(message)

    def update_plot(self):
        if not self.is_paused:
            for track in self.tracks:
                track.draw()

    def closeEvent(self, event):
        print("Closing application")
        self.receiver_thread.stop()
        self.receiver_thread.wait()
        self.client_socket.close()
        event.accept()


class SessantaquattroPlus:
    def __init__(self, host="0.0.0.0", port=45454):
        self.host = host
        self.port = port
        self.nchannels = 72
        self.frequency = 2000
        self.server_socket = None
        self.client_socket = None

    def get_num_channels(self, NCH, MODE):
        """Calculate number of channels based on NCH and MODE settings"""
        if NCH == 0:  # 8 channels
            return 12 if MODE == 1 else 16
        elif NCH == 1:  # 16 channels
            return 16 if MODE == 1 else 24
        elif NCH == 2:  # 32 channels
            return 24 if MODE == 1 else 40
        elif NCH == 3:  # 64 channels
            return 40 if MODE == 1 else 72
        return 72

    def get_sampling_frequency(self, FSAMP, MODE):
        """Calculate sampling frequency based on FSAMP and MODE settings"""
        if MODE == 3:  # Accelerometer mode
            frequencies = {
                0: 2000,
                1: 4000,
                2: 8000,
                3: 16000
            }
        else:  # Other modes
            frequencies = {
                0: 500,
                1: 1000,
                2: 2000,
                3: 4000
            }
        return frequencies.get(FSAMP, 2000)

    def create_command(self, FSAMP=2, NCH=3, MODE=0, HRES=0, HPF=0, EXTEN=0, TRIG=0, REC=0, GO=1):
        self.nchannels = self.get_num_channels(NCH, MODE)
        self.frequency = self.get_sampling_frequency(FSAMP, MODE)

        Command = 0
        Command = Command + GO
        Command = Command + (REC << 1)
        Command = Command + (TRIG << 2)
        Command = Command + (EXTEN << 4)
        Command = Command + (HPF << 6)
        Command = Command + (HRES << 7)
        Command = Command + (MODE << 8)
        Command = Command + (NCH << 11)
        Command = Command + (FSAMP << 13)

        binary_command = format(Command, '016b')
        print(f"Command in binary: {binary_command}")
        return Command

    def start_server(self):
        command = self.create_command()
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            print(f"Server listening on {self.host}:{self.port}...")

            self.client_socket, addr = self.server_socket.accept()
            print(f"Connection accepted from {addr}")
            self.client_socket.send(command.to_bytes(2, byteorder='big', signed=True))

        except socket.error as e:
            print(f"Error creating server: {e}")
            sys.exit(1)

    def stop_server(self):
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()

def main():
    app = QtWidgets.QApplication([])
    
    # Set PyQtGraph dark theme
    pg.setConfigOption('background', '#1e1e1e')
    pg.setConfigOption('foreground', 'w')
    
    # Create device instance
    device = SessantaquattroPlus()
    
    # Configure device with specific parameters
    FSAMP = 0  # 2000 Hz
    NCH = 0    # 64 channels
    MODE = 0   # Standard mode
    HRES = 0   # Normal resolution
    HPF = 0    # High-pass filter enabled
    EXTEN = 0  # External trigger disabled
    TRIG = 0   # Trigger mode disabled
    REC = 0    # Recording disabled
    GO = 0     # Start acquisition

    # Create command and configure device
    command = device.create_command(
        FSAMP=FSAMP, NCH=NCH, MODE=MODE, 
        HRES=HRES, HPF=HPF, EXTEN=EXTEN, 
        TRIG=TRIG, REC=REC, GO=GO
    )
    
    # Start server with configured command
    device.start_server()

    # Create and show application window
    window = Soundtrack(device, device.client_socket)
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()