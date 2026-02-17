# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None
scripts_dir = os.path.join(os.getcwd(), 'BMEG 457 scripts')

a = Analysis(
    [os.path.join(scripts_dir, 'main.py')],
    pathex=[scripts_dir],
    binaries=[],
    datas=[
        (os.path.join(scripts_dir, 'data', 'previous_session.csv'), 'data'),
    ],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OTB-EMG',
)
