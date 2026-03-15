/// Animation keyframe generation and interpolation.
///
/// Uses ChaCha8Rng seeded with the 32-byte digest to generate 64
/// keyframes of 8 float channels. Catmull-Rom spline interpolation
/// produces smooth C1-continuous animation curves.

use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

/// Generate 64 animation keyframes from a digest seed.
/// Each keyframe has 8 float channels in [0, 1].
pub fn generate_keyframes(digest: &[u8; 32]) -> Vec<[f32; 8]> {
    let mut rng = ChaCha8Rng::from_seed(*digest);
    let mut keyframes = Vec::with_capacity(64);
    for _ in 0..64 {
        let mut frame = [0.0f32; 8];
        for ch in &mut frame {
            *ch = rng.random::<f32>();
        }
        keyframes.push(frame);
    }
    keyframes
}

/// Interpolate keyframes at normalized time t (0–1) using Catmull-Rom splines.
/// Returns 8-element array of interpolated values clamped to [0, 1].
pub fn interpolate_keyframes(keyframes: &[[f32; 8]], t: f32) -> [f32; 8] {
    let n = keyframes.len();
    if n == 0 {
        return [0.0; 8];
    }
    if n == 1 {
        return keyframes[0];
    }

    let t = t.clamp(0.0, 1.0);
    let pos = t * (n as f32 - 1.0);
    let idx = pos as usize;
    let frac = pos - idx as f32;

    let i0 = idx.saturating_sub(1);
    let i1 = idx;
    let i2 = (idx + 1).min(n - 1);
    let i3 = (idx + 2).min(n - 1);

    let mut result = [0.0f32; 8];
    for ch in 0..8 {
        let p0 = keyframes[i0][ch] as f64;
        let p1 = keyframes[i1][ch] as f64;
        let p2 = keyframes[i2][ch] as f64;
        let p3 = keyframes[i3][ch] as f64;
        let f = frac as f64;
        let f2 = f * f;
        let f3 = f2 * f;

        let val = 0.5
            * ((2.0 * p1)
                + (-p0 + p2) * f
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * f3);
        result[ch] = val.clamp(0.0, 1.0) as f32;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_keyframe_count() {
        let digest = [0u8; 32];
        let kf = generate_keyframes(&digest);
        assert_eq!(kf.len(), 64);
    }

    #[test]
    fn test_keyframe_range() {
        let digest = [0xAB; 32];
        let kf = generate_keyframes(&digest);
        for frame in &kf {
            for &v in frame {
                assert!((0.0..1.0).contains(&v), "value {v} out of range");
            }
        }
    }

    #[test]
    fn test_deterministic() {
        let digest = [0x42; 32];
        let kf1 = generate_keyframes(&digest);
        let kf2 = generate_keyframes(&digest);
        assert_eq!(kf1, kf2);
    }

    #[test]
    fn test_different_digests() {
        let kf1 = generate_keyframes(&[0x00; 32]);
        let kf2 = generate_keyframes(&[0xFF; 32]);
        assert_ne!(kf1, kf2);
    }

    #[test]
    fn test_interpolate_endpoints() {
        let kf = vec![[0.0f32; 8], [1.0; 8]];
        let start = interpolate_keyframes(&kf, 0.0);
        let end = interpolate_keyframes(&kf, 1.0);
        for &v in &start {
            assert!((v - 0.0).abs() < 0.02);
        }
        for &v in &end {
            assert!((v - 1.0).abs() < 0.02);
        }
    }

    #[test]
    fn test_interpolate_midpoint() {
        let kf = vec![[0.0f32; 8], [1.0; 8]];
        let mid = interpolate_keyframes(&kf, 0.5);
        for &v in &mid {
            assert!((v - 0.5).abs() < 0.2);
        }
    }
}
