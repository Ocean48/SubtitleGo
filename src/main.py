import os
import sys

# Ensure src directory is in sys.path
sys_path_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)

# Initialize logging system immediately
from src.core.logger import setup_app_logging, install_global_exception_handler, get_log_file_path
log_file = setup_app_logging()
install_global_exception_handler()

import logging
logger = logging.getLogger("SubtitleGo.Main")

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

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from src.__version__ import __app_name__, __version__, __title__
from src.ui.main_window import MainWindow
from src.core.runtime_manager import (
    init_runtime_environment,
    is_runtime_installed,
    get_installed_runtime_info,
    diagnose_runtime_environment
)
from src.core.model_manager import is_model_downloaded
from src.ui.widgets.setup_wizard_dialog import SetupWizardDialog


def _warmup_ai_runtime():
    """
    Initializes PyTorch, Transformers, and Qwen-ASR runtime on the main thread.
    Prevents C-extension dynamic loader initialization race conditions and segmentation faults
    when background QThreads load models or perform speech recognition inference.
    """
    try:
        init_runtime_environment()
        import torch
        import transformers
        from qwen_asr import Qwen3ASRModel
        logger.info(f"AI runtime warmup successful. PyTorch {getattr(torch, '__version__', 'unknown')}, CUDA available: {torch.cuda.is_available()}")
    except Exception as e:
        logger.warning(f"AI runtime warmup notice: {e}")


def main():
    logger.info(f"Starting {__title__} v{__version__}")
    logger.info(f"Executable: {sys.executable} (Frozen: {getattr(sys, 'frozen', False)})")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Log file active at: {log_file}")

    # Initialize runtime environment paths early
    init_runtime_environment()

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__title__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("SubtitleGo")

    # Run and log runtime diagnostic status
    diag = diagnose_runtime_environment()
    logger.info(f"Runtime Diagnostics Summary: PyTorch Installed={diag.get('torch_installed')}, "
                f"CUDA Available={diag.get('cuda_available')}, Device={diag.get('device_type')}, "
                f"GPU={diag.get('gpu_name', 'None')}")

    # Check if AI runtime and model weights exist, prompt setup wizard if missing
    if not is_runtime_installed() or not is_model_downloaded():
        logger.info("AI runtime or model weights missing; opening Setup Wizard.")
        dlg = SetupWizardDialog()
        res = dlg.exec()
        if res != SetupWizardDialog.Accepted and (not is_runtime_installed() or not is_model_downloaded()):
            logger.warning("Setup cancelled or incomplete. Exiting application.")
            sys.exit(0)

    # Re-initialize runtime environment paths after setup wizard completes
    init_runtime_environment()
    from src.core.model_manager import ModelManager
    ModelManager.get_instance().refresh_hardware_detection()

    # Warm up AI runtime on main thread if installed
    _warmup_ai_runtime()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
