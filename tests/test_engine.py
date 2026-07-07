"""Tests for the non-hardware parts of the engine.

The streaming/OutputStream path needs PortAudio + a device and is verified
manually; here we cover the pure pieces.
"""
from uma.engine import MixState, audio_available
from uma.model import Track


def _track(name, gain=1.0, pan=0.0, mute=False, solo=False):
    return Track(path=f"/tmp/{name}.wav", name=name, frames=10,
                 gain=gain, pan=pan, mute=mute, solo=solo)


class TestMixState:
    def test_snapshots_track_parameters(self):
        tracks = [_track("a", gain=0.5, pan=-1.0),
                  _track("b", gain=1.0, pan=1.0, mute=True, solo=True)]
        st = MixState.for_tracks(tracks)
        assert st.gains == [0.5, 1.0]
        assert st.pans == [-1.0, 1.0]
        assert st.mutes == [False, True]
        assert st.solos == [False, True]
        assert st.master_gain == 1.0

    def test_empty_tracks(self):
        st = MixState.for_tracks([])
        assert st.gains == [] and st.pans == []


class TestAudioAvailable:
    def test_returns_bool_and_reason(self):
        ok, reason = audio_available()
        assert isinstance(ok, bool)
        assert isinstance(reason, str)
        # when unavailable, a reason must be given
        assert ok or reason
