import numpy as np
import pyqtgraph as pg
from .config import Config

# individual plots
class Track:
    def __init__(self, title, frequency, num_channels, offset, conv_fact, plot_time=Config.DEFAULT_PLOT_TIME):
        self.title = title
        self.frequency = frequency
        self.num_channels = num_channels
        self.offset = offset
        self.conv_fact = conv_fact
        self.plot_time = plot_time

        self.buffer = np.zeros((num_channels, int(plot_time * frequency)))
        self.buffer_index = 0
        self.time_array = np.linspace(0, plot_time, self.buffer.shape[1])

        self.plot_widget = pg.PlotWidget(title=self.title)
        self.plot_widget.setXRange(0, self.plot_time)
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.showGrid(x=True, y=True, alpha=Config.GRID_ALPHA)
        self.plot_widget.getViewBox().setBackgroundColor(Config.PLOT_BACKGROUND_COLOR)
        self.plot_widget.setAntialiasing(Config.ENABLE_ANTIALIASING)
        if Config.ENABLE_AUTO_RANGE:
            self.plot_widget.enableAutoRange()

        # Add labels and units
        if 'HDsEMG' in title or 'channels' in title:
            self.plot_widget.setLabel("left", "Amplitude", units="V")
        else:
            self.plot_widget.setLabel("left", "Amplitude", units="A.U.")
        self.plot_widget.setLabel("bottom", "Time", units="s")

        self.curves = []
        for i in range(num_channels):
            pen = pg.mkPen(color=(255, 255, 255), width=Config.PLOT_WIDTH) if title in [
                "AUX 1", "AUX 2", "Quaternions", "Buffer", "Ramp"
            ] else pg.mkPen(color=i, width=Config.PLOT_WIDTH)

            curve_name = f"Ch {i+1}" if i < Config.MAX_LEGEND_CHANNELS or num_channels <= Config.MAX_LEGEND_CHANNELS else None
            self.curves.append(self.plot_widget.plot(pen=pen, name=curve_name))

        # by default all channels are visible; use set_visible_channels to change
        self.visible_channels = list(range(self.num_channels))

    def feed(self, packet):
        packet_size = packet.shape[1]
        # Use buffer management with proper wrap-around
        if self.buffer_index + packet_size > self.buffer.shape[1]:
            end_space = self.buffer.shape[1] - self.buffer_index
            if end_space > 0:
                self.buffer[:, self.buffer_index:] = packet[:, :end_space]
            self.buffer[:, :packet_size-end_space] = packet[:, end_space:]
            self.buffer_index = packet_size - end_space
        else:
            self.buffer[:, self.buffer_index:self.buffer_index + packet_size] = packet
            self.buffer_index = (self.buffer_index + packet_size) % self.buffer.shape[1]

    def draw(self):
        for i, curve in enumerate(self.curves):
            # draw data for channel i regardless of visibility — visibility is controlled via show()/hide()
            curve.setData(self.time_array, self.buffer[i, :] * self.conv_fact + (self.offset * i))

    def set_visible_channels(self, channels):
        """
        Show only the channels listed in `channels` (iterable of channel indices).
        Channels not listed will be hidden.
        """
        channels_set = set(int(c) for c in channels)
        self.visible_channels = sorted([c for c in channels_set if 0 <= c < self.num_channels])

        for ch_idx, curve in enumerate(self.curves):
            if ch_idx in channels_set:
                try:
                    curve.show()
                except Exception:
                    pass
            else:
                try:
                    curve.hide()
                except Exception:
                    pass

    def get_visible_channels(self):
        return list(self.visible_channels)
