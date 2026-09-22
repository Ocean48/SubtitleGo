# SubtitleGo (Subtitle Studio)

[![GitHub Release](https://img.shields.io/github/v/release/Ocean48/SubtitleGo?color=38bdf8)](https://github.com/Ocean48/SubtitleGo/releases)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20(Qt)-green)](https://wiki.qt.io/Qt_for_Python)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A standalone, high-performance Windows desktop application powered by **PySide6** and **Qwen3-ASR (1.7B)** for automatic speech recognition, smart silence-based pause detection, live video playback, and natural-paced subtitle generation.

---

## Key Features

- **Direct In-Process Inference**: Runs Qwen3-ASR locally without external web servers or Docker containers. Automatic CUDA GPU acceleration with CPU fallback.
- **Smart Pacing Engine**: Intelligent speech pause segmentation, clause splitting, line character limits (42 Latin / 18 CJK), and timestamp interpolation (target 2.0s - 4.5s per cue).
- **52 Languages & Dialects**: Multi-language support with automatic language detection.
- **Media Player & Subtitle Overlay**: Built-in video preview player with live synchronized high-contrast subtitle overlay.
- **Interactive Cue Studio**:
  - Live subtitle text search with instant highlight.
  - In-place text editing with real-time video sync.
  - Seek-to-timestamp on click.
  - Active cue auto-scroll and highlight during playback.
- **Bidirectional Raw Subtitle Editor**: Live synchronization across Cue Table, SRT View, and WebVTT View with one-click clipboard copy.
- **Batch Processing & Concurrency**: Multi-file batch queue with configurable worker threads (1, 2, or 4).
- **Auto-Save & ZIP Bundling**: Automatically saves `.srt` and `.vtt` alongside source media files, or export all subtitles as a single `.zip` archive.
- **Standalone Distribution**: Portable Windows package with bundled FFmpeg and externalized model weights.

---

## Quick Start (Pre-built Windows Executable)

No Python installation or command-line setup is required to run the pre-built version.

### 1. Download Release
1. Go to the [SubtitleGo Releases Page](https://github.com/Ocean48/SubtitleGo/releases).
2. Download **`SubtitleGo-v1.0.0-windows-x64.zip`**.

### 2. Run
1. Extract the ZIP archive to any folder on your computer.
2. Double-click **`SubtitleStudio.exe`**.
3. On first startup, if model weights are not pre-bundled, the application will display a one-click download dialog to fetch the Qwen3-ASR model from Hugging Face Hub.

---

## Hardware Compatibility & Tested Environments

| Component | Tested / Supported | Notes |
| :--- | :--- | :--- |
| **Operating System** | **Windows 11 (64-bit)** (Tested)<br>Windows 10 (64-bit) | Fully tested and validated on Windows 11. |
| **GPU / Acceleration** | **NVIDIA RTX 50-Series (Blackwell architecture)** (Tested)<br>NVIDIA RTX 40 / 30 / 20 Series | High-speed FP16/BF16 tensor acceleration via CUDA. |
| **CPU Fallback** | Intel / AMD x64 processors | Automatic CPU execution fallback when no compatible CUDA GPU is detected. |

---

## Running from Source

### Prerequisites
- **Operating System**: Windows 10/11 (64-bit) (Tested on Windows 11)
- **Python**: 3.10, 3.11, or 3.12 (64-bit)
- **GPU (Recommended)**: NVIDIA GPU with CUDA 11.8+ or 12.1+ (Tested with NVIDIA RTX 50-Series; CPU mode supported)

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ocean48/SubtitleGo.git
   cd SubtitleGo
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install PyTorch with CUDA support (or CPU)**:
   ```bash
   # For NVIDIA RTX 50-Series (Blackwell sm_120, CUDA 12.8):
   pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
   
   # For NVIDIA RTX 40 / 30 / 20 Series (CUDA 12.4 / 12.1):
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
   
   # For CPU only:
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Download FFmpeg binaries**:
   Run the automated downloader to place static `ffmpeg.exe` and `ffprobe.exe` into the `bin/` folder:
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

1. `./models/Qwen3-ASR-1.7B` (folder adjacent to `main.py` or `SubtitleStudio.exe`)
2. Local Hugging Face cache (`~/.cache/huggingface/hub/`)
3. Automatic GUI download prompt from Hugging Face Hub (`Qwen/Qwen3-ASR-1.7B`)

To pre-download the model weights manually:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Qwen/Qwen3-ASR-1.7B', local_dir='models/Qwen3-ASR-1.7B', local_dir_use_symlinks=False)"
```

---

## Building the Standalone Executable (.exe)

To build the standalone Windows executable and create the release ZIP package:

1. **Activate the virtual environment**:
   Make sure you have completed the environment setup in [Running from Source](#running-from-source) and activated the `.venv`:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Ensure all dependencies and PyInstaller are installed**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure FFmpeg is present in `bin/`**:
   ```bash
   python download_ffmpeg.py
   ```

4. **Run the build script**:
   ```bash
   # Standard lightweight release (recommended for GitHub Releases):
   python build.py

   # Optional offline standalone bundle with embedded weights:
   python build.py --include-models

   # Fast compilation without creating a .zip archive:
   python build.py --no-zip
   ```

5. **Locate build outputs**:
   The script will package and output:
   - **`dist/SubtitleStudio/`**: Portable standalone application folder containing `SubtitleStudio.exe`, bundled FFmpeg binaries, and dependencies.
   - **`dist/SubtitleGo-v1.0.0-windows-x64.zip`**: Compressed release archive (~200MB) ready for distribution via GitHub Releases.

---

## Project Structure

```
SubtitleGo/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml     # Structured bug report template
│   │   └── feature_request.yml # Feature request template
│   ├── workflows/
│   │   └── ci.yml             # Automated unit test CI workflow
│   └── PULL_REQUEST_TEMPLATE.md
├── bin/                       # Bundled static FFmpeg / FFprobe binaries
│   └── .gitkeep
├── build.py                   # PyInstaller automated build & ZIP packager
├── CONTRIBUTING.md             # Contributor guidelines and workflow
├── download_ffmpeg.py         # One-click static FFmpeg downloader
├── models/                    # Qwen3-ASR model weights directory
│   └── .gitkeep
├── requirements.txt           # Python package requirements
├── src/
│   ├── __init__.py            # Package metadata & exports
│   ├── __version__.py         # Single source of truth for version constants
│   ├── main.py                # Desktop application entry point
│   ├── core/                  # In-process engine modules
│   │   ├── audio_processor.py # 16kHz WAV conversion & silence detection
│   │   ├── ffmpeg_helper.py   # FFmpeg binary auto-discovery
│   │   ├── model_manager.py   # Qwen3-ASR lifecycle & batch inference
│   │   ├── queue_manager.py   # Multi-task batch queue & concurrency
│   │   ├── subtitle_formatter.py # Smart pacing & SRT/VTT parsing
│   │   └── transcription_worker.py # Multi-stage QThread background worker
│   └── ui/                    # PySide6 Desktop UI
│       ├── main_window.py     # Main application window & split layout
│       ├── styles.py          # Dark theme QSS stylesheet
│       └── widgets/           # Modular Qt widgets
│           ├── cue_editor.py  # Searchable & editable cue table
│           ├── header_bar.py  # Hardware & GPU status indicator
│           ├── model_download_dialog.py # Model weights downloader dialog
│           ├── queue_list.py  # Drag-and-drop queue & folder loader
│           ├── raw_view.py    # Synchronized raw SRT / WebVTT editor
│           ├── settings_panel.py # Language & pacing settings panel
│           └── video_player.py # Media preview with live subtitle overlay
├── subtitle_studio.spec       # PyInstaller build specification
├── test_subtitle_pipeline.py  # Unit test suite
├── .gitignore                 # Clean repository exclusion rules
├── LICENSE                    # GNU General Public License v3.0
└── README.md                  # Project documentation & release guide
```

---

## License

This project is licensed under the [GNU General Public License v3.0 (GPLv3)](LICENSE).
