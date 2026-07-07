"""A track row: left control panel (name, mute/solo, gain, pan) + waveform lane."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider,
)

from .waveform_lane import WaveformLane, LANE_HEIGHT

CONTROL_WIDTH = 200


class TrackRow(QWidget):
    gain_changed = Signal(int, float)
    pan_changed = Signal(int, float)
    mute_toggled = Signal(int, bool)
    solo_toggled = Signal(int, bool)
    seek_requested = Signal(int)

    def __init__(self, index: int, name: str, color: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedHeight(LANE_HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        panel = QWidget()
        panel.setFixedWidth(CONTROL_WIDTH)
        panel.setStyleSheet("background:#2b2b2b;")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(6, 4, 6, 4)
        pv.setSpacing(2)

        top = QHBoxLayout()
        swatch = QLabel("  ")
        swatch.setStyleSheet(f"background:{color}; border-radius:2px;")
        swatch.setFixedWidth(12)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color:#eee; font-weight:bold;")
        self.mute_btn = QPushButton("M"); self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedWidth(24)
        self.solo_btn = QPushButton("S"); self.solo_btn.setCheckable(True)
        self.solo_btn.setFixedWidth(24)
        top.addWidget(swatch)
        top.addWidget(self.name_label, 1)
        top.addWidget(self.mute_btn)
        top.addWidget(self.solo_btn)
        pv.addLayout(top)

        self.gain = QSlider(Qt.Horizontal)
        self.gain.setRange(0, 150); self.gain.setValue(100)
        pv.addWidget(self._labeled("Gain", self.gain))

        self.pan = QSlider(Qt.Horizontal)
        self.pan.setRange(-100, 100); self.pan.setValue(0)
        pv.addWidget(self._labeled("Pan", self.pan))

        row.addWidget(panel)
        self.lane = WaveformLane(color=color)
        row.addWidget(self.lane, 1)

        # wiring
        self.gain.valueChanged.connect(
            lambda v: self.gain_changed.emit(self.index, v / 100.0))
        self.pan.valueChanged.connect(
            lambda v: self.pan_changed.emit(self.index, v / 100.0))
        self.mute_btn.toggled.connect(
            lambda on: self.mute_toggled.emit(self.index, on))
        self.solo_btn.toggled.connect(
            lambda on: self.solo_toggled.emit(self.index, on))
        self.lane.seek_requested.connect(self.seek_requested)

    def _labeled(self, text, slider) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(text); lab.setFixedWidth(30)
        lab.setStyleSheet("color:#bbb;")
        h.addWidget(lab)
        h.addWidget(slider, 1)
        return w
