"""Map SHA-256 digest bytes and round states to 3D visual parameters.

The 32-byte digest determines static properties (shape, color, lighting, camera).
The round-state array (num_blocks, 64, 8) drives animation keyframes.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from motionprint.sha256_state import HashResult
from motionprint.palette import PRESETS, PaletteSpec, apply_palette

SHAPE_NAMES = ("icosphere", "torus", "superellipsoid", "octahedron", "twisted_torus")


@dataclasses.dataclass(frozen=True)
class VisualParams:
    """All parameters needed to render a motionprint video."""

    # Shape
    base_shape: str
    subdivision: int

    # Colors (RGB 0-1)
    primary_color: tuple[float, float, float]
    secondary_color: tuple[float, float, float]
    background_color: tuple[float, float, float]

    # Lighting
    light_elevation: float  # degrees
    light_azimuth_start: float  # degrees
    light_warmth: float  # 0-1

    # Camera
    camera_radius: float
    camera_elevation: float  # degrees
    camera_fov: float  # degrees

    # Animation
    rotation_speed: float  # revolutions per duration
    axis_tilt: float  # degrees

    # Deformation
    deformation_amplitudes: tuple[float, float, float, float]

    # Material
    shininess: float
    specular_strength: float

    # Pulse
    pulse_amplitude: float
    pulse_frequency: float

    # Seeds
    morph_seed: tuple[int, int, int, int]

    # Animated keyframes: (total_rounds, 8) float32, normalized 0-1
    keyframes: np.ndarray

    # Render-time configuration (not hash-derived)
    speed_multiplier: float = 1.0
    palette_name: str = "default"


def compute_visual_params(
    result: HashResult,
    palette: PaletteSpec | None = None,
    speed_multiplier: float = 1.0,
) -> VisualParams:
    """Map a HashResult to visual parameters for rendering.

    ``palette`` selects colors (default palette reproduces prior hash-driven
    output byte-for-byte). ``speed_multiplier`` scales cyclic animation rates
    at render time and is carried through on :class:`VisualParams`.
    """
    if palette is None:
        palette = PRESETS["default"]

    b = result.digest  # 32 bytes

    # Shape selection
    shape_idx = ((b[0] << 8) | b[1]) % len(SHAPE_NAMES)
    base_shape = SHAPE_NAMES[shape_idx]
    subdivision = 2 + (b[2] % 3)

    # Colors (palette-aware; default palette falls back to legacy formulas)
    primary_color, secondary_color, background_color = apply_palette(palette, b)

    # Lighting
    light_elevation = b[12] / 255 * 60 + 15
    light_azimuth_start = b[13] / 255 * 360
    light_warmth = b[14] / 255

    # Camera
    camera_radius = 2.5 + b[15] / 255 * 1.5
    camera_elevation = b[16] / 255 * 40 - 5
    camera_fov = 40 + b[17] / 255 * 30

    # Rotation
    rotation_speed = 0.5 + b[18] / 255 * 2.0
    axis_tilt = b[19] / 255 * 30

    # Deformation amplitudes
    deformation_amplitudes = tuple(b[20 + i] / 255 * 0.3 for i in range(4))

    # Material
    shininess = 8 + b[24] / 255 * 120
    specular_strength = 0.2 + b[25] / 255 * 0.8

    # Pulse
    pulse_amplitude = b[26] / 255 * 0.08
    pulse_frequency = 1 + b[27] % 5

    # Morph seed
    morph_seed = (b[28], b[29], b[30], b[31])

    # Normalize round states to [0, 1] for keyframes
    # Shape: (num_blocks, 64, 8) -> (num_blocks * 64, 8)
    flat_states = result.round_states.reshape(-1, 8).astype(np.float64)
    keyframes = (flat_states / 0xFFFFFFFF).astype(np.float32)

    return VisualParams(
        base_shape=base_shape,
        subdivision=subdivision,
        primary_color=primary_color,
        secondary_color=secondary_color,
        background_color=background_color,
        light_elevation=light_elevation,
        light_azimuth_start=light_azimuth_start,
        light_warmth=light_warmth,
        camera_radius=camera_radius,
        camera_elevation=camera_elevation,
        camera_fov=camera_fov,
        rotation_speed=rotation_speed,
        axis_tilt=axis_tilt,
        deformation_amplitudes=deformation_amplitudes,
        shininess=shininess,
        specular_strength=specular_strength,
        pulse_amplitude=pulse_amplitude,
        pulse_frequency=pulse_frequency,
        morph_seed=morph_seed,
        keyframes=keyframes,
        speed_multiplier=speed_multiplier,
        palette_name=palette.name,
    )


def interpolate_keyframes(keyframes: np.ndarray, t: float) -> np.ndarray:
    """Interpolate keyframe values at normalized time t (0-1).

    Uses Catmull-Rom spline interpolation for smooth C1 animation.
    Returns 8-element float32 array of interpolated values.
    """
    n = len(keyframes)
    if n == 0:
        return np.zeros(8, dtype=np.float32)
    if n == 1:
        return keyframes[0].copy()

    # Map t to keyframe index
    t = max(0.0, min(1.0, t))
    pos = t * (n - 1)
    idx = int(pos)
    frac = pos - idx

    # Clamp indices for Catmull-Rom (need 4 points: p0, p1, p2, p3)
    i0 = max(0, idx - 1)
    i1 = idx
    i2 = min(n - 1, idx + 1)
    i3 = min(n - 1, idx + 2)

    p0 = keyframes[i0].astype(np.float64)
    p1 = keyframes[i1].astype(np.float64)
    p2 = keyframes[i2].astype(np.float64)
    p3 = keyframes[i3].astype(np.float64)

    # Catmull-Rom interpolation
    f = frac
    f2 = f * f
    f3 = f2 * f
    result = 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * f
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * f3
    )

    # Clamp to [0, 1]
    return np.clip(result, 0.0, 1.0).astype(np.float32)
