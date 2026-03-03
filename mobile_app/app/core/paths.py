import os


def _is_android():
    try:
        import android  # noqa: F401 — available only on Android via p4a
        return True
    except ImportError:
        return False


def get_data_dir():
    """Return the writable data directory for the app.

    Priority on Android:
      1. App's own external files dir — never needs WRITE_EXTERNAL_STORAGE,
         visible in file manager at Phone/Android/data/<pkg>/files/OTB_EMG
      2. Public Documents/OTB_EMG — needs WRITE_EXTERNAL_STORAGE + legacy
         storage; only accessible after app restart post-permission-grant
      3. Kivy user_data_dir (private) — last resort, not visible to user
    On desktop: ~/OTB_EMG_Data.
    """
    if _is_android():
        # Attempt 1: use Android's Java API to obtain the external files dir.
        # getExternalFilesDir() via jnius can succeed even when direct POSIX
        # access to /storage/emulated/0/ is blocked by EMUI's SELinux policy.
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            ext = PythonActivity.mActivity.getExternalFilesDir(None)
            if ext is not None:
                path = os.path.join(ext.getAbsolutePath(), 'OTB_EMG')
                os.makedirs(path, exist_ok=True)
                test = os.path.join(path, '.write_test')
                with open(test, 'w') as f:
                    f.write('ok')
                os.remove(test)
                print(f"[PATHS] using jnius external files dir: {path}")
                return path
        except Exception as e:
            print(f"[PATHS] jnius external files dir failed: {e}")

        # Attempt 2: direct POSIX path candidates (require storage GID in process).
        package = 'org.bmeg457.otbemgapp'
        candidates = [
            f"/storage/emulated/0/Android/data/{package}/files/OTB_EMG",
            "/storage/emulated/0/Documents/OTB_EMG",
            "/sdcard/Documents/OTB_EMG",
        ]
        for path in candidates:
            try:
                os.makedirs(path, exist_ok=True)
                test = os.path.join(path, '.write_test')
                with open(test, 'w') as f:
                    f.write('ok')
                os.remove(test)
                return path
            except Exception:
                continue

        # Attempt 3: Kivy private internal storage (always accessible).
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
