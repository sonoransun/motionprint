"""Pure-Python SHA-256 implementation with round-state capture.

Implements FIPS 180-4 SHA-256, capturing the 8 working variables (a-h)
after each of the 64 rounds per block. This intermediate state data
drives the animation in motionprint visualizations.
"""

from __future__ import annotations

import dataclasses
import struct

import numpy as np

# SHA-256 constants: first 32 bits of the fractional parts of the
# cube roots of the first 64 primes.
_K = [
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
]

# Initial hash values: first 32 bits of the fractional parts of the
# square roots of the first 8 primes.
_H0 = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)

_MASK32 = 0xFFFFFFFF


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & _MASK32


def _shr(x: int, n: int) -> int:
    return x >> n


def _ch(x: int, y: int, z: int) -> int:
    return (x & y) ^ (~x & z) & _MASK32


def _maj(x: int, y: int, z: int) -> int:
    return (x & y) ^ (x & z) ^ (y & z)


def _sigma0(x: int) -> int:
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)


def _sigma1(x: int) -> int:
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)


def _gamma0(x: int) -> int:
    return _rotr(x, 7) ^ _rotr(x, 18) ^ _shr(x, 3)


def _gamma1(x: int) -> int:
    return _rotr(x, 17) ^ _rotr(x, 19) ^ _shr(x, 10)


def _pad(message: bytes) -> bytes:
    """Apply SHA-256 padding to message."""
    length = len(message)
    bit_length = length * 8
    # Append 0x80
    message += b"\x80"
    # Pad with zeros until length ≡ 56 (mod 64)
    message += b"\x00" * ((55 - length) % 64)
    # Append 64-bit big-endian bit length
    message += struct.pack(">Q", bit_length)
    return message


def _schedule(block: bytes) -> list[int]:
    """Expand 512-bit block into 64-word message schedule."""
    w = list(struct.unpack(">16I", block))
    for i in range(16, 64):
        w.append(
            (_gamma1(w[i - 2]) + w[i - 7] + _gamma0(w[i - 15]) + w[i - 16])
            & _MASK32
        )
    return w


def _compress(
    state: tuple[int, ...], block: bytes
) -> tuple[tuple[int, ...], list[tuple[int, ...]]]:
    """SHA-256 compression function with round-state capture.

    Returns (new_state, round_states) where round_states is a list of
    64 tuples, each containing the 8 working variables after that round.
    """
    w = _schedule(block)
    a, b, c, d, e, f, g, h = state
    round_states: list[tuple[int, ...]] = []

    for i in range(64):
        t1 = (h + _sigma1(e) + _ch(e, f, g) + _K[i] + w[i]) & _MASK32
        t2 = (_sigma0(a) + _maj(a, b, c)) & _MASK32
        h = g
        g = f
        f = e
        e = (d + t1) & _MASK32
        d = c
        c = b
        b = a
        a = (t1 + t2) & _MASK32
        round_states.append((a, b, c, d, e, f, g, h))

    new_state = tuple((s + v) & _MASK32 for s, v in zip(state, (a, b, c, d, e, f, g, h)))
    return new_state, round_states


@dataclasses.dataclass(frozen=True)
class HashResult:
    """Result of SHA-256 computation with captured round states."""

    digest: bytes
    """32-byte SHA-256 digest."""

    hex_digest: str
    """64-character hexadecimal digest string."""

    round_states: np.ndarray
    """Shape (num_blocks, 64, 8) uint32 array of working variables per round."""

    num_blocks: int
    """Number of 512-bit blocks processed."""


def sha256_with_states(data: bytes) -> HashResult:
    """Compute SHA-256 of data, capturing intermediate round states.

    Returns a HashResult containing the digest and the full history of
    working variables (a-h) after each of the 64 rounds in each block.
    """
    padded = _pad(data)
    num_blocks = len(padded) // 64
    state = _H0
    all_round_states: list[list[tuple[int, ...]]] = []

    for block_idx in range(num_blocks):
        block = padded[block_idx * 64 : (block_idx + 1) * 64]
        state, round_states = _compress(state, block)
        all_round_states.append(round_states)

    digest = struct.pack(">8I", *state)
    hex_digest = digest.hex()

    # Convert to numpy array: (num_blocks, 64, 8)
    states_array = np.array(all_round_states, dtype=np.uint32)

    return HashResult(
        digest=digest,
        hex_digest=hex_digest,
        round_states=states_array,
        num_blocks=num_blocks,
    )
