"""Tests for pure-Python SHA-256 with state capture."""

import hashlib

import numpy as np

from motionprint.sha256_state import sha256_with_states


def test_empty_string():
    result = sha256_with_states(b"")
    assert result.digest == hashlib.sha256(b"").digest()
    assert result.hex_digest == hashlib.sha256(b"").hexdigest()


def test_abc():
    result = sha256_with_states(b"abc")
    assert result.digest == hashlib.sha256(b"abc").digest()


def test_long_message():
    msg = b"a" * 1000
    result = sha256_with_states(msg)
    assert result.digest == hashlib.sha256(msg).digest()


def test_nist_vector():
    # NIST test vector: "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    msg = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    result = sha256_with_states(msg)
    assert result.hex_digest == hashlib.sha256(msg).hexdigest()


def test_round_states_shape_single_block():
    result = sha256_with_states(b"hello")
    assert result.round_states.shape == (1, 64, 8)
    assert result.round_states.dtype == np.uint32
    assert result.num_blocks == 1


def test_round_states_shape_multi_block():
    # 56+ bytes forces 2 blocks
    msg = b"x" * 64
    result = sha256_with_states(msg)
    assert result.num_blocks == 2
    assert result.round_states.shape == (2, 64, 8)


def test_deterministic():
    r1 = sha256_with_states(b"test")
    r2 = sha256_with_states(b"test")
    assert r1.digest == r2.digest
    assert np.array_equal(r1.round_states, r2.round_states)


def test_different_inputs_different_states():
    r1 = sha256_with_states(b"hello")
    r2 = sha256_with_states(b"Hello")
    assert r1.digest != r2.digest
    assert not np.array_equal(r1.round_states, r2.round_states)
