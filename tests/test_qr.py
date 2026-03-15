"""Tests for QR code generation, compositing, and PNG export."""

import os
import tempfile

import numpy as np

from motionprint.qr import (
    generate_qr_matrix,
    render_qr_overlay,
    composite_qr_onto_frame,
    save_qr_png,
)


SAMPLE_DIGEST = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_generate_qr_matrix_shape():
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    assert matrix.ndim == 2
    assert matrix.shape[0] == matrix.shape[1]  # square
    assert matrix.dtype == np.uint8


def test_generate_qr_matrix_values():
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    unique = set(np.unique(matrix))
    assert unique <= {0, 1}  # only 0 and 1


def test_generate_qr_matrix_deterministic():
    m1 = generate_qr_matrix(SAMPLE_DIGEST)
    m2 = generate_qr_matrix(SAMPLE_DIGEST)
    assert np.array_equal(m1, m2)


def test_generate_qr_different_digests():
    m1 = generate_qr_matrix(SAMPLE_DIGEST)
    m2 = generate_qr_matrix("a" * 64)
    assert not np.array_equal(m1, m2)


def test_render_qr_overlay_shape():
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, 1280, 720)
    assert overlay.ndim == 3
    assert overlay.shape[2] == 3  # RGB
    assert overlay.dtype == np.uint8
    # Should be square
    assert overlay.shape[0] == overlay.shape[1]


def test_render_qr_overlay_contains_black_and_white():
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, 1280, 720)
    assert np.any(overlay == 0)    # has dark modules
    assert np.any(overlay == 255)  # has light modules


def test_composite_preserves_frame_size():
    width, height = 640, 360
    frame = np.full((height, width, 3), 128, dtype=np.uint8).tobytes()
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, width, height)
    result = composite_qr_onto_frame(frame, width, height, overlay)
    assert len(result) == len(frame)


def test_composite_modifies_corner():
    width, height = 640, 360
    frame_arr = np.full((height, width, 3), 128, dtype=np.uint8)
    frame = frame_arr.tobytes()
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, width, height)
    result = composite_qr_onto_frame(frame, width, height, overlay)
    result_arr = np.frombuffer(result, dtype=np.uint8).reshape(height, width, 3)
    # Bottom-right corner should be different from the uniform gray
    corner = result_arr[height - 50:, width - 50:]
    assert not np.all(corner == 128)


def test_composite_leaves_top_left_unchanged():
    width, height = 640, 360
    frame_arr = np.full((height, width, 3), 100, dtype=np.uint8)
    frame = frame_arr.tobytes()
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, width, height)
    result = composite_qr_onto_frame(frame, width, height, overlay)
    result_arr = np.frombuffer(result, dtype=np.uint8).reshape(height, width, 3)
    # Top-left quadrant should be untouched
    top_left = result_arr[:height // 2, :width // 2]
    assert np.all(top_left == 100)


def test_save_qr_png():
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        save_qr_png(matrix, path, scale=5)
        assert os.path.exists(path)
        size = os.path.getsize(path)
        assert size > 100  # valid PNG is at least a few hundred bytes
        # Verify PNG signature
        with open(path, "rb") as f:
            sig = f.read(8)
        assert sig == b"\x89PNG\r\n\x1a\n"
    finally:
        os.unlink(path)


def test_composite_tiny_frame_returns_unchanged():
    """Frame too small for QR overlay should be returned unchanged."""
    width, height = 30, 30
    frame = np.zeros((height, width, 3), dtype=np.uint8).tobytes()
    matrix = generate_qr_matrix(SAMPLE_DIGEST)
    overlay = render_qr_overlay(matrix, width, height)
    result = composite_qr_onto_frame(frame, width, height, overlay)
    assert result == frame
