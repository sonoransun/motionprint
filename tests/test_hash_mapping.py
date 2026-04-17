"""Tests for hash-to-visual parameter mapping."""

import numpy as np
import pytest

from motionprint.sha256_state import sha256_with_states
from motionprint.hash_mapping import compute_visual_params, interpolate_keyframes
from motionprint.palette import PRESETS, resolve_palette


def test_deterministic():
    r = sha256_with_states(b"test")
    p1 = compute_visual_params(r)
    p2 = compute_visual_params(r)
    assert p1.base_shape == p2.base_shape
    assert p1.primary_color == p2.primary_color
    assert np.array_equal(p1.keyframes, p2.keyframes)


def test_different_inputs():
    r1 = sha256_with_states(b"hello")
    r2 = sha256_with_states(b"world")
    p1 = compute_visual_params(r1)
    p2 = compute_visual_params(r2)
    # At least some parameters should differ
    assert p1.primary_color != p2.primary_color or p1.base_shape != p2.base_shape


def test_color_ranges():
    r = sha256_with_states(b"color test")
    p = compute_visual_params(r)
    for c in [p.primary_color, p.secondary_color, p.background_color]:
        for channel in c:
            assert 0.0 <= channel <= 1.0


def test_keyframes_shape():
    r = sha256_with_states(b"keyframes")
    p = compute_visual_params(r)
    assert p.keyframes.shape == (64, 8)  # single block
    assert p.keyframes.dtype == np.float32
    assert np.all(p.keyframes >= 0.0)
    assert np.all(p.keyframes <= 1.0)


def test_interpolate_endpoints():
    kf = np.array([[0.0] * 8, [1.0] * 8], dtype=np.float32)
    start = interpolate_keyframes(kf, 0.0)
    end = interpolate_keyframes(kf, 1.0)
    np.testing.assert_allclose(start, 0.0, atol=0.01)
    np.testing.assert_allclose(end, 1.0, atol=0.01)


def test_interpolate_midpoint():
    kf = np.array([[0.0] * 8, [1.0] * 8], dtype=np.float32)
    mid = interpolate_keyframes(kf, 0.5)
    # Should be approximately 0.5
    np.testing.assert_allclose(mid, 0.5, atol=0.15)


def test_shape_is_valid():
    r = sha256_with_states(b"shape")
    p = compute_visual_params(r)
    valid_shapes = {"icosphere", "torus", "superellipsoid", "octahedron", "twisted_torus"}
    assert p.base_shape in valid_shapes


def test_default_palette_matches_no_palette_arg():
    r = sha256_with_states(b"regression")
    baseline = compute_visual_params(r)
    explicit = compute_visual_params(r, palette=PRESETS["default"])
    assert baseline.primary_color == explicit.primary_color
    assert baseline.secondary_color == explicit.secondary_color
    assert baseline.background_color == explicit.background_color


def test_speed_multiplier_defaults_to_one():
    r = sha256_with_states(b"speed")
    p = compute_visual_params(r)
    assert p.speed_multiplier == 1.0
    assert p.palette_name == "default"


def test_speed_multiplier_is_carried():
    r = sha256_with_states(b"speed")
    p = compute_visual_params(r, speed_multiplier=2.5)
    assert p.speed_multiplier == 2.5


def test_palette_name_is_carried():
    r = sha256_with_states(b"palette")
    p = compute_visual_params(r, palette=PRESETS["vibrant"])
    assert p.palette_name == "vibrant"


def test_keyframes_independent_of_palette():
    r = sha256_with_states(b"keyframes invariant")
    base = compute_visual_params(r)
    vibrant = compute_visual_params(r, palette=PRESETS["vibrant"])
    np.testing.assert_array_equal(base.keyframes, vibrant.keyframes)


def test_palette_changes_colors():
    r = sha256_with_states(b"color change")
    base = compute_visual_params(r)
    cyber = compute_visual_params(r, palette=PRESETS["cyberpunk"])
    assert base.primary_color != cyber.primary_color


def test_override_color_applied():
    r = sha256_with_states(b"override")
    spec = resolve_palette("default", primary_hex="#ff00aa")
    p = compute_visual_params(r, palette=spec)
    assert p.primary_color == pytest.approx((1.0, 0.0, 0xAA / 255))
