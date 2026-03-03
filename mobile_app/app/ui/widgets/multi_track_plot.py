"""Multi-track stacked EMG plot widget rendered via Kivy canvas."""

import numpy as np
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import sp
from app.core import config as CFG


class MultiTrackPlotWidget(Widget):
    """Vertically stacked rolling plots — one track per aggregated signal.

    Each track has an independent rolling buffer of length PLOT_DISPLAY_SAMPLES.
    Call update_track(idx, samples) to feed new data, then render() once per
    60fps tick to redraw all tracks.

    Args:
        track_labels: list of str — one label per track (determines track count).
        track_colors: optional list of (r,g,b,a) tuples; cycles through
                      CFG.MULTI_TRACK_COLORS if not supplied.
    """

    def __init__(self, track_labels, track_colors=None, **kwargs):
        super().__init__(**kwargs)
        self._n = len(track_labels)
        self._labels = track_labels
        self._buffers = [np.zeros(CFG.PLOT_DISPLAY_SAMPLES) for _ in range(self._n)]

        palette = track_colors or CFG.MULTI_TRACK_COLORS
        self._colors = [palette[i % len(palette)] for i in range(self._n)]

        # Pre-allocate canvas instructions: one background rect + one line per track
        self._rects = []
        self._lines = []
        with self.canvas:
            for i in range(self._n):
                Color(*CFG.PLOT_BG_RGBA)
                self._rects.append(Rectangle(pos=self.pos, size=self.size))
                Color(*self._colors[i])
                self._lines.append(Line(points=[], width=1))

        self.bind(pos=self._update_layout, size=self._update_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_track(self, idx, samples):
        """Roll new samples into one track buffer.

        Args:
            idx: track index (0-based).
            samples: 1-D np.ndarray of new samples.
        """
        if idx < 0 or idx >= self._n:
            return
        n = len(samples)
        buf = self._buffers[idx]
        if n >= CFG.PLOT_DISPLAY_SAMPLES:
            self._buffers[idx] = samples[-CFG.PLOT_DISPLAY_SAMPLES:]
        else:
            self._buffers[idx] = np.roll(buf, -n)
            self._buffers[idx][-n:] = samples

    def render(self):
        """Redraw all tracks. Call once per 60fps tick."""
        if self.width == 0 or self.height == 0:
            return
        track_h = self.height / self._n
        for i in range(self._n):
            y_base = self.y + (self._n - 1 - i) * track_h
            self._rects[i].pos  = (self.x, y_base)
            self._rects[i].size = (self.width, track_h)
            self._draw_track(i, self._buffers[i], y_base, track_h)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_layout(self, *args):
        self.render()

    def _draw_track(self, idx, buf, y_base, track_h):
        """Draw a single track in its allocated horizontal strip."""
        ds  = buf[::CFG.PLOT_DOWNSAMPLE]
        n   = len(ds)
        if n < 2:
            self._lines[idx].points = []
            return

        buf_min = ds.min()
        buf_max = ds.max()
        span    = buf_max - buf_min

        if span == 0:
            ys = np.full(n, y_base + track_h * 0.5)
        else:
            # 80% of strip height, 10% padding top and bottom
            ys = y_base + ((ds - buf_min) / span) * track_h * 0.8 + track_h * 0.1

        xs  = self.x + np.arange(n) * (self.width / (n - 1))
        pts = np.empty(2 * n, dtype=float)
        pts[0::2] = xs
        pts[1::2] = ys
        self._lines[idx].points = list(pts)
