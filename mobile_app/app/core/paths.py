import os


def get_data_dir():
    """Return the writable data directory for the app.

    On Android, uses the Kivy app's private user_data_dir.
    On desktop, falls back to ~/OTB_EMG_Data.
    """
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            return app.user_data_dir
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "OTB_EMG_Data")


def get_recordings_dir():
    return os.path.join(get_data_dir(), "recordings")
