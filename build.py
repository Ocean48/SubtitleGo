import os
import sys
import shutil
import platform
import argparse
import subprocess
import zipfile

# Add project root to sys.path to load version metadata
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.__version__ import __app_name__, __version__, __title__
except ImportError:
    __app_name__ = "SubtitleGo"
    __version__ = "1.0.0"
    __title__ = "SubtitleGo (Subtitle Studio)"


def get_default_platform_tag() -> str:
    """
    Returns normalized OS and architecture tag (e.g., windows-x64, linux-x64, macos-arm64).
    """
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        sys_name = "macos"

    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        arch = "x64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = machine

    return f"{sys_name}-{arch}"


def build_and_package(
    include_models: bool = False,
    create_zip: bool = True,
    custom_version: str = None,
    platform_tag: str = None,
    skip_pyinstaller: bool = False,
):
    version = custom_version or __version__
    plat_tag = platform_tag or get_default_platform_tag()

    print("========================================")
    print(f"Building {__title__}")
    print(f"Version:  v{version}")
    print(f"Platform: {plat_tag}")
    print(f"Models:   {'Bundled (Offline mode)' if include_models else 'Externalized (Standard mode)'}")
    print("========================================")

    root_dir = PROJECT_ROOT
    spec_file = os.path.join(root_dir, "subtitle_studio.spec")
    dist_app_dir = os.path.join(root_dir, "dist", "SubtitleStudio")

    # 1. Run PyInstaller
    if not skip_pyinstaller:
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", spec_file]
        print(f"Executing PyInstaller command: {' '.join(cmd)}")

        res = subprocess.run(cmd, cwd=root_dir)
        if res.returncode != 0:
            print("PyInstaller build failed.")
            sys.exit(1)
        print(f"\nPyInstaller build successful: {dist_app_dir}")
    else:
        print(f"Skipping PyInstaller compilation. Using existing build at {dist_app_dir}")

    # 2. Copy FFmpeg binaries into dist directory if present
    local_bin = os.path.join(root_dir, "bin")
    target_bin = os.path.join(dist_app_dir, "bin")
    target_app_bundle = os.path.join(root_dir, "dist", "SubtitleStudio.app")

    if os.path.exists(local_bin):
        print(f"Bundling bin directory to {target_bin}...")
        os.makedirs(target_bin, exist_ok=True)
        for item in os.listdir(local_bin):
            s = os.path.join(local_bin, item)
            d = os.path.join(target_bin, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
                if sys.platform != "win32":
                    os.chmod(d, 0o755)

        # Also copy to macOS .app bundle if present
        if os.path.exists(target_app_bundle):
            app_macos_bin = os.path.join(target_app_bundle, "Contents", "MacOS", "bin")
            os.makedirs(app_macos_bin, exist_ok=True)
            for item in os.listdir(local_bin):
                s = os.path.join(local_bin, item)
                d = os.path.join(app_macos_bin, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
                    os.chmod(d, 0o755)
        print("FFmpeg binaries bundled.")

    # 3. Handle model weights
    target_models = os.path.join(dist_app_dir, "models")
    os.makedirs(target_models, exist_ok=True)

    if include_models:
        local_models = os.path.join(root_dir, "models", "Qwen3-ASR-1.7B")
        target_qwen_models = os.path.join(target_models, "Qwen3-ASR-1.7B")
        if os.path.exists(local_models) and not os.path.exists(target_qwen_models):
            print(f"Copying local Qwen3-ASR weights to {target_qwen_models}...")
            shutil.copytree(local_models, target_qwen_models, dirs_exist_ok=True)
            if os.path.exists(target_app_bundle):
                app_models = os.path.join(target_app_bundle, "Contents", "MacOS", "models", "Qwen3-ASR-1.7B")
                shutil.copytree(local_models, app_models, dirs_exist_ok=True)
            print("Model weights copied.")
    else:
        print("Standard mode: Model weights externalized (downloadable on first run).")

    # 4. Create release ZIP package
    if create_zip:
        suffix = "-offline" if include_models else ""
        release_zip_name = f"{__app_name__}-v{version}-{plat_tag}{suffix}.zip"
        release_zip_path = os.path.join(root_dir, "dist", release_zip_name)
        print(f"\nCreating release archive: {release_zip_path} ...")

        if os.path.exists(release_zip_path):
            try:
                os.unlink(release_zip_path)
            except Exception:
                pass

        # On macOS, use Apple's native ditto tool to preserve app bundle symlinks, permissions, and resource forks
        packaged_with_ditto = False
        if sys.platform == "darwin" and os.path.exists(target_app_bundle) and shutil.which("ditto"):
            # Ensure executable permission on main binary inside bundle
            app_binary = os.path.join(target_app_bundle, "Contents", "MacOS", "SubtitleStudio")
            if os.path.exists(app_binary):
                os.chmod(app_binary, 0o755)

            cmd = ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", "SubtitleStudio.app", release_zip_path]
            res = subprocess.run(cmd, cwd=os.path.join(root_dir, "dist"))
            if res.returncode == 0:
                packaged_with_ditto = True

        if not packaged_with_ditto:
            # Select items to archive
            items_to_zip = [dist_app_dir]
            if sys.platform == "darwin" and os.path.exists(target_app_bundle):
                items_to_zip.append(target_app_bundle)

            with zipfile.ZipFile(release_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for item_dir in items_to_zip:
                    for root, _, files in os.walk(item_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, os.path.join(root_dir, "dist"))

                            zinfo = zipfile.ZipInfo.from_file(full_path, rel_path)
                            # Preserve POSIX file permissions in zip header
                            if sys.platform != "win32":
                                st = os.stat(full_path)
                                zinfo.external_attr = (st.st_mode & 0xFFFF) << 16
                            with open(full_path, "rb") as f:
                                zipf.writestr(zinfo, f.read())

        zip_size_mb = os.path.getsize(release_zip_path) / (1024 * 1024)
        print("\nPackage generated successfully!")
        print(f"Archive:    {release_zip_path} ({zip_size_mb:.2f} MB)")
        print(f"App Folder: {dist_app_dir}")
        exe_path = os.path.join(dist_app_dir, "SubtitleStudio.exe" if sys.platform == "win32" else "SubtitleStudio")
        if os.path.exists(exe_path):
            print(f"Executable: {exe_path}")
        if os.path.exists(target_app_bundle):
            print(f"macOS App:  {target_app_bundle}")
    else:
        print("\nSkipping ZIP package generation (--no-zip specified).")
        print(f"App Folder: {dist_app_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and package SubtitleGo.")
    parser.add_argument(
        "--include-models",
        action="store_true",
        help="Bundle local model weights into distribution (offline release)",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip creating the release .zip archive",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help=f"Override release version (default: {__version__})",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help=f"Override platform/arch tag (default: {get_default_platform_tag()})",
    )
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Skip PyInstaller compilation and only perform asset bundling / packaging",
    )

    args = parser.parse_args()

    build_and_package(
        include_models=args.include_models,
        create_zip=not args.no_zip,
        custom_version=args.version,
        platform_tag=args.platform,
        skip_pyinstaller=args.skip_pyinstaller,
    )

