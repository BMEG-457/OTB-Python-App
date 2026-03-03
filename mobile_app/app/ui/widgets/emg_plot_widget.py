"""Real-time EMG plot widget rendered via Kivy canvas (no matplotlib)."""

import numpy as np
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from app.core import config as CFG


class EMGPlotWidget(Widget):
    """Rolling single-channel EMG plot.

    Displays the last CFG.PLOT_DISPLAY_SAMPLES samples of one channel,
    downsampled by CFG.PLOT_DOWNSAMPLE for performance.
    Call update(data) with a (channels, samples) array on each packet.
    """

    def __init__(self, channel_index=CFG.PLOT_CHANNEL_INDEX, **kwargs):
        super().__init__(**kwargs)
        self.channel_index = channel_index
        self._buffer = np.zeros(CFG.PLOT_DISPLAY_SAMPLES)

        with self.canvas:
            Color(*CFG.PLOT_BG_RGBA)
            self._rect = Rectangle(pos=self.pos, size=self.size)
            Color(*CFG.PLOT_LINE_RGBA)
            self._line = Line(points=[], width=1)

        self.bind(pos=self._update_layout, size=self._update_layout)

    def _update_layout(self, *args):
        self._rect.pos  = self.pos
        self._rect.size = self.size
        self._draw()

    def update(self, data):
        """Roll new samples into buffer. Does not redraw — call render() separately.

        Args:
            data: np.ndarray of shape (channels, samples).
        """
        if data.shape[0] <= self.channel_index:
            return

        new_samples = data[self.channel_index]
        n = len(new_samples)

        if n >= CFG.PLOT_DISPLAY_SAMPLES:
            self._buffer = new_samples[-CFG.PLOT_DISPLAY_SAMPLES:]
        else:
            self._buffer = np.roll(self._buffer, -n)
            self._buffer[-n:] = new_samples

    def render(self):
        """Redraw the canvas from the current buffer. Call from the 60fps tick."""
        self._draw()

    def _draw(self):
        buf = self._buffer[::CFG.PLOT_DOWNSAMPLE]
        n   = len(buf)
        w, h = self.width, self.height

        if n < 2 or w == 0 or h == 0:
            self._line.points = []
            return

        buf_min = buf.min()
        buf_max = buf.max()
        span    = buf_max - buf_min

        # Map signal to 80% of widget height with 10% padding top and bottom
        if span == 0:
            ys = np.full(n, self.y + h * 0.5)
        else:
            ys = self.y + ((buf - buf_min) / span) * h * 0.8 + h * 0.1

        xs  = self.x + np.arange(n) * (w / (n - 1))
        pts = np.empty(2 * n, dtype=float)
        pts[0::2] = xs
        pts[1::2] = ys
        self._line.points = list(pts)
