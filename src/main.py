import os
import sys

# Ensure src directory is in sys.path
sys_path_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from src.__version__ import __app_name__, __version__, __title__
from src.ui.main_window import MainWindow
from src.core.model_manager import is_model_downloaded
from src.ui.widgets.model_download_dialog import ModelDownloadDialog


def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__title__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("SubtitleGo")

    # Check if model weights exist, prompt download if missing
    if not is_model_downloaded():
        dlg = ModelDownloadDialog()
        res = dlg.exec()
        if res != ModelDownloadDialog.Accepted and not is_model_downloaded():
            # User cancelled or failed download
            print("Model weights not available. Continuing with download prompt accessible from settings.")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
