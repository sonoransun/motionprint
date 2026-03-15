"""Tests for mesh generation and deformation."""

import numpy as np

from motionprint.geometry import icosphere, torus, superellipsoid, deform_mesh


def test_icosphere_vertex_count():
    # Formula: V = 10 * 4^n + 2
    for n in range(4):
        mesh = icosphere(n)
        expected = 10 * (4 ** n) + 2
        assert len(mesh.vertices) == expected, f"subdivision {n}: got {len(mesh.vertices)}, expected {expected}"


def test_icosphere_unit_sphere():
    mesh = icosphere(2)
    radii = np.linalg.norm(mesh.vertices, axis=1)
    np.testing.assert_allclose(radii, 1.0, atol=1e-6)


def test_icosphere_normals_equal_positions():
    mesh = icosphere(2)
    # For a unit sphere, normals should equal vertex positions
    np.testing.assert_allclose(mesh.normals, mesh.vertices, atol=1e-6)


def test_torus_has_vertices():
    mesh = torus()
    assert len(mesh.vertices) > 0
    assert len(mesh.indices) > 0
    assert mesh.normals.shape == mesh.vertices.shape


def test_superellipsoid_has_vertices():
    mesh = superellipsoid(1.0, 1.0)
    assert len(mesh.vertices) > 0
    assert len(mesh.indices) > 0


def test_interleaved_shape():
    mesh = icosphere(1)
    interleaved = mesh.interleaved()
    assert interleaved.shape == (len(mesh.vertices), 6)
    assert interleaved.dtype == np.float32


def test_flat_indices():
    mesh = icosphere(1)
    flat = mesh.flat_indices()
    assert flat.shape == (len(mesh.indices) * 3,)
    assert flat.dtype == np.uint32


def test_deform_mesh_preserves_shape():
    mesh = icosphere(2)
    deformed = deform_mesh(
        mesh,
        amplitudes=(0.1, 0.1, 0.1, 0.1),
        morph_seed=(42, 13, 7, 99),
        deform_blend=1.0,
        noise_amount=0.01,
    )
    assert deformed.vertices.shape == mesh.vertices.shape
    assert deformed.normals.shape == mesh.normals.shape
    assert np.array_equal(deformed.indices, mesh.indices)


def test_deform_zero_blend_minimal_change():
    mesh = icosphere(2)
    deformed = deform_mesh(
        mesh,
        amplitudes=(0.1, 0.1, 0.1, 0.1),
        morph_seed=(0, 0, 0, 0),
        deform_blend=0.0,
        noise_amount=0.0,
    )
    # With zero blend and zero noise, vertices should be unchanged
    np.testing.assert_allclose(deformed.vertices, mesh.vertices, atol=1e-6)
