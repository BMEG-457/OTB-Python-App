# OTB-Python-App: Beginner-Intermediate Guide

This document provides a comprehensive overview of the Python application found in the `/BMEG 457 scripts/app` directory. It is designed for beginner to intermediate programmers and aims to break down complex concepts into simple, understandable language.

---

## Table of Contents
1. [Project Structure](#project-structure)
2. [Core Concepts](#core-concepts)
3. [Main Components](#main-components)
    - [Core](#core)
    - [Data](#data)
    - [Managers](#managers)
    - [Processing](#processing)
    - [UI (User Interface)](#ui-user-interface)
4. [How Data Flows Through the App](#how-data-flows-through-the-app)
5. [Common Workflows](#common-workflows)
6. [Glossary](#glossary)
7. [Further Reading](#further-reading)

---

## Project Structure

The `/app` folder is organized into several subfolders, each with a specific purpose:

- `core/`: Fundamental logic and configuration for the app.
- `data/`: Handles data loading and receiving.
- `managers/`: Controls and coordinates different parts of the app.
- `processing/`: Processes and transforms data.
- `ui/`: Manages the user interface, including windows, dialogs, and tabs.
- `docs/`: Contains documentation for specific features.

Each folder contains Python files (`.py`) that define classes and functions for their respective roles.

---

## Core Concepts

### 1. **Modularity**
The app is split into modules (folders and files) so that each part of the program has a clear responsibility. This makes the code easier to understand, maintain, and extend.

### 2. **Data Flow**
Data typically enters the app through the `data/` module, is processed by the `processing/` module, managed by the `managers/`, and presented to the user via the `ui/` module.

### 3. **Object-Oriented Programming (OOP)**
Most of the code uses classes to represent things like tracks, devices, and windows. OOP helps organize code by grouping related data and functions together.

---

## Main Components

Below is a breakdown of the main files in each module, describing their purpose and what they do:

### Core
- **analysis_track.py**: Defines the `AnalysisTrack` class for displaying and analyzing EMG data. Handles multiple channels, data processing (rectification, envelope detection, RMS, lowpass filtering), and manages the view window for visualizing preprocessed data.
- **config.py**: Contains configuration settings for the app, such as default plot time, update rate, window size, and device parameters (sampling frequency, number of channels, etc.). Centralizes app-wide constants.
- **device.py**: Implements the `SessantaquattroPlus` class, which manages device communication (e.g., connecting to hardware via sockets), device configuration, and command creation for controlling the EMG device.
- **track.py**: Defines the `Track` class for plotting individual EMG signal tracks. Manages data buffers, time arrays, and sets up interactive plots with labels and units using pyqtgraph.

### Data
- **csv_loader.py**: Implements the `CSVDataLoader` class for loading and parsing EMG data from CSV files. Supports multi-resolution preprocessing (raw, 500Hz, 200Hz, 50Hz), extracts channel names, timestamps, and organizes data for analysis.
- **data_receiver.py**: Contains the `DataReceiverThread` class, which receives live data from the device over a network socket. Handles threading, data packet parsing, and emits signals for new data and status updates. Integrates with processing pipelines for real-time analysis.

### Managers
- **analysis_track_manager.py**: Manages a single analysis track for data analysis mode. Initializes tracks from loaded CSV data, manages view settings, and coordinates with the UI for displaying processed data.
- **recording_manager.py**: Handles recording EMG data and exporting it to CSV files. Manages recording state, sample limits, and emits signals for status updates and overflow events.
- **streaming_controller.py**: Controls live data streaming, manages the receiver thread, and handles starting, pausing, and resuming streaming sessions.
- **time_navigation_controller.py**: Manages time navigation for data analysis, allowing users to change the view window (zoom/scroll through data) and emits signals when the view changes.
- **track_manager.py**: Initializes and organizes EMG signal tracks based on device configuration. Manages multiple tracks (HDsEMG, AUX, Quaternions, Buffer), their containers, and feature tracks for visualization.

### Processing
- **features.py**: Provides functions for EMG feature extraction and analysis, such as RMS, mean absolute value (MAV), integrated EMG, contraction detection, fatigue analysis, and activation timing. Many functions assume a calibration phase.
- **filters.py**: Implements signal filtering functions, including bandpass, notch, moving average, rectification, and envelope extraction. Used to clean and preprocess EMG signals before analysis.
- **pipeline.py**: Defines the `ProcessingPipeline` class for chaining together multiple processing steps. Includes a registry for named pipelines, allowing flexible configuration and reuse of processing chains.
- **transforms.py**: Contains functions for frequency-domain transforms (e.g., FFT) for EMG analysis. Provides tools for spectral analysis and future expansion (STFT, wavelets, etc.).

### UI (User Interface)
- **windows/main_window.py**: Implements the main application window (`SoundtrackWindow`) for EMG data visualization and control. Integrates device setup, calibration, session loading, and provides the central hub for user interaction.
- **windows/control_window.py**: Legacy control window with start/stop recording buttons. Not currently used in the main app, but kept for reference.
- **windows/data_analysis_window.py**: Provides a window for analyzing recorded EMG data from CSV files. Integrates CSV loading, track management, and time navigation controls for reviewing sessions.
- **dialogs/dialogs.py**: Contains dialog classes for calibration, channel selection, and track visibility. Handles user input for calibration phases and configuration.
- **tabs/base_tab.py**: Defines the `BaseTab` abstract class, which standardizes the layout and structure of all tabs in the app. Ensures consistent UI with a top control bar, content area, and control panel.
- **tabs/tab_implementations.py**: Example implementations of tabs using `BaseTab`, such as a heatmap tab for visualizing HD-EMG arrays. Demonstrates how to create custom tabs with specialized visualizations.

---

## How Data Flows Through the App

1. **Data Loading:**
    - Data is loaded from files (like CSVs) or received from external sources.
2. **Processing:**
    - Raw data is cleaned, filtered, and transformed into a usable format.
3. **Management:**
    - Managers coordinate which data is being processed, recorded, or analyzed.
4. **Presentation:**
    - The processed data is displayed to the user through windows, tabs, and dialogs.

---

## Common Workflows

- **Loading Data:**
    - Use the UI to select a file. The app loads it using `csv_loader.py`.
- **Analyzing Data:**
    - Managers coordinate analysis tracks. Processing modules extract features and apply filters.
- **Recording/Streaming:**
    - The app can record sessions or stream live data, managed by the relevant manager modules.
- **Navigating Data:**
    - Time navigation allows users to move through data over time, useful for reviewing sessions.

---

## Glossary

- **Track:** A sequence of data points, often representing a signal or measurement over time.
- **Feature Extraction:** Identifying important characteristics in data (e.g., peaks, averages).
- **Filter:** A method to clean or modify data, such as removing noise.
- **Pipeline:** A series of processing steps applied to data.
- **Manager:** A class or module that coordinates actions between different parts of the app.
- **UI (User Interface):** The part of the app that users interact with directly.

---

## Further Reading

- For more details on the tab interface, see `docs/TAB_INTERFACE_GUIDE.md`.
- Explore the code in each module to see how classes and functions are implemented.
- Check out the `README.md` and `requirements.txt` for setup instructions and dependencies.

---

## Final Notes

This application is designed to be modular and extensible. As you learn more about Python and programming, you can dive deeper into each module to understand how it works and even contribute new features or improvements.

If you have questions or want to learn more, start by reading the documentation and exploring the code. Happy coding!
