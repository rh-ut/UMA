"""Timeline view mapping: frames <-> pixels, plus zoom/scroll.

Pure (no Qt), so the coordinate math is unit-tested. Shared by the ruler and
every waveform lane so they stay aligned on one horizontal scale.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ViewState:
    start_frame: float          # frame at x = 0
    samples_per_pixel: float    # horizontal scale
    sample_rate: int

    def frame_to_x(self, frame: float) -> float:
        return (frame - self.start_frame) / self.samples_per_pixel

    def x_to_frame(self, x: float) -> float:
        return self.start_frame + x * self.samples_per_pixel

    def zoom(self, factor: float, pivot_x: float,
             min_spp: float = 1.0, max_spp: float = 1e9) -> None:
        """Scale by `factor` (<1 zooms in) keeping the frame under pivot_x fixed."""
        pivot_frame = self.x_to_frame(pivot_x)
        new_spp = self.samples_per_pixel * factor
        new_spp = max(min_spp, min(max_spp, new_spp))
        self.samples_per_pixel = new_spp
        # keep pivot_frame at pivot_x: start = pivot_frame - pivot_x*spp
        self.start_frame = pivot_frame - pivot_x * new_spp

    def fit(self, total_frames: int, width_px: int) -> None:
        """Scale so `total_frames` fills `width_px`, scrolled to the start."""
        self.start_frame = 0
        self.samples_per_pixel = max(1.0, total_frames / max(1, width_px))


def pick_marker(x: float, candidates: Sequence[tuple], view: ViewState,
                tol: float = 5.0):
    """Return the (kind, index) of the marker nearest pixel `x`, or None.

    `candidates` is a sequence of (kind, index, frame). A marker is only
    picked if its screen position is within `tol` pixels of `x`.
    """
    best = None
    best_dist = tol
    for kind, index, frame in candidates:
        dist = abs(view.frame_to_x(frame) - x)
        if dist <= best_dist:
            best_dist = dist
            best = (kind, index)
    return best
