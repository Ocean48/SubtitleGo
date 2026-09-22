import os
import sys
import gc
import threading
from typing import List, Tuple, Optional, Dict, Any, Callable

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


class ModelManager:
    _instance: Optional["ModelManager"] = None

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.dtype = None
        self.model_path = None
        self.is_loading = False
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance

    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns current hardware capability (CUDA GPU vs CPU)."""
        import torch
        cuda_available = torch.cuda.is_available()
        gpu_name = ""
        vram_gb = 0.0

        if cuda_available:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram_gb = round(props.total_memory / (1024 ** 3), 1)
            except Exception:
                gpu_name = "CUDA Device"

        return {
            "cuda_available": cuda_available,
            "device": self.device if self.model else ("cuda" if cuda_available else "cpu"),
            "gpu_name": gpu_name,
            "vram_gb": vram_gb,
            "model_loaded": self.model is not None,
            "model_path": self.model_path
        }

    def load_model(
        self,
        custom_path: Optional[str] = None,
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
                else:
                    self.device = "cpu"
                    self.dtype = torch.float32

                model_path = custom_path or find_model_path() or "Qwen/Qwen3-ASR-1.7B"
                self.model_path = model_path

                if progress_callback:
                    progress_callback(f"Loading Qwen3-ASR model ({self.device})...")

                self.model = Qwen3ASRModel.from_pretrained(
                    model_path,
                    dtype=self.dtype,
                    device_map=self.device,
                    max_inference_batch_size=16,
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
            gc.collect()

    def transcribe_batch(
        self,
        audio_paths: List[str],
        contexts: Optional[List[str]] = None,
        languages: Optional[List[Optional[str]]] = None
    ) -> List[Tuple[str, str]]:
        """
        Runs batch speech recognition inference.
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
            with torch.inference_mode():
                results = self.model.transcribe(
                    audio=audio_paths,
                    context=contexts,
                    language=languages,
                    return_time_stamps=False,
                )

        return [(r.text.strip(), r.language or "Unknown") for r in results]
