# -*- mode: python ; coding: utf-8 -*-

import glob as _glob
import os
import sys

block_cipher = None
scripts_dir = SPECPATH  # directory containing this spec file (desktop_app/)

# Locate runtime DLL sources
_py_dir = os.path.dirname(sys.executable)
import PyQt5 as _PyQt5
_qt_bin = os.path.join(os.path.dirname(_PyQt5.__file__), 'Qt5', 'bin')

# Collect VC++ and MSVC runtime DLLs — required on machines without Visual C++ Redistributable
_runtime_patterns = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'concrt140.dll',
]
_qt_extra_patterns = [
    'd3dcompiler_47.dll',   # Direct3D shader compiler (Qt OpenGL backend)
    'libEGL.dll',           # EGL interface (Qt ANGLE renderer)
    'libGLESv2.dll',        # OpenGL ES 2.0 (Qt ANGLE renderer)
    'opengl32sw.dll',       # Software OpenGL fallback (no GPU driver needed)
]

_seen = {}
for _pat in _runtime_patterns:
    for _src in [_py_dir, _qt_bin]:
        _path = os.path.join(_src, _pat)
        if os.path.exists(_path) and _pat.lower() not in _seen:
            _seen[_pat.lower()] = _path
for _pat in _qt_extra_patterns:
    _path = os.path.join(_qt_bin, _pat)
    if os.path.exists(_path) and _pat.lower() not in _seen:
        _seen[_pat.lower()] = _path

# dest '.' places DLLs alongside the exe in the _internal folder root
_extra_binaries = [(_path, '.') for _path in _seen.values()]

a = Analysis(
    [os.path.join(scripts_dir, 'main.py')],
    pathex=[scripts_dir],
    binaries=_extra_binaries,
    datas=[],
    hiddenimports=[
        'scipy.signal',
        'scipy.ndimage',
        'scipy.special',
        'scipy.fft',
        'scipy.fft._pocketfft',
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OTB-EMG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,      # UPX disabled: causes antivirus false positives on end-user machines
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,      # UPX disabled: causes antivirus false positives on end-user machines
    upx_exclude=[],
    name='OTB-EMG',
)
