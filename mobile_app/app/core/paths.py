import os


def _is_android():
    try:
        import android  # noqa: F401 — available only on Android via p4a
        return True
    except ImportError:
        return False


def get_data_dir():
    """Return the writable data directory for the app.

    On Android, uses /sdcard/Documents/OTB_EMG so files are visible in any
    file manager and accessible via USB without adb.  Falls back to the
    Kivy private user_data_dir if the public path cannot be created.
    On desktop, falls back to ~/OTB_EMG_Data.
    """
    if _is_android():
        public = "/sdcard/Documents/OTB_EMG"
        try:
            os.makedirs(public, exist_ok=True)
            return public
        except Exception:
            # Fallback to private app storage if public path fails
            try:
                from kivy.app import App
                app = App.get_running_app()
                if app is not None:
                    return app.user_data_dir
            except Exception:
                pass

    return os.path.join(os.path.expanduser("~"), "OTB_EMG_Data")


def get_recordings_dir():
    rec = os.path.join(get_data_dir(), "recordings")
    os.makedirs(rec, exist_ok=True)
    return rec
