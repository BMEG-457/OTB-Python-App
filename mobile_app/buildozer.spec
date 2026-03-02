[app]

# App identity
title = OTB EMG App
package.name = otbemgapp
package.domain = org.bmeg457

# Entry point
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*

# Dependencies
# scipy, matplotlib, and kivy_matplotlib_widget have been removed.
# IIR filtering, peak detection, and resampling are implemented in
# app/processing/iir_filter.py using numpy only.
# The EMG plot widget uses Kivy's canvas directly (no matplotlib).
requirements = python3,kivy==2.3.0,numpy

# Android permissions
android.permissions = INTERNET

# Android API targets
android.api = 33
android.minapi = 21

# Build for both 64-bit and 32-bit ARM devices
android.archs = arm64-v8a, armeabi-v7a

# Force landscape for the wider plot area
orientation = landscape

# App version
version = 0.1

[buildozer]
log_level = 2
warn_on_root = 1
