"""Color palette presets and custom overrides.

A PaletteSpec holds optional H/S/L bands per color plus optional fixed RGB overrides.
The ``default`` palette has all bands ``None`` so apply_palette falls back to the
legacy formulas in ``hash_mapping`` and produces byte-identical output to the
pre-palette version. Named presets set bands; the digest still drives variation
within each band via ``lo + (byte/255) * (hi - lo)``. Explicit RGB overrides
beat bands per-channel.
"""

from __future__ import annotations

import colorsys
import dataclasses
import re

RGB = tuple[float, float, float]
Band = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class PaletteSpec:
    name: str
    primary_hue_range: Band | None = None
    primary_sat_range: Band | None = None
    primary_light_range: Band | None = None
    secondary_hue_range: Band | None = None
    secondary_sat_range: Band | None = None
    secondary_light_range: Band | None = None
    background_hue_range: Band | None = None
    background_sat_range: Band | None = None
    background_light_range: Band | None = None
    primary_override: RGB | None = None
    secondary_override: RGB | None = None
    background_override: RGB | None = None


PRESETS: dict[str, PaletteSpec] = {
    "default": PaletteSpec(name="default"),
    "vibrant": PaletteSpec(
        name="vibrant",
        primary_sat_range=(0.85, 1.0),
        primary_light_range=(0.45, 0.60),
        secondary_sat_range=(0.85, 1.0),
        secondary_light_range=(0.45, 0.60),
    ),
    "pastel": PaletteSpec(
        name="pastel",
        primary_sat_range=(0.30, 0.55),
        primary_light_range=(0.70, 0.85),
        secondary_sat_range=(0.30, 0.55),
        secondary_light_range=(0.70, 0.85),
    ),
    "mono": PaletteSpec(
        name="mono",
        primary_sat_range=(0.0, 0.08),
        primary_light_range=(0.30, 0.70),
        secondary_sat_range=(0.0, 0.08),
        secondary_light_range=(0.30, 0.70),
    ),
    "sunset": PaletteSpec(
        name="sunset",
        primary_hue_range=(0.0, 40.0),
        primary_sat_range=(0.70, 0.95),
        primary_light_range=(0.50, 0.70),
        secondary_hue_range=(270.0, 330.0),
        secondary_sat_range=(0.60, 0.90),
        secondary_light_range=(0.45, 0.65),
    ),
    "cyberpunk": PaletteSpec(
        name="cyberpunk",
        primary_hue_range=(280.0, 320.0),
        primary_sat_range=(0.80, 1.0),
        primary_light_range=(0.45, 0.60),
        secondary_hue_range=(170.0, 200.0),
        secondary_sat_range=(0.80, 1.0),
        secondary_light_range=(0.45, 0.60),
        background_hue_range=(240.0, 280.0),
        background_sat_range=(0.15, 0.30),
        background_light_range=(0.05, 0.12),
    ),
    "ocean": PaletteSpec(
        name="ocean",
        primary_hue_range=(170.0, 230.0),
        primary_sat_range=(0.55, 0.85),
        primary_light_range=(0.30, 0.55),
        secondary_hue_range=(170.0, 230.0),
        secondary_sat_range=(0.55, 0.85),
        secondary_light_range=(0.30, 0.55),
    ),
}


_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def parse_hex_color(s: str) -> RGB:
    """Parse '#RRGGBB' or 'RRGGBB' into (r, g, b) floats in [0, 1]."""
    m = _HEX_RE.match(s)
    if not m:
        raise ValueError(f"must be 6 hex digits (#RRGGBB), got {s!r}")
    h = m.group(1)
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
    )


def resolve_palette(
    name: str = "default",
    primary_hex: str | None = None,
    secondary_hex: str | None = None,
    background_hex: str | None = None,
) -> PaletteSpec:
    """Look up a preset by name and layer hex overrides on top.

    Unknown names and malformed hex raise ValueError with a precise message.
    """
    if name not in PRESETS:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown palette: {name!r} (known: {known})")
    spec = PRESETS[name]
    if primary_hex is None and secondary_hex is None and background_hex is None:
        return spec
    return dataclasses.replace(
        spec,
        primary_override=parse_hex_color(primary_hex)
        if primary_hex is not None
        else spec.primary_override,
        secondary_override=parse_hex_color(secondary_hex)
        if secondary_hex is not None
        else spec.secondary_override,
        background_override=parse_hex_color(background_hex)
        if background_hex is not None
        else spec.background_override,
    )


def _hls(h_deg: float, s: float, l: float) -> RGB:
    return colorsys.hls_to_rgb(h_deg / 360.0, l, s)


def _band(band: Band | None, byte_val: int, legacy_value: float) -> float:
    """Map byte into ``band`` linearly, or return ``legacy_value`` if band is None.

    When the band is None for every channel of a color, each call returns the
    legacy expression unchanged so the default palette produces byte-identical
    output to the pre-palette implementation.
    """
    if band is None:
        return legacy_value
    lo, hi = band
    return lo + (byte_val / 255.0) * (hi - lo)


def apply_palette(spec: PaletteSpec, digest: bytes) -> tuple[RGB, RGB, RGB]:
    """Return (primary, secondary, background) RGB for the given digest bytes."""
    b = digest

    if spec.primary_override is not None:
        primary = spec.primary_override
    else:
        h = _band(spec.primary_hue_range, b[4], b[4] / 255 * 360)
        s = _band(spec.primary_sat_range, b[5], 0.5 + b[5] / 510)
        l = _band(spec.primary_light_range, b[6], 0.35 + b[6] / 425)
        primary = _hls(h, s, l)

    if spec.secondary_override is not None:
        secondary = spec.secondary_override
    else:
        h = _band(spec.secondary_hue_range, b[7], b[7] / 255 * 360)
        s = _band(spec.secondary_sat_range, b[8], 0.5 + b[8] / 510)
        l = _band(spec.secondary_light_range, b[9], 0.35 + b[9] / 425)
        secondary = _hls(h, s, l)

    if spec.background_override is not None:
        background = spec.background_override
    else:
        h = _band(spec.background_hue_range, b[10], b[10] / 255 * 360)
        s = _band(spec.background_sat_range, b[11], 0.05 + b[11] / 2550)
        l = _band(spec.background_light_range, b[11], 0.08 + b[11] / 1275)
        background = _hls(h, s, l)

    return primary, secondary, background
