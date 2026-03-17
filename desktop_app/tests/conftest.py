"""Pytest configuration: add desktop_app to sys.path and provide shared fixtures."""

import sys
import os

# Ensure 'desktop_app/' is on sys.path so 'app.*' imports work from any cwd.
_here = os.path.dirname(os.path.abspath(__file__))
_desktop_app = os.path.dirname(_here)
if _desktop_app not in sys.path:
    sys.path.insert(0, _desktop_app)

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Single QApplication instance for the whole test session."""
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app
