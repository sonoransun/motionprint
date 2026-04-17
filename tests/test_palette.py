"""Tests for palette presets, hex overrides, and apply_palette."""

from __future__ import annotations

import colorsys

import pytest

from motionprint.palette import (
    PRESETS,
    PaletteSpec,
    apply_palette,
    parse_hex_color,
    resolve_palette,
)


def _legacy_colors(digest: bytes):
    """Reproduction of the pre-palette color formulas for regression testing."""
    b = digest

    def hls(h, s, l):
        return colorsys.hls_to_rgb(h / 360.0, l, s)

    primary = hls(b[4] / 255 * 360, 0.5 + b[5] / 510, 0.35 + b[6] / 425)
    secondary = hls(b[7] / 255 * 360, 0.5 + b[8] / 510, 0.35 + b[9] / 425)
    background = hls(
        b[10] / 255 * 360, 0.05 + b[11] / 2550, 0.08 + b[11] / 1275
    )
    return primary, secondary, background


# --- parse_hex_color ----------------------------------------------------------


def test_parse_hex_accepts_with_and_without_hash():
    assert parse_hex_color("#ff0000") == pytest.approx((1.0, 0.0, 0.0))
    assert parse_hex_color("00ff00") == pytest.approx((0.0, 1.0, 0.0))
    assert parse_hex_color("#0000FF") == pytest.approx((0.0, 0.0, 1.0))


@pytest.mark.parametrize("bad", ["", "#", "#abcde", "#abcdefg", "xyz123", "##ff0000", "0xff0000"])
def test_parse_hex_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_hex_color(bad)


# --- default palette regression ----------------------------------------------


@pytest.mark.parametrize("seed", [b"", b"\x00" * 32, bytes(range(32)), b"\xff" * 32])
def test_default_palette_matches_legacy_bytes(seed):
    digest = (seed + b"\x00" * 32)[:32]
    primary, secondary, background = apply_palette(PRESETS["default"], digest)
    expected = _legacy_colors(digest)
    assert primary == expected[0]
    assert secondary == expected[1]
    assert background == expected[2]


# --- preset band enforcement --------------------------------------------------


def _digest_with(bytes_map: dict[int, int]) -> bytes:
    b = bytearray(32)
    for i, v in bytes_map.items():
        b[i] = v
    return bytes(b)


@pytest.mark.parametrize("byte_val", [0, 64, 128, 200, 255])
def test_pastel_primary_sat_light_in_band(byte_val):
    spec = PRESETS["pastel"]
    digest = _digest_with({5: byte_val, 6: byte_val})
    primary, _, _ = apply_palette(spec, digest)
    h, l, s = colorsys.rgb_to_hls(*primary)
    assert spec.primary_sat_range[0] - 1e-6 <= s <= spec.primary_sat_range[1] + 1e-6
    assert spec.primary_light_range[0] - 1e-6 <= l <= spec.primary_light_range[1] + 1e-6


@pytest.mark.parametrize("byte_val", [0, 64, 128, 200, 255])
def test_sunset_primary_hue_in_band(byte_val):
    spec = PRESETS["sunset"]
    digest = _digest_with({4: byte_val, 5: 128, 6: 128})
    primary, _, _ = apply_palette(spec, digest)
    h, l, s = colorsys.rgb_to_hls(*primary)
    h_deg = h * 360.0
    lo, hi = spec.primary_hue_range
    assert lo - 0.5 <= h_deg <= hi + 0.5


def test_mono_is_nearly_gray():
    spec = PRESETS["mono"]
    for byte_val in (0, 128, 255):
        digest = _digest_with({4: byte_val, 5: byte_val, 6: byte_val})
        primary, _, _ = apply_palette(spec, digest)
        r, g, b = primary
        assert abs(r - g) < 0.10 and abs(g - b) < 0.10


def test_cyberpunk_background_in_bands():
    spec = PRESETS["cyberpunk"]
    for byte_val in (0, 128, 255):
        digest = _digest_with({10: byte_val, 11: byte_val})
        _, _, bg = apply_palette(spec, digest)
        h, l, s = colorsys.rgb_to_hls(*bg)
        assert spec.background_hue_range[0] - 0.5 <= h * 360.0 <= spec.background_hue_range[1] + 0.5
        assert spec.background_light_range[0] - 1e-6 <= l <= spec.background_light_range[1] + 1e-6


# --- overrides ----------------------------------------------------------------


def test_primary_override_wins_over_preset():
    spec = resolve_palette("vibrant", primary_hex="#ff0000")
    digest = bytes(range(32))
    primary, secondary, _ = apply_palette(spec, digest)
    assert primary == pytest.approx((1.0, 0.0, 0.0))
    # Secondary still follows vibrant band (no override).
    _, l, s = colorsys.rgb_to_hls(*secondary)
    assert 0.85 - 1e-6 <= s <= 1.0 + 1e-6
    assert 0.45 - 1e-6 <= l <= 0.60 + 1e-6


def test_all_three_overrides_apply_independently():
    spec = resolve_palette(
        "default",
        primary_hex="#112233",
        secondary_hex="#445566",
        background_hex="#778899",
    )
    digest = bytes(range(32))
    primary, secondary, background = apply_palette(spec, digest)
    assert primary == pytest.approx((0x11 / 255, 0x22 / 255, 0x33 / 255))
    assert secondary == pytest.approx((0x44 / 255, 0x55 / 255, 0x66 / 255))
    assert background == pytest.approx((0x77 / 255, 0x88 / 255, 0x99 / 255))


def test_override_deterministic_across_digest_changes():
    spec = resolve_palette("default", primary_hex="#abcdef")
    d1 = bytes(range(32))
    d2 = bytes(range(32, 0, -1))
    p1, _, _ = apply_palette(spec, d1)
    p2, _, _ = apply_palette(spec, d2)
    assert p1 == p2


# --- resolve_palette ----------------------------------------------------------


def test_unknown_palette_raises():
    with pytest.raises(ValueError, match="unknown palette"):
        resolve_palette("neon")


def test_resolve_without_overrides_returns_preset_unchanged():
    assert resolve_palette("vibrant") is PRESETS["vibrant"]


def test_resolve_rejects_bad_hex():
    with pytest.raises(ValueError):
        resolve_palette("default", primary_hex="not-a-color")


def test_all_presets_are_palette_specs():
    for name, spec in PRESETS.items():
        assert isinstance(spec, PaletteSpec)
        assert spec.name == name
