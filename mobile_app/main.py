"""Kivy entry point for the OTB EMG Android app."""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager

from app.core.device import SessantaquattroPlus
from app.ui.screens.selection_screen import SelectionScreen
from app.ui.screens.live_data_screen import LiveDataScreen
from app.ui.screens.data_analysis_screen import DataAnalysisScreen


class OTBApp(App):
    def build(self):
        self.device = SessantaquattroPlus()

        sm = ScreenManager()
        sm.add_widget(SelectionScreen(name='selection'))
        sm.add_widget(LiveDataScreen(name='live_data', device=self.device))
        sm.add_widget(DataAnalysisScreen(name='data_analysis'))

        return sm

    def on_stop(self):
        """Clean up device connection when the app closes."""
        try:
            self.device.stop_server()
        except Exception:
            pass


if __name__ == '__main__':
    OTBApp().run()
