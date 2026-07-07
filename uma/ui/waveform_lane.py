"""One track's waveform lane, drawn against the shared ViewState.

Also draws the shared vertical markers (in/out, splits, playhead) so they line
up across every stacked lane.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .viewport import ViewState

LANE_HEIGHT = 90


class WaveformLane(QWidget):
    """Displays a peak pyramid; forwards clicks as seek requests (in frames)."""

    seek_requested = Signal(int)

    def __init__(self, color="#4e9a06", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(LANE_HEIGHT)
        self.color = QColor(color)
        self.view: ViewState | None = None
        self.pyramid = None
        self.frames = 0
        self.playhead = 0
        self.in_point = 0
        self.out_point = 0
        self.splits: list[int] = []

    def set_view(self, view: ViewState):
        self.view = view
        self.update()

    def set_markers(self, in_point, out_point, splits, playhead):
        self.in_point = in_point
        self.out_point = out_point
        self.splits = splits
        self.playhead = playhead
        self.update()

    # ------------------------------------------------------------------
    def mousePressEvent(self, ev):
        if self.view is not None and ev.button() == Qt.LeftButton:
            frame = int(self.view.x_to_frame(ev.position().x()))
            self.seek_requested.emit(max(0, min(self.frames, frame)))

    def paintEvent(self, _ev):
        p = QPainter(self)
        w, h = self.width(), self.height()
        mid = h / 2
        p.fillRect(0, 0, w, h, QColor("#1b1b1b"))
        p.setPen(QPen(QColor("#333333")))
        p.drawLine(0, int(mid), w, int(mid))

        if self.view is None:
            return
        if self.pyramid is None:
            p.setPen(QColor("#888888"))
            p.drawText(6, int(mid) - 4, "… lade Waveform")
        else:
            self._draw_wave(p, w, h, mid)

        self._draw_markers(p, h)
        p.end()

    def _draw_wave(self, p: QPainter, w, h, mid):
        view = self.view
        spp = view.samples_per_pixel
        level = self.pyramid.level_for(spp)
        mins, maxs = self.pyramid.levels[level]
        spb = self.pyramid.samples_per_bucket(level)
        nb = len(mins)
        amp = mid * 0.9

        p.setPen(QPen(self.color))
        for x in range(w):
            frame = view.x_to_frame(x)
            if frame < 0 or frame >= self.frames:
                continue
            b = int(frame / spb)
            if b < 0 or b >= nb:
                continue
            y_top = mid - float(maxs[b]) * amp
            y_bot = mid - float(mins[b]) * amp
            p.drawLine(x, int(y_top), x, int(y_bot))

    def _draw_markers(self, p: QPainter, h):
        view = self.view

        def vline(frame, color, width=1, style=Qt.SolidLine):
            x = view.frame_to_x(frame)
            if 0 <= x <= self.width():
                pen = QPen(QColor(color)); pen.setWidth(width); pen.setStyle(style)
                p.setPen(pen)
                p.drawLine(int(x), 0, int(x), h)

        vline(self.in_point, "#00b0ff", 2)
        vline(self.out_point, "#00b0ff", 2)
        for s in self.splits:
            vline(s, "#f57900", 1, Qt.DashLine)
        vline(self.playhead, "#ffffff", 1)
