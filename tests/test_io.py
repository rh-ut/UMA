import os

import numpy as np
import soundfile as sf
import pytest

from uma.io_audio import (
    open_source, scan_session_folder, load_track, export_segment,
)


def write_wav(path, data, sr=48000, subtype="PCM_24"):
    sf.write(str(path), np.asarray(data, dtype=np.float32), sr, subtype=subtype)


class TestReadBlock:
    def test_reads_requested_range(self, tmp_path):
        p = tmp_path / "a.wav"
        write_wav(p, np.linspace(-1, 1, 100, dtype=np.float32))
        src = open_source(str(p))
        block = src.read_block(10, 16)
        assert block.shape == (16,)
        assert block.dtype == np.float32
        src.close()

    def test_pads_past_end_with_silence(self, tmp_path):
        p = tmp_path / "a.wav"
        write_wav(p, np.ones(10, dtype=np.float32))
        src = open_source(str(p))
        block = src.read_block(8, 5)   # only 2 real samples then EOF
        assert block[:2] == pytest.approx(1.0)
        assert block[2:] == pytest.approx(0.0)
        src.close()

    def test_start_past_end_is_all_silence(self, tmp_path):
        p = tmp_path / "a.wav"
        write_wav(p, np.ones(10, dtype=np.float32))
        src = open_source(str(p))
        assert src.read_block(50, 4) == pytest.approx(0.0)
        src.close()


class TestScanFolder:
    def test_natural_sort_of_channel_files(self, tmp_path):
        for name in ["ch10.wav", "ch2.wav", "ch1.wav", "notes.txt"]:
            (tmp_path / name).write_bytes(b"") if name.endswith(".txt") else \
                write_wav(tmp_path / name, np.zeros(4, dtype=np.float32))
        found = [os.path.basename(p) for p in scan_session_folder(str(tmp_path))]
        assert found == ["ch1.wav", "ch2.wav", "ch10.wav"]

    def test_picks_up_flac_too(self, tmp_path):
        write_wav(tmp_path / "a.wav", np.zeros(4, dtype=np.float32))
        sf.write(str(tmp_path / "b.flac"), np.zeros(4, dtype=np.float32), 48000)
        found = [os.path.basename(p) for p in scan_session_folder(str(tmp_path))]
        assert set(found) == {"a.wav", "b.flac"}


class TestLoadTrack:
    def test_builds_track_with_name_and_frames(self, tmp_path):
        p = tmp_path / "CH 3 Bass.wav"
        write_wav(p, np.zeros(123, dtype=np.float32))
        track, src = load_track(str(p))
        assert track.frames == 123
        assert track.name == "CH 3 Bass"
        assert src.samplerate == 48000
        src.close()


class TestExport:
    def test_wav_roundtrip_matches_mix(self, tmp_path):
        # two mono tracks, hard-left and hard-right, exported and reread
        write_wav(tmp_path / "l.wav", np.full(64, 0.5, dtype=np.float32))
        write_wav(tmp_path / "r.wav", np.full(64, 0.25, dtype=np.float32))
        sl = open_source(str(tmp_path / "l.wav"))
        sr = open_source(str(tmp_path / "r.wav"))
        out = tmp_path / "mix.wav"
        export_segment(
            sources=[sl, sr],
            gains=[1.0, 1.0], pans=[-1.0, 1.0],
            mutes=[False, False], solos=[False, False],
            master_gain=1.0, seg=(0, 64), sample_rate=48000,
            out_path=str(out), fmt="wav", subtype="PCM_24", block_size=16,
        )
        data, rate = sf.read(str(out), dtype="float32")
        assert rate == 48000
        assert data.shape == (64, 2)
        assert data[:, 0] == pytest.approx(0.5, abs=1e-4)   # left track only in L
        assert data[:, 1] == pytest.approx(0.25, abs=1e-4)  # right track only in R
        sl.close(); sr.close()

    def test_mp3_export_creates_nonempty_file(self, tmp_path):
        write_wav(tmp_path / "a.wav", np.sin(np.linspace(0, 100, 4800)).astype(np.float32))
        s = open_source(str(tmp_path / "a.wav"))
        out = tmp_path / "mix.mp3"
        export_segment(
            sources=[s], gains=[1.0], pans=[0.0], mutes=[False], solos=[False],
            master_gain=1.0, seg=(0, 4800), sample_rate=48000,
            out_path=str(out), fmt="mp3", bitrate=192, block_size=1152,
        )
        assert out.exists() and out.stat().st_size > 0
        s.close()

    def test_segment_export_only_covers_range(self, tmp_path):
        # ramp so we can tell which slice was written
        ramp = np.arange(100, dtype=np.float32) / 100.0
        write_wav(tmp_path / "a.wav", ramp)
        s = open_source(str(tmp_path / "a.wav"))
        out = tmp_path / "seg.wav"
        export_segment(
            sources=[s], gains=[1.0], pans=[-1.0], mutes=[False], solos=[False],
            master_gain=1.0, seg=(20, 30), sample_rate=48000,
            out_path=str(out), fmt="wav", subtype="PCM_24", block_size=8,
        )
        data, _ = sf.read(str(out), dtype="float32")
        assert data.shape == (10, 2)
        assert data[0, 0] == pytest.approx(0.20, abs=1e-4)
        assert data[-1, 0] == pytest.approx(0.29, abs=1e-4)
        s.close()
