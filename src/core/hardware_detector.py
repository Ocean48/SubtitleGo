import os
import sys
import shutil
import subprocess
import platform
from typing import Dict, Any, Optional


def get_system_ram_gb() -> float:
    """Returns total system physical memory in GB."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        pass

    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL).strip()
            return round(int(out) / (1024 ** 3), 1)
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
        except Exception:
            pass
    else:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round((pages * page_size) / (1024 ** 3), 1)
        except Exception:
            pass

    return 8.0


def _query_nvidia_smi() -> Optional[Dict[str, Any]]:
    """Attempts to query GPU info via nvidia-smi command-line tool."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi and sys.platform == "win32":
        # Check standard Windows paths if not in PATH
        default_paths = [
            os.path.expandvars(r"%SystemRoot%\System32\nvidia-smi.exe"),
            os.path.expandvars(r"%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
        ]
        for p in default_paths:
            if os.path.isfile(p):
                nvidia_smi = p
                break

    if not nvidia_smi:
        return None

    try:
        cmd = [
            nvidia_smi,
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits"
        ]
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, **kwargs)
        if result.returncode == 0 and result.stdout.strip():
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            if lines:
                parts = [p.strip() for p in lines[0].split(",")]
                gpu_name = parts[0] if len(parts) > 0 else "NVIDIA GPU"
                vram_mb = float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "", 1).isdigit() else 0.0
                driver_ver = parts[2] if len(parts) > 2 else ""
                vram_gb = round(vram_mb / 1024.0, 1)

                return {
                    "has_nvidia_gpu": True,
                    "gpu_name": gpu_name,
                    "vram_gb": vram_gb,
                    "driver_version": driver_ver,
                    "device_type": "cuda"
                }
    except Exception:
        pass

    return None


def _check_windows_cuda_dll() -> bool:
    """Checks for nvcuda.dll presence on Windows without importing PyTorch."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        h = ctypes.windll.kernel32.LoadLibraryW("nvcuda.dll")
        if h:
            ctypes.windll.kernel32.FreeLibrary(h)
            return True
    except Exception:
        pass
    return False


def _check_linux_cuda_so() -> bool:
    """Checks for libcuda.so presence on Linux without importing PyTorch."""
    if sys.platform != "linux":
        return False
    candidates = ["libcuda.so", "libcuda.so.1", "/usr/lib/x86_64-linux-gnu/libcuda.so.1", "/usr/lib64/libcuda.so"]
    for c in candidates:
        if os.path.exists(c):
            return True
    return False


def detect_hardware_capabilities() -> Dict[str, Any]:
    """
    Detects hardware capabilities (NVIDIA GPU, Apple Silicon MPS, or CPU)
    without requiring PyTorch or CUDA binaries to be imported first.
    """
    ram_gb = get_system_ram_gb()
    is_macos = (sys.platform == "darwin")
    is_apple_silicon = False

    if is_macos:
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, stderr=subprocess.DEVNULL).strip()
            if "Apple" in out or platform.machine().lower() in ("arm64", "aarch64"):
                is_apple_silicon = True
        except Exception:
            if platform.machine().lower() in ("arm64", "aarch64"):
                is_apple_silicon = True

    # 1. Check NVIDIA GPU via nvidia-smi
    smi_info = _query_nvidia_smi()
    if smi_info:
        vram_gb = smi_info["vram_gb"]
        rec = "cuda" if vram_gb >= 3.5 else "cpu"
        gpu_name = smi_info["gpu_name"]
        is_rtx_50 = any(x in gpu_name.upper() for x in ["5090", "5080", "5070", "5060", "RTX 50", "RTX50", "BLACKWELL", "B200", "B100"])
        return {
            "has_nvidia_gpu": True,
            "gpu_name": gpu_name,
            "is_rtx_50_series": is_rtx_50,
            "vram_gb": vram_gb,
            "driver_version": smi_info.get("driver_version", ""),
            "total_ram_gb": ram_gb,
            "recommended_runtime": rec,
            "hardware_summary": f"{gpu_name} ({vram_gb} GB VRAM)"
        }

    # 2. Check CUDA driver DLL/SO if nvidia-smi was not accessible
    if _check_windows_cuda_dll() or _check_linux_cuda_so():
        return {
            "has_nvidia_gpu": True,
            "gpu_name": "NVIDIA CUDA GPU (Driver Active)",
            "is_rtx_50_series": False,
            "vram_gb": 4.0,  # Estimated fallback
            "driver_version": "",
            "total_ram_gb": ram_gb,
            "recommended_runtime": "cuda",
            "hardware_summary": "NVIDIA GPU with CUDA driver support"
        }

    # 3. Check Apple Silicon
    if is_macos and is_apple_silicon:
        return {
            "has_nvidia_gpu": False,
            "gpu_name": f"Apple Silicon GPU (MPS) ({ram_gb} GB Unified Memory)",
            "is_rtx_50_series": False,
            "vram_gb": ram_gb,
            "driver_version": "",
            "total_ram_gb": ram_gb,
            "recommended_runtime": "mps",
            "hardware_summary": f"Apple Silicon ({ram_gb} GB Unified Memory)"
        }

    # 4. Fallback: CPU only
    return {
        "has_nvidia_gpu": False,
        "gpu_name": "CPU Mode (No Dedicated GPU Detected)",
        "is_rtx_50_series": False,
        "vram_gb": 0.0,
        "driver_version": "",
        "total_ram_gb": ram_gb,
        "recommended_runtime": "cpu",
        "hardware_summary": f"CPU Mode ({ram_gb} GB System RAM)"
    }
