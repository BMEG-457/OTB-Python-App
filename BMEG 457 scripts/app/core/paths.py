import sys
import os


def _is_frozen():
    return getattr(sys, 'frozen', False)


def get_base_dir():
    """Root directory for user-writable data (next to the exe when frozen, or BMEG 457 scripts/ when running from source)."""
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_recordings_dir():
    return os.path.join(get_base_dir(), 'recordings')


def get_data_dir():
    return os.path.join(get_base_dir(), 'data')


def get_config_path():
    return os.path.join(get_base_dir(), 'config.json')


def get_bundled_resource(relative_path):
    """Resolve a path to a read-only resource bundled inside the exe (via sys._MEIPASS)."""
    if _is_frozen():
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(get_base_dir(), relative_path)
