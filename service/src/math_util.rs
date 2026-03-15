/// Color conversion and coordinate utilities.
///
/// HSL↔RGB conversion is an exact port of Python's `colorsys` module
/// to ensure visual parameter parity with the Python CLI.

/// Port of Python `colorsys.hls_to_rgb(h, l, s)`.
/// h, l, s all in [0, 1]. Returns (r, g, b) in [0, 1].
pub fn hls_to_rgb(h: f32, l: f32, s: f32) -> [f32; 3] {
    if s == 0.0 {
        return [l, l, l];
    }
    let m2 = if l <= 0.5 {
        l * (1.0 + s)
    } else {
        l + s - l * s
    };
    let m1 = 2.0 * l - m2;
    [
        v(m1, m2, h + 1.0 / 3.0),
        v(m1, m2, h),
        v(m1, m2, h - 1.0 / 3.0),
    ]
}

fn v(m1: f32, m2: f32, mut hue: f32) -> f32 {
    hue = hue.rem_euclid(1.0);
    if hue < 1.0 / 6.0 {
        m1 + (m2 - m1) * hue * 6.0
    } else if hue < 0.5 {
        m2
    } else if hue < 2.0 / 3.0 {
        m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0
    } else {
        m1
    }
}

/// Port of Python `colorsys.rgb_to_hls(r, g, b)`.
/// r, g, b in [0, 1]. Returns (h, l, s) in [0, 1].
pub fn rgb_to_hls(r: f32, g: f32, b: f32) -> (f32, f32, f32) {
    let max_c = r.max(g).max(b);
    let min_c = r.min(g).min(b);
    let l = (min_c + max_c) / 2.0;
    if min_c == max_c {
        return (0.0, l, 0.0);
    }
    let s = if l <= 0.5 {
        (max_c - min_c) / (max_c + min_c)
    } else {
        (max_c - min_c) / (2.0 - max_c - min_c)
    };
    let rc = (max_c - r) / (max_c - min_c);
    let gc = (max_c - g) / (max_c - min_c);
    let bc = (max_c - b) / (max_c - min_c);
    let h = if r == max_c {
        bc - gc
    } else if g == max_c {
        2.0 + rc - bc
    } else {
        4.0 + gc - rc
    };
    let h = (h / 6.0).rem_euclid(1.0);
    (h, l, s)
}

/// Linear interpolation between two RGB colors.
pub fn lerp_color(c1: [f32; 3], c2: [f32; 3], t: f32) -> [f32; 3] {
    [
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    ]
}

/// Shift the hue of an RGB color by `degrees`.
pub fn hue_shift_rgb(color: [f32; 3], degrees: f32) -> [f32; 3] {
    let (h, l, s) = rgb_to_hls(color[0], color[1], color[2]);
    let h = (h + degrees / 360.0).rem_euclid(1.0);
    hls_to_rgb(h, l, s)
}

/// Convert spherical coordinates (degrees) to cartesian.
pub fn spherical_to_cartesian(azimuth_deg: f32, elevation_deg: f32, radius: f32) -> [f32; 3] {
    let az = azimuth_deg.to_radians();
    let el = elevation_deg.to_radians();
    [
        radius * el.cos() * az.cos(),
        radius * el.cos() * az.sin(),
        radius * el.sin(),
    ]
}

/// Interpolate between cool and warm light colors.
pub fn light_color_from_warmth(warmth: f32) -> [f32; 3] {
    let cool = [0.85_f32, 0.90, 1.0];
    let warm = [1.0_f32, 0.95, 0.85];
    lerp_color(cool, warm, warmth)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hls_to_rgb_red() {
        let [r, g, b] = hls_to_rgb(0.0, 0.5, 1.0);
        assert!((r - 1.0).abs() < 1e-5);
        assert!(g.abs() < 1e-5);
        assert!(b.abs() < 1e-5);
    }

    #[test]
    fn test_hls_to_rgb_gray() {
        let [r, g, b] = hls_to_rgb(0.0, 0.5, 0.0);
        assert!((r - 0.5).abs() < 1e-5);
        assert!((g - 0.5).abs() < 1e-5);
        assert!((b - 0.5).abs() < 1e-5);
    }

    #[test]
    fn test_roundtrip_rgb_hls() {
        let original = [0.3, 0.7, 0.5];
        let (h, l, s) = rgb_to_hls(original[0], original[1], original[2]);
        let result = hls_to_rgb(h, l, s);
        for i in 0..3 {
            assert!((original[i] - result[i]).abs() < 1e-4, "channel {i} mismatch");
        }
    }

    #[test]
    fn test_spherical_to_cartesian_z_up() {
        let pos = spherical_to_cartesian(0.0, 90.0, 5.0);
        assert!(pos[0].abs() < 1e-4);
        assert!(pos[1].abs() < 1e-4);
        assert!((pos[2] - 5.0).abs() < 1e-4);
    }
}
