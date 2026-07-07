"""Real-time synchronous multitrack playback.

Design (see spec): a producer thread reads + mixes blocks ahead of time into a
bounded queue (the "ring buffer"); the sounddevice callback only drains it.
This keeps playback glitch-free even when streaming long files from disk, at
the cost of ~one buffer of latency on control changes — irrelevant for
monitoring.

`sounddevice`/PortAudio is imported lazily so the rest of the app runs on
machines without the PortAudio system library installed.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from .dsp import mix_block
from .io_audio import AudioSource


def audio_available() -> tuple[bool, str]:
    """Whether live playback is possible. Returns (ok, reason_if_not)."""
    try:
        import sounddevice  # noqa: F401
    except Exception as exc:  # PortAudio missing, no device, etc.
        return False, str(exc)
    return True, ""


@dataclass
class MixState:
    """Live, mutable per-track mix parameters, read by the producer thread.

    Single scalar/list-element assignments are atomic under the GIL, which is
    all the producer needs — it snapshots the values each block.
    """
    gains: list[float] = field(default_factory=list)
    pans: list[float] = field(default_factory=list)
    mutes: list[bool] = field(default_factory=list)
    solos: list[bool] = field(default_factory=list)
    master_gain: float = 1.0

    @classmethod
    def for_tracks(cls, tracks) -> "MixState":
        return cls(
            gains=[t.gain for t in tracks],
            pans=[t.pan for t in tracks],
            mutes=[t.mute for t in tracks],
            solos=[t.solo for t in tracks],
            master_gain=1.0,
        )


class PlaybackEngine:
    """Streams a synchronized stereo mix of `sources` to the audio device."""

    def __init__(
        self,
        sources: Sequence[AudioSource],
        state: MixState,
        sample_rate: int,
        end_frame: int,
        block_size: int = 1024,
        prefetch_blocks: int = 8,
        on_position: Callable[[int], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ):
        self.sources = list(sources)
        self.state = state
        self.sample_rate = sample_rate
        self.end_frame = end_frame
        self.block_size = block_size
        self.on_position = on_position
        self.on_stop = on_stop

        self._pos = 0                      # next frame the producer will read
        self._loop_end = end_frame
        self._q: queue.Queue = queue.Queue(maxsize=prefetch_blocks)
        self._generation = 0               # bumped on seek to invalidate queue
        self._lock = threading.Lock()
        self._playing = False
        self._producer: threading.Thread | None = None
        self._stream = None
        self.last_peak = 0.0               # max |sample| of the last output block

    # ---- transport ------------------------------------------------------
    def play(self, from_frame: int, to_frame: int | None = None) -> None:
        import sounddevice as sd

        self.stop()
        with self._lock:
            self._pos = max(0, from_frame)
            self._loop_end = self.end_frame if to_frame is None else to_frame
            self._generation += 1
            self._drain_queue()
            self._playing = True
        gen = self._generation
        self._producer = threading.Thread(
            target=self._produce, args=(gen,), daemon=True)
        self._producer.start()
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate, channels=2, dtype="float32",
            blocksize=self.block_size, callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._generation += 1
            self._drain_queue()
        if self._stream is not None:
            try:
                self._stream.stop(); self._stream.close()
            finally:
                self._stream = None
        if self._producer is not None:
            self._producer.join(timeout=1.0)
            self._producer = None

    def set_position(self, frame: int) -> None:
        """Seek. If playing, the producer restarts from `frame` immediately."""
        with self._lock:
            self._pos = max(0, frame)
            self._generation += 1
            self._drain_queue()
        if self.on_position:
            self.on_position(frame)

    @property
    def is_playing(self) -> bool:
        return self._playing

    def close(self) -> None:
        self.stop()

    # ---- internals ------------------------------------------------------
    def _drain_queue(self) -> None:
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass

    def _produce(self, gen: int) -> None:
        while True:
            with self._lock:
                if not self._playing or gen != self._generation:
                    return
                pos = self._pos
                end = self._loop_end
            if pos >= end:
                return
            n = min(self.block_size, end - pos)
            blocks = [s.read_block(pos, n) for s in self.sources]
            st = self.state
            stereo = mix_block(blocks, st.gains, st.pans, st.mutes, st.solos,
                               st.master_gain, n_frames=n)
            try:
                self._q.put((gen, pos, stereo), timeout=0.5)
            except queue.Full:
                continue  # re-check generation/playing, then retry
            with self._lock:
                if gen == self._generation:
                    self._pos = pos + n

    def _callback(self, outdata, frames, time_info, status):  # noqa: ARG002
        try:
            gen, pos, stereo = self._q.get_nowait()
        except queue.Empty:
            outdata[:] = 0
            # queue empty at end of material -> finish
            if not self._playing or self._pos >= self._loop_end:
                self._finish()
            return
        if gen != self._generation:
            outdata[:] = 0
            return
        m = len(stereo)
        outdata[:m] = stereo
        if m < frames:
            outdata[m:] = 0
        self.last_peak = float(np.abs(stereo).max()) if m else 0.0
        if self.on_position:
            self.on_position(pos)

    def _finish(self) -> None:
        # called from the audio thread; hand back to the app to tear down
        if self.on_stop:
            self.on_stop()
