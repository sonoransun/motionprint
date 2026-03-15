"""QR code generation, frame compositing, and standalone image export.

Generates a QR code encoding the SHA-256 hex digest, composites it onto
video frames as a corner overlay, and can export standalone PNG images
using a minimal writer (no Pillow dependency).
"""

from __future__ import annotations

import struct
import zlib

import numpy as np
import qrcode


def generate_qr_matrix(hex_digest: str) -> np.ndarray:
    """Generate a binary QR code matrix from a hex digest string.

    Returns a 2D uint8 array where 1 = dark module, 0 = light module.
    """
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=2,
    )
    qr.add_data(hex_digest)
    qr.make(fit=True)
    return np.array(qr.modules, dtype=np.uint8)


def render_qr_overlay(
    matrix: np.ndarray,
    frame_width: int,
    frame_height: int,
) -> np.ndarray:
    """Render QR matrix to an RGB overlay sized for the given frame.

    The overlay targets ~10% of the smaller frame dimension.
    Returns an (overlay_h, overlay_w, 3) uint8 array.
    """
    module_count = matrix.shape[0]
    target_size = int(min(frame_width, frame_height) * 0.12)
    scale = max(1, target_size // module_count)
    img_size = module_count * scale

    # White background
    overlay = np.full((img_size, img_size, 3), 255, dtype=np.uint8)

    # Draw dark modules
    for i in range(module_count):
        for j in range(module_count):
            if matrix[i, j]:
                overlay[i * scale:(i + 1) * scale,
                        j * scale:(j + 1) * scale] = 0

    return overlay


def composite_qr_onto_frame(
    frame_bytes: bytes,
    width: int,
    height: int,
    qr_overlay: np.ndarray,
    margin: int = 12,
    padding: int = 6,
    bg_opacity: float = 0.85,
) -> bytes:
    """Composite QR overlay onto the bottom-right corner of a frame.

    Args:
        frame_bytes: Raw RGB frame bytes (width * height * 3).
        width: Frame width in pixels.
        height: Frame height in pixels.
        qr_overlay: Pre-rendered QR overlay from render_qr_overlay().
        margin: Pixel margin from frame edge.
        padding: Pixel padding around QR code (background extends this far).
        bg_opacity: Opacity of the white background behind the QR code.

    Returns:
        Composited RGB frame bytes.
    """
    frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(height, width, 3).copy()
    qh, qw = qr_overlay.shape[:2]

    padded_h = qh + 2 * padding
    padded_w = qw + 2 * padding

    y_start = height - padded_h - margin
    x_start = width - padded_w - margin

    if y_start < 0 or x_start < 0:
        return frame_bytes  # Frame too small for overlay

    # Draw semi-transparent white background
    bg_region = frame[y_start:y_start + padded_h, x_start:x_start + padded_w]
    frame[y_start:y_start + padded_h, x_start:x_start + padded_w] = (
        bg_region.astype(np.float32) * (1.0 - bg_opacity) + 255.0 * bg_opacity
    ).astype(np.uint8)

    # Blit QR code onto the padded region
    qr_y = y_start + padding
    qr_x = x_start + padding
    frame[qr_y:qr_y + qh, qr_x:qr_x + qw] = qr_overlay

    return frame.tobytes()


def save_qr_png(
    matrix: np.ndarray,
    path: str,
    scale: int = 10,
) -> None:
    """Save QR matrix as a standalone PNG image.

    Uses a minimal PNG writer — no Pillow dependency required.

    Args:
        matrix: Binary QR matrix from generate_qr_matrix().
        path: Output file path.
        scale: Pixels per QR module (default 10 for a crisp image).
    """
    module_count = matrix.shape[0]
    img_size = module_count * scale

    # Build RGB pixel data
    pixels = np.full((img_size, img_size, 3), 255, dtype=np.uint8)
    for i in range(module_count):
        for j in range(module_count):
            if matrix[i, j]:
                pixels[i * scale:(i + 1) * scale,
                       j * scale:(j + 1) * scale] = 0

    _write_png(path, pixels, img_size, img_size)


def _write_png(path: str, pixels: np.ndarray, width: int, height: int) -> None:
    """Write an RGB numpy array as a PNG file (minimal encoder)."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    # Build raw scanlines with filter byte 0 (none) per row
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        raw.extend(pixels[y].tobytes())

    idat = _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    iend = _chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)
