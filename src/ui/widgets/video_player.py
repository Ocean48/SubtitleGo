import os
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QStyle, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QUrl, Signal, QTime
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class SubtitleOverlay(QLabel):
    """
    Floating high-contrast subtitle overlay rendered over video viewport.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("""
            SubtitleOverlay {
                background-color: rgba(8, 8, 8, 0.85);
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 16px;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)
        self.hide()


class VideoPlayerWidget(QWidget):
    """
    Complete video/audio preview player with live subtitle overlay.
    """
    sig_position_changed = Signal(float)  # current time in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cues: List[Dict[str, Any]] = []
        self._is_seeking = False
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.setMinimumHeight(140)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video Viewport Container
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background-color: #000000; border: none;")
        v_layout = QVBoxLayout(self.video_container)
        v_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(self.video_container)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v_layout.addWidget(self.video_widget)

        # Subtitle Overlay
        self.overlay = SubtitleOverlay(self.video_container)

        layout.addWidget(self.video_container, stretch=1)

        # Control Bar
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #0f172a; border-top: 1px solid #334155; padding: 6px 12px;")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(4, 4, 4, 4)
        ctrl_layout.setSpacing(4)

        # Slider Row
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(0)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        ctrl_layout.addWidget(self.slider)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(32, 28)
        self.btn_play.setStyleSheet("font-size: 14px; padding: 0;")
        self.btn_play.clicked.connect(self.toggle_playback)
        btn_row.addWidget(self.btn_play)

        self.lbl_time = QLabel("00:00:00 / 00:00:00")
        self.lbl_time.setStyleSheet("font-family: monospace; font-size: 11px; color: #94a3b8;")
        btn_row.addWidget(self.lbl_time)

        btn_row.addStretch()

        # Volume Controls
        lbl_vol = QLabel("Vol")
        lbl_vol.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        btn_row.addWidget(lbl_vol)

        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(80)
        self.slider_vol.setFixedWidth(80)
        self.slider_vol.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.slider_vol)

        ctrl_layout.addLayout(btn_row)
        layout.addWidget(ctrl_frame)

        # Multimedia Setup
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_overlay()

    def _reposition_overlay(self):
        """Positions overlay centered near the bottom of the video widget."""
        c_rect = self.video_container.rect()
        ov_width = min(int(c_rect.width() * 0.85), 700)
        self.overlay.setFixedWidth(ov_width)
        self.overlay.adjustSize()
        ov_height = self.overlay.height()
        
        x = (c_rect.width() - ov_width) // 2
        y = max(10, c_rect.height() - ov_height - 30)
        self.overlay.move(x, y)

    def load_media(self, file_path: str):
        """Loads and prepares a media file for playback."""
        if os.path.isfile(file_path):
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.btn_play.setText("▶")
            self.overlay.hide()

    def set_cues(self, cues: List[Dict[str, Any]]):
        """Sets subtitle cues for live overlay synchronization."""
        self.cues = cues
        self._update_overlay(self.player.position() / 1000.0)

    def seek_to_seconds(self, sec: float):
        """Seeks player to position in seconds."""
        ms = int(sec * 1000)
        self.player.setPosition(ms)

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")

    def _on_position_changed(self, pos_ms: int):
        if not self._is_seeking:
            dur = self.player.duration()
            if dur > 0:
                self.slider.setValue(int((pos_ms / dur) * 1000))
            self._update_time_label(pos_ms, dur)

        sec = pos_ms / 1000.0
        self._update_overlay(sec)
        self.sig_position_changed.emit(sec)

    def _on_duration_changed(self, dur_ms: int):
        self._update_time_label(self.player.position(), dur_ms)

    def _on_slider_pressed(self):
        self._is_seeking = True

    def _on_slider_released(self):
        self._is_seeking = False
        dur = self.player.duration()
        if dur > 0:
            target_ms = int((self.slider.value() / 1000.0) * dur)
            self.player.setPosition(target_ms)

    def _on_slider_moved(self, val: int):
        dur = self.player.duration()
        if dur > 0:
            target_ms = int((val / 1000.0) * dur)
            self._update_time_label(target_ms, dur)

    def _on_volume_changed(self, val: int):
        self.audio_output.setVolume(val / 100.0)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        t_pos = QTime(0, 0, 0).addMSecs(max(0, pos_ms))
        t_dur = QTime(0, 0, 0).addMSecs(max(0, dur_ms))
        fmt = "hh:mm:ss" if dur_ms >= 3600000 else "mm:ss"
        self.lbl_time.setText(f"{t_pos.toString(fmt)} / {t_dur.toString(fmt)}")

    def _update_overlay(self, current_sec: float):
        """Matches current time with active cue to display on overlay."""
        active_text = None
        for cue in self.cues:
            start = float(cue.get("start", 0.0))
            end = float(cue.get("end", 0.0))
            if start <= current_sec <= end:
                active_text = cue.get("text", "").strip()
                break

        if active_text:
            self.overlay.setText(active_text)
            self.overlay.show()
            self._reposition_overlay()
        else:
            self.overlay.hide()
