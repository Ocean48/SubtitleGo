import os
import sys
import zipfile
import urllib.request
import shutil
import tempfile

def download_ffmpeg(target_bin_dir=None):
    """
    Downloads static FFmpeg essentials build for Windows and extracts ffmpeg.exe and ffprobe.exe to bin/.
    """
    if target_bin_dir is None:
        target_bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "bin"))

    os.makedirs(target_bin_dir, exist_ok=True)
    
    ffmpeg_target = os.path.join(target_bin_dir, "ffmpeg.exe")
    ffprobe_target = os.path.join(target_bin_dir, "ffprobe.exe")

    if os.path.exists(ffmpeg_target) and os.path.exists(ffprobe_target):
        print(f"FFmpeg binaries already present in {target_bin_dir}")
        return True

    # Reliable static build download URL (Gyan.dev essentials release)
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    print(f"Downloading FFmpeg from {url}...")

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "ffmpeg.zip")

    def progress(block_num, block_size, total_size):
        if total_size > 0:
            percent = min(100.0, (block_num * block_size / total_size) * 100.0)
            sys.stdout.write(f"\rDownloading: {percent:.1f}% ({block_num * block_size / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, zip_path, reporthook=progress)
        print("\nExtracting FFmpeg binaries...")

        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                filename = os.path.basename(member)
                if filename in ["ffmpeg.exe", "ffprobe.exe"]:
                    with z.open(member) as source:
                        target_file = os.path.join(target_bin_dir, filename)
                        with open(target_file, "wb") as f:
                            shutil.copyfileobj(source, f)
                    print(f"Extracted: {os.path.join(target_bin_dir, filename)}")
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    print(f"\nFFmpeg successfully installed in {target_bin_dir}")
    return True

if __name__ == "__main__":
    download_ffmpeg()
