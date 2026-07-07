"""Pure DSP functions: panning and multitrack mixing.

No file or hardware I/O — fully unit-testable. Shared by the playback engine
and the offline exporter so that *what you hear is what you export*.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def pan_gains(pan: float) -> tuple[float, float]:
    """Constant-power pan law.

    pan in [-1, 1]: -1 = hard left, 0 = center, +1 = hard right.
    Returns (left_gain, right_gain) with left^2 + right^2 == 1, so the
    perceived loudness stays constant across the stereo field.
    """
    pan = max(-1.0, min(1.0, pan))
    angle = (pan + 1.0) * 0.25 * math.pi  # maps [-1,1] -> [0, pi/2]
    return math.cos(angle), math.sin(angle)


def mix_block(
    blocks: Sequence[np.ndarray],
    gains: Sequence[float],
    pans: Sequence[float],
    mutes: Sequence[bool],
    solos: Sequence[bool],
    master_gain: float,
    n_frames: int | None = None,
) -> np.ndarray:
    """Mix mono track blocks into one stereo block.

    All blocks must have the same length (the reader zero-pads past EOF).
    Because every track contributes the same sample range, tracks stay
    sample-accurately synchronous by construction.

    Returns a float32 array of shape (n_frames, 2).
    """
    if n_frames is None:
        n_frames = len(blocks[0]) if len(blocks) else 0

    out = np.zeros((n_frames, 2), dtype=np.float32)
    any_solo = any(solos)

    for block, gain, pan, mute, solo in zip(blocks, gains, pans, mutes, solos):
        if mute:
            continue
        if any_solo and not solo:
            continue
        left_g, right_g = pan_gains(pan)
        scaled = block * gain
        out[:, 0] += scaled * left_g
        out[:, 1] += scaled * right_g

    out *= master_gain
    return out
