"""One track's waveform lane, drawn against the shared ViewState.

Also draws the shared vertical markers (in/out, splits, playhead) so they line
up across every stacked lane.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal, QLine
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .viewport import ViewState, pick_marker
from ..peaks import pixel_envelope

LANE_HEIGHT = 90
GRAB_TOL = 6  # pixels within which a marker can be grabbed


class WaveformLane(QWidget):
    """Displays a peak pyramid and lets the shared markers be dragged.

    Emits frame-space signals; the main window owns the Session and applies
    them, then pushes the updated markers back via set_markers().
    """

    seek_requested = Signal(int)
    marker_grabbed = Signal(str, int)     # (kind, index)  kind in in/out/split
    marker_moved = Signal(int)            # new frame during a drag
    marker_released = Signal()
    split_add_requested = Signal(int)     # frame (double-click)
    split_remove_requested = Signal(int)  # split index (right-click)

    def __init__(self, color="#4e9a06", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(LANE_HEIGHT)
        self.setMouseTracking(True)  # so we can show a resize cursor on hover
        self.color = QColor(color)
        self.view: ViewState | None = None
        self.pyramid = None
        self.frames = 0
        self.playhead = 0
        self.in_point = 0
        self.out_point = 0
        self.splits: list[int] = []
        self._dragging = False
        self._wave_key = None      # cache: envelope only recomputed on view change
        self._wave_lines: list[QLine] = []

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
    def _candidates(self):
        cands = [("in", -1, self.in_point), ("out", -1, self.out_point)]
        cands += [("split", i, f) for i, f in enumerate(self.splits)]
        return cands

    def _frame_at(self, x) -> int:
        return int(max(0, min(self.frames, self.view.x_to_frame(x))))

    def mousePressEvent(self, ev):
        if self.view is None:
            return
        x = ev.position().x()
        if ev.button() == Qt.RightButton:
            hit = pick_marker(x, self._candidates(), self.view, GRAB_TOL)
            if hit and hit[0] == "split":
                self.split_remove_requested.emit(hit[1])
            return
        if ev.button() != Qt.LeftButton:
            return
        hit = pick_marker(x, self._candidates(), self.view, GRAB_TOL)
        if hit is not None:
            self._dragging = True
            self.marker_grabbed.emit(hit[0], hit[1])
        else:
            self.seek_requested.emit(self._frame_at(x))

    def mouseMoveEvent(self, ev):
        if self.view is None:
            return
        if self._dragging:
            self.marker_moved.emit(self._frame_at(ev.position().x()))
        else:
            hit = pick_marker(ev.position().x(), self._candidates(), self.view, GRAB_TOL)
            self.setCursor(Qt.SizeHorCursor if hit else Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev):
        if self._dragging and ev.button() == Qt.LeftButton:
            self._dragging = False
            self.marker_released.emit()

    def mouseDoubleClickEvent(self, ev):
        if self.view is not None and ev.button() == Qt.LeftButton:
            self.split_add_requested.emit(self._frame_at(ev.position().x()))

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
        amp = mid * 0.9

        key = (id(self.pyramid), level, round(view.start_frame, 1),
               round(spp, 4), w, h)
        if key != self._wave_key:
            vmin, vmax, valid = pixel_envelope(
                mins, maxs, spb, view.start_frame, spp, w, self.frames)
            y_top = (mid - vmax * amp).astype(int)
            y_bot = (mid - vmin * amp).astype(int)
            self._wave_lines = [QLine(x, int(y_top[x]), x, int(y_bot[x]))
                                for x in range(w) if valid[x]]
            self._wave_key = key

        p.setPen(QPen(self.color))
        p.drawLines(self._wave_lines)

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
