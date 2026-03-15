/// Software triangle rasterizer with depth buffer.
///
/// CPU-only rendering: no GPU dependency. Implements edge-function
/// triangle rasterization with perspective-correct interpolation
/// and per-pixel Blinn-Phong shading.

use glam::{Mat4, Vec2, Vec3, Vec4};

use crate::shading::{blinn_phong, ShadeUniforms};

pub struct FrameBuffer {
    pub width: u32,
    pub height: u32,
    pub color: Vec<[f32; 3]>,
    pub depth: Vec<f32>,
}

impl FrameBuffer {
    pub fn new(width: u32, height: u32) -> Self {
        let size = (width * height) as usize;
        Self {
            width,
            height,
            color: vec![[0.0; 3]; size],
            depth: vec![f32::INFINITY; size],
        }
    }

    pub fn clear(&mut self, bg: [f32; 3]) {
        self.color.fill(bg);
        self.depth.fill(f32::INFINITY);
    }

    /// Convert to raw RGB bytes (top-down, 3 bytes per pixel).
    pub fn to_rgb_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity((self.width * self.height * 3) as usize);
        for px in &self.color {
            bytes.push((px[0].clamp(0.0, 1.0) * 255.0) as u8);
            bytes.push((px[1].clamp(0.0, 1.0) * 255.0) as u8);
            bytes.push((px[2].clamp(0.0, 1.0) * 255.0) as u8);
        }
        bytes
    }
}

struct TransformedVert {
    clip: Vec4,
    world_pos: Vec3,
    world_normal: Vec3,
}

fn edge_fn(a: Vec2, b: Vec2, c: Vec2) -> f32 {
    (c.x - a.x) * (b.y - a.y) - (c.y - a.y) * (b.x - a.x)
}

/// Rasterize all triangles in a mesh into the framebuffer.
pub fn rasterize_mesh(
    fb: &mut FrameBuffer,
    vertices: &[Vec3],
    normals: &[Vec3],
    indices: &[[u32; 3]],
    mvp: &Mat4,
    model: &Mat4,
    uniforms: &ShadeUniforms,
) {
    let normal_mat = model.inverse().transpose();
    let w = fb.width as f32;
    let h = fb.height as f32;

    // Transform all vertices once
    let transformed: Vec<TransformedVert> = vertices
        .iter()
        .zip(normals.iter())
        .map(|(&v, &n)| {
            let clip = *mvp * v.extend(1.0);
            let world = (*model * v.extend(1.0)).truncate();
            let wn = (normal_mat * n.extend(0.0)).truncate();
            TransformedVert {
                clip,
                world_pos: world,
                world_normal: wn,
            }
        })
        .collect();

    for tri in indices {
        let tv0 = &transformed[tri[0] as usize];
        let tv1 = &transformed[tri[1] as usize];
        let tv2 = &transformed[tri[2] as usize];

        // Skip if any vertex is behind camera
        if tv0.clip.w <= 0.0 || tv1.clip.w <= 0.0 || tv2.clip.w <= 0.0 {
            continue;
        }

        // Perspective divide → NDC
        let ndc0 = tv0.clip.truncate() / tv0.clip.w;
        let ndc1 = tv1.clip.truncate() / tv1.clip.w;
        let ndc2 = tv2.clip.truncate() / tv2.clip.w;

        // Viewport transform (top-down: Y is flipped)
        let s0 = Vec2::new((ndc0.x + 1.0) * 0.5 * w, (1.0 - ndc0.y) * 0.5 * h);
        let s1 = Vec2::new((ndc1.x + 1.0) * 0.5 * w, (1.0 - ndc1.y) * 0.5 * h);
        let s2 = Vec2::new((ndc2.x + 1.0) * 0.5 * w, (1.0 - ndc2.y) * 0.5 * h);

        // Triangle area (2x via edge function)
        let area = edge_fn(s0, s1, s2);
        if area.abs() < 1e-6 {
            continue; // Degenerate triangle
        }
        let inv_area = 1.0 / area;

        // Bounding box
        let min_x = s0.x.min(s1.x).min(s2.x).max(0.0) as u32;
        let min_y = s0.y.min(s1.y).min(s2.y).max(0.0) as u32;
        let max_x = (s0.x.max(s1.x).max(s2.x).ceil() as u32).min(fb.width - 1);
        let max_y = (s0.y.max(s1.y).max(s2.y).ceil() as u32).min(fb.height - 1);

        // Reciprocal clip-w for perspective correction
        let inv_w0 = 1.0 / tv0.clip.w;
        let inv_w1 = 1.0 / tv1.clip.w;
        let inv_w2 = 1.0 / tv2.clip.w;

        for py in min_y..=max_y {
            for px in min_x..=max_x {
                let p = Vec2::new(px as f32 + 0.5, py as f32 + 0.5);

                let b0 = edge_fn(s1, s2, p) * inv_area;
                let b1 = edge_fn(s2, s0, p) * inv_area;
                let b2 = edge_fn(s0, s1, p) * inv_area;

                // Inside test: handle both winding orders via area sign
                let inside = if area > 0.0 {
                    b0 >= 0.0 && b1 >= 0.0 && b2 >= 0.0
                } else {
                    b0 <= 0.0 && b1 <= 0.0 && b2 <= 0.0
                };

                if !inside {
                    continue;
                }

                // Perspective-correct interpolation
                let inv_w_interp = b0 * inv_w0 + b1 * inv_w1 + b2 * inv_w2;
                if inv_w_interp <= 0.0 {
                    continue;
                }
                let w_interp = 1.0 / inv_w_interp;

                // Interpolate depth (NDC z)
                let depth = (b0 * ndc0.z * inv_w0 + b1 * ndc1.z * inv_w1 + b2 * ndc2.z * inv_w2)
                    * w_interp;

                let pixel_idx = (py * fb.width + px) as usize;
                if depth >= fb.depth[pixel_idx] {
                    continue;
                }

                // Interpolate world position and normal
                let world_pos = (b0 * tv0.world_pos * inv_w0
                    + b1 * tv1.world_pos * inv_w1
                    + b2 * tv2.world_pos * inv_w2)
                    * w_interp;
                let world_normal = (b0 * tv0.world_normal * inv_w0
                    + b1 * tv1.world_normal * inv_w1
                    + b2 * tv2.world_normal * inv_w2)
                    * w_interp;

                let color = blinn_phong(world_pos, world_normal, uniforms);

                fb.color[pixel_idx] = color;
                fb.depth[pixel_idx] = depth;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_framebuffer_clear() {
        let mut fb = FrameBuffer::new(4, 4);
        fb.clear([0.5, 0.5, 0.5]);
        for px in &fb.color {
            assert_eq!(*px, [0.5, 0.5, 0.5]);
        }
    }

    #[test]
    fn test_rgb_bytes_length() {
        let fb = FrameBuffer::new(10, 10);
        let bytes = fb.to_rgb_bytes();
        assert_eq!(bytes.len(), 10 * 10 * 3);
    }

    #[test]
    fn test_rasterize_visible_triangle() {
        let mut fb = FrameBuffer::new(64, 64);
        fb.clear([0.0, 0.0, 0.0]);

        // A triangle facing the camera
        let verts = vec![
            Vec3::new(0.0, 0.5, 0.0),
            Vec3::new(-0.5, -0.5, 0.0),
            Vec3::new(0.5, -0.5, 0.0),
        ];
        let normals = vec![Vec3::Z; 3];
        let indices = vec![[0, 1, 2]];

        let model = Mat4::IDENTITY;
        let view = Mat4::look_at_rh(Vec3::new(0.0, 0.0, 3.0), Vec3::ZERO, Vec3::Y);
        let proj = Mat4::perspective_rh_gl(45.0_f32.to_radians(), 1.0, 0.1, 100.0);
        let mvp = proj * view * model;

        let uniforms = ShadeUniforms {
            light_pos: Vec3::new(0.0, 0.0, 5.0),
            light_color: Vec3::ONE,
            camera_pos: Vec3::new(0.0, 0.0, 3.0),
            object_color: Vec3::new(1.0, 0.0, 0.0),
            shininess: 32.0,
            specular_strength: 0.5,
            ambient_strength: 0.15,
        };

        rasterize_mesh(&mut fb, &verts, &normals, &indices, &mvp, &model, &uniforms);

        // At least some pixels should be non-black
        let has_color = fb.color.iter().any(|c| c[0] > 0.01 || c[1] > 0.01 || c[2] > 0.01);
        assert!(has_color, "Triangle should produce visible pixels");
    }
}
