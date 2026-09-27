import os
import sys
import gc
import logging
import threading
from typing import List, Tuple, Optional, Dict, Any, Callable

logger = logging.getLogger("SubtitleGo.ModelManager")

# Fix nagisa implicit relative imports in frozen PyInstaller bundles (No module named 'prepro')
try:
    import nagisa.prepro
    import nagisa.model
    import nagisa.mecab_system_eval
    import nagisa.tagger
    sys.modules['prepro'] = nagisa.prepro
    sys.modules['model'] = nagisa.model
    sys.modules['mecab_system_eval'] = nagisa.mecab_system_eval
    sys.modules['tagger'] = nagisa.tagger
except Exception:
    pass

from .runtime_manager import init_runtime_environment, is_runtime_installed, diagnose_runtime_environment

# Initialize runtime paths (custom packages directory / CUDA DLLs)
init_runtime_environment()

# Safely import heavy AI runtime libraries at module load time on the main thread
# to avoid C-extension dynamic loading race conditions in background QThreads.
try:
    import torch
    import torchaudio
    import transformers
    from qwen_asr import Qwen3ASRModel
except ImportError:
    torch = None
    torchaudio = None
    transformers = None
    Qwen3ASRModel = None


def patch_qwen_asr_audio_loader():
    """
    Patches qwen_asr's audio loader to use soundfile directly instead of librosa/numba/llvmlite.
    Eliminates WinError 206, eliminates Numba JIT warmup overhead, and provides faster C-level audio decoding across Windows, macOS, and Linux.
    """
    try:
        import soundfile as sf
        import numpy as np
        import qwen_asr.inference.utils as q_utils

        def fast_load_audio_any(x):
            if isinstance(x, (tuple, list)) and len(x) == 2:
                return x[0], x[1]
            if isinstance(x, dict) and "array" in x:
                return x["array"], x.get("sampling_rate", 16000)
            if isinstance(x, np.ndarray):
                return x, 16000
            if isinstance(x, str):
                data, sr = sf.read(x, dtype="float32")
                if data.ndim > 1:
                    data = data.T
                return data, sr
            return x

        q_utils.load_audio_any = fast_load_audio_any
        logger.info("Patched qwen_asr audio loader with soundfile backend.")
    except Exception as e:
        logger.debug(f"Could not patch qwen_asr audio loader: {e}")

# Apply patch when module loads
patch_qwen_asr_audio_loader()

SUPPORTED_LANGUAGES = [
    "Auto Detect", "Chinese", "English", "Cantonese", "Japanese", "Korean", 
    "Spanish", "French", "German", "Russian", "Arabic", "Portuguese",
    "Italian", "Indonesian", "Thai", "Vietnamese", "Turkish", "Hindi",
    "Malay", "Dutch", "Swedish", "Danish", "Finnish", "Polish", "Czech",
    "Filipino", "Persian", "Greek", "Hungarian", "Macedonian", "Romanian",
    "Anhui", "Dongbei", "Fujian", "Gansu", "Guizhou", "Hebei", "Henan",
    "Hubei", "Hunan", "Jiangxi", "Ningxia", "Shandong", "Shaanxi", "Shanxi",
    "Sichuan", "Tianjin", "Yunnan", "Zhejiang", "Cantonese (Hong Kong)",
    "Cantonese (Guangdong)", "Wu", "Minnan"
]


def get_base_dir() -> str:
    """Returns the base application directory."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _is_valid_model_dir(dir_path: str) -> bool:
    """
    Validates whether a directory contains fully downloaded and intact Qwen3-ASR model weights.
    Requires config.json AND actual .safetensors / .bin weights with minimum size threshold (>1.0 GB).
    Prevents premature startup when only metadata/config has downloaded.
    """
    if not dir_path or not os.path.isdir(dir_path):
        return False

    config_path = os.path.join(dir_path, "config.json")
    if not os.path.isfile(config_path):
        return False

    # Check for weight files (safetensors or bin)
    weight_files = []
    try:
        for f in os.listdir(dir_path):
            if f.endswith(".safetensors") or f.endswith(".bin"):
                fp = os.path.join(dir_path, f)
                if os.path.isfile(fp):
                    weight_files.append(fp)
    except Exception:
        return False

    if not weight_files:
        return False

    # Check total size of weight files (Qwen3-ASR-1.7B is ~3.4 GB, minimum threshold is 1.0 GB)
    try:
        total_size = sum(os.path.getsize(fp) for fp in weight_files)
        if total_size < (1024 * 1024 * 1024):  # < 1 GB means incomplete download
            return False
    except Exception:
        return False

    return True


def get_candidate_model_dirs() -> List[str]:
    """
    Returns candidate model weight search directories across macOS, Windows, and Linux.
    """
    candidates = []
    base_dir = get_base_dir()
    
    # 1. Local application folder (alongside executable / portable)
    candidates.append(os.path.abspath(os.path.join(base_dir, "models", "Qwen3-ASR-1.7B")))
    candidates.append(os.path.abspath(os.path.join(base_dir, "models")))

    # 2. Platform user data directory
    if sys.platform == "darwin":
        candidates.append(os.path.abspath(os.path.expanduser("~/Library/Application Support/SubtitleGo/models/Qwen3-ASR-1.7B")))
        candidates.append(os.path.abspath(os.path.expanduser("~/Library/Application Support/SubtitleStudio/models/Qwen3-ASR-1.7B")))
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(os.path.abspath(os.path.join(local_app_data, "SubtitleGo", "models", "Qwen3-ASR-1.7B")))
            candidates.append(os.path.abspath(os.path.join(local_app_data, "SubtitleStudio", "models", "Qwen3-ASR-1.7B")))
        home_appdata = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SubtitleGo", "models", "Qwen3-ASR-1.7B")
        if home_appdata not in candidates:
            candidates.append(os.path.abspath(home_appdata))
    else:
        candidates.append(os.path.abspath(os.path.expanduser("~/.local/share/subtitlego/models/Qwen3-ASR-1.7B")))
        candidates.append(os.path.abspath(os.path.expanduser("~/.local/share/subtitlestudio/models/Qwen3-ASR-1.7B")))

    # 3. Hugging Face Hub cache directory
    hf_hub_dir = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-1.7B")
    if os.path.isdir(hf_hub_dir):
        candidates.append(os.path.abspath(hf_hub_dir))
        snapshots_dir = os.path.join(hf_hub_dir, "snapshots")
        if os.path.isdir(snapshots_dir):
            try:
                for snap in os.listdir(snapshots_dir):
                    snap_path = os.path.join(snapshots_dir, snap)
                    if os.path.isdir(snap_path):
                        candidates.append(os.path.abspath(snap_path))
            except Exception:
                pass

    return candidates


def get_model_dir() -> str:
    """
    Returns the target directory for storing Qwen3-ASR-1.7B model weights.
    Prefers local 'models' folder if writable; otherwise uses User Application Support / AppData.
    """
    # If valid weights already exist anywhere, return their directory
    existing = find_model_path()
    if existing:
        return existing

    base_dir = get_base_dir()
    local_target = os.path.join(base_dir, "models", "Qwen3-ASR-1.7B")

    # On macOS, if inside .app bundle, do not write inside bundle; use Application Support
    is_mac_bundle = sys.platform == "darwin" and getattr(sys, "frozen", False) and ".app" in base_dir
    if not is_mac_bundle:
        try:
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            test_file = os.path.join(os.path.dirname(local_target), ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return local_target
        except Exception:
            pass

    # User Application Data directory fallback
    if sys.platform == "darwin":
        user_dir = os.path.expanduser("~/Library/Application Support/SubtitleGo/models/Qwen3-ASR-1.7B")
    elif sys.platform == "win32":
        user_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SubtitleGo", "models", "Qwen3-ASR-1.7B")
    else:
        user_dir = os.path.expanduser("~/.local/share/subtitlego/models/Qwen3-ASR-1.7B")

    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def find_model_path() -> Optional[str]:
    """
    Finds the path to verified local Qwen3-ASR model weights.
    Returns directory path string if valid model files exist, else None.
    """
    for c in get_candidate_model_dirs():
        if _is_valid_model_dir(c):
            return os.path.abspath(c)

    return None


def is_model_downloaded() -> bool:
    """Returns True if verified local model weights are present and intact."""
    p = find_model_path()
    return p is not None and os.path.isdir(p)


def download_model_weights(
    target_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Downloads Qwen3-ASR-1.7B model weights from Hugging Face Hub.
    """
    from huggingface_hub import snapshot_download

    if target_dir is None:
        target_dir = get_model_dir()

    os.makedirs(target_dir, exist_ok=True)
    repo_id = "Qwen/Qwen3-ASR-1.7B"

    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        print(f"[ModelManager] {msg}")

    _log(f"Starting Qwen3-ASR model download from Hugging Face ({repo_id})...")
    _log(f"Destination folder: {target_dir}")

    if progress_callback:
        progress_callback("Connecting to Hugging Face Hub...", 5.0)

    # Use snapshot_download with direct local_dir
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False
    )

    _log("Model weights downloaded and verified in destination directory.")

    if progress_callback:
        progress_callback("Download completed successfully.", 100.0)

    return target_dir


def get_system_memory_info() -> Dict[str, Any]:
    """
    Detects system RAM and GPU VRAM across macOS (Apple Silicon UMA), Windows (CUDA/CPU), and Linux.
    Initializes runtime environment so that dynamically installed PyTorch CUDA binaries are detected.
    """
    init_runtime_environment()
    total_ram_gb = 8.0
    try:
        import psutil
        total_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        if sys.platform == "darwin":
            try:
                import subprocess
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                total_ram_gb = round(int(out) / (1024 ** 3), 1)
            except Exception:
                try:
                    total_ram_gb = round((os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3), 1)
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
                total_ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
            except Exception:
                pass
        else:
            try:
                total_ram_gb = round((os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3), 1)
            except Exception:
                pass

    cuda_available = False
    mps_available = False
    vram_gb = 0.0
    gpu_name = ""

    try:
        import torch
        cuda_available = torch.cuda.is_available()
        mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

        if cuda_available:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram_gb = round(props.total_memory / (1024 ** 3), 1)
            except Exception:
                gpu_name = "CUDA GPU"
        elif mps_available:
            gpu_name = "Apple Silicon GPU (MPS)"
            vram_gb = total_ram_gb  # Unified memory
    except Exception:
        pass

    if cuda_available:
        device_type = "cuda"
    elif mps_available:
        device_type = "mps"
    else:
        device_type = "cpu"

    return {
        "total_ram_gb": total_ram_gb,
        "vram_gb": vram_gb,
        "cuda_available": cuda_available,
        "mps_available": mps_available,
        "device_type": device_type,
        "gpu_name": gpu_name
    }


def get_recommended_settings() -> Dict[str, Any]:
    """
    Computes recommended batch size and worker concurrency based on detected device and RAM/VRAM.
    
    ========================================================================================================
    MEMORY REFERENCE TABLE (Qwen3-ASR-1.7B FP16: ~3.4 GB weights + activations per batch item)
    ========================================================================================================
    Batch Size | Approx Memory | Dedicated GPU VRAM (CUDA) | Apple Unified Memory (MPS) | System RAM (CPU Mode)
    -----------+---------------+---------------------------+----------------------------+-----------------------
    1 Chunk    | ~4.0 GB       | 4 GB entry VRAM           | 8 GB Macs (safety mode)    | 8 GB RAM
    2 Chunks   | ~4.5 - 5.0 GB | 4 GB - 6 GB VRAM          | 8 GB Macs (safe default)   | 8 GB - 16 GB RAM
    4 Chunks   | ~5.0 - 5.5 GB | 6 GB VRAM (RTX 2060/3060) | 12 GB - 16 GB Macs         | 16 GB RAM
    8 Chunks   | ~6.0 - 6.5 GB | 8 GB VRAM (RTX 3070/4060) | 16 GB - 24 GB Macs         | 16 GB - 32 GB RAM
    16 Chunks  | ~7.0 - 8.0 GB | 12 GB - 16 GB VRAM (RTX)  | 24 GB - 32 GB Macs         | 32 GB RAM
    32 Chunks  | ~10.5 - 12 GB | 16 GB - 24 GB VRAM        | 32 GB - 64 GB Macs         | 64 GB RAM
    64 Chunks  | ~17.5 - 19 GB | 24 GB+ VRAM               | 64 GB+                     | 64 GB+ RAM
    ========================================================================================================
    """
    mem = get_system_memory_info()
    dev = mem["device_type"]
    ram = mem["total_ram_gb"]
    vram = mem["vram_gb"]

    if dev == "cuda":
        if vram >= 23.0:
            batch_size = 32
            concurrency = 4
        elif vram >= 11.5:
            batch_size = 16
            concurrency = 2
        elif vram >= 5.5:
            batch_size = 8
            concurrency = 2
        else:
            batch_size = 4
            concurrency = 1
        memory_label = f"NVIDIA CUDA GPU ({vram:.1f} GB Dedicated VRAM)"
    elif dev == "mps":
        if ram >= 63.0:
            batch_size = 32
            concurrency = 4
        elif ram >= 31.0:
            batch_size = 16
            concurrency = 2
        elif ram >= 23.5:
            batch_size = 12
            concurrency = 2
        elif ram >= 15.0:
            batch_size = 8
            concurrency = 2
        elif ram >= 11.5:
            batch_size = 4
            concurrency = 1
        else:
            # 8GB Apple Silicon Macs have ~2-3GB free after macOS system overhead
            batch_size = 2
            concurrency = 1
        memory_label = f"Apple Silicon ({ram:.0f} GB Unified Memory)"
    else:
        # CPU Mode
        if ram >= 63.0:
            batch_size = 16
            concurrency = 4
        elif ram >= 31.0:
            batch_size = 8
            concurrency = 2
        elif ram >= 15.0:
            batch_size = 4
            concurrency = 2
        else:
            batch_size = 2
            concurrency = 1
        memory_label = f"CPU Mode ({ram:.0f} GB System RAM)"

    return {
        "recommended_batch_size": batch_size,
        "recommended_concurrency": concurrency,
        "memory_label": memory_label,
        "device_type": dev,
        "total_ram_gb": ram,
        "vram_gb": vram
    }


class ModelManager:
    _instance: Optional["ModelManager"] = None

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.preferred_device = "auto"
        self.dtype = None
        self.model_path = None
        self.is_loading = False
        self.max_batch_size = 4
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance

    def refresh_hardware_detection(self):
        """Forces runtime environment and hardware cache refresh."""
        init_runtime_environment()
        get_system_memory_info()

    def get_available_devices(self) -> List[Tuple[str, str]]:
        """
        Returns list of available compute devices as (label, key).
        E.g. [('Auto (NVIDIA GeForce RTX 5060 Ti)', 'auto'), ('NVIDIA GPU (CUDA)', 'cuda'), ('CPU Mode', 'cpu')]
        """
        self.refresh_hardware_detection()
        mem = get_system_memory_info()
        cuda_ok = mem.get("cuda_available", False)
        mps_ok = mem.get("mps_available", False)
        gpu_name = mem.get("gpu_name", "")
        vram_gb = mem.get("vram_gb", 0.0)
        ram_gb = mem.get("total_ram_gb", 8.0)

        options: List[Tuple[str, str]] = []

        if cuda_ok:
            auto_label = f"Auto ({gpu_name} - {vram_gb:.1f}GB VRAM)"
            options.append((auto_label, "auto"))
            options.append((f"NVIDIA GPU (CUDA: {gpu_name})", "cuda"))
        elif mps_ok:
            auto_label = f"Auto (Apple Silicon MPS - {ram_gb:.0f}GB RAM)"
            options.append((auto_label, "auto"))
            options.append(("Apple Silicon GPU (MPS)", "mps"))
        else:
            auto_label = f"Auto (CPU Mode - {ram_gb:.0f}GB RAM)"
            options.append((auto_label, "auto"))

        options.append((f"CPU Mode (Compatible / Low Power - {ram_gb:.0f}GB RAM)", "cpu"))
        return options

    def set_preferred_device(self, device_choice: str) -> bool:
        """
        Sets user compute device preference ('auto', 'cuda', 'mps', 'cpu').
        If the model is currently loaded in memory, hot-reloads it onto the newly selected device.
        """
        with self._lock:
            self.preferred_device = device_choice.lower()
            print(f"[ModelManager] Preferred device set to: '{self.preferred_device}'")

            # If model is currently loaded, hot-reload on the new device
            if self.model is not None:
                print(f"[ModelManager] Hot-reloading active model onto {self.preferred_device}...")
                current_path = self.model_path
                current_bs = self.max_batch_size
                self.unload_model()
                self._load_model_internal(custom_path=current_path, max_batch_size=current_bs)
                return True
            return True

    def resolve_target_device_and_dtype(self) -> Tuple[str, Any]:
        """
        Resolves the actual PyTorch device string and dtype to use,
        taking preferred_device and real hardware availability into account.
        """
        init_runtime_environment()
        import torch

        pref = self.preferred_device.lower()
        logger.info(f"Resolving target compute device (preference='{pref}')...")

        # 1. Force CPU
        if pref == "cpu":
            logger.info("Preferred device is CPU. Selecting CPU mode.")
            return "cpu", torch.float32

        # 2. Force CUDA or Auto with CUDA
        if pref in ("cuda", "cuda:0", "auto"):
            if torch.cuda.is_available():
                try:
                    _test_t = torch.zeros(1, device="cuda:0")
                    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                    gpu_name = torch.cuda.get_device_name(0)
                    logger.info(f"CUDA device verified: {gpu_name} (dtype={dtype})")
                    return "cuda:0", dtype
                except Exception as cuda_err:
                    logger.warning(f"CUDA validation test failed ({cuda_err}), falling back.")
                    if pref != "auto":
                        raise RuntimeError(f"Requested CUDA device failed validation: {cuda_err}")
            elif pref != "auto":
                diag = diagnose_runtime_environment()
                reasons = "; ".join(diag.get("cuda_diagnosis_notes", [])) or "No CUDA GPU detected or CUDA runtime missing."
                err_msg = f"CUDA GPU is not available on this system. Details: {reasons}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

        # 3. Force MPS or Auto with MPS
        if pref in ("mps", "auto"):
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                try:
                    _test_t = torch.zeros(1, device="mps")
                    logger.info("Apple Silicon MPS verified (dtype=float16).")
                    return "mps", torch.float16
                except Exception as mps_err:
                    logger.warning(f"MPS validation test failed ({mps_err}), falling back.")
                    if pref != "auto":
                        raise RuntimeError(f"Requested Apple Silicon MPS device failed validation: {mps_err}")
            elif pref != "auto":
                raise RuntimeError("Apple Silicon MPS is not available on this system.")

        # 4. Default fallback: CPU
        logger.info("Defaulting to CPU mode (torch.float32).")
        return "cpu", torch.float32

    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns current hardware capability (CUDA GPU vs Apple Silicon MPS vs CPU)."""
        mem_info = get_system_memory_info()
        default_device = mem_info["device_type"]

        # Resolve effective device
        eff_dev = self.device if self.model else (
            "cpu" if self.preferred_device == "cpu" else default_device
        )

        return {
            "cuda_available": mem_info["cuda_available"],
            "mps_available": mem_info["mps_available"],
            "device": eff_dev,
            "preferred_device": self.preferred_device,
            "gpu_name": mem_info["gpu_name"],
            "vram_gb": mem_info["vram_gb"],
            "total_ram_gb": mem_info["total_ram_gb"],
            "model_loaded": self.model is not None,
            "model_path": self.model_path,
            "max_batch_size": self.max_batch_size
        }

    def load_model_on_device(self, target_device: str, max_batch_size: Optional[int] = None) -> bool:
        """Forces loading model onto a specific device (e.g. 'cpu', 'mps', 'cuda:0')."""
        self.set_preferred_device(target_device)
        return self.load_model(max_batch_size=max_batch_size)

    def _load_model_internal(
        self,
        custom_path: Optional[str] = None,
        max_batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Internal model loader without re-acquiring self._lock."""
        self.is_loading = True
        try:
            init_runtime_environment()
            import torch
            from qwen_asr import Qwen3ASRModel

            # Ensure audio loader patch is active
            patch_qwen_asr_audio_loader()

            target_device, target_dtype = self.resolve_target_device_and_dtype()
            self.device = target_device
            self.dtype = target_dtype

            if "cuda" in self.device:
                logger.info(f"Engaging {self.device} ({torch.cuda.get_device_name(0)}) with dtype {self.dtype}")
                try:
                    torch.backends.cuda.enable_flash_sdp(True)
                    torch.backends.cuda.enable_mem_efficient_sdp(True)
                    torch.backends.cuda.enable_math_sdp(True)
                    if hasattr(torch.backends.cuda, "enable_cudnn_sdp"):
                        torch.backends.cuda.enable_cudnn_sdp(True)
                except Exception:
                    pass
            elif self.device == "mps":
                logger.info(f"Engaging Apple Silicon MPS with dtype {self.dtype}")
            else:
                logger.info(f"Engaging CPU Mode with dtype {self.dtype}")

            model_path = custom_path or find_model_path() or "Qwen/Qwen3-ASR-1.7B"
            self.model_path = model_path
            logger.info(f"Loading weights from model path: {model_path}")

            if progress_callback:
                progress_callback(f"Loading Qwen3-ASR model ({self.device})...")

            rec = get_recommended_settings()
            self.max_batch_size = max_batch_size or rec["recommended_batch_size"]

            self.model = Qwen3ASRModel.from_pretrained(
                model_path,
                dtype=self.dtype,
                device_map=self.device,
                max_inference_batch_size=max(self.max_batch_size, 4),
                max_new_tokens=512,
            )
            logger.info(f"Qwen3-ASR model loaded successfully on {self.device}.")
            return True
        except Exception as e:
            import traceback
            err_trace = traceback.format_exc()
            logger.error(f"Failed to load Qwen3-ASR model:\n{err_trace}")
            raise
        finally:
            self.is_loading = False

    def load_model(
        self,
        custom_path: Optional[str] = None,
        max_batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Loads Qwen3-ASR model into memory."""
        with self._lock:
            if self.model is not None:
                return True
            return self._load_model_internal(
                custom_path=custom_path,
                max_batch_size=max_batch_size,
                progress_callback=progress_callback
            )

    def unload_model(self):
        """Unloads model to release GPU/CPU memory."""
        with self._lock:
            self.model = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                try:
                    torch.mps.empty_cache()
                except Exception:
                    pass
            gc.collect()

    @staticmethod
    def _is_oom_error(e: Exception) -> bool:
        """Determines if an exception is related to GPU / MPS memory exhaustion."""
        msg = str(e).lower()
        oom_signatures = [
            "out of memory",
            "insufficient memory",
            "command buffer exited",
            "kiogpucommandbuffercallbackerroroutofmemory",
            "cuda out of memory",
            "mps backend out of memory",
            "allocation failed",
            "cannot allocate memory"
        ]
        return any(sig in msg for sig in oom_signatures)

    def transcribe_batch(
        self,
        audio_paths: List[str],
        contexts: Optional[List[str]] = None,
        languages: Optional[List[Optional[str]]] = None
    ) -> List[Tuple[str, str]]:
        """
        Runs batch speech recognition inference.
        Includes automatic GPU OOM handling, sequential fallback, and CPU fallback for MPS.
        Returns list of (transcription_text, detected_language).
        """
        if self.model is None:
            self.load_model()

        if contexts is None:
            contexts = ["" for _ in audio_paths]
        if languages is None:
            languages = [None for _ in audio_paths]

        with self._lock:
            import torch
            try:
                with torch.inference_mode():
                    results = self.model.transcribe(
                        audio=audio_paths,
                        context=contexts,
                        language=languages,
                        return_time_stamps=False,
                    )
                return [(r.text.strip(), r.language or "Unknown") for r in results]

            except Exception as e:
                if self._is_oom_error(e):
                    print(f"\n[ModelManager] GPU Out-Of-Memory warning during batch ({len(audio_paths)} items): {e}")

                    if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                        try:
                            torch.mps.empty_cache()
                        except Exception:
                            pass
                    elif torch.cuda.is_available():
                        torch.cuda.empty_cache()

                    # Strategy 1: If batch size > 1, retry item-by-item
                    if len(audio_paths) > 1:
                        print("[ModelManager] Retrying batch item-by-item to reduce instantaneous GPU memory...")
                        single_results = []
                        for p, c, l in zip(audio_paths, contexts, languages):
                            # Recursively call transcribe_batch with single item
                            res = self.transcribe_batch([p], [c], [l])
                            single_results.extend(res)
                        return single_results

                    # Strategy 2: If single item failed on MPS, seamlessly switch to CPU
                    if self.device == "mps":
                        print("[ModelManager] Single chunk exceeded Apple Silicon MPS memory. Falling back to CPU mode...")
                        self.load_model_on_device("cpu")
                        with torch.inference_mode():
                            results = self.model.transcribe(
                                audio=audio_paths,
                                context=contexts,
                                language=languages,
                                return_time_stamps=False,
                            )
                        return [(r.text.strip(), r.language or "Unknown") for r in results]

                raise e
