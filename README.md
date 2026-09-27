# SubtitleGo (Subtitle Studio)

[![GitHub Release](https://img.shields.io/github/v/release/Ocean48/SubtitleGo?color=38bdf8)](https://github.com/Ocean48/SubtitleGo/releases)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey)](https://github.com/Ocean48/SubtitleGo)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20(Qt)-green)](https://wiki.qt.io/Qt_for_Python)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A standalone, high-performance cross-platform desktop application powered by **PySide6** and **Qwen3-ASR (1.7B)** for automatic speech recognition, smart silence-based pause detection, live video playback, and natural-paced subtitle generation.

---

## Key Features

- **Direct In-Process Inference**: Runs Qwen3-ASR locally without external web servers or Docker containers. Automatic CUDA (Linux/Windows) and Apple Silicon Metal/MPS (macOS) GPU acceleration with CPU fallback.
- **Smart Pacing Engine**: Intelligent speech pause segmentation, clause splitting, line character limits (42 Latin / 18 CJK), and timestamp interpolation (target 2.0s – 4.5s per cue).
- **52 Languages & Dialects**: Multi-language recognition with automatic language detection.
- **Media Player & Subtitle Overlay**: Built-in video preview player with live synchronized high-contrast subtitle overlay.
- **Interactive Cue Studio**:
  - Live subtitle text search with instant highlight.
  - In-place text editing with real-time video sync.
  - Seek-to-timestamp on click.
  - Active cue auto-scroll and highlight during playback.
- **Bidirectional Raw Subtitle Editor**: Live synchronization across Cue Table, SRT View, and WebVTT View with one-click clipboard copy.
- **Batch Processing & Concurrency**: Multi-file batch queue with configurable worker threads (1, 2, or 4).
- **Auto-Save & ZIP Bundling**: Automatically saves `.srt` and `.vtt` alongside source media files, or exports all subtitles as a single `.zip` archive.
- **Standalone Distribution**: Portable binary packages with bundled static FFmpeg and automatic model management.

---

## Quick Start (Pre-built Release)

Pre-built binaries require no Python installation or command-line setup.

### 1. Download Release
Grab the latest package for your operating system from the [SubtitleGo Releases Page](https://github.com/Ocean48/SubtitleGo/releases):

| OS | Package | Executable |
| :--- | :--- | :--- |
| **Windows (x64)** | `SubtitleGo-v0.1.0-windows-x64.zip` | `SubtitleGo.exe` |
| **Linux (x64)** | `SubtitleGo-v0.1.0-linux-x64.zip` | `./SubtitleGo` |
| **macOS (Apple Silicon)** | `SubtitleGo-v0.1.0-macos-arm64.zip` | `SubtitleGo.app` |

### 2. Launch
1. Extract the ZIP archive to your preferred directory.
2. Launch the application (`SubtitleGo.exe` on Windows, `./SubtitleGo` on Linux, or `SubtitleGo.app` on macOS).
3. On first startup, the application provides an automated setup wizard to configure the local AI engine and download the Qwen3-ASR model weights from Hugging Face Hub if not already present.

---

## Hardware Compatibility & Acceleration

| Component | Supported / Tested | Notes |
| :--- | :--- | :--- |
| **Operating System** | **Linux (Ubuntu, Debian, Fedora, Arch)**<br>**Windows 10 / 11 (64-bit)**<br>**macOS Sonoma / Sequoia (Apple Silicon & Intel)** | Fully validated across Linux, Windows, and macOS. |
| **GPU Acceleration** | **NVIDIA RTX 20 / 30 / 40 / 50 Series** (CUDA)<br>**Apple Silicon M1 / M2 / M3 / M4 Series** (Metal / MPS) | High-speed FP16/BF16 tensor acceleration via CUDA (Linux/Windows) and Metal Performance Shaders (macOS). |
| **CPU Fallback** | Intel / AMD x64 & Apple Silicon CPU | Automatic fallback when no compatible GPU/MPS device is detected or under low VRAM conditions. |

---

## Running from Source

### Prerequisites
- **Python**: 3.10, 3.11, or 3.12 (64-bit)
- **FFmpeg**: Static binaries auto-downloaded via script, or system-installed.
- **GPU (Recommended)**: NVIDIA GPU with CUDA 11.8+ / 12.1+ / 12.8+, or Apple Silicon Mac.

### Linux System Dependencies

On Linux distributions, ensure the required multimedia and GUI libraries are installed:

- **Ubuntu / Debian / Linux Mint**:
  ```bash
  sudo apt update
  sudo apt install -y build-essential python3-dev binutils ffmpeg libsndfile1 \
                      libgl1 libegl1 libxkbcommon-x11-0 libdbus-1-3 \
                      gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                      gstreamer1.0-plugins-bad gstreamer1.0-libav libgstreamer1.0-0
  ```

- **Fedora / RHEL**:
  ```bash
  sudo dnf install -y gcc gcc-c++ python3-devel binutils ffmpeg libsndfile \
                      mesa-libGL mesa-libEGL libxkbcommon-x11 \
                      gstreamer1-plugins-base gstreamer1-plugins-good \
                      gstreamer1-plugins-bad-free gstreamer1-plugin-libav
  ```

- **Arch Linux**:
  ```bash
  sudo pacman -S base-devel binutils ffmpeg libsndfile libxkbcommon xcb-util-wm xcb-util-image \
                 gst-plugins-base gst-plugins-good gst-plugins-bad gst-libav
  ```

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ocean48/SubtitleGo.git
   cd SubtitleGo
   ```

2. **Create and activate a virtual environment**:
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

3. **Install PyTorch**:
   ```bash
   # NVIDIA RTX 50-Series (Blackwell sm_120, CUDA 12.8):
   pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

   # NVIDIA RTX 40 / 30 / 20 Series (CUDA 12.4 / 12.1):
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

   # Apple Silicon (MPS) or CPU only:
   pip install torch torchaudio
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Download static FFmpeg binaries**:
   ```bash
   python download_ffmpeg.py
   ```

6. **Launch the application**:
   ```bash
   python src/main.py
   ```

---

## Model Weights Configuration

The application resolves Qwen3-ASR model weights in the following order:

1. `./models/Qwen3-ASR-1.7B` (folder adjacent to the application root or executable)
2. Local Hugging Face cache (`~/.cache/huggingface/hub/`)
3. Automatic in-app download prompt from Hugging Face Hub (`Qwen/Qwen3-ASR-1.7B`)

To pre-download the model weights manually:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Qwen/Qwen3-ASR-1.7B', local_dir='models/Qwen3-ASR-1.7B', local_dir_use_symlinks=False)"
```

---

## Building Standalone Packages

To compile the standalone distribution package with PyInstaller:

1. **Activate your virtual environment and install dependencies**:
   ```bash
   source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
   pip install -r requirements.txt
   python download_ffmpeg.py
   ```

2. **Run the automated build script**:
   ```bash
   # Standard lightweight distribution (recommended for GitHub Releases):
   python build.py

   # Offline standalone bundle (includes pre-bundled model weights):
   python build.py --include-models

   # Fast local build without creating a .zip archive:
   python build.py --no-zip
   ```

3. **Build outputs**:
   - **`dist/SubtitleGo/`**: Portable standalone application folder containing the binary executable, bundled FFmpeg, and dependencies.
   - **`dist/SubtitleGo-v0.1.0-<platform>.zip`**: Compressed release archive ready for distribution.

---

## Project Structure

```
SubtitleGo/
├── .github/
│   ├── ISSUE_TEMPLATE/        # Structured bug report & feature request templates
│   └── workflows/ci.yml       # Automated CI test workflow
├── bin/                       # Static FFmpeg / FFprobe binaries
├── build.py                   # PyInstaller automated build & ZIP packager
├── CONTRIBUTING.md             # Contributor guidelines and workflow
├── download_ffmpeg.py         # Static FFmpeg downloader
├── models/                    # Qwen3-ASR model weights directory
├── requirements.txt           # Python package dependencies
├── src/
│   ├── __init__.py            # Package metadata & exports
│   ├── __version__.py         # Single source of truth for version constants
│   ├── main.py                # Application entry point
│   ├── core/                  # Core processing engine
│   │   ├── audio_processor.py # 16kHz WAV conversion & silence detection
│   │   ├── ffmpeg_helper.py   # FFmpeg binary auto-discovery
│   │   ├── hardware_detector.py # GPU & hardware acceleration detection
│   │   ├── model_manager.py   # Qwen3-ASR lifecycle & batch inference
│   │   ├── queue_manager.py   # Batch processing queue & concurrency
│   │   ├── runtime_manager.py # Isolated AI runtime management & pip bootstrap
│   │   ├── subtitle_formatter.py # Smart pacing, clause split & SRT/VTT parsing
│   │   └── transcription_worker.py # Background QThread transcription worker
│   └── ui/                    # PySide6 User Interface
│       ├── main_window.py     # Main application window & layout
│       ├── styles.py          # Dark theme QSS stylesheet
│       └── widgets/           # Modular Qt UI components
├── subtitle_studio.spec       # PyInstaller build specification
├── test_subtitle_pipeline.py  # Pipeline & unit test suite
├── LICENSE                    # GNU General Public License v3.0
└── README.md                  # Project documentation & release guide
```

---

## License

This project is licensed under the [GNU General Public License v3.0 (GPLv3)](LICENSE).
