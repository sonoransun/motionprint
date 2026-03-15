/// Digest-to-visual-parameter mapping.
///
/// Port of Python `hash_mapping.py:compute_visual_params()`.
/// Identical byte allocations and formulas.

use crate::math_util::hls_to_rgb;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Shape {
    Icosphere,
    Torus,
    Superellipsoid,
    Octahedron,
    TwistedTorus,
}

const SHAPES: [Shape; 5] = [
    Shape::Icosphere,
    Shape::Torus,
    Shape::Superellipsoid,
    Shape::Octahedron,
    Shape::TwistedTorus,
];

#[derive(Debug, Clone)]
pub struct VisualParams {
    pub base_shape: Shape,
    pub subdivision: u32,
    pub primary_color: [f32; 3],
    pub secondary_color: [f32; 3],
    pub background_color: [f32; 3],
    pub light_elevation: f32,
    pub light_azimuth_start: f32,
    pub light_warmth: f32,
    pub camera_radius: f32,
    pub camera_elevation: f32,
    pub camera_fov: f32,
    pub rotation_speed: f32,
    pub axis_tilt: f32,
    pub deformation_amplitudes: [f32; 4],
    pub shininess: f32,
    pub specular_strength: f32,
    pub pulse_amplitude: f32,
    pub pulse_frequency: f32,
    pub morph_seed: [u8; 4],
}

pub fn compute_visual_params(digest: &[u8; 32]) -> VisualParams {
    let b = digest;

    let shape_idx = (((b[0] as u16) << 8) | b[1] as u16) % 5;
    let base_shape = SHAPES[shape_idx as usize];
    let subdivision = 2 + (b[2] % 3) as u32;

    let primary_color = hls_to_rgb(
        b[4] as f32 / 255.0,
        0.35 + b[6] as f32 / 425.0,
        0.5 + b[5] as f32 / 510.0,
    );

    let secondary_color = hls_to_rgb(
        b[7] as f32 / 255.0,
        0.35 + b[9] as f32 / 425.0,
        0.5 + b[8] as f32 / 510.0,
    );

    let background_color = hls_to_rgb(
        b[10] as f32 / 255.0,
        0.08 + b[11] as f32 / 1275.0,
        0.05 + b[11] as f32 / 2550.0,
    );

    let light_elevation = b[12] as f32 / 255.0 * 60.0 + 15.0;
    let light_azimuth_start = b[13] as f32 / 255.0 * 360.0;
    let light_warmth = b[14] as f32 / 255.0;

    let camera_radius = 2.5 + b[15] as f32 / 255.0 * 1.5;
    let camera_elevation = b[16] as f32 / 255.0 * 40.0 - 5.0;
    let camera_fov = 40.0 + b[17] as f32 / 255.0 * 30.0;

    let rotation_speed = 0.5 + b[18] as f32 / 255.0 * 2.0;
    let axis_tilt = b[19] as f32 / 255.0 * 30.0;

    let deformation_amplitudes = [
        b[20] as f32 / 255.0 * 0.3,
        b[21] as f32 / 255.0 * 0.3,
        b[22] as f32 / 255.0 * 0.3,
        b[23] as f32 / 255.0 * 0.3,
    ];

    let shininess = 8.0 + b[24] as f32 / 255.0 * 120.0;
    let specular_strength = 0.2 + b[25] as f32 / 255.0 * 0.8;

    let pulse_amplitude = b[26] as f32 / 255.0 * 0.08;
    let pulse_frequency = (1 + b[27] % 5) as f32;

    let morph_seed = [b[28], b[29], b[30], b[31]];

    VisualParams {
        base_shape,
        subdivision,
        primary_color,
        secondary_color,
        background_color,
        light_elevation,
        light_azimuth_start,
        light_warmth,
        camera_radius,
        camera_elevation,
        camera_fov,
        rotation_speed,
        axis_tilt,
        deformation_amplitudes,
        shininess,
        specular_strength,
        pulse_amplitude,
        pulse_frequency,
        morph_seed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shape_selection() {
        let mut digest = [0u8; 32];
        for i in 0..5u16 {
            digest[0] = (i >> 8) as u8;
            digest[1] = (i & 0xff) as u8;
            let params = compute_visual_params(&digest);
            assert_eq!(params.base_shape, SHAPES[i as usize]);
        }
    }

    #[test]
    fn test_subdivision_range() {
        for val in 0..=255u8 {
            let mut digest = [0u8; 32];
            digest[2] = val;
            let params = compute_visual_params(&digest);
            assert!(params.subdivision >= 2 && params.subdivision <= 4);
        }
    }

    #[test]
    fn test_color_in_range() {
        let digest = [0x55u8; 32];
        let params = compute_visual_params(&digest);
        for ch in params.primary_color {
            assert!((0.0..=1.0).contains(&ch));
        }
        for ch in params.secondary_color {
            assert!((0.0..=1.0).contains(&ch));
        }
    }

    #[test]
    fn test_deterministic() {
        let digest = [0xAB; 32];
        let p1 = compute_visual_params(&digest);
        let p2 = compute_visual_params(&digest);
        assert_eq!(p1.base_shape, p2.base_shape);
        assert_eq!(p1.primary_color, p2.primary_color);
        assert_eq!(p1.shininess, p2.shininess);
    }
}
