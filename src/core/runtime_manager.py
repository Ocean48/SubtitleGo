import os
import sys
import shutil
import subprocess
import threading
import urllib.request
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple

from .hardware_detector import detect_hardware_capabilities, get_system_ram_gb
from .logger import get_log_file_path

logger = logging.getLogger("SubtitleGo.RuntimeManager")


def get_app_base_dir() -> str:
    """Returns the root directory where the application is installed or running."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_candidate_package_dirs() -> List[str]:
    """
    Returns all candidate package directories in priority order:
    1. Local application runtime/packages (portable / alongside executable)
    2. User AppData / Application Support directory
    """
    candidates = []
    app_base = get_app_base_dir()
    candidates.append(os.path.abspath(os.path.join(app_base, "runtime", "packages")))

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(os.path.abspath(os.path.join(local_app_data, "SubtitleStudio", "runtime", "packages")))
        home_appdata = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SubtitleStudio", "runtime", "packages")
        if home_appdata not in candidates:
            candidates.append(os.path.abspath(home_appdata))
    elif sys.platform == "darwin":
        candidates.append(os.path.abspath(os.path.expanduser("~/Library/Application Support/SubtitleStudio/runtime/packages")))
    else:
        candidates.append(os.path.abspath(os.path.expanduser("~/.local/share/subtitlestudio/runtime/packages")))

    return candidates


def get_runtime_base_dir() -> str:
    """
    Returns the target directory for the managed AI runtime environment.
    Prefers a local 'runtime' directory next to the app if writable,
    otherwise falls back to user app data directory.
    """
    # If an existing package installation is found in any candidate directory, use its parent
    for cand in get_candidate_package_dirs():
        if os.path.isdir(cand) and (
            os.path.exists(os.path.join(cand, "torch"))
            or os.path.exists(os.path.join(cand, "transformers"))
        ):
            return os.path.dirname(cand)

    app_base = get_app_base_dir()
    local_runtime = os.path.join(app_base, "runtime")

    # Test if app_base is writable
    try:
        os.makedirs(local_runtime, exist_ok=True)
        test_file = os.path.join(local_runtime, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return local_runtime
    except Exception:
        pass

    # Fallback to User AppData
    if sys.platform == "win32":
        user_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SubtitleStudio", "runtime")
    elif sys.platform == "darwin":
        user_dir = os.path.expanduser("~/Library/Application Support/SubtitleStudio/runtime")
    else:
        user_dir = os.path.expanduser("~/.local/share/subtitlestudio/runtime")

    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def get_runtime_packages_dir() -> str:
    """Returns the path where installed Python package wheels reside."""
    for cand in get_candidate_package_dirs():
        if os.path.isdir(cand) and (
            os.path.exists(os.path.join(cand, "torch"))
            or os.path.exists(os.path.join(cand, "transformers"))
        ):
            return cand
    return os.path.join(get_runtime_base_dir(), "packages")


# Keep persistent global references to _AddedDllDirectory objects so Python's GC does not remove them
_DLL_DIRECTORIES: List[Any] = []


def init_runtime_environment():
    """
    Initializes sys.path and OS DLL/shared library search paths
    to ensure dynamically installed PyTorch, CUDA libraries, and AI modules are loaded.
    Should be called early in application startup.
    """
    global _DLL_DIRECTORIES
    import importlib
    importlib.invalidate_caches()

    # Wrap os.add_dll_directory on Windows to safely ignore non-existent or invalid delvewheel directories (e.g. llvmlite.libs)
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        if not getattr(os.add_dll_directory, "_safe_wrapped", False):
            _orig_add_dll_directory = os.add_dll_directory
            def _safe_add_dll_directory(path):
                try:
                    if isinstance(path, str) and os.path.isdir(path):
                        return _orig_add_dll_directory(path)
                except Exception:
                    pass
                return None
            _safe_add_dll_directory._safe_wrapped = True
            os.add_dll_directory = _safe_add_dll_directory

    candidate_dirs = get_candidate_package_dirs()
    existing_dirs = [d for d in candidate_dirs if os.path.isdir(d)]

    # Add all existing package candidate directories to sys.path
    for pkg_dir in reversed(existing_dirs):
        if pkg_dir not in sys.path:
            sys.path.insert(0, pkg_dir)

    # On Windows, register all package and C-extension DLL directories
    if sys.platform == "win32":
        dll_dirs: List[str] = [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        ]

        for pkg_dir in existing_dirs:
            if pkg_dir not in dll_dirs:
                dll_dirs.append(pkg_dir)
            torch_lib = os.path.join(pkg_dir, "torch", "lib")
            if os.path.isdir(torch_lib) and torch_lib not in dll_dirs:
                dll_dirs.append(torch_lib)
            torchaudio_lib = os.path.join(pkg_dir, "torchaudio", "lib")
            if os.path.isdir(torchaudio_lib) and torchaudio_lib not in dll_dirs:
                dll_dirs.append(torchaudio_lib)

            # Look for nvidia subpackages (nvidia/cuda_runtime/bin, nvidia/cublas/bin, etc.)
            nvidia_dir = os.path.join(pkg_dir, "nvidia")
            if os.path.isdir(nvidia_dir):
                for root, dirs, files in os.walk(nvidia_dir):
                    if any(f.lower().endswith((".dll", ".pyd")) for f in files):
                        if root not in dll_dirs:
                            dll_dirs.append(root)

            try:
                for root, dirs, files in os.walk(pkg_dir):
                    if any(f.lower().endswith((".dll", ".pyd")) for f in files):
                        if root not in dll_dirs:
                            dll_dirs.append(root)
            except Exception:
                pass

        # Register with os.add_dll_directory and keep cookie references
        if hasattr(os, "add_dll_directory"):
            for d in dll_dirs:
                if os.path.isdir(d):
                    try:
                        cookie = os.add_dll_directory(d)
                        _DLL_DIRECTORIES.append(cookie)
                    except Exception:
                        pass

        # Also set Windows DLL search directory via SetDllDirectoryW to the first torch\lib found
        try:
            import ctypes
            for pkg_dir in existing_dirs:
                tlib = os.path.join(pkg_dir, "torch", "lib")
                if os.path.isdir(tlib):
                    ctypes.windll.kernel32.SetDllDirectoryW(tlib)
                    break
        except Exception:
            pass

        # Also update PATH environment variable
        curr_path = os.environ.get("PATH", "")
        for d in dll_dirs:
            if os.path.isdir(d) and d not in curr_path:
                curr_path = d + os.pathsep + curr_path
        os.environ["PATH"] = curr_path


def check_runtime_status() -> Tuple[bool, str]:
    """
    Performs full import verification and returns (is_ok, detailed_status_or_error_trace).
    """
    import importlib
    import traceback
    init_runtime_environment()

    # Clear any None / broken cached modules
    for mod_name in ["torch", "torchaudio", "transformers", "accelerate", "qwen_asr", "soundfile", "librosa", "scipy"]:
        if mod_name in sys.modules and sys.modules[mod_name] is None:
            del sys.modules[mod_name]

    errors = []
    # Primary required packages for Qwen-ASR speech recognition
    core_packages = ["torch", "transformers", "accelerate", "qwen_asr", "soundfile", "librosa", "scipy"]
    for pkg in core_packages:
        try:
            importlib.import_module(pkg)
        except Exception as e:
            errors.append(f"Package '{pkg}' failed to load: {e}\n{traceback.format_exc()}")

    # Optional packages - test but do not fail core runtime if unavailable
    for pkg in ["torchaudio", "nagisa", "soynlp"]:
        try:
            importlib.import_module(pkg)
        except Exception:
            pass

    if errors:
        return False, "\n".join(errors)
    return True, "All AI runtime packages imported successfully."


def is_runtime_installed() -> bool:
    """
    Checks whether the necessary AI runtime libraries (PyTorch, transformers, qwen_asr)
    are available and importable.
    """
    ok, _ = check_runtime_status()
    return ok


def diagnose_runtime_environment() -> Dict[str, Any]:
    """
    Produces a comprehensive diagnostic inspection of the AI runtime environment,
    CUDA capabilities, Windows DLL presence, and module load errors.
    """
    init_runtime_environment()
    hw = detect_hardware_capabilities()
    pkg_dirs = get_candidate_package_dirs()
    existing_pkg_dirs = [d for d in pkg_dirs if os.path.isdir(d)]
    active_pkg_dir = get_runtime_packages_dir()

    report: Dict[str, Any] = {
        "os_platform": sys.platform,
        "python_executable": sys.executable,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "is_frozen": getattr(sys, "frozen", False),
        "candidate_package_dirs": pkg_dirs,
        "existing_package_dirs": existing_pkg_dirs,
        "active_package_dir": active_pkg_dir,
        "hardware_summary": hw.get("hardware_summary", "Unknown"),
        "has_nvidia_gpu": hw.get("has_nvidia_gpu", False),
        "gpu_name": hw.get("gpu_name", ""),
        "driver_version": hw.get("driver_version", ""),
        "vram_gb": hw.get("vram_gb", 0.0),
        "total_ram_gb": hw.get("total_ram_gb", 8.0),
        "torch_installed": False,
        "torch_version": None,
        "torch_cuda_build": None,
        "cuda_available": False,
        "cuda_device_count": 0,
        "mps_available": False,
        "device_type": "cpu",
        "import_error": None,
        "cuda_diagnosis_notes": []
    }

    try:
        import torch
        report["torch_installed"] = True
        report["torch_version"] = getattr(torch, "__version__", "unknown")
        report["torch_cuda_build"] = getattr(torch.version, "cuda", None) if hasattr(torch, "version") else None
        
        cuda_ok = torch.cuda.is_available()
        report["cuda_available"] = cuda_ok
        report["cuda_device_count"] = torch.cuda.device_count() if cuda_ok else 0

        mps_ok = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        report["mps_available"] = mps_ok

        if cuda_ok:
            report["device_type"] = "cuda"
            try:
                report["active_device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                report["active_device_name"] = "NVIDIA CUDA GPU"
        elif mps_ok:
            report["device_type"] = "mps"
            report["active_device_name"] = "Apple Silicon GPU (MPS)"
        else:
            report["device_type"] = "cpu"
            report["active_device_name"] = "CPU"

        # Diagnose why CUDA might be unavailable
        if not cuda_ok and hw.get("has_nvidia_gpu"):
            if not report["torch_cuda_build"]:
                report["cuda_diagnosis_notes"].append(
                    "PyTorch was installed as a CPU-only build (torch.version.cuda is None). "
                    "Re-running AI Setup with 'NVIDIA GPU Acceleration (CUDA)' will install CUDA 12.4 wheels."
                )
            else:
                report["cuda_diagnosis_notes"].append(
                    f"PyTorch has CUDA build '{report['torch_cuda_build']}' but torch.cuda.is_available() returned False. "
                    "This usually indicates missing/outdated NVIDIA drivers or unlinked CUDA DLLs."
                )

    except Exception as e:
        import traceback
        report["import_error"] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        report["cuda_diagnosis_notes"].append(f"Failed to import PyTorch: {e}")

    return report


def get_installed_runtime_info() -> Dict[str, Any]:
    """
    Returns information about the currently active PyTorch runtime,
    including version, device support, and CUDA availability.
    """
    diag = diagnose_runtime_environment()
    return {
        "installed": diag.get("torch_installed", False),
        "package_dir": diag.get("active_package_dir"),
        "torch_version": diag.get("torch_version"),
        "cuda_available": diag.get("cuda_available", False),
        "cuda_version": diag.get("torch_cuda_build"),
        "mps_available": diag.get("mps_available", False),
        "gpu_name": diag.get("gpu_name") or diag.get("active_device_name", ""),
        "vram_gb": diag.get("vram_gb", 0.0),
        "device_type": diag.get("device_type", "cpu"),
        "error": diag.get("import_error")
    }


def find_system_python() -> Optional[str]:
    """
    Finds a suitable Python executable on the host system to run pip installations.
    Ensures that the Python version matches the application's runtime ABI (major.minor).
    """
    target_ver = sys.version_info[:2]

    # In development mode, return current executable
    if not getattr(sys, "frozen", False):
        return sys.executable

    # Try py launcher with explicit target version first on Windows
    if sys.platform == "win32":
        try:
            cmd = ["py", f"-{target_ver[0]}.{target_ver[1]}", "-c", "import sys; print(sys.executable)"]
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW}
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, **kwargs)
            if res.returncode == 0 and res.stdout.strip() and os.path.isfile(res.stdout.strip()):
                return res.stdout.strip()
        except Exception:
            pass

    candidates = [
        shutil.which("python"),
        shutil.which("python3"),
        shutil.which("py"),
    ]
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
        ver_tag = f"Python{target_ver[0]}{target_ver[1]}"
        
        candidates.insert(0, os.path.join(local_app_data, "Programs", "Python", ver_tag, "python.exe"))
        candidates.insert(0, os.path.join(program_files, ver_tag, "python.exe"))
        candidates.insert(0, os.path.join(program_files_x86, ver_tag, "python.exe"))

    run_kwargs = {}
    if sys.platform == "win32":
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    # Check candidates for exact version match first
    for c in candidates:
        if c and os.path.isfile(c):
            try:
                res = subprocess.run(
                    [c, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                    capture_output=True, text=True, timeout=2, **run_kwargs
                )
                if res.returncode == 0:
                    v_str = res.stdout.strip()
                    parts = tuple(int(x) for x in v_str.split("."))
                    if parts == target_ver:
                        return c
            except Exception:
                pass

    # Fallback to any working Python executable
    for c in candidates:
        if c and os.path.isfile(c):
            try:
                res = subprocess.run([c, "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, timeout=2, **run_kwargs)
                if res.returncode == 0 and res.stdout.strip() and os.path.isfile(res.stdout.strip()):
                    return res.stdout.strip()
            except Exception:
                pass

    return None


def _run_pip_step(
    cmd: List[str],
    _log: Callable[[str], None],
    progress_callback: Optional[Callable[[str, float], None]],
    base_pct: float,
    scale_pct: float,
    cancel_event: Optional[threading.Event] = None,
    pkg_dir: Optional[str] = None
):
    _log(f"Executing: {' '.join(cmd)}")
    popen_kwargs = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    env = os.environ.copy()
    if pkg_dir and os.path.isdir(pkg_dir):
        env["PYTHONPATH"] = pkg_dir + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        **popen_kwargs
    )

    while True:
        if cancel_event and cancel_event.is_set():
            p.terminate()
            _log("Installation cancelled by user.")
            raise RuntimeError("Installation was cancelled by user.")
        line = p.stdout.readline()
        if not line and p.poll() is not None:
            break
        if line:
            cleaned = line.strip()
            if cleaned:
                _log(cleaned)
                if progress_callback and any(w in cleaned for w in ["Collecting", "Downloading", "Installing", "Successfully installed"]):
                    progress_callback(cleaned[:80], base_pct + (scale_pct * 0.5))

    if p.returncode != 0:
        raise RuntimeError(f"Pip command failed with exit code {p.returncode}. Please check network connection.")


def install_ai_runtime(
    target_type: str = "cuda",
    progress_callback: Optional[Callable[[str, float], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Installs PyTorch and required AI speech libraries with isolated index resolution
    to ensure CUDA binaries are never overwritten by CPU packages.
    """
    pkg_dir = get_runtime_packages_dir()
    os.makedirs(pkg_dir, exist_ok=True)

    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        print(f"[RuntimeManager] {msg}")

    python_exe = find_system_python()
    if not python_exe:
        err = "No compatible Python interpreter found on the system to execute package installation."
        _log(f"ERROR: {err}")
        raise RuntimeError(err)

    _log(f"Using host Python: {python_exe}")
    _log(f"Target runtime directory: {pkg_dir}")
    _log(f"Selected AI acceleration mode: {target_type.upper()}")

    if progress_callback:
        progress_callback("Preparing AI Runtime environment...", 5.0)

    # Clean existing torch/torchaudio/nvidia directories to prevent mixing CPU and CUDA wheels
    if os.path.isdir(pkg_dir):
        _log("Cleaning previous PyTorch and CUDA cache in runtime directory...")
        for item in os.listdir(pkg_dir):
            if item.startswith(("torch", "torchaudio", "nvidia", "caffe2", "functorch")):
                full_item = os.path.join(pkg_dir, item)
                try:
                    if os.path.isdir(full_item):
                        shutil.rmtree(full_item, ignore_errors=True)
                    else:
                        os.unlink(full_item)
                except Exception:
                    pass

    # Step 1: Install PyTorch exclusively from the official PyTorch repository index
    if target_type == "cuda":
        hw = detect_hardware_capabilities()
        is_rtx_50 = hw.get("is_rtx_50_series", False)
        
        if is_rtx_50:
            cuda_desc = "CUDA 12.8 (RTX 50-Series / Blackwell sm_120)"
            cuda_index_url = "https://download.pytorch.org/whl/nightly/cu128"
            extra_flags = ["--pre"]
        else:
            cuda_desc = "CUDA 12.4 (RTX 20/30/40 Series)"
            cuda_index_url = "https://download.pytorch.org/whl/cu124"
            extra_flags = []

        if progress_callback:
            progress_callback(f"Downloading PyTorch {cuda_desc} runtime (~2.0 GB)...", 10.0)
        _log(f"Step 1/2: Installing PyTorch {cuda_desc} and NVIDIA CUDA runtime libraries...")
        torch_cmd = [
            python_exe, "-m", "pip", "install",
            "--target", pkg_dir,
            "--no-user",
            "--no-cache-dir",
            "--upgrade",
            "--index-url", cuda_index_url,
        ] + extra_flags + ["torch", "torchaudio"]
        _run_pip_step(torch_cmd, _log, progress_callback, 10.0, 40.0, cancel_event, pkg_dir=pkg_dir)
    elif target_type == "cpu" and sys.platform != "darwin":
        if progress_callback:
            progress_callback("Downloading PyTorch CPU runtime (~200 MB)...", 10.0)
        _log("Step 1/2: Installing PyTorch CPU from pytorch.org...")
        torch_cmd = [
            python_exe, "-m", "pip", "install",
            "--target", pkg_dir,
            "--no-user",
            "--no-cache-dir",
            "--upgrade",
            "--index-url", "https://download.pytorch.org/whl/cpu",
            "torch", "torchaudio"
        ]
        _run_pip_step(torch_cmd, _log, progress_callback, 10.0, 40.0, cancel_event, pkg_dir=pkg_dir)
    else:  # mps or macOS standard PyPI (includes Metal MPS support)
        if progress_callback:
            desc = "Apple Silicon (Metal/MPS)" if sys.platform == "darwin" else "standard PyTorch"
            progress_callback(f"Downloading {desc} runtime (~250 MB)...", 10.0)
        _log(f"Step 1/2: Installing PyTorch from PyPI ({'macOS Apple Silicon / MPS' if sys.platform == 'darwin' else 'Standard'})...")
        torch_cmd = [
            python_exe, "-m", "pip", "install",
            "--target", pkg_dir,
            "--no-user",
            "--upgrade",
            "torch", "torchaudio"
        ]
        _run_pip_step(torch_cmd, _log, progress_callback, 10.0, 40.0, cancel_event, pkg_dir=pkg_dir)

    # Step 2: Install remaining AI packages from PyPI without overwriting PyTorch
    common_pkgs = [
        "transformers>=4.40.0",
        "accelerate>=0.28.0",
        "qwen-asr>=0.0.1",
        "soundfile>=0.12.1",
        "librosa>=0.10.1",
        "scipy>=1.11.0",
        "psutil>=5.9.0",
        "huggingface_hub>=0.22.0",
        "nagisa>=0.2.7",
        "soynlp>=0.0.493",
    ]

    if progress_callback:
        progress_callback("Installing speech recognition and audio libraries...", 55.0)
    _log("Step 2/2: Installing transformers, qwen-asr, and audio dependencies from PyPI...")
    
    if target_type == "cuda":
        hw = detect_hardware_capabilities()
        cuda_extra_idx = "https://download.pytorch.org/whl/nightly/cu128" if hw.get("is_rtx_50_series") else "https://download.pytorch.org/whl/cu124"
        extra_idx = ["--extra-index-url", cuda_extra_idx]
    elif target_type == "cpu" and sys.platform != "darwin":
        extra_idx = ["--extra-index-url", "https://download.pytorch.org/whl/cpu"]
    else:
        extra_idx = []

    deps_cmd = [
        python_exe, "-m", "pip", "install",
        "--target", pkg_dir,
        "--no-user",
    ] + extra_idx + common_pkgs
    _run_pip_step(deps_cmd, _log, progress_callback, 55.0, 35.0, cancel_event, pkg_dir=pkg_dir)

    # Re-initialize runtime environment and verify
    _log("Re-initializing runtime environment and searching for imported packages...")
    init_runtime_environment()

    if progress_callback:
        progress_callback("Verifying AI Runtime installation...", 92.0)

    ok, details = check_runtime_status()
    if not ok:
        _log(f"Verification details / Diagnostics:\n{details}")
        raise RuntimeError(f"AI Runtime verification check failed after installation:\n{details}")

    info = get_installed_runtime_info()
    _log(f"AI Runtime verification passed! PyTorch v{info.get('torch_version', 'unknown')} | CUDA Available: {info.get('cuda_available', False)} | CUDA Version: {info.get('cuda_version', 'None')}")

    if target_type == "cuda" and not info.get("cuda_available", False):
        diag = diagnose_runtime_environment()
        notes = "; ".join(diag.get("cuda_diagnosis_notes", []))
        err = f"CUDA acceleration was requested, but PyTorch reported CUDA is not available (Installed: {info.get('torch_version')}). {notes}"
        _log(f"ERROR: {err}")
        raise RuntimeError(err)

    if progress_callback:
        progress_callback("AI Runtime ready.", 100.0)

    return True
