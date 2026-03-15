/// Procedural 3D mesh generation and deformation.
///
/// Port of Python `geometry.py`. Generates icosphere, torus, and
/// superellipsoid meshes with hash-driven vertex deformation.

use std::collections::HashMap;

use glam::Vec3;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use rand_distr::{Distribution, StandardNormal};

use crate::params::Shape;

#[derive(Debug, Clone)]
pub struct MeshData {
    pub vertices: Vec<Vec3>,
    pub normals: Vec<Vec3>,
    pub indices: Vec<[u32; 3]>,
}

pub fn generate_mesh(shape: Shape, subdivision: u32) -> MeshData {
    match shape {
        Shape::Icosphere => icosphere(subdivision),
        Shape::Torus => torus(1.0, 0.4, 48, 24),
        Shape::Superellipsoid => superellipsoid(0.6, 0.6, 32, 32),
        Shape::Octahedron => superellipsoid(1.5, 1.5, 32, 32),
        Shape::TwistedTorus => torus(1.0, 0.3, 64, 16),
    }
}

pub fn icosphere(subdivision: u32) -> MeshData {
    let t = (1.0 + 5.0_f32.sqrt()) / 2.0;

    let raw_verts: [(f32, f32, f32); 12] = [
        (-1.0, t, 0.0), (1.0, t, 0.0), (-1.0, -t, 0.0), (1.0, -t, 0.0),
        (0.0, -1.0, t), (0.0, 1.0, t), (0.0, -1.0, -t), (0.0, 1.0, -t),
        (t, 0.0, -1.0), (t, 0.0, 1.0), (-t, 0.0, -1.0), (-t, 0.0, 1.0),
    ];

    let mut vertices: Vec<Vec3> = raw_verts
        .iter()
        .map(|&(x, y, z)| Vec3::new(x, y, z).normalize())
        .collect();

    let mut triangles: Vec<[u32; 3]> = vec![
        [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
        [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
        [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
        [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1],
    ];

    for _ in 0..subdivision {
        let mut midpoint_cache: HashMap<(u32, u32), u32> = HashMap::new();
        let mut new_triangles = Vec::with_capacity(triangles.len() * 4);

        for tri in &triangles {
            let a = get_midpoint(&mut vertices, &mut midpoint_cache, tri[0], tri[1]);
            let b = get_midpoint(&mut vertices, &mut midpoint_cache, tri[1], tri[2]);
            let c = get_midpoint(&mut vertices, &mut midpoint_cache, tri[2], tri[0]);
            new_triangles.push([tri[0], a, c]);
            new_triangles.push([tri[1], b, a]);
            new_triangles.push([tri[2], c, b]);
            new_triangles.push([a, b, c]);
        }
        triangles = new_triangles;
    }

    let normals = vertices.clone(); // For unit sphere, normal == position
    MeshData { vertices, normals, indices: triangles }
}

fn get_midpoint(
    vertices: &mut Vec<Vec3>,
    cache: &mut HashMap<(u32, u32), u32>,
    i1: u32,
    i2: u32,
) -> u32 {
    let key = (i1.min(i2), i1.max(i2));
    if let Some(&idx) = cache.get(&key) {
        return idx;
    }
    let mid = ((vertices[i1 as usize] + vertices[i2 as usize]) / 2.0).normalize();
    let idx = vertices.len() as u32;
    vertices.push(mid);
    cache.insert(key, idx);
    idx
}

pub fn torus(major_radius: f32, minor_radius: f32, major_seg: u32, minor_seg: u32) -> MeshData {
    let mut vertices = Vec::new();
    let mut indices = Vec::new();

    for i in 0..major_seg {
        let theta = 2.0 * std::f32::consts::PI * i as f32 / major_seg as f32;
        let (cos_t, sin_t) = (theta.cos(), theta.sin());
        for j in 0..minor_seg {
            let phi = 2.0 * std::f32::consts::PI * j as f32 / minor_seg as f32;
            let (cos_p, sin_p) = (phi.cos(), phi.sin());
            let r = major_radius + minor_radius * cos_p;
            vertices.push(Vec3::new(r * cos_t, r * sin_t, minor_radius * sin_p));
        }
    }

    for i in 0..major_seg {
        for j in 0..minor_seg {
            let curr = i * minor_seg + j;
            let next_j = i * minor_seg + (j + 1) % minor_seg;
            let next_i = ((i + 1) % major_seg) * minor_seg + j;
            let next_ij = ((i + 1) % major_seg) * minor_seg + (j + 1) % minor_seg;
            indices.push([curr, next_i, next_ij]);
            indices.push([curr, next_ij, next_j]);
        }
    }

    let normals = compute_normals(&vertices, &indices);
    MeshData { vertices, normals, indices }
}

pub fn superellipsoid(e1: f32, e2: f32, u_seg: u32, v_seg: u32) -> MeshData {
    fn sign_pow(base: f32, exp: f32) -> f32 {
        if base == 0.0 { return 0.0; }
        base.signum() * base.abs().powf(exp)
    }

    let mut vertices = Vec::new();
    for i in 0..=u_seg {
        let u = -std::f32::consts::FRAC_PI_2
            + std::f32::consts::PI * i as f32 / u_seg as f32;
        let (cos_u, sin_u) = (u.cos(), u.sin());
        for j in 0..=v_seg {
            let v = -std::f32::consts::PI
                + 2.0 * std::f32::consts::PI * j as f32 / v_seg as f32;
            let (cos_v, sin_v) = (v.cos(), v.sin());
            let x = sign_pow(cos_u, e1) * sign_pow(cos_v, e2);
            let y = sign_pow(cos_u, e1) * sign_pow(sin_v, e2);
            let z = sign_pow(sin_u, e1);
            vertices.push(Vec3::new(x, y, z));
        }
    }

    let mut indices = Vec::new();
    let row = v_seg + 1;
    for i in 0..u_seg {
        for j in 0..v_seg {
            let curr = i * row + j;
            indices.push([curr, curr + row, curr + row + 1]);
            indices.push([curr, curr + row + 1, curr + 1]);
        }
    }

    let normals = compute_normals(&vertices, &indices);
    MeshData { vertices, normals, indices }
}

fn compute_normals(vertices: &[Vec3], indices: &[[u32; 3]]) -> Vec<Vec3> {
    let mut normals = vec![Vec3::ZERO; vertices.len()];
    for tri in indices {
        let v0 = vertices[tri[0] as usize];
        let v1 = vertices[tri[1] as usize];
        let v2 = vertices[tri[2] as usize];
        let face_normal = (v1 - v0).cross(v2 - v0);
        for &idx in tri {
            normals[idx as usize] += face_normal;
        }
    }
    for n in &mut normals {
        let len = n.length();
        if len > 1e-10 {
            *n /= len;
        }
    }
    normals
}

pub fn deform_mesh(
    mesh: &MeshData,
    amplitudes: &[f32; 4],
    morph_seed: &[u8; 4],
    deform_blend: f32,
    noise_amount: f32,
) -> MeshData {
    let mut verts = mesh.vertices.clone();

    // Spherical-harmonic-like modes
    for (i, vert) in verts.iter_mut().enumerate() {
        let v = mesh.vertices[i];
        let n = mesh.normals[i];
        let r = v.length().max(1e-10);
        let theta = (v.z / r).clamp(-1.0, 1.0).acos();
        let phi = v.y.atan2(v.x);

        let mode0 = (2.0 * theta).cos();
        let mode1 = theta.sin() * phi.cos();
        let mode2 = (2.0 * theta).sin() * (2.0 * phi).cos();
        let mode3 = (3.0 * theta).cos();

        let displacement = amplitudes[0] * mode0
            + amplitudes[1] * mode1
            + amplitudes[2] * mode2
            + amplitudes[3] * mode3;

        *vert = v + n * displacement * deform_blend;
    }

    // Add noise
    if noise_amount > 0.0 {
        let mut seed = [0u8; 32];
        for i in 0..32 {
            seed[i] = morph_seed[i % 4].wrapping_add(i as u8);
        }
        let mut rng = ChaCha8Rng::from_seed(seed);
        for (i, vert) in verts.iter_mut().enumerate() {
            let noise: f32 = StandardNormal.sample(&mut rng);
            *vert += mesh.normals[i] * noise * noise_amount;
        }
    }

    let normals = compute_normals(&verts, &mesh.indices);
    MeshData {
        vertices: verts,
        normals,
        indices: mesh.indices.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_icosphere_vertex_count() {
        for n in 0..4 {
            let mesh = icosphere(n);
            let expected = 10 * 4u32.pow(n) + 2;
            assert_eq!(mesh.vertices.len() as u32, expected,
                       "subdivision {n}: got {}, expected {expected}", mesh.vertices.len());
        }
    }

    #[test]
    fn test_icosphere_unit_sphere() {
        let mesh = icosphere(2);
        for v in &mesh.vertices {
            assert!((v.length() - 1.0).abs() < 1e-5);
        }
    }

    #[test]
    fn test_torus_nonempty() {
        let mesh = torus(1.0, 0.4, 48, 24);
        assert!(!mesh.vertices.is_empty());
        assert!(!mesh.indices.is_empty());
    }

    #[test]
    fn test_deform_zero_blend() {
        let mesh = icosphere(2);
        let deformed = deform_mesh(&mesh, &[0.1; 4], &[0; 4], 0.0, 0.0);
        for (orig, def) in mesh.vertices.iter().zip(deformed.vertices.iter()) {
            assert!((orig - def).length() < 1e-6);
        }
    }
}
