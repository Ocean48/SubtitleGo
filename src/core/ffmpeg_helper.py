import os
import sys
import shutil
import subprocess
from typing import Optional, List


def get_base_dir() -> str:
    """Returns the base application directory for both source and frozen PyInstaller execution."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_ffmpeg_path() -> str:
    """
    Resolves the path to the ffmpeg executable.
    Checks:
    1. PyInstaller MEIPASS bundled directory
    2. Executable adjacent bin/ or root
    3. Project bin/ directory
    4. Common system installation paths (/opt/homebrew/bin, /usr/local/bin)
    5. System PATH
    """
    candidates = []

    # If running in PyInstaller bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = getattr(sys, "_MEIPASS")
        candidates.append(os.path.join(meipass, "bin", "ffmpeg.exe"))
        candidates.append(os.path.join(meipass, "ffmpeg.exe"))
        candidates.append(os.path.join(meipass, "bin", "ffmpeg"))
        candidates.append(os.path.join(meipass, "ffmpeg"))

    base_dir = get_base_dir()
    candidates.append(os.path.join(base_dir, "bin", "ffmpeg.exe"))
    candidates.append(os.path.join(base_dir, "ffmpeg.exe"))
    candidates.append(os.path.join(base_dir, "bin", "ffmpeg"))
    candidates.append(os.path.join(base_dir, "ffmpeg"))

    # macOS GUI app fallback paths (when PATH is not inherited from terminal)
    if sys.platform == "darwin":
        candidates.append("/opt/homebrew/bin/ffmpeg")
        candidates.append("/usr/local/bin/ffmpeg")
        candidates.append("/opt/local/bin/ffmpeg")

    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if os.name != "nt" else os.F_OK):
            return os.path.abspath(c)

    # Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # Default fallback
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Resolves the path to the ffprobe executable."""
    candidates = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = getattr(sys, "_MEIPASS")
        candidates.append(os.path.join(meipass, "bin", "ffprobe.exe"))
        candidates.append(os.path.join(meipass, "ffprobe.exe"))
        candidates.append(os.path.join(meipass, "bin", "ffprobe"))
        candidates.append(os.path.join(meipass, "ffprobe"))

    base_dir = get_base_dir()
    candidates.append(os.path.join(base_dir, "bin", "ffprobe.exe"))
    candidates.append(os.path.join(base_dir, "ffprobe.exe"))
    candidates.append(os.path.join(base_dir, "bin", "ffprobe"))
    candidates.append(os.path.join(base_dir, "ffprobe"))

    # macOS GUI app fallback paths
    if sys.platform == "darwin":
        candidates.append("/opt/homebrew/bin/ffprobe")
        candidates.append("/usr/local/bin/ffprobe")
        candidates.append("/opt/local/bin/ffprobe")

    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if os.name != "nt" else os.F_OK):
            return os.path.abspath(c)

    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe

    return "ffprobe"


def is_ffmpeg_available() -> bool:
    """Checks if ffmpeg can be executed."""
    ffmpeg_bin = get_ffmpeg_path()
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        res = subprocess.run([ffmpeg_bin, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)
        return res.returncode == 0
    except Exception:
        return False


def run_ffmpeg(args: List[str]) -> subprocess.CompletedProcess:
    """Runs FFmpeg with no popup console window on Windows."""
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [ffmpeg_bin] + args
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)
