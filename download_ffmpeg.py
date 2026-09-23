import os
import sys
import platform
import zipfile
import tarfile
import urllib.request
import shutil
import tempfile


import os
import sys
import platform
import zipfile
import tarfile
import urllib.request
import ssl
import shutil
import tempfile


def _get_ssl_context():
    """Creates a resilient SSL context that handles macOS Python certificate stores."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass

    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        ctx = ssl._create_unverified_context()
        return ctx


def download_ffmpeg(target_bin_dir=None):
    """
    Downloads static FFmpeg binaries and extracts ffmpeg and ffprobe to target_bin_dir (defaults to bin/).
    Supports Windows (x64), macOS (arm64 Apple Silicon & x86_64 Intel), and Linux (x64 & arm64).
    """
    if target_bin_dir is None:
        target_bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "bin"))

    os.makedirs(target_bin_dir, exist_ok=True)
    is_win = sys.platform == "win32" or os.name == "nt"

    exe_suffix = ".exe" if is_win else ""
    ffmpeg_target = os.path.join(target_bin_dir, f"ffmpeg{exe_suffix}")
    ffprobe_target = os.path.join(target_bin_dir, f"ffprobe{exe_suffix}")

    if os.path.exists(ffmpeg_target) and os.path.exists(ffprobe_target):
        if not is_win:
            os.chmod(ffmpeg_target, 0o755)
            os.chmod(ffprobe_target, 0o755)
        print(f"FFmpeg binaries already present in {target_bin_dir}")
        return True

    machine = platform.machine().lower()
    is_arm64 = machine in ("arm64", "aarch64")

    print(f"Installing FFmpeg for {sys.platform} ({machine}) into {target_bin_dir}...")

    # Helper function to download single file stream with progress
    def _download_file(download_url: str, out_path: str, desc: str):
        print(f"Downloading {desc} from {download_url}...")
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        ctx = _get_ssl_context()
        try:
            response = urllib.request.urlopen(req, context=ctx)
        except Exception:
            unverified_ctx = ssl._create_unverified_context()
            response = urllib.request.urlopen(req, context=unverified_ctx)

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 64

        with open(out_path, "wb") as out_file:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = min(100.0, (downloaded / total_size) * 100.0)
                    sys.stdout.write(f"\r{desc}: {percent:.1f}% ({downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)")
                    sys.stdout.flush()
        print()

    temp_dir = tempfile.mkdtemp()
    try:
        if is_win:
            # Gyan.dev Windows Essentials release
            zip_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            zip_path = os.path.join(temp_dir, "ffmpeg.zip")
            _download_file(zip_url, zip_path, "FFmpeg Essentials (Windows)")

            print("Extracting FFmpeg binaries...")
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.namelist():
                    filename = os.path.basename(member)
                    if filename in ["ffmpeg.exe", "ffprobe.exe"]:
                        with z.open(member) as source:
                            target_file = os.path.join(target_bin_dir, filename)
                            with open(target_file, "wb") as f:
                                shutil.copyfileobj(source, f)
                        print(f"Extracted: {os.path.join(target_bin_dir, filename)}")
        else:
            # Direct static binaries from GitHub releases (eugeneware/ffmpeg-static)
            plat_key = "darwin-arm64" if (sys.platform == "darwin" and is_arm64) else (
                "darwin-x64" if sys.platform == "darwin" else (
                    "linux-arm64" if is_arm64 else "linux-x64"
                )
            )

            ffmpeg_url = f"https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-{plat_key}"
            ffprobe_url = f"https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffprobe-{plat_key}"

            _download_file(ffmpeg_url, ffmpeg_target, "ffmpeg")
            os.chmod(ffmpeg_target, 0o755)

            _download_file(ffprobe_url, ffprobe_target, "ffprobe")
            os.chmod(ffprobe_target, 0o755)

    except Exception as e:
        print(f"\nDirect download failed: {e}")
        # Fallback: Check if system has ffmpeg installed and copy it
        sys_ffmpeg = shutil.which("ffmpeg") or ("/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else None) or ("/usr/local/bin/ffmpeg" if os.path.exists("/usr/local/bin/ffmpeg") else None)
        sys_ffprobe = shutil.which("ffprobe") or ("/opt/homebrew/bin/ffprobe" if os.path.exists("/opt/homebrew/bin/ffprobe") else None) or ("/usr/local/bin/ffprobe" if os.path.exists("/usr/local/bin/ffprobe") else None)

        if sys_ffmpeg and os.path.exists(sys_ffmpeg):
            print(f"Copying system ffmpeg from {sys_ffmpeg}...")
            shutil.copy2(sys_ffmpeg, ffmpeg_target)
            if not is_win:
                os.chmod(ffmpeg_target, 0o755)

        if sys_ffprobe and os.path.exists(sys_ffprobe):
            print(f"Copying system ffprobe from {sys_ffprobe}...")
            shutil.copy2(sys_ffprobe, ffprobe_target)
            if not is_win:
                os.chmod(ffprobe_target, 0o755)

        if not (os.path.exists(ffmpeg_target) and os.path.exists(ffprobe_target)):
            raise RuntimeError(f"Could not download or copy FFmpeg binaries to {target_bin_dir}") from e
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    print(f"\nFFmpeg successfully installed in {target_bin_dir}")
    return True

if __name__ == "__main__":
    download_ffmpeg()
