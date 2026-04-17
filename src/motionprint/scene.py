"""Scene orchestrator: ties hashing, mapping, geometry, rendering, and encoding."""

from __future__ import annotations

import math
import sys

import numpy as np
import pyrr

from motionprint.sha256_state import sha256_with_states
from motionprint.hash_mapping import compute_visual_params, interpolate_keyframes, VisualParams
from motionprint.palette import PaletteSpec
from motionprint.geometry import generate_mesh, deform_mesh, MeshData
from motionprint.renderer import Renderer
from motionprint.encoder import VideoEncoder


def _lerp_color(
    c1: tuple[float, float, float],
    c2: tuple[float, float, float],
    t: float,
) -> tuple[float, float, float]:
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    )


def _hue_shift(
    color: tuple[float, float, float], shift_deg: float
) -> tuple[float, float, float]:
    """Shift hue of an RGB color by shift_deg degrees."""
    import colorsys

    h, l, s = colorsys.rgb_to_hls(*color)
    h = (h + shift_deg / 360.0) % 1.0
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r, g, b)


def _compute_light_pos(
    azimuth_deg: float, elevation_deg: float, radius: float = 5.0
) -> tuple[float, float, float]:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = radius * math.cos(el) * math.cos(az)
    y = radius * math.cos(el) * math.sin(az)
    z = radius * math.sin(el)
    return (x, y, z)


def _compute_camera_pos(
    azimuth_deg: float, elevation_deg: float, radius: float
) -> tuple[float, float, float]:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = radius * math.cos(el) * math.cos(az)
    y = radius * math.cos(el) * math.sin(az)
    z = radius * math.sin(el)
    return (x, y, z)


def _light_color_from_warmth(warmth: float) -> tuple[float, float, float]:
    cool = (0.85, 0.90, 1.0)
    warm = (1.0, 0.95, 0.85)
    return _lerp_color(cool, warm, warmth)


def generate(
    data: bytes,
    output_path: str,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    duration: float = 6.0,
    verbose: bool = False,
    qr: bool = False,
    palette: PaletteSpec | None = None,
    speed_multiplier: float = 1.0,
) -> str:
    """Generate a motionprint video from input data.

    Args:
        data: Raw input bytes to hash.
        output_path: Path for the output MP4 file.
        width: Video width in pixels.
        height: Video height in pixels.
        fps: Frames per second.
        duration: Video duration in seconds.
        verbose: Print progress to stderr.
        qr: Embed QR code of hex digest in video frames.
        palette: Color palette. ``None`` selects the default palette, which
            reproduces the prior hash-driven colors byte-for-byte.
        speed_multiplier: Scales cyclic animation rates (rotation, pulse,
            camera orbit, light orbit). Keyframe traversal still spans the
            full duration exactly once regardless of this value.

    Returns:
        The hex digest of the input data.
    """
    total_frames = int(fps * duration)

    # Step 1: Hash with state capture
    hash_result = sha256_with_states(data)
    if verbose:
        print(f"SHA-256: {hash_result.hex_digest}", file=sys.stderr)
        print(f"Blocks: {hash_result.num_blocks}", file=sys.stderr)

    # Step 1b: Prepare QR overlay if requested
    qr_overlay = None
    if qr:
        from motionprint.qr import generate_qr_matrix, render_qr_overlay
        qr_matrix = generate_qr_matrix(hash_result.hex_digest)
        qr_overlay = render_qr_overlay(qr_matrix, width, height)
        if verbose:
            print("QR: embedded in video", file=sys.stderr)

    # Step 2: Map to visual parameters
    params = compute_visual_params(
        hash_result, palette=palette, speed_multiplier=speed_multiplier
    )
    if verbose:
        print(f"Shape: {params.base_shape} (subdivision {params.subdivision})", file=sys.stderr)
        print(
            f"Palette: {params.palette_name}, speed: {params.speed_multiplier:g}",
            file=sys.stderr,
        )

    # Step 3: Generate base mesh
    base_mesh = generate_mesh(params.base_shape, params.subdivision)

    # Step 4: Initialize renderer and encoder
    renderer = Renderer(width, height)
    encoder = VideoEncoder(output_path, width, height, fps)

    try:
        # Projection matrix (constant)
        projection = pyrr.matrix44.create_perspective_projection(
            fovy=params.camera_fov,
            aspect=width / height,
            near=0.1,
            far=100.0,
            dtype=np.float32,
        )

        # Step 5: Frame loop
        for frame_idx in range(total_frames):
            t = frame_idx / max(total_frames - 1, 1)

            # Interpolate keyframes at this time
            animated = interpolate_keyframes(params.keyframes, t)

            # Extract animated properties
            deform_blend = animated[0]
            hue_shift_val = (animated[1] - 0.5) * 60  # ±30 degrees
            light_offset = animated[2] * 45  # 0-45 degrees
            cam_dist_mod = (animated[3] - 0.5) * 0.6  # ±0.3
            rotation_offset = animated[4] * 15  # 0-15 degrees
            spec_mod = 0.5 + animated[5] * 1.0  # 0.5-1.5
            color_blend = animated[6]
            noise_amount = animated[7] * 0.05

            # Deform mesh
            mesh = deform_mesh(
                base_mesh,
                params.deformation_amplitudes,
                params.morph_seed,
                deform_blend,
                noise_amount,
            )

            speed = params.speed_multiplier

            # Pulse scale
            pulse = 1.0 + params.pulse_amplitude * math.sin(
                2 * math.pi * params.pulse_frequency * speed * t
            )

            # Model matrix: rotation + scale
            angle = (params.rotation_speed * speed * t * 360 + rotation_offset)
            tilt_rad = math.radians(params.axis_tilt)
            model = pyrr.matrix44.create_identity(dtype=np.float32)
            model = pyrr.matrix44.multiply(
                model,
                pyrr.matrix44.create_from_axis_rotation(
                    [math.sin(tilt_rad), math.cos(tilt_rad), 0],
                    math.radians(angle),
                    dtype=np.float32,
                ),
            )
            scale = pyrr.matrix44.create_from_scale(
                [pulse, pulse, pulse], dtype=np.float32
            )
            model = pyrr.matrix44.multiply(scale, model)

            # Camera
            cam_azimuth = t * 360 * 0.5 * speed  # orbit (half revolution at speed=1)
            cam_radius = params.camera_radius + cam_dist_mod
            cam_pos = _compute_camera_pos(
                cam_azimuth, params.camera_elevation, cam_radius
            )
            view = pyrr.matrix44.create_look_at(
                eye=np.array(cam_pos, dtype=np.float32),
                target=np.array([0, 0, 0], dtype=np.float32),
                up=np.array([0, 0, 1], dtype=np.float32),
                dtype=np.float32,
            )

            # Light
            light_az = params.light_azimuth_start + t * 90 * speed + light_offset
            light_pos = _compute_light_pos(light_az, params.light_elevation)
            light_color = _light_color_from_warmth(params.light_warmth)

            # Object color (blend + hue shift)
            blended = _lerp_color(
                params.primary_color, params.secondary_color, color_blend
            )
            obj_color = _hue_shift(blended, hue_shift_val)

            # Upload geometry and uniforms
            renderer.update_geometry(mesh)
            renderer.set_uniforms(
                model=model,
                view=view,
                projection=projection,
                object_color=obj_color,
                light_pos=light_pos,
                light_color=light_color,
                camera_pos=cam_pos,
                shininess=params.shininess,
                specular_strength=params.specular_strength * spec_mod,
            )

            # Render and encode
            frame = renderer.render_frame(bg_color=params.background_color)
            if qr_overlay is not None:
                from motionprint.qr import composite_qr_onto_frame
                frame = composite_qr_onto_frame(frame, width, height, qr_overlay)
            encoder.write_frame(frame)

            if verbose and (frame_idx % 10 == 0 or frame_idx == total_frames - 1):
                pct = (frame_idx + 1) / total_frames * 100
                print(
                    f"\rRendering: {frame_idx + 1}/{total_frames} ({pct:.0f}%)",
                    end="",
                    file=sys.stderr,
                )

        if verbose:
            print(file=sys.stderr)

    finally:
        encoder.close()
        renderer.release()

    if verbose:
        print(f"Output: {output_path}", file=sys.stderr)

    return hash_result.hex_digest
