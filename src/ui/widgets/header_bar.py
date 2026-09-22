from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Signal, Qt

from ...core.model_manager import ModelManager


class HeaderBar(QFrame):
    """
    Top header bar showing application branding, subtitle description,
    and live hardware / GPU acceleration indicator.
    """
    sig_refresh_hardware = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "headerFrame")
        self._init_ui()
        self.update_hardware_status()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # Left Branding
        left_layout = QHBoxLayout()
        left_layout.setSpacing(12)

        self.lbl_brand = QLabel("QWEN3-ASR")
        self.lbl_brand.setObjectName("brandBadge")
        left_layout.addWidget(self.lbl_brand)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_title = QLabel("SubtitleGo - Subtitle Studio")
        self.lbl_title.setObjectName("appTitle")
        title_box.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel("Drop video -> Instant preview -> Fast speech recognition -> One-click paced subtitles")
        self.lbl_subtitle.setObjectName("appSubtitle")
        self.lbl_subtitle.setWordWrap(True)
        title_box.addWidget(self.lbl_subtitle)

        left_layout.addLayout(title_box)
        layout.addLayout(left_layout, stretch=1)

        # Right Hardware Status
        right_layout = QHBoxLayout()
        right_layout.setSpacing(8)

        self.lbl_status = QLabel("Checking Hardware...")
        self.lbl_status.setObjectName("statusBadge")
        right_layout.addWidget(self.lbl_status)

        layout.addLayout(right_layout)

    def update_hardware_status(self):
        """Refreshes hardware and GPU availability badge."""
        try:
            mgr = ModelManager.get_instance()
            info = mgr.get_hardware_status()
            if info["cuda_available"]:
                gpu_text = f"● Online (GPU: {info['gpu_name']} {info['vram_gb']}GB)" if info.get('vram_gb') else f"● Online (GPU: {info['gpu_name']})"
                self.lbl_status.setText(gpu_text)
                self.lbl_status.setProperty("class", "gpu")
                self.lbl_status.setStyleSheet("background-color: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid #166534; border-radius: 6px; padding: 4px 10px; font-weight: 600; font-size: 11px;")
            else:
                self.lbl_status.setText("● Online (CPU Mode)")
                self.lbl_status.setProperty("class", "cpu")
                self.lbl_status.setStyleSheet("background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid #854d0e; border-radius: 6px; padding: 4px 10px; font-weight: 600; font-size: 11px;")
        except Exception:
            self.lbl_status.setText("● Offline / Initializing")
            self.lbl_status.setStyleSheet("background-color: #0f172a; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 11px;")
