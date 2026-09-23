import os
import sys
import gc
import threading
from typing import List, Tuple, Optional, Dict, Any, Callable

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


def get_model_dir() -> str:
    """Returns the standard local model directory."""
    return os.path.join(get_base_dir(), "models", "Qwen3-ASR-1.7B")


def find_model_path() -> Optional[str]:
    """
    Finds the path to local Qwen3-ASR model weights.
    Returns path string if valid model files exist, else None.
    """
    candidates = [
        get_model_dir(),
        os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-1.7B")
    ]

    for c in candidates:
        if os.path.isdir(c):
            # Check for config.json and model weights
            if os.path.exists(os.path.join(c, "config.json")):
                return os.path.abspath(c)

    return None


def is_model_downloaded() -> bool:
    """Returns True if local model weights are present."""
    p = find_model_path()
    return p is not None and os.path.isdir(p)


def download_model_weights(
    target_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> str:
    """
    Downloads Qwen3-ASR-1.7B model weights from Hugging Face Hub.
    """
    from huggingface_hub import snapshot_download

    if target_dir is None:
        target_dir = get_model_dir()

    os.makedirs(target_dir, exist_ok=True)
    repo_id = "Qwen/Qwen3-ASR-1.7B"

    if progress_callback:
        progress_callback("Connecting to Hugging Face Hub...", 5.0)

    # Use snapshot_download with direct local_dir
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False
    )

    if progress_callback:
        progress_callback("Download completed successfully.", 100.0)

    return target_dir


def get_system_memory_info() -> Dict[str, Any]:
    """
    Detects system RAM and GPU VRAM across macOS (Apple Silicon UMA), Windows (CUDA/CPU), and Linux.
    Returns dictionary with total_ram_gb, vram_gb, device_type, and hardware description.
    """
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

    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns current hardware capability (CUDA GPU vs Apple Silicon MPS vs CPU)."""
        mem_info = get_system_memory_info()
        default_device = mem_info["device_type"]

        return {
            "cuda_available": mem_info["cuda_available"],
            "mps_available": mem_info["mps_available"],
            "device": self.device if self.model else default_device,
            "gpu_name": mem_info["gpu_name"],
            "vram_gb": mem_info["vram_gb"],
            "total_ram_gb": mem_info["total_ram_gb"],
            "model_loaded": self.model is not None,
            "model_path": self.model_path,
            "max_batch_size": self.max_batch_size
        }

    def load_model_on_device(self, target_device: str, max_batch_size: Optional[int] = None) -> bool:
        """Forces loading model onto a specific device (e.g. 'cpu', 'mps', 'cuda:0')."""
        self.unload_model()
        import torch
        from qwen_asr import Qwen3ASRModel

        self.device = target_device
        self.dtype = torch.float32 if target_device == "cpu" else torch.float16
        model_path = self.model_path or find_model_path() or "Qwen/Qwen3-ASR-1.7B"
        self.model_path = model_path

        rec = get_recommended_settings()
        self.max_batch_size = max_batch_size or rec["recommended_batch_size"]

        self.model = Qwen3ASRModel.from_pretrained(
            model_path,
            dtype=self.dtype,
            device_map=self.device,
            max_inference_batch_size=max(self.max_batch_size, 4),
            max_new_tokens=512,
        )
        return True

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

            self.is_loading = True
            try:
                import torch
                from qwen_asr import Qwen3ASRModel

                if torch.cuda.is_available():
                    try:
                        _test_t = torch.zeros(1, device="cuda:0")
                        self.device = "cuda:0"
                        self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                    except Exception as cuda_err:
                        print(f"CUDA device check failed ({cuda_err}), falling back to CPU.")
                        self.device = "cpu"
                        self.dtype = torch.float32
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    try:
                        _test_t = torch.zeros(1, device="mps")
                        self.device = "mps"
                        self.dtype = torch.float16
                    except Exception as mps_err:
                        print(f"MPS device check failed ({mps_err}), falling back to CPU.")
                        self.device = "cpu"
                        self.dtype = torch.float32
                else:
                    self.device = "cpu"
                    self.dtype = torch.float32

                model_path = custom_path or find_model_path() or "Qwen/Qwen3-ASR-1.7B"
                self.model_path = model_path

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
                return True
            finally:
                self.is_loading = False

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
