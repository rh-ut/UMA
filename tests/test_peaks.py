import numpy as np
import pytest

from uma.peaks import compute_peaks, downsample_peaks


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
