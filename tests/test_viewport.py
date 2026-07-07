import pytest

from uma.ui.viewport import ViewState


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
