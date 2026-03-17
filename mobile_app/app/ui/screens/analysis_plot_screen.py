"""Static EMG plot screen for post-session data inspection."""

import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import sp

from app.core import config as CFG

_MAX_DISPLAY_PTS = 2000
_Y_PAD = 0.05  # 5% vertical padding on each side
_MIN_WINDOW = 0.05  # 50ms minimum view window
_DEFAULT_WINDOW = 5.0  # initial view window in seconds


class StaticEMGPlotWidget(Widget):
    """Canvas-based renderer for a fixed 1D signal array."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pts_y = None
        self._y_min = 0.0
        self._y_max = 0.0

        with self.canvas:
            Color(*CFG.PLOT_BG_RGBA)
            self._rect = Rectangle(pos=self.pos, size=self.size)
            Color(*CFG.PLOT_LINE_RGBA)
            self._line = Line(points=[], width=1)

        self.bind(pos=self._update_layout, size=self._update_layout)

    def set_y_range(self, y_min, y_max):
        """Set fixed Y-axis range. Call once when the full channel is known."""
        self._y_min = float(y_min)
        self._y_max = float(y_max)

    def set_signal(self, signal_1d):
        """Load a new signal for display. Downsamples to _MAX_DISPLAY_PTS."""
        if signal_1d is None or len(signal_1d) == 0:
            self._pts_y = None
            self._line.points = []
            return

        step = max(1, len(signal_1d) // _MAX_DISPLAY_PTS)
        self._pts_y = signal_1d[::step].copy()
        self._draw()

    def _update_layout(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._draw()

    def _draw(self):
        if self._pts_y is None or self.width == 0 or self.height == 0:
            self._line.points = []
            return

        n = len(self._pts_y)
        span = self._y_max - self._y_min

        # x: evenly spaced across widget width
        xs = self.x + np.linspace(0, self.width, n)

        # y: normalise to widget height with padding
        if span == 0:
            ys = np.full(n, self.y + self.height * 0.5)
        else:
            inner_h = self.height * (1.0 - 2 * _Y_PAD)
            ys = self.y + self.height * _Y_PAD + (self._pts_y - self._y_min) / span * inner_h

        pts = np.empty(2 * n)
        pts[0::2] = xs
        pts[1::2] = ys
        self._line.points = pts.tolist()


class AnalysisPlotScreen(Screen):
    """Screen that displays a static EMG signal from a loaded recording.

    Call set_data() before switching to this screen.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._data = None
        self._ts = None
        self._filename = ''
        self._channel_idx = 0

        # Time navigation state
        self._total_duration = 0.0
        self._view_start = 0.0
        self._view_duration = _DEFAULT_WINDOW
        self._slider_updating = False

        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # Top bar: back + filename
        top_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.07), padding=4, spacing=4)
        btn_back = Button(text='Back', size_hint=(0.12, 1), font_size=sp(16))
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'data_analysis'))
        self._filename_label = Label(
            text='', font_size=sp(16), bold=True,
            size_hint=(0.88, 1), halign='left', valign='middle',
        )
        self._filename_label.bind(
            size=lambda inst, _: setattr(inst, 'text_size', (inst.width, None))
        )
        top_bar.add_widget(btn_back)
        top_bar.add_widget(self._filename_label)
        root.add_widget(top_bar)

        # Channel navigation bar
        nav_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.07), padding=4, spacing=4)
        btn_prev = Button(text='<< Prev', size_hint=(0.2, 1), font_size=sp(15))
        btn_prev.bind(on_press=self._prev_ch)
        self._ch_label = Label(text='', font_size=sp(15), size_hint=(0.6, 1))
        btn_next = Button(text='Next >>', size_hint=(0.2, 1), font_size=sp(15))
        btn_next.bind(on_press=self._next_ch)
        nav_bar.add_widget(btn_prev)
        nav_bar.add_widget(self._ch_label)
        nav_bar.add_widget(btn_next)
        root.add_widget(nav_bar)

        # Plot area
        self._plot = StaticEMGPlotWidget(size_hint=(1, 0.68))
        root.add_widget(self._plot)

        # Time navigation bar: [<<] [<] [---slider---] [>] [>>]
        time_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), padding=4, spacing=4)
        btn_start = Button(text='<<', size_hint=(0.1, 1), font_size=sp(16))
        btn_start.bind(on_press=lambda x: self._go_to_start())
        btn_step_back = Button(text='<', size_hint=(0.1, 1), font_size=sp(16))
        btn_step_back.bind(on_press=lambda x: self._scroll_left())
        self._time_slider = Slider(min=0, max=1, value=0, size_hint=(0.6, 1))
        self._time_slider.bind(value=self._on_slider_changed)
        btn_step_fwd = Button(text='>', size_hint=(0.1, 1), font_size=sp(16))
        btn_step_fwd.bind(on_press=lambda x: self._scroll_right())
        btn_end = Button(text='>>', size_hint=(0.1, 1), font_size=sp(16))
        btn_end.bind(on_press=lambda x: self._go_to_end())
        time_bar.add_widget(btn_start)
        time_bar.add_widget(btn_step_back)
        time_bar.add_widget(self._time_slider)
        time_bar.add_widget(btn_step_fwd)
        time_bar.add_widget(btn_end)
        root.add_widget(time_bar)

        # Info bar: position label + zoom controls
        info_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.07), padding=4, spacing=4)
        self._pos_label = Label(text='0.00s / 0.00s', size_hint=(0.45, 1), font_size=sp(14),
                                halign='left', valign='middle')
        self._pos_label.bind(size=lambda inst, _: setattr(inst, 'text_size', (inst.width, None)))
        btn_zoom_out = Button(text='-', size_hint=(0.1, 1), font_size=sp(18))
        btn_zoom_out.bind(on_press=lambda x: self._zoom_out())
        self._window_label = Label(text='5.0s', size_hint=(0.25, 1), font_size=sp(14))
        btn_zoom_in = Button(text='+', size_hint=(0.1, 1), font_size=sp(18))
        btn_zoom_in.bind(on_press=lambda x: self._zoom_in())
        info_bar.add_widget(self._pos_label)
        info_bar.add_widget(btn_zoom_out)
        info_bar.add_widget(self._window_label)
        info_bar.add_widget(btn_zoom_in)
        root.add_widget(info_bar)

        # Spacer to fill remaining 0.03
        root.add_widget(Widget(size_hint=(1, 0.03)))

        self.add_widget(root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, data, timestamps, filename=''):
        """Load data for display. Call before switching to this screen.

        Args:
            data: np.ndarray shape (channels, samples)
            timestamps: np.ndarray shape (N,)
            filename: display name shown in the top bar
        """
        self._data = data
        self._ts = timestamps
        self._filename = filename
        self._channel_idx = 0

        # Compute total duration from timestamps
        if timestamps is not None and len(timestamps) > 1:
            self._total_duration = float(timestamps[-1] - timestamps[0])
        else:
            self._total_duration = 0.0

        # Set initial view window
        self._view_start = 0.0
        self._view_duration = min(_DEFAULT_WINDOW, self._total_duration) if self._total_duration > 0 else _DEFAULT_WINDOW
        self._update_display()

    # ------------------------------------------------------------------
    # Time navigation
    # ------------------------------------------------------------------

    def _clamp_position(self):
        if self._total_duration <= 0:
            self._view_start = 0.0
            return
        max_start = max(0, self._total_duration - self._view_duration)
        self._view_start = max(0, min(self._view_start, max_start))

    def _scroll_left(self):
        self._view_start -= self._view_duration * 0.1
        self._clamp_position()
        self._update_display()

    def _scroll_right(self):
        self._view_start += self._view_duration * 0.1
        self._clamp_position()
        self._update_display()

    def _go_to_start(self):
        self._view_start = 0.0
        self._update_display()

    def _go_to_end(self):
        self._view_start = max(0, self._total_duration - self._view_duration)
        self._update_display()

    def _zoom_in(self):
        new_dur = self._view_duration / 2
        if new_dur < _MIN_WINDOW:
            return
        center = self._view_start + self._view_duration / 2
        self._view_duration = new_dur
        self._view_start = center - self._view_duration / 2
        self._clamp_position()
        self._update_display()

    def _zoom_out(self):
        new_dur = self._view_duration * 2
        if self._total_duration > 0:
            new_dur = min(new_dur, self._total_duration)
        center = self._view_start + self._view_duration / 2
        self._view_duration = new_dur
        self._view_start = center - self._view_duration / 2
        self._clamp_position()
        self._update_display()

    def _on_slider_changed(self, instance, value):
        if self._slider_updating or self._total_duration <= 0:
            return
        center = value * self._total_duration
        self._view_start = center - self._view_duration / 2
        self._clamp_position()
        self._update_display(update_slider=False)

    def _get_normalized_position(self):
        if self._total_duration <= 0:
            return 0.0
        center = self._view_start + self._view_duration / 2
        return min(1.0, max(0.0, center / self._total_duration))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _update_display(self, update_slider=True):
        if self._data is None:
            return
        n_ch = self._data.shape[0]
        self._filename_label.text = self._filename
        self._ch_label.text = f'Channel {self._channel_idx + 1} / {n_ch}'

        # Fix Y-axis to the full channel's range
        signal = self._data[self._channel_idx]
        self._plot.set_y_range(float(signal.min()), float(signal.max()))

        # Slice visible data using time window
        if self._ts is not None and len(self._ts) > 1:
            t0 = float(self._ts[0])
            start_idx = int(np.searchsorted(self._ts, t0 + self._view_start))
            end_idx = int(np.searchsorted(self._ts, t0 + self._view_start + self._view_duration))
            end_idx = min(end_idx, len(signal))
            start_idx = min(start_idx, end_idx)
            visible = signal[start_idx:end_idx]
        else:
            visible = signal

        self._plot.set_signal(visible)

        # Update position label
        self._pos_label.text = f'{self._view_start:.2f}s / {self._total_duration:.2f}s'

        # Update window label
        if self._view_duration >= 1.0:
            self._window_label.text = f'Window: {self._view_duration:.1f}s'
        else:
            self._window_label.text = f'Window: {self._view_duration * 1000:.0f}ms'

        # Sync slider
        if update_slider:
            self._slider_updating = True
            self._time_slider.value = self._get_normalized_position()
            self._slider_updating = False

    # ------------------------------------------------------------------
    # Channel navigation
    # ------------------------------------------------------------------

    def _prev_ch(self, *_):
        if self._data is None:
            return
        self._channel_idx = (self._channel_idx - 1) % self._data.shape[0]
        self._update_display()

    def _next_ch(self, *_):
        if self._data is None:
            return
        self._channel_idx = (self._channel_idx + 1) % self._data.shape[0]
        self._update_display()
