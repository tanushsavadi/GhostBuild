import numpy as np
import pytest

from ghostbuild_pi.features import (FeatureExtractor, downscale, laplacian_variance, motion_fraction, parse_roi,
                                    to_gray)

rng = np.random.default_rng(1)


def textured(h=240, w=320):
    yy, xx = np.mgrid[0:h, 0:w]
    return 85 + (((xx // 16) + (yy // 16)) % 2) * 70 + rng.normal(0, 2, (h, w))


def test_covered_lens_is_dark_and_flat():
    f = FeatureExtractor().process(np.clip(5 + rng.normal(0, 0.6, (240, 320)), 0, 255))
    assert f.mean_luma < 10 and f.luma_std < 3 and f.detail < 20


def test_textured_scene_has_contrast_and_detail():
    f = FeatureExtractor().process(textured())
    assert 90 < f.mean_luma < 150 and f.luma_std > 25 and f.detail > 100


def test_defocused_flat_bright_is_bright_but_flat():
    f = FeatureExtractor().process(200 + rng.normal(0, 0.5, (240, 320)))
    assert f.mean_luma > 190 and f.luma_std < 3 and f.detail < 10


def test_noise_has_high_detail_but_is_not_a_scene():
    n = FeatureExtractor().process(np.clip(128 + rng.normal(0, 40, (240, 320)), 0, 255))
    flat = FeatureExtractor().process(np.full((240, 320), 128.0))
    assert n.detail > 50 * (flat.detail + 1)
    assert flat.detail == 0 and flat.luma_std == 0


def test_laplacian_variance_of_constant_and_ramp_is_zero():
    assert laplacian_variance(np.full((10, 10), 7.0, dtype=np.float32)) == 0.0
    ramp = np.tile(np.arange(10, dtype=np.float32), (10, 1))
    assert laplacian_variance(ramp) == pytest.approx(0.0)


def test_laplacian_variance_known_value():
    img = np.zeros((5, 5), dtype=np.float32)
    img[2, 2] = 10.0  # single impulse: interior 3x3 laplacian = -40 at centre, +10 at 4 neighbours
    lap = np.array([0, 10, 0, 10, -40, 10, 0, 10, 0], dtype=np.float64)
    assert laplacian_variance(img) == pytest.approx(lap.var(), rel=1e-5)


def test_moving_blob_gives_motion_and_static_gives_zero():
    ex = FeatureExtractor()
    a = np.full((240, 320), 100.0)
    b = a.copy()
    b[60:180, 20:120] = 220.0  # 100x120 of 320x240 = 15.6%
    assert ex.process(a).motion == 0.0  # first frame has no baseline
    m = ex.process(b).motion
    assert 0.14 < m < 0.17
    assert ex.process(b).motion == 0.0


def test_motion_respects_roi():
    a = np.full((120, 160), 100.0)
    b = a.copy()
    b[:, :80] = 220.0  # left half changes
    left = motion_fraction(a, b, (0.0, 0.0, 0.5, 1.0))
    right = motion_fraction(a, b, (0.5, 0.0, 1.0, 1.0))
    assert left == 1.0 and right == 0.0


def test_motion_ignores_small_noise_below_threshold():
    a = np.full((120, 160), 100.0)
    assert motion_fraction(a, a + 5.0) == 0.0


def test_downscale_shapes_and_rgb_rgba_gray():
    assert downscale(to_gray(np.zeros((480, 640, 3), np.uint8))).shape == (120, 160)
    assert to_gray(np.zeros((10, 10, 4), np.uint8)).shape == (10, 10)
    assert to_gray(np.zeros((10, 10), np.uint8)).shape == (10, 10)
    assert downscale(np.zeros((60, 80), np.float32)).shape == (60, 80)  # never upsamples
    with pytest.raises(ValueError):
        to_gray(np.zeros((4, 4, 2)))


def test_values_stay_in_contract_ranges():
    f = FeatureExtractor().process(np.full((240, 320, 3), 255, np.uint8))
    assert 0 <= f.mean_luma <= 255 and f.luma_std >= 0 and f.detail >= 0 and 0 <= f.motion <= 1


def test_parse_roi():
    assert parse_roi("0.1,0.2,0.9,0.8") == (0.1, 0.2, 0.9, 0.8)
    for bad in ("1,2,3", "0,0,2,1", "0.5,0,0.4,1", "a,b,c,d"):
        with pytest.raises(ValueError):
            parse_roi(bad)
