"""Data model: Session and Track.

Pure data + derivation logic — no GUI, no audio hardware. Everything is
sample-based on a single shared timeline, so synchronicity is structural:
there is no per-track time offset to drift.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# A small palette cycled through for track colors in the UI.
TRACK_COLORS = [
    "#4e9a06", "#3465a4", "#c4a000", "#cc0000",
    "#75507b", "#06989a", "#f57900", "#8f5902",
]


@dataclass
class Track:
    """One channel file on the shared timeline."""
    path: str
    name: str
    frames: int
    gain: float = 1.0
    pan: float = 0.0          # -1 left .. +1 right
    mute: bool = False
    solo: bool = False
    color: str = "#4e9a06"


@dataclass
class Session:
    """A project: several tracks sharing one sample-based timeline."""
    sample_rate: int
    tracks: list[Track] = field(default_factory=list)
    in_point: int = 0
    out_point: int | None = None   # None -> full length
    split_markers: list[int] = field(default_factory=list)
    master_gain: float = 1.0

    @property
    def frames(self) -> int:
        """Timeline length = the longest track (shorter tracks are silence after)."""
        return max((t.frames for t in self.tracks), default=0)

    @property
    def effective_out(self) -> int:
        """out_point, or the full length when not set."""
        return self.frames if self.out_point is None else self.out_point

    def segments(self) -> list[tuple[int, int]]:
        """Export segments between in/out, divided at the split markers.

        Splits outside the trim range are ignored; markers are sorted and
        de-duplicated. An empty range yields no segments.
        """
        lo, hi = self.in_point, self.effective_out
        if lo >= hi:
            return []
        splits = sorted({s for s in self.split_markers if lo < s < hi})
        bounds = [lo, *splits, hi]
        return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
