"""Background computation of a track's peak pyramid.

Streams the file in large chunks so long recordings don't spike memory, and
reports the finished pyramid back on the GUI thread via a Qt signal.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from ..io_audio import open_source
from ..peaks import compute_peaks, PeakPyramid

BASE_BUCKET = 64      # finer base -> sharper detail when zoomed in
FACTOR = 8
CHUNK = 1 << 20  # ~1M frames per read


class PeakWorker(QThread):
    ready = Signal(int, object)   # (track_index, PeakPyramid)

    def __init__(self, index: int, path: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.path = path

    def run(self):
        src = open_source(self.path)
        try:
            mins_parts, maxs_parts = [], []
            pos = 0
            # read in multiples of BASE_BUCKET so buckets align across chunks
            step = (CHUNK // BASE_BUCKET) * BASE_BUCKET
            while pos < src.frames:
                n = min(step, src.frames - pos)
                block = src.read_block(pos, n)
                mn, mx = compute_peaks(block, BASE_BUCKET)
                mins_parts.append(mn); maxs_parts.append(mx)
                pos += n
            if mins_parts:
                base_mins = np.concatenate(mins_parts)
                base_maxs = np.concatenate(maxs_parts)
            else:
                base_mins = np.empty(0, dtype=np.float32)
                base_maxs = np.empty(0, dtype=np.float32)
            pyramid = PeakPyramid(base_mins, base_maxs, BASE_BUCKET, FACTOR)
            self.ready.emit(self.index, pyramid)
        finally:
            src.close()
