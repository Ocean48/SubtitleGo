# Contributing to SubtitleGo

Thank you for your interest in contributing to SubtitleGo! This document provides guidelines and instructions for setting up your development environment, submitting bug reports, feature requests, and contributing code changes.

---

## Code of Conduct

All contributors and participants are expected to maintain a respectful, welcoming, and collaborative environment.

---

## Getting Started

### 1. Fork and Clone
```bash
git clone https://github.com/<your-username>/SubtitleGo.git
cd SubtitleGo
```

### 2. Set Up a Virtual Environment
```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install PyTorch and Dependencies
Install PyTorch compatible with your hardware (CUDA or CPU):
```bash
# NVIDIA RTX 50-Series (Blackwell sm_120, CUDA 12.8):
pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# NVIDIA RTX 40 / 30 / 20 Series (CUDA 12.4 / 12.1):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# CPU only:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Install application dependencies:
```bash
pip install -r requirements.txt
```

### 4. Download FFmpeg Binaries (Windows)
```bash
python download_ffmpeg.py
```

### 5. Run the Application
```bash
python src/main.py
```

---

## Running Tests

Before submitting changes, run the automated test suite to verify subtitle formatting, audio segmentation, and pacing calculations:
```bash
python test_subtitle_pipeline.py
```

---

## Building Standalone Packages

To test executable packaging locally:
```bash
python build.py --no-zip
```

To create a full release archive:
```bash
python build.py
```

---

## Pull Request Guidelines

1. **Create a Topic Branch**: Create a descriptive branch from `main` (e.g., `feature/pacing-algorithm` or `fix/srt-timestamp-parser`).
2. **Follow Code Conventions**:
   - Write clean, readable, well-commented Python.
   - Use PEP 8 formatting standards.
   - Maintain separation of concerns between core logic (`src/core/`) and Qt UI widgets (`src/ui/`).
3. **Test Your Changes**: Ensure all tests in `test_subtitle_pipeline.py` pass.
4. **Submit Pull Request**: Open a PR against the `main` branch with a clear summary of your changes.
