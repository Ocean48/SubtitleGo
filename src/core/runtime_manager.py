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
            candidates.append(os.path.abspath(os.path.join(local_app_data, "SubtitleGo", "runtime", "packages")))
            candidates.append(os.path.abspath(os.path.join(local_app_data, "SubtitleStudio", "runtime", "packages")))
        home_appdata = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SubtitleGo", "runtime", "packages")
        if home_appdata not in candidates:
            candidates.append(os.path.abspath(home_appdata))
    elif sys.platform == "darwin":
        candidates.append(os.path.abspath(os.path.expanduser("~/Library/Application Support/SubtitleGo/runtime/packages")))
        candidates.append(os.path.abspath(os.path.expanduser("~/Library/Application Support/SubtitleStudio/runtime/packages")))
    else:
        candidates.append(os.path.abspath(os.path.expanduser("~/.local/share/subtitlego/runtime/packages")))
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
        user_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SubtitleGo", "runtime")
    elif sys.platform == "darwin":
        user_dir = os.path.expanduser("~/Library/Application Support/SubtitleGo/runtime")
    else:
        user_dir = os.path.expanduser("~/.local/share/subtitlego/runtime")

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

    # On Linux, register torch and nvidia CUDA shared library directories in LD_LIBRARY_PATH & LIBRARY_PATH
    elif sys.platform.startswith("linux"):
        lib_dirs: List[str] = [
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib64",
            "/lib/x86_64-linux-gnu",
        ]
        for pkg_dir in existing_dirs:
            if pkg_dir not in lib_dirs:
                lib_dirs.append(pkg_dir)
            torch_lib = os.path.join(pkg_dir, "torch", "lib")
            if os.path.isdir(torch_lib) and torch_lib not in lib_dirs:
                lib_dirs.append(torch_lib)
            torchaudio_lib = os.path.join(pkg_dir, "torchaudio", "lib")
            if os.path.isdir(torchaudio_lib) and torchaudio_lib not in lib_dirs:
                lib_dirs.append(torchaudio_lib)

            # Triton nvidia library directory
            triton_lib = os.path.join(pkg_dir, "triton", "backends", "nvidia", "lib")
            if os.path.isdir(triton_lib) and triton_lib not in lib_dirs:
                lib_dirs.append(triton_lib)

            nvidia_dir = os.path.join(pkg_dir, "nvidia")
            if os.path.isdir(nvidia_dir):
                for root, dirs, files in os.walk(nvidia_dir):
                    if any(f.endswith(".so") or ".so." in f for f in files):
                        if root not in lib_dirs:
                            lib_dirs.append(root)

        if lib_dirs:
            for env_var in ["LD_LIBRARY_PATH", "LIBRARY_PATH"]:
                curr_ld = os.environ.get(env_var, "")
                parts = curr_ld.split(":") if curr_ld else []
                for ld in lib_dirs:
                    if os.path.isdir(ld) and ld not in parts:
                        parts.insert(0, ld)
                os.environ[env_var] = ":".join(parts)

    # Configure C/C++ include paths for dynamic C-extensions and Triton JIT compilation
    app_base = get_app_base_dir()
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidate_includes = [
        os.path.join(app_base, "_internal", "include", py_ver),
        os.path.join(app_base, "include", py_ver),
        os.path.join(app_base, "_internal", "include"),
        os.path.join(app_base, "include"),
    ]
    try:
        import sysconfig
        inc = sysconfig.get_path("include")
        if inc and inc not in candidate_includes:
            candidate_includes.append(inc)
    except Exception:
        pass

    valid_includes = [p for p in candidate_includes if os.path.isdir(p)]
    if valid_includes:
        for env_var in ["C_INCLUDE_PATH", "CPATH", "CPLUS_INCLUDE_PATH", "INCLUDE"]:
            curr = os.environ.get(env_var, "")
            parts = curr.split(os.pathsep) if curr else []
            for inc_p in valid_includes:
                if inc_p not in parts:
                    parts.insert(0, inc_p)
            os.environ[env_var] = os.pathsep.join(parts)

    # Configure PyTorch inference optimizations
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def check_runtime_status() -> Tuple[bool, str]:
    """
    Performs full import verification and returns (is_ok, detailed_status_or_error_trace).
    """
    import importlib
    import traceback
    init_runtime_environment()

    # Clear any None / broken cached modules before testing
    core_packages = ["torch", "transformers", "accelerate", "qwen_asr", "soundfile", "librosa", "scipy"]
    for mod_name in list(sys.modules.keys()):
        for pkg in core_packages:
            if mod_name == pkg or mod_name.startswith(f"{pkg}."):
                if sys.modules[mod_name] is None or not hasattr(sys.modules[mod_name], "__file__"):
                    del sys.modules[mod_name]
                    break

    errors = []
    # Primary required packages for Qwen-ASR speech recognition
    for pkg in core_packages:
        try:
            importlib.import_module(pkg)
        except Exception as e:
            errors.append(f"Package '{pkg}' failed to load: {e}\n{traceback.format_exc()}")
            # Purge the failed package and all its submodules from sys.modules to prevent circular import cascades
            prefix = f"{pkg}."
            to_del = [k for k in list(sys.modules.keys()) if k == pkg or k.startswith(prefix)]
            for k in to_del:
                del sys.modules[k]

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


def get_pip_pyz_path() -> str:
    """Returns the expected path to the standalone pip.pyz archive in the runtime base directory."""
    return os.path.join(get_runtime_base_dir(), "pip.pyz")


def get_pip_bootstrap_dir() -> str:
    """Returns the directory for isolated pip bootstrap packages."""
    return os.path.join(get_runtime_base_dir(), "pip_bootstrap")


def get_pip_env(pkg_dir: Optional[str] = None) -> Dict[str, str]:
    """Builds an environment dictionary with PYTHONPATH pointing to bootstrap pip and target package dirs."""
    env = os.environ.copy()
    python_paths: List[str] = []
    
    pip_boot = get_pip_bootstrap_dir()
    if os.path.isdir(pip_boot):
        python_paths.append(pip_boot)
    if pkg_dir and os.path.isdir(pkg_dir) and pkg_dir not in python_paths:
        python_paths.append(pkg_dir)
        
    if python_paths:
        orig = env.get("PYTHONPATH", "")
        combined = os.pathsep.join(python_paths)
        env["PYTHONPATH"] = (combined + os.pathsep + orig) if orig else combined
    return env


def resolve_pip_command(
    python_exe: str,
    log_callback: Optional[Callable[[str], None]] = None
) -> List[str]:
    """
    Resolves a working pip command invocation for the given Python executable.
    Tries in order:
    1. python_exe -m pip
    2. python_exe -m ensurepip --default-pip
    3. Cached isolated pip bootstrap in runtime directory
    4. Bootstrapping pip via official get-pip.py from PyPA
    5. Host system pip / pip3 CLI (if python version matches)
    """
    def _log(m: str):
        if log_callback:
            log_callback(m)

    run_kwargs: Dict[str, Any] = {"capture_output": True, "text": True, "timeout": 6}
    if sys.platform == "win32":
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    env = get_pip_env()

    # 1. Check if python_exe -m pip works
    try:
        res = subprocess.run([python_exe, "-m", "pip", "--version"], env=env, **run_kwargs)
        if res.returncode == 0 and "pip" in res.stdout.lower():
            return [python_exe, "-m", "pip"]
    except Exception:
        pass

    _log("Host Python is missing the 'pip' module. Attempting automated bootstrapping...")

    # 2. Try ensurepip
    try:
        ensure_kwargs = dict(run_kwargs)
        ensure_kwargs["timeout"] = 15
        res = subprocess.run([python_exe, "-m", "ensurepip", "--default-pip"], env=env, **ensure_kwargs)
        if res.returncode == 0:
            res2 = subprocess.run([python_exe, "-m", "pip", "--version"], env=env, **run_kwargs)
            if res2.returncode == 0:
                _log("Successfully bootstrapped pip via ensurepip.")
                return [python_exe, "-m", "pip"]
    except Exception:
        pass

    # 3. Check for existing isolated pip bootstrap directory
    pip_boot = get_pip_bootstrap_dir()
    if os.path.isdir(os.path.join(pip_boot, "pip")):
        env = get_pip_env()
        try:
            res = subprocess.run([python_exe, "-m", "pip", "--version"], env=env, **run_kwargs)
            if res.returncode == 0:
                _log(f"Using isolated pip bootstrap environment: {pip_boot}")
                return [python_exe, "-m", "pip"]
        except Exception:
            pass

    # 4. Bootstrap pip using get-pip.py from PyPA
    get_pip_script = os.path.join(get_runtime_base_dir(), "get-pip.py")
    if not os.path.isfile(get_pip_script) or os.path.getsize(get_pip_script) < 100000:
        _log("Downloading standalone pip installer from PyPA (https://bootstrap.pypa.io/get-pip.py)...")
        os.makedirs(os.path.dirname(get_pip_script), exist_ok=True)
        downloaded = False
        mirrors = [
            "https://bootstrap.pypa.io/get-pip.py",
            "https://raw.githubusercontent.com/pypa/get-pip/main/public/get-pip.py"
        ]
        for url in mirrors:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SubtitleGo-Installer/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                    if len(data) > 100000:
                        with open(get_pip_script, "wb") as f:
                            f.write(data)
                        downloaded = True
                        break
            except Exception as dl_err:
                _log(f"Download mirror '{url}' returned error: {dl_err}")

        if not downloaded:
            _log("Could not download get-pip.py script from PyPA mirrors.")

    if os.path.isfile(get_pip_script):
        _log(f"Installing pip into isolated runtime directory: {pip_boot}...")
        os.makedirs(pip_boot, exist_ok=True)
        boot_cmd = [
            python_exe, get_pip_script,
            "--target", pip_boot,
            "--no-setuptools",
            "--no-wheel",
            "--break-system-packages",
            "--no-warn-script-location"
        ]
        try:
            res = subprocess.run(boot_cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                env = get_pip_env()
                res2 = subprocess.run([python_exe, "-m", "pip", "--version"], env=env, **run_kwargs)
                if res2.returncode == 0:
                    _log("Pip bootstrapping completed successfully.")
                    return [python_exe, "-m", "pip"]
            else:
                _log(f"get-pip.py execution notice: {res.stderr or res.stdout}")
        except Exception as boot_err:
            _log(f"get-pip.py invocation error: {boot_err}")

    # 5. Check if system pip3 / pip CLI can be used
    for p_cli in ["pip3", "pip"]:
        which_p = shutil.which(p_cli)
        if which_p:
            try:
                res = subprocess.run([which_p, "--version"], **run_kwargs)
                if res.returncode == 0:
                    _log(f"Falling back to system {p_cli} executable: {which_p}")
                    return [which_p]
            except Exception:
                pass

    err_msg = (
        "No working pip installer could be found or bootstrapped for Python.\n"
        "On Debian/Ubuntu Linux, please install pip using:\n"
        "    sudo apt update && sudo apt install -y python3-pip\n"
        "On Fedora/RHEL Linux, use:\n"
        "    sudo dnf install -y python3-pip\n"
        "On Arch Linux, use:\n"
        "    sudo pacman -S python-pip"
    )
    _log(f"ERROR: {err_msg}")
    raise RuntimeError(err_msg)


def get_pip_extra_install_flags(pip_cmd: List[str]) -> List[str]:
    """
    Returns extra flags like --break-system-packages and --no-warn-script-location
    if supported by the pip invocation.
    This prevents PEP 668 errors on Debian 12+ / Ubuntu 24.04+ when installing to custom targets.
    """
    extra: List[str] = []
    run_kwargs: Dict[str, Any] = {"capture_output": True, "text": True, "timeout": 5}
    if sys.platform == "win32":
        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    env = get_pip_env()
    try:
        res = subprocess.run(pip_cmd + ["help", "install"], env=env, **run_kwargs)
        if res.returncode == 0:
            if "--break-system-packages" in res.stdout:
                extra.append("--break-system-packages")
            if "--no-warn-script-location" in res.stdout:
                extra.append("--no-warn-script-location")
    except Exception:
        pass
    return extra


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

    env = get_pip_env(pkg_dir)

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        **popen_kwargs
    )

    recent_logs: List[str] = []
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
                recent_logs.append(cleaned)
                if len(recent_logs) > 30:
                    recent_logs.pop(0)
                _log(cleaned)
                if progress_callback and any(w in cleaned for w in ["Collecting", "Downloading", "Installing", "Successfully installed"]):
                    progress_callback(cleaned[:80], base_pct + (scale_pct * 0.5))

    if p.returncode != 0:
        err_tail = "\n".join(recent_logs[-8:]) if recent_logs else f"Exit code {p.returncode}"
        raise RuntimeError(f"Pip command failed with exit code {p.returncode}:\n{err_tail}")


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

    pip_cmd_base = resolve_pip_command(python_exe, log_callback=_log)
    pip_extra_flags = get_pip_extra_install_flags(pip_cmd_base)
    if pip_extra_flags:
        _log(f"Detected additional pip install flags: {' '.join(pip_extra_flags)}")

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
        torch_cmd = pip_cmd_base + [
            "install",
            "--target", pkg_dir,
            "--no-user",
            "--no-cache-dir",
            "--upgrade",
            "--index-url", cuda_index_url,
        ] + pip_extra_flags + extra_flags + ["torch", "torchaudio"]
        _run_pip_step(torch_cmd, _log, progress_callback, 10.0, 40.0, cancel_event, pkg_dir=pkg_dir)
    elif target_type == "cpu" and sys.platform != "darwin":
        if progress_callback:
            progress_callback("Downloading PyTorch CPU runtime (~200 MB)...", 10.0)
        _log("Step 1/2: Installing PyTorch CPU from pytorch.org...")
        torch_cmd = pip_cmd_base + [
            "install",
            "--target", pkg_dir,
            "--no-user",
            "--no-cache-dir",
            "--upgrade",
            "--index-url", "https://download.pytorch.org/whl/cpu",
        ] + pip_extra_flags + ["torch", "torchaudio"]
        _run_pip_step(torch_cmd, _log, progress_callback, 10.0, 40.0, cancel_event, pkg_dir=pkg_dir)
    else:  # mps or macOS standard PyPI (includes Metal MPS support)
        if progress_callback:
            desc = "Apple Silicon (Metal/MPS)" if sys.platform == "darwin" else "standard PyTorch"
            progress_callback(f"Downloading {desc} runtime (~250 MB)...", 10.0)
        _log(f"Step 1/2: Installing PyTorch from PyPI ({'macOS Apple Silicon / MPS' if sys.platform == 'darwin' else 'Standard'})...")
        torch_cmd = pip_cmd_base + [
            "install",
            "--target", pkg_dir,
            "--no-user",
            "--upgrade",
        ] + pip_extra_flags + ["torch", "torchaudio"]
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
        cuda_index_url = "https://download.pytorch.org/whl/nightly/cu128" if hw.get("is_rtx_50_series") else "https://download.pytorch.org/whl/cu124"
        index_args = ["--index-url", cuda_index_url, "--extra-index-url", "https://pypi.org/simple"]
        if hw.get("is_rtx_50_series"):
            index_args.append("--pre")
    elif target_type == "cpu" and sys.platform != "darwin":
        index_args = ["--index-url", "https://download.pytorch.org/whl/cpu", "--extra-index-url", "https://pypi.org/simple"]
    else:
        index_args = []

    deps_cmd = pip_cmd_base + [
        "install",
        "--target", pkg_dir,
        "--no-user",
        "--no-cache-dir",
    ] + pip_extra_flags + index_args + common_pkgs
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
