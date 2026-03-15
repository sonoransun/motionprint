"""Procedural 3D mesh generation and deformation.

Generates icosphere, torus, and superellipsoid meshes, plus hash-driven
vertex deformation for creating unique organic shapes.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np


@dataclasses.dataclass
class MeshData:
    """Triangle mesh with per-vertex positions and normals."""

    vertices: np.ndarray   # (N, 3) float32
    normals: np.ndarray    # (N, 3) float32
    indices: np.ndarray    # (M, 3) uint32

    def interleaved(self) -> np.ndarray:
        """Return (N, 6) float32 array: [x,y,z, nx,ny,nz] per vertex."""
        return np.hstack([self.vertices, self.normals]).astype(np.float32)

    def flat_indices(self) -> np.ndarray:
        """Return (M*3,) uint32 array for element buffer."""
        return self.indices.flatten().astype(np.uint32)


def _compute_normals(vertices: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Compute per-vertex normals by averaging adjacent face normals."""
    normals = np.zeros_like(vertices, dtype=np.float64)
    v0 = vertices[indices[:, 0]]
    v1 = vertices[indices[:, 1]]
    v2 = vertices[indices[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)
    for i in range(3):
        np.add.at(normals, indices[:, i], face_normals)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-10)
    return (normals / lengths).astype(np.float32)


def icosphere(subdivision: int = 3) -> MeshData:
    """Generate an icosphere by subdividing an icosahedron.

    Args:
        subdivision: Number of subdivision levels (0=icosahedron, 3=642 verts).
    """
    # Golden ratio
    t = (1.0 + math.sqrt(5.0)) / 2.0

    # 12 vertices of a regular icosahedron
    verts = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]

    # 20 triangular faces
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    # Normalize initial vertices to unit sphere
    vertices = []
    for v in verts:
        length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        vertices.append((v[0] / length, v[1] / length, v[2] / length))

    # Subdivide
    midpoint_cache: dict[tuple[int, int], int] = {}

    def get_midpoint(i1: int, i2: int) -> int:
        key = (min(i1, i2), max(i1, i2))
        if key in midpoint_cache:
            return midpoint_cache[key]
        v1, v2 = vertices[i1], vertices[i2]
        mid = ((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2, (v1[2] + v2[2]) / 2)
        length = math.sqrt(mid[0] ** 2 + mid[1] ** 2 + mid[2] ** 2)
        mid = (mid[0] / length, mid[1] / length, mid[2] / length)
        idx = len(vertices)
        vertices.append(mid)
        midpoint_cache[key] = idx
        return idx

    triangles = list(faces)
    for _ in range(subdivision):
        midpoint_cache.clear()
        new_triangles = []
        for tri in triangles:
            a = get_midpoint(tri[0], tri[1])
            b = get_midpoint(tri[1], tri[2])
            c = get_midpoint(tri[2], tri[0])
            new_triangles.extend([
                (tri[0], a, c),
                (tri[1], b, a),
                (tri[2], c, b),
                (a, b, c),
            ])
        triangles = new_triangles

    verts_arr = np.array(vertices, dtype=np.float32)
    idx_arr = np.array(triangles, dtype=np.uint32)
    normals = verts_arr.copy()  # For a unit sphere, normals equal positions

    return MeshData(vertices=verts_arr, normals=normals, indices=idx_arr)


def torus(major_radius: float = 1.0, minor_radius: float = 0.4,
          major_segments: int = 48, minor_segments: int = 24) -> MeshData:
    """Generate a torus mesh."""
    vertices = []
    indices = []

    for i in range(major_segments):
        theta = 2.0 * math.pi * i / major_segments
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for j in range(minor_segments):
            phi = 2.0 * math.pi * j / minor_segments
            cos_p, sin_p = math.cos(phi), math.sin(phi)
            r = major_radius + minor_radius * cos_p
            x = r * cos_t
            y = r * sin_t
            z = minor_radius * sin_p
            vertices.append((x, y, z))

    for i in range(major_segments):
        for j in range(minor_segments):
            curr = i * minor_segments + j
            next_j = i * minor_segments + (j + 1) % minor_segments
            next_i = ((i + 1) % major_segments) * minor_segments + j
            next_ij = ((i + 1) % major_segments) * minor_segments + (j + 1) % minor_segments
            indices.append((curr, next_i, next_ij))
            indices.append((curr, next_ij, next_j))

    verts_arr = np.array(vertices, dtype=np.float32)
    idx_arr = np.array(indices, dtype=np.uint32)
    normals = _compute_normals(verts_arr, idx_arr)

    return MeshData(vertices=verts_arr, normals=normals, indices=idx_arr)


def superellipsoid(e1: float = 1.0, e2: float = 1.0,
                   u_segments: int = 32, v_segments: int = 32) -> MeshData:
    """Generate a superellipsoid mesh.

    e1, e2 control the shape: (1,1)=sphere, (0.1,0.1)≈cube, (2,2)=octahedron-ish.
    """
    def _sign_pow(base: float, exp: float) -> float:
        if base == 0:
            return 0.0
        sign = 1.0 if base > 0 else -1.0
        return sign * abs(base) ** exp

    vertices = []
    for i in range(u_segments + 1):
        u = -math.pi / 2 + math.pi * i / u_segments
        cos_u, sin_u = math.cos(u), math.sin(u)
        for j in range(v_segments + 1):
            v = -math.pi + 2 * math.pi * j / v_segments
            cos_v, sin_v = math.cos(v), math.sin(v)
            x = _sign_pow(cos_u, e1) * _sign_pow(cos_v, e2)
            y = _sign_pow(cos_u, e1) * _sign_pow(sin_v, e2)
            z = _sign_pow(sin_u, e1)
            vertices.append((x, y, z))

    indices = []
    for i in range(u_segments):
        for j in range(v_segments):
            row = v_segments + 1
            curr = i * row + j
            indices.append((curr, curr + row, curr + row + 1))
            indices.append((curr, curr + row + 1, curr + 1))

    verts_arr = np.array(vertices, dtype=np.float32)
    idx_arr = np.array(indices, dtype=np.uint32)
    normals = _compute_normals(verts_arr, idx_arr)

    return MeshData(vertices=verts_arr, normals=normals, indices=idx_arr)


def deform_mesh(
    mesh: MeshData,
    amplitudes: tuple[float, float, float, float],
    morph_seed: tuple[int, int, int, int],
    deform_blend: float,
    noise_amount: float,
) -> MeshData:
    """Apply hash-driven deformation to a mesh.

    Uses 4 spherical-harmonic-like displacement modes along normals,
    plus a high-frequency noise displacement.

    Args:
        mesh: Base mesh to deform.
        amplitudes: Weights for 4 deformation modes (0-0.3 each).
        morph_seed: 4 seed bytes for noise generation.
        deform_blend: 0=no deformation, 1=full deformation (animated).
        noise_amount: High-frequency noise displacement magnitude (animated).
    """
    verts = mesh.vertices.copy()
    normals = mesh.normals.copy()

    # Convert to spherical coords for spherical-harmonic-like modes
    x, y, z = verts[:, 0], verts[:, 1], verts[:, 2]
    r = np.sqrt(x**2 + y**2 + z**2)
    r = np.maximum(r, 1e-10)
    theta = np.arccos(np.clip(z / r, -1, 1))  # polar angle
    phi = np.arctan2(y, x)  # azimuthal angle

    # 4 deformation modes (simplified spherical harmonics)
    mode0 = np.cos(2 * theta)  # Y_2^0 like
    mode1 = np.sin(theta) * np.cos(phi)  # Y_1^1 like
    mode2 = np.sin(2 * theta) * np.cos(2 * phi)  # Y_2^2 like
    mode3 = np.cos(3 * theta)  # Y_3^0 like

    displacement = (
        amplitudes[0] * mode0
        + amplitudes[1] * mode1
        + amplitudes[2] * mode2
        + amplitudes[3] * mode3
    )

    # Add pseudo-random noise using morph_seed
    seed_val = sum(s << (i * 8) for i, s in enumerate(morph_seed))
    rng = np.random.RandomState(seed_val)
    noise = rng.randn(len(verts)) * noise_amount

    # Apply displacement along normals, scaled by deform_blend
    total_disp = (displacement * deform_blend + noise)[:, np.newaxis]
    deformed = verts + normals * total_disp

    # Recompute normals
    new_normals = _compute_normals(deformed, mesh.indices)

    return MeshData(vertices=deformed.astype(np.float32), normals=new_normals, indices=mesh.indices)


def generate_mesh(shape: str, subdivision: int = 3) -> MeshData:
    """Generate a mesh by shape name."""
    match shape:
        case "icosphere":
            return icosphere(subdivision)
        case "torus":
            return torus()
        case "superellipsoid":
            return superellipsoid(e1=0.6, e2=0.6)
        case "octahedron":
            return superellipsoid(e1=1.5, e2=1.5)
        case "twisted_torus":
            return torus(major_radius=1.0, minor_radius=0.3,
                         major_segments=64, minor_segments=16)
        case _:
            return icosphere(subdivision)
