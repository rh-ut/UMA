"""Headless smoke test of the GUI stack (QT_QPA_PLATFORM=offscreen).

Not a unit test — exercises import -> peak build -> paint -> markers -> export
end to end to catch wiring/rendering errors without a real display or audio.
"""
import os
import sys
import tempfile
import time

import numpy as np
import soundfile as sf

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

from uma.ui.main_window import MainWindow
from uma.io_audio import open_source, export_segment
from uma.ui.export_dialog import ExportOptions


def make_tracks(d, sr=48000, secs=1.0):
    n = int(sr * secs)
    t = np.arange(n) / sr
    paths = []
    for i, f in enumerate((220.0, 440.0, 660.0)):
        y = (0.5 * np.sin(2 * np.pi * f * t)).astype(np.float32)
        p = os.path.join(d, f"ch{i+1}.wav")
        sf.write(p, y, sr, subtype="PCM_24")
        paths.append(p)
    return paths


def main():
    app = QApplication(sys.argv)
    d = tempfile.mkdtemp(prefix="uma_smoke_")
    paths = make_tracks(d)

    win = MainWindow()
    win.resize(1000, 600)
    win._load_tracks(paths)
    assert win.session is not None
    assert len(win.rows) == 3
    print(f"loaded {len(win.rows)} tracks, {win.session.frames} frames")

    # wait for peak workers to finish, pumping the event loop for signals
    deadline = time.time() + 10
    while any(w.isRunning() for w in win.workers) and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    QCoreApplication.processEvents()
    have_peaks = sum(r.lane.pyramid is not None for r in win.rows)
    print(f"peaks ready on {have_peaks}/3 lanes")
    assert have_peaks == 3, "peak workers did not finish"

    # exercise view + paint (force paintEvent through _draw_wave)
    win.fit_view()
    win.show()
    QCoreApplication.processEvents()
    for r in win.rows:
        r.lane.grab()  # forces a paint pass offscreen
    print("paint pass ok")

    # markers + segments
    win.play_pos = win.session.frames // 4
    win.set_in()
    win.play_pos = win.session.frames * 3 // 4
    win.set_out()
    win.play_pos = win.session.frames // 2
    win.add_split()
    segs = win.session.segments()
    print(f"segments: {segs}")
    assert len(segs) == 2

    # mix params live
    win._on_gain(0, 0.5)
    win._on_pan(0, -1.0)
    win._on_mute(1, True)
    assert win.state.gains[0] == 0.5 and win.state.mutes[1] is True

    # export both segments (wav) + one mp3, bypassing dialogs
    out_wav = [os.path.join(d, f"seg_{i}.wav") for i in range(len(segs))]
    win._run_export(list(zip(segs, out_wav)),
                    ExportOptions("wav", "PCM_24", 320))
    for p in out_wav:
        assert os.path.exists(p) and os.path.getsize(p) > 0, p
    data, rate = sf.read(out_wav[0], dtype="float32")
    assert data.shape[1] == 2 and rate == 48000
    print(f"wav export ok: {[os.path.basename(p) for p in out_wav]}")

    out_mp3 = os.path.join(d, "seg.mp3")
    win._run_export([(segs[0], out_mp3)], ExportOptions("mp3", "PCM_24", 192))
    assert os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0
    print(f"mp3 export ok: {os.path.getsize(out_mp3)} bytes")

    win.close()
    print("SMOKE OK")


if __name__ == "__main__":
    main()
