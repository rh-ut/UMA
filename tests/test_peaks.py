import numpy as np
import pytest

from uma.peaks import compute_peaks, downsample_peaks, pixel_envelope, PeakPyramid


class TestComputePeaks:
    def test_min_max_per_bucket(self):
        x = np.array([0.0, 0.5, -0.5, 1.0, -1.0, 0.2], dtype=np.float32)
        mins, maxs = compute_peaks(x, bucket=3)
        # bucket 0: [0, .5, -.5] -> min -.5, max .5 ; bucket 1: [1,-1,.2] -> -1,1
        assert mins == pytest.approx([-0.5, -1.0])
        assert maxs == pytest.approx([0.5, 1.0])

    def test_partial_last_bucket(self):
        x = np.array([0.1, 0.2, 0.3, 0.9], dtype=np.float32)
        mins, maxs = compute_peaks(x, bucket=3)
        assert len(mins) == 2
        assert maxs[1] == pytest.approx(0.9)
        assert mins[1] == pytest.approx(0.9)

    def test_empty_input(self):
        mins, maxs = compute_peaks(np.array([], dtype=np.float32), bucket=4)
        assert len(mins) == 0 and len(maxs) == 0


class TestDownsamplePeaks:
    def test_aggregates_by_factor(self):
        mins = np.array([-0.5, -1.0, -0.2, -0.9], dtype=np.float32)
        maxs = np.array([0.5, 1.0, 0.2, 0.3], dtype=np.float32)
        dmin, dmax = downsample_peaks(mins, maxs, factor=2)
        # pair 0: min(-.5,-1)=-1 max(.5,1)=1 ; pair 1: min(-.2,-.9)=-.9 max(.2,.3)=.3
        assert dmin == pytest.approx([-1.0, -0.9])
        assert dmax == pytest.approx([1.0, 0.3])

    def test_preserves_extremes(self):
        # downsampling must never shrink the envelope
        mins = np.array([-0.1, -0.8, -0.3], dtype=np.float32)
        maxs = np.array([0.4, 0.2, 0.9], dtype=np.float32)
        dmin, dmax = downsample_peaks(mins, maxs, factor=4)
        assert dmin[0] == pytest.approx(-0.8)
        assert dmax[0] == pytest.approx(0.9)


class TestPixelEnvelope:
    def _bank(self):
        # 10 buckets of 100 samples each; distinctive extremes
        mins = np.array([-0.1, -0.5, -0.2, -0.9, -0.3,
                         -0.4, -0.6, -0.1, -0.8, -0.2], dtype=np.float32)
        maxs = np.array([0.1, 0.5, 0.2, 0.9, 0.3,
                         0.4, 0.6, 0.1, 0.8, 0.2], dtype=np.float32)
        return mins, maxs

    def test_each_pixel_aggregates_all_covered_buckets(self):
        mins, maxs = self._bank()
        # spp=200, spb=100 -> each pixel spans exactly 2 buckets
        vmin, vmax, valid = pixel_envelope(mins, maxs, spb=100, start_frame=0,
                                           spp=200, width=5, frames=1000)
        assert valid.all()
        assert vmin[0] == pytest.approx(min(-0.1, -0.5))   # buckets 0,1
        assert vmax[1] == pytest.approx(max(0.2, 0.9))     # buckets 2,3
        assert vmin[1] == pytest.approx(min(-0.2, -0.9))

    def test_last_pixel_does_not_swallow_the_tail(self):
        # view ends well before the data end; the last visible pixel must NOT
        # aggregate every remaining bucket (that was the blocky/tall-edge bug)
        mins, maxs = self._bank()
        vmin, vmax, valid = pixel_envelope(mins, maxs, spb=100, start_frame=0,
                                           spp=100, width=3, frames=1000)
        # pixel 2 covers only bucket 2, not buckets 2..9
        assert vmax[2] == pytest.approx(0.2)
        assert vmin[2] == pytest.approx(-0.2)

    def test_pixels_past_end_are_invalid(self):
        mins, maxs = self._bank()
        vmin, vmax, valid = pixel_envelope(mins, maxs, spb=100, start_frame=0,
                                           spp=100, width=20, frames=1000)
        assert valid[:10].all()
        assert not valid[10:].any()   # frames 1000.. are past the data


class TestLevelSelection:
    def test_picks_level_with_bucket_at_most_one_pixel(self):
        # base 256, factor 8 -> levels have 256, 2048, 16384, ... samples/bucket
        mins = np.zeros(100000, dtype=np.float32)
        pyr = PeakPyramid(mins, mins.copy(), base_bucket=256, factor=8)
        # at 3000 samples/pixel we want a level whose bucket <= 3000 (i.e. 2048),
        # never a coarser one (16384) that would look blocky
        lvl = pyr.level_for(3000)
        assert pyr.samples_per_bucket(lvl) <= 3000

    def test_extreme_zoom_falls_back_to_finest(self):
        mins = np.zeros(100000, dtype=np.float32)
        pyr = PeakPyramid(mins, mins.copy(), base_bucket=256, factor=8)
        assert pyr.level_for(10) == 0   # spp below base bucket -> finest level
