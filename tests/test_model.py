import pytest

from uma.model import Track, Session


def make_track(frames, name="t"):
    return Track(path=f"/tmp/{name}.wav", name=name, frames=frames)


class TestSessionFrames:
    def test_length_is_longest_track(self):
        s = Session(sample_rate=48000, tracks=[make_track(100), make_track(250), make_track(80)])
        assert s.frames == 250

    def test_empty_session_has_zero_frames(self):
        s = Session(sample_rate=48000, tracks=[])
        assert s.frames == 0


class TestSessionDefaults:
    def test_out_point_defaults_to_full_length(self):
        s = Session(sample_rate=48000, tracks=[make_track(500)])
        assert s.in_point == 0
        assert s.effective_out == 500

    def test_explicit_out_point_used(self):
        s = Session(sample_rate=48000, tracks=[make_track(500)], out_point=400)
        assert s.effective_out == 400


class TestSegments:
    def test_no_splits_single_segment_over_trim(self):
        s = Session(sample_rate=48000, tracks=[make_track(1000)],
                    in_point=100, out_point=900)
        assert s.segments() == [(100, 900)]

    def test_splits_divide_the_session(self):
        s = Session(sample_rate=48000, tracks=[make_track(1000)],
                    in_point=0, out_point=1000, split_markers=[300, 700])
        assert s.segments() == [(0, 300), (300, 700), (700, 1000)]

    def test_splits_outside_trim_ignored(self):
        s = Session(sample_rate=48000, tracks=[make_track(1000)],
                    in_point=200, out_point=800, split_markers=[100, 500, 900])
        assert s.segments() == [(200, 500), (500, 800)]

    def test_splits_are_sorted_and_deduped(self):
        s = Session(sample_rate=48000, tracks=[make_track(1000)],
                    split_markers=[700, 300, 300])
        assert s.segments() == [(0, 300), (300, 700), (700, 1000)]

    def test_empty_range_returns_no_segments(self):
        s = Session(sample_rate=48000, tracks=[make_track(1000)],
                    in_point=500, out_point=500)
        assert s.segments() == []
