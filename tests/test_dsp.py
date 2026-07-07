import numpy as np
import pytest

from uma.dsp import pan_gains, mix_block


class TestPanGains:
    def test_center_is_equal_power(self):
        left, right = pan_gains(0.0)
        assert left == pytest.approx(np.sqrt(0.5), abs=1e-9)
        assert right == pytest.approx(np.sqrt(0.5), abs=1e-9)

    def test_hard_left(self):
        left, right = pan_gains(-1.0)
        assert left == pytest.approx(1.0, abs=1e-9)
        assert right == pytest.approx(0.0, abs=1e-9)

    def test_hard_right(self):
        left, right = pan_gains(1.0)
        assert left == pytest.approx(0.0, abs=1e-9)
        assert right == pytest.approx(1.0, abs=1e-9)

    def test_constant_power_everywhere(self):
        # left^2 + right^2 == 1 for any pan position
        for pan in np.linspace(-1.0, 1.0, 21):
            left, right = pan_gains(float(pan))
            assert left**2 + right**2 == pytest.approx(1.0, abs=1e-9)


def _ones(n):
    return np.ones(n, dtype=np.float32)


class TestMixBlock:
    def test_single_center_track_scaled_by_pan_gain(self):
        out = mix_block([_ones(8)], gains=[1.0], pans=[0.0],
                        mutes=[False], solos=[False], master_gain=1.0)
        assert out.shape == (8, 2)
        assert out[:, 0] == pytest.approx(np.sqrt(0.5))
        assert out[:, 1] == pytest.approx(np.sqrt(0.5))

    def test_two_tracks_sum(self):
        out = mix_block([_ones(4), _ones(4)], gains=[1.0, 1.0], pans=[-1.0, -1.0],
                        mutes=[False, False], solos=[False, False], master_gain=1.0)
        # both hard-left: left channel = 1 + 1 = 2, right = 0
        assert out[:, 0] == pytest.approx(2.0)
        assert out[:, 1] == pytest.approx(0.0)

    def test_gain_scales_track(self):
        out = mix_block([_ones(4)], gains=[0.5], pans=[-1.0],
                        mutes=[False], solos=[False], master_gain=1.0)
        assert out[:, 0] == pytest.approx(0.5)

    def test_master_gain_scales_output(self):
        out = mix_block([_ones(4)], gains=[1.0], pans=[-1.0],
                        mutes=[False], solos=[False], master_gain=0.25)
        assert out[:, 0] == pytest.approx(0.25)

    def test_muted_track_is_silent(self):
        out = mix_block([_ones(4), _ones(4)], gains=[1.0, 1.0], pans=[-1.0, -1.0],
                        mutes=[True, False], solos=[False, False], master_gain=1.0)
        assert out[:, 0] == pytest.approx(1.0)  # only second track

    def test_solo_isolates_soloed_tracks(self):
        # track 0 soloed -> track 1 silent even though not muted
        out = mix_block([_ones(4), _ones(4)], gains=[1.0, 1.0], pans=[-1.0, 1.0],
                        mutes=[False, False], solos=[True, False], master_gain=1.0)
        assert out[:, 0] == pytest.approx(1.0)   # soloed left track
        assert out[:, 1] == pytest.approx(0.0)   # non-soloed right track silenced

    def test_hard_left_track_has_no_right_signal(self):
        out = mix_block([_ones(4)], gains=[1.0], pans=[-1.0],
                        mutes=[False], solos=[False], master_gain=1.0)
        assert out[:, 1] == pytest.approx(0.0)

    def test_no_tracks_returns_silence(self):
        out = mix_block([], gains=[], pans=[], mutes=[], solos=[],
                        master_gain=1.0, n_frames=4)
        assert out.shape == (4, 2)
        assert np.all(out == 0.0)
