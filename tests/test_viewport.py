import pytest

from uma.ui.viewport import ViewState, pick_marker


class TestMapping:
    def test_frame_to_x_at_origin(self):
        v = ViewState(start_frame=0, samples_per_pixel=100, sample_rate=48000)
        assert v.frame_to_x(0) == pytest.approx(0)
        assert v.frame_to_x(1000) == pytest.approx(10)

    def test_x_to_frame_inverse(self):
        v = ViewState(start_frame=500, samples_per_pixel=50, sample_rate=48000)
        for x in (0, 12.5, 100):
            assert v.frame_to_x(v.x_to_frame(x)) == pytest.approx(x)

    def test_start_offset_shifts_mapping(self):
        v = ViewState(start_frame=1000, samples_per_pixel=10, sample_rate=48000)
        assert v.frame_to_x(1000) == pytest.approx(0)
        assert v.frame_to_x(1100) == pytest.approx(10)


class TestZoom:
    def test_zoom_keeps_pivot_frame_fixed(self):
        v = ViewState(start_frame=0, samples_per_pixel=100, sample_rate=48000)
        pivot_x = 40
        frame_before = v.x_to_frame(pivot_x)
        v.zoom(0.5, pivot_x)   # zoom in: fewer samples per pixel
        assert v.samples_per_pixel == pytest.approx(50)
        assert v.x_to_frame(pivot_x) == pytest.approx(frame_before)

    def test_zoom_clamps_to_min_spp(self):
        v = ViewState(start_frame=0, samples_per_pixel=1.0, sample_rate=48000)
        v.zoom(0.001, 0, min_spp=0.5)
        assert v.samples_per_pixel >= 0.5


class TestPickMarker:
    def setup_method(self):
        # 10 samples per pixel; frame 1000 -> x 100, frame 2000 -> x 200
        self.v = ViewState(start_frame=0, samples_per_pixel=10, sample_rate=48000)
        self.cands = [("in", -1, 0), ("out", -1, 5000),
                      ("split", 0, 1000), ("split", 1, 2000)]

    def test_picks_marker_within_tolerance(self):
        # click at x=102 -> nearest is split@frame1000 (x=100)
        hit = pick_marker(102, self.cands, self.v, tol=5)
        assert hit == ("split", 0)

    def test_returns_none_when_far(self):
        assert pick_marker(150, self.cands, self.v, tol=5) is None

    def test_picks_nearest_of_several(self):
        # x=198 -> split@frame2000 (x=200) is nearest within tol
        assert pick_marker(198, self.cands, self.v, tol=5) == ("split", 1)

    def test_in_and_out_are_pickable(self):
        assert pick_marker(1, self.cands, self.v, tol=5) == ("in", -1)
        assert pick_marker(500, self.cands, self.v, tol=5) == ("out", -1)
