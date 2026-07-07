"""Audio I/O: import (scan/open/read) and export (WAV/MP3).

Thin layer over soundfile (libsndfile) and lameenc. Reads stream in blocks so
long files never need to be fully resident in memory.
"""
from __future__ import annotations

import os
import re
from typing import Callable, Sequence

import numpy as np
import soundfile as sf

from .dsp import mix_block
from .model import Track, TRACK_COLORS

AUDIO_EXTS = {".wav", ".flac", ".aif", ".aiff"}


class AudioSource:
    """A streamable mono view over one audio file.

    Multichannel files are downmixed to mono (mean). Reads past EOF are
    zero-padded so every track yields the same block length on the shared
    timeline.
    """

    def __init__(self, path: str):
        self.path = path
        self._sf = sf.SoundFile(path, mode="r")
        self.samplerate = self._sf.samplerate
        self.frames = len(self._sf)
        self.channels = self._sf.channels

    def read_block(self, start: int, n: int) -> np.ndarray:
        out = np.zeros(n, dtype=np.float32)
        if start >= self.frames or n <= 0:
            return out
        self._sf.seek(start)
        avail = min(n, self.frames - start)
        data = self._sf.read(avail, dtype="float32", always_2d=True)
        mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
        out[: len(mono)] = mono
        return out

    def close(self) -> None:
        self._sf.close()


def open_source(path: str) -> AudioSource:
    return AudioSource(path)


def _natural_key(name: str):
    # split into digit / non-digit chunks so ch2 < ch10
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def scan_session_folder(folder: str) -> list[str]:
    """Audio files in `folder`, naturally sorted by filename."""
    entries = [e for e in os.listdir(folder)
               if os.path.splitext(e)[1].lower() in AUDIO_EXTS]
    entries.sort(key=_natural_key)
    return [os.path.join(folder, e) for e in entries]


def load_track(path: str, index: int = 0) -> tuple[Track, AudioSource]:
    """Open a file and build its Track (name from filename stem)."""
    src = open_source(path)
    name = os.path.splitext(os.path.basename(path))[0]
    color = TRACK_COLORS[index % len(TRACK_COLORS)]
    track = Track(path=path, name=name, frames=src.frames, color=color)
    return track, src


def _float_to_int16(stereo: np.ndarray) -> np.ndarray:
    clipped = np.clip(stereo, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2")


def export_segment(
    sources: Sequence[AudioSource],
    gains: Sequence[float],
    pans: Sequence[float],
    mutes: Sequence[bool],
    solos: Sequence[bool],
    master_gain: float,
    seg: tuple[int, int],
    sample_rate: int,
    out_path: str,
    fmt: str = "wav",
    subtype: str = "PCM_24",
    bitrate: int = 320,
    block_size: int = 4096,
    progress: Callable[[float], None] | None = None,
) -> None:
    """Render one segment [start, end) of the mix to `out_path`.

    Uses the same `mix_block` as playback, so the export is bit-for-bit what
    the engine would produce. `fmt` is "wav" or "mp3".
    """
    start, end = seg
    total = max(1, end - start)

    if fmt == "mp3":
        _export_mp3(sources, gains, pans, mutes, solos, master_gain,
                    start, end, sample_rate, out_path, bitrate, block_size, progress)
        return

    with sf.SoundFile(out_path, mode="w", samplerate=sample_rate,
                      channels=2, subtype=subtype) as out:
        pos = start
        while pos < end:
            n = min(block_size, end - pos)
            blocks = [s.read_block(pos, n) for s in sources]
            stereo = mix_block(blocks, gains, pans, mutes, solos,
                               master_gain, n_frames=n)
            out.write(stereo)
            pos += n
            if progress:
                progress((pos - start) / total)


def _export_mp3(sources, gains, pans, mutes, solos, master_gain,
                start, end, sample_rate, out_path, bitrate, block_size, progress):
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(2)
    encoder.set_quality(2)  # 2 = high quality / near-best
    total = max(1, end - start)

    with open(out_path, "wb") as f:
        pos = start
        while pos < end:
            n = min(block_size, end - pos)
            blocks = [s.read_block(pos, n) for s in sources]
            stereo = mix_block(blocks, gains, pans, mutes, solos,
                               master_gain, n_frames=n)
            pcm = _float_to_int16(stereo)  # interleaved (n,2) int16
            f.write(encoder.encode(pcm.tobytes()))
            pos += n
            if progress:
                progress((pos - start) / total)
        f.write(encoder.flush())
