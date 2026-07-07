"""Waveform peak computation (min/max envelopes and a resolution pyramid).

Pure numpy. The base level is computed once per track (streamed in blocks for
long files); coarser levels are derived by aggregation so zooming never has to
re-read the raw samples.
"""
from __future__ import annotations

import numpy as np


def compute_peaks(samples: np.ndarray, bucket: int) -> tuple[np.ndarray, np.ndarray]:
    """Min/max envelope of `samples` grouped into buckets of `bucket` samples.

    Returns (mins, maxs) float32 arrays, one entry per bucket. A partial final
    bucket is kept.
    """
    n = len(samples)
    if n == 0:
        return (np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32))
    nbuckets = (n + bucket - 1) // bucket
    pad = nbuckets * bucket - n
    if pad:
        # edge-pad the last bucket; repeating an existing value can't widen min/max
        samples = np.pad(samples, (0, pad), mode="edge")
    grid = samples.reshape(nbuckets, bucket)
    return grid.min(axis=1).astype(np.float32), grid.max(axis=1).astype(np.float32)


def downsample_peaks(mins: np.ndarray, maxs: np.ndarray, factor: int
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Aggregate an envelope to a coarser one by grouping `factor` entries.

    Extremes are preserved (min of mins, max of maxs).
    """
    n = len(mins)
    if n == 0:
        return (np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32))
    ngroups = (n + factor - 1) // factor
    pad = ngroups * factor - n
    if pad:
        mins = np.pad(mins, (0, pad), mode="edge")
        maxs = np.pad(maxs, (0, pad), mode="edge")
    dmin = mins.reshape(ngroups, factor).min(axis=1).astype(np.float32)
    dmax = maxs.reshape(ngroups, factor).max(axis=1).astype(np.float32)
    return dmin, dmax


def pixel_envelope(mins: np.ndarray, maxs: np.ndarray, spb: int,
                   start_frame: float, spp: float, width: int, frames: int
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-pixel min/max envelope for a waveform view.

    For each of `width` pixel columns, aggregates every peak bucket that falls
    within that column's frame span (min of mins, max of maxs) — so the drawn
    envelope is smooth and accurate at any zoom, instead of blocky when buckets
    are wider than a pixel. `spb` is samples per bucket of the chosen level.

    Returns (vmin, vmax, valid); `valid[x]` is False where the column lies past
    the end of the data.
    """
    vmin = np.zeros(width, dtype=np.float32)
    vmax = np.zeros(width, dtype=np.float32)
    valid = np.zeros(width, dtype=bool)
    nb = len(mins)
    if nb == 0 or width <= 0:
        return vmin, vmax, valid

    edges = start_frame + np.arange(width + 1) * spp   # frame at each pixel edge
    bounds = np.clip((edges / spb).astype(np.int64), 0, nb)
    lo = bounds[:width]
    hi = bounds[1:]

    f0 = edges[:width]
    valid = (f0 >= 0) & (f0 < frames) & (lo < nb)

    idx = np.clip(lo, 0, nb - 1)
    vmin = np.minimum.reduceat(mins, idx).astype(np.float32)
    vmax = np.maximum.reduceat(maxs, idx).astype(np.float32)

    # reduceat lumps [idx[-1]:] into the final column; recompute it exactly
    l, h = int(idx[width - 1]), int(hi[width - 1])
    if h > l:
        vmin[width - 1] = mins[l:h].min()
        vmax[width - 1] = maxs[l:h].max()
    else:
        vmin[width - 1] = mins[l]
        vmax[width - 1] = maxs[l]
    return vmin, vmax, valid


class PeakPyramid:
    """A stack of min/max envelopes at geometrically increasing bucket sizes.

    level 0 has bucket = base_bucket samples; each further level is `factor`
    times coarser. The UI picks the finest level whose bucket >= samples-per-pixel.
    """

    def __init__(self, base_mins: np.ndarray, base_maxs: np.ndarray,
                 base_bucket: int, factor: int = 8, min_buckets: int = 2):
        self.base_bucket = base_bucket
        self.factor = factor
        self.levels: list[tuple[np.ndarray, np.ndarray]] = [(base_mins, base_maxs)]
        mins, maxs = base_mins, base_maxs
        while len(mins) > min_buckets:
            mins, maxs = downsample_peaks(mins, maxs, factor)
            self.levels.append((mins, maxs))

    def samples_per_bucket(self, level: int) -> int:
        return self.base_bucket * (self.factor ** level)

    def level_for(self, samples_per_pixel: float) -> int:
        """Coarsest level whose buckets are no wider than one pixel.

        Buckets finer than a pixel let each pixel aggregate several of them
        into a smooth envelope; a level coarser than a pixel would make
        neighbouring pixels share one bucket value and look blocky. Falls back
        to the finest level when even that is coarser than a pixel (deep zoom).
        """
        best = 0
        for lvl in range(len(self.levels)):
            if self.samples_per_bucket(lvl) <= samples_per_pixel:
                best = lvl
            else:
                break
        return best

    @classmethod
    def from_samples(cls, samples: np.ndarray, base_bucket: int,
                     factor: int = 8) -> "PeakPyramid":
        mins, maxs = compute_peaks(samples, base_bucket)
        return cls(mins, maxs, base_bucket, factor)
