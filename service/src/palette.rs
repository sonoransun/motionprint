/// Color palette presets and custom overrides.
///
/// Mirror of Python `motionprint.palette`. The `default` preset keeps every
/// band as `None` so `apply_palette` falls back to the legacy formulas and
/// reproduces the pre-palette output byte-for-byte. Named presets set bands;
/// the digest still drives variation within each band. Explicit RGB overrides
/// beat bands per-channel.
///
/// `hls_to_rgb` in `math_util` takes (h, l, s) in canonical order with `h`
/// already normalized to [0, 1]. Do not reintroduce a (h, s, l) wrapper —
/// Python's `_hsl_to_rgb` helper reorders internally; Rust calls canonical
/// order directly.
use crate::math_util::hls_to_rgb;

pub type Rgb = [f32; 3];
pub type Band = (f32, f32);

#[derive(Debug, Clone, Copy, Default)]
pub struct PaletteSpec {
    pub name: &'static str,
    pub primary_hue_range: Option<Band>,
    pub primary_sat_range: Option<Band>,
    pub primary_light_range: Option<Band>,
    pub secondary_hue_range: Option<Band>,
    pub secondary_sat_range: Option<Band>,
    pub secondary_light_range: Option<Band>,
    pub background_hue_range: Option<Band>,
    pub background_sat_range: Option<Band>,
    pub background_light_range: Option<Band>,
    pub primary_override: Option<Rgb>,
    pub secondary_override: Option<Rgb>,
    pub background_override: Option<Rgb>,
}

pub const KNOWN_PALETTES: &[&str] = &[
    "default",
    "vibrant",
    "pastel",
    "mono",
    "sunset",
    "cyberpunk",
    "ocean",
];

/// Return the preset by name, or `None` for unknown names.
pub fn preset(name: &str) -> Option<PaletteSpec> {
    let spec = match name {
        "default" => PaletteSpec {
            name: "default",
            ..Default::default()
        },
        "vibrant" => PaletteSpec {
            name: "vibrant",
            primary_sat_range: Some((0.85, 1.0)),
            primary_light_range: Some((0.45, 0.60)),
            secondary_sat_range: Some((0.85, 1.0)),
            secondary_light_range: Some((0.45, 0.60)),
            ..Default::default()
        },
        "pastel" => PaletteSpec {
            name: "pastel",
            primary_sat_range: Some((0.30, 0.55)),
            primary_light_range: Some((0.70, 0.85)),
            secondary_sat_range: Some((0.30, 0.55)),
            secondary_light_range: Some((0.70, 0.85)),
            ..Default::default()
        },
        "mono" => PaletteSpec {
            name: "mono",
            primary_sat_range: Some((0.0, 0.08)),
            primary_light_range: Some((0.30, 0.70)),
            secondary_sat_range: Some((0.0, 0.08)),
            secondary_light_range: Some((0.30, 0.70)),
            ..Default::default()
        },
        "sunset" => PaletteSpec {
            name: "sunset",
            primary_hue_range: Some((0.0, 40.0)),
            primary_sat_range: Some((0.70, 0.95)),
            primary_light_range: Some((0.50, 0.70)),
            secondary_hue_range: Some((270.0, 330.0)),
            secondary_sat_range: Some((0.60, 0.90)),
            secondary_light_range: Some((0.45, 0.65)),
            ..Default::default()
        },
        "cyberpunk" => PaletteSpec {
            name: "cyberpunk",
            primary_hue_range: Some((280.0, 320.0)),
            primary_sat_range: Some((0.80, 1.0)),
            primary_light_range: Some((0.45, 0.60)),
            secondary_hue_range: Some((170.0, 200.0)),
            secondary_sat_range: Some((0.80, 1.0)),
            secondary_light_range: Some((0.45, 0.60)),
            background_hue_range: Some((240.0, 280.0)),
            background_sat_range: Some((0.15, 0.30)),
            background_light_range: Some((0.05, 0.12)),
            ..Default::default()
        },
        "ocean" => PaletteSpec {
            name: "ocean",
            primary_hue_range: Some((170.0, 230.0)),
            primary_sat_range: Some((0.55, 0.85)),
            primary_light_range: Some((0.30, 0.55)),
            secondary_hue_range: Some((170.0, 230.0)),
            secondary_sat_range: Some((0.55, 0.85)),
            secondary_light_range: Some((0.30, 0.55)),
            ..Default::default()
        },
        _ => return None,
    };
    Some(spec)
}

#[derive(Debug)]
pub enum PaletteError {
    BadHex(String),
    UnknownPalette(String),
}

impl std::fmt::Display for PaletteError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::BadHex(s) => write!(f, "must be 6 hex digits (#RRGGBB), got {s:?}"),
            Self::UnknownPalette(name) => {
                write!(
                    f,
                    "unknown palette: {name:?} (known: {})",
                    KNOWN_PALETTES.join(", ")
                )
            }
        }
    }
}

impl std::error::Error for PaletteError {}

/// Parse `#RRGGBB` or `RRGGBB` into an RGB triple in [0, 1].
pub fn parse_hex(s: &str) -> Result<Rgb, PaletteError> {
    let stripped = s.strip_prefix('#').unwrap_or(s);
    if stripped.len() != 6 || !stripped.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(PaletteError::BadHex(s.to_string()));
    }
    let r = u8::from_str_radix(&stripped[0..2], 16).unwrap();
    let g = u8::from_str_radix(&stripped[2..4], 16).unwrap();
    let b = u8::from_str_radix(&stripped[4..6], 16).unwrap();
    Ok([r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0])
}

/// Resolve a palette by name and layer optional hex overrides on top.
pub fn resolve_palette(
    name: &str,
    primary_hex: Option<&str>,
    secondary_hex: Option<&str>,
    background_hex: Option<&str>,
) -> Result<PaletteSpec, PaletteError> {
    let mut spec = preset(name).ok_or_else(|| PaletteError::UnknownPalette(name.to_string()))?;
    if let Some(h) = primary_hex {
        spec.primary_override = Some(parse_hex(h)?);
    }
    if let Some(h) = secondary_hex {
        spec.secondary_override = Some(parse_hex(h)?);
    }
    if let Some(h) = background_hex {
        spec.background_override = Some(parse_hex(h)?);
    }
    Ok(spec)
}

#[inline]
fn band(b: Option<Band>, byte_val: u8, legacy: f32) -> f32 {
    match b {
        None => legacy,
        Some((lo, hi)) => lo + (byte_val as f32 / 255.0) * (hi - lo),
    }
}

#[inline]
fn band_hue(b: Option<Band>, byte_val: u8) -> f32 {
    // Hue bands are expressed in degrees. Legacy path feeds normalized (0-1)
    // hue directly into hls_to_rgb; band path divides degrees by 360.
    match b {
        None => byte_val as f32 / 255.0,
        Some((lo, hi)) => {
            let deg = lo + (byte_val as f32 / 255.0) * (hi - lo);
            deg / 360.0
        }
    }
}

/// Return (primary, secondary, background) RGB for `digest` under `spec`.
pub fn apply_palette(spec: &PaletteSpec, digest: &[u8; 32]) -> (Rgb, Rgb, Rgb) {
    let b = digest;

    let primary = if let Some(rgb) = spec.primary_override {
        rgb
    } else {
        let h = band_hue(spec.primary_hue_range, b[4]);
        let s = band(spec.primary_sat_range, b[5], 0.5 + b[5] as f32 / 510.0);
        let l = band(spec.primary_light_range, b[6], 0.35 + b[6] as f32 / 425.0);
        hls_to_rgb(h, l, s)
    };

    let secondary = if let Some(rgb) = spec.secondary_override {
        rgb
    } else {
        let h = band_hue(spec.secondary_hue_range, b[7]);
        let s = band(spec.secondary_sat_range, b[8], 0.5 + b[8] as f32 / 510.0);
        let l = band(spec.secondary_light_range, b[9], 0.35 + b[9] as f32 / 425.0);
        hls_to_rgb(h, l, s)
    };

    let background = if let Some(rgb) = spec.background_override {
        rgb
    } else {
        let h = band_hue(spec.background_hue_range, b[10]);
        let s = band(spec.background_sat_range, b[11], 0.05 + b[11] as f32 / 2550.0);
        let l = band(spec.background_light_range, b[11], 0.08 + b[11] as f32 / 1275.0);
        hls_to_rgb(h, l, s)
    };

    (primary, secondary, background)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn legacy_colors(digest: &[u8; 32]) -> (Rgb, Rgb, Rgb) {
        let b = digest;
        let p = hls_to_rgb(
            b[4] as f32 / 255.0,
            0.35 + b[6] as f32 / 425.0,
            0.5 + b[5] as f32 / 510.0,
        );
        let s = hls_to_rgb(
            b[7] as f32 / 255.0,
            0.35 + b[9] as f32 / 425.0,
            0.5 + b[8] as f32 / 510.0,
        );
        let bg = hls_to_rgb(
            b[10] as f32 / 255.0,
            0.08 + b[11] as f32 / 1275.0,
            0.05 + b[11] as f32 / 2550.0,
        );
        (p, s, bg)
    }

    #[test]
    fn parse_hex_accepts_with_and_without_hash() {
        assert_eq!(parse_hex("#ff0000").unwrap(), [1.0, 0.0, 0.0]);
        assert_eq!(parse_hex("00ff00").unwrap(), [0.0, 1.0, 0.0]);
    }

    #[test]
    fn parse_hex_rejects_bad_input() {
        assert!(parse_hex("").is_err());
        assert!(parse_hex("#abcde").is_err());
        assert!(parse_hex("xyz123").is_err());
        assert!(parse_hex("##ff0000").is_err());
    }

    #[test]
    fn default_palette_matches_legacy() {
        let digest = [0xABu8; 32];
        let spec = preset("default").unwrap();
        let (p, s, bg) = apply_palette(&spec, &digest);
        let (lp, ls, lbg) = legacy_colors(&digest);
        assert_eq!(p, lp);
        assert_eq!(s, ls);
        assert_eq!(bg, lbg);
    }

    #[test]
    fn default_palette_matches_legacy_across_digests() {
        for seed in 0u8..8 {
            let digest = [seed.wrapping_mul(31); 32];
            let spec = preset("default").unwrap();
            let (p, s, bg) = apply_palette(&spec, &digest);
            let (lp, ls, lbg) = legacy_colors(&digest);
            assert_eq!(p, lp);
            assert_eq!(s, ls);
            assert_eq!(bg, lbg);
        }
    }

    #[test]
    fn pastel_primary_in_sat_light_band() {
        let spec = preset("pastel").unwrap();
        for byte_val in [0u8, 64, 128, 200, 255] {
            let mut digest = [0u8; 32];
            digest[5] = byte_val;
            digest[6] = byte_val;
            let (primary, _, _) = apply_palette(&spec, &digest);
            let (_h, l, s) = crate::math_util::rgb_to_hls(primary[0], primary[1], primary[2]);
            let (ps_lo, ps_hi) = spec.primary_sat_range.unwrap();
            let (pl_lo, pl_hi) = spec.primary_light_range.unwrap();
            assert!(s >= ps_lo - 1e-5 && s <= ps_hi + 1e-5, "s={s}");
            assert!(l >= pl_lo - 1e-5 && l <= pl_hi + 1e-5, "l={l}");
        }
    }

    #[test]
    fn sunset_primary_hue_in_band() {
        let spec = preset("sunset").unwrap();
        for byte_val in [0u8, 64, 128, 200, 255] {
            let mut digest = [128u8; 32];
            digest[4] = byte_val;
            let (primary, _, _) = apply_palette(&spec, &digest);
            let (h, _l, _s) = crate::math_util::rgb_to_hls(primary[0], primary[1], primary[2]);
            // rgb_to_hls may round-trip 0° as either 0 or ~360; fold to [-180, 180).
            let mut h_deg = h * 360.0;
            if h_deg > 180.0 {
                h_deg -= 360.0;
            }
            let (lo, hi) = spec.primary_hue_range.unwrap();
            assert!(h_deg >= lo - 0.5 && h_deg <= hi + 0.5, "h_deg={h_deg}");
        }
    }

    #[test]
    fn override_wins_over_preset() {
        let spec = resolve_palette("vibrant", Some("#ff0000"), None, None).unwrap();
        let digest = [0x55u8; 32];
        let (primary, _, _) = apply_palette(&spec, &digest);
        assert_eq!(primary, [1.0, 0.0, 0.0]);
    }

    #[test]
    fn per_channel_overrides_independent() {
        let spec =
            resolve_palette("default", Some("#112233"), Some("#445566"), Some("#778899")).unwrap();
        let digest = [42u8; 32];
        let (p, s, bg) = apply_palette(&spec, &digest);
        assert_eq!(p, [0x11 as f32 / 255.0, 0x22 as f32 / 255.0, 0x33 as f32 / 255.0]);
        assert_eq!(s, [0x44 as f32 / 255.0, 0x55 as f32 / 255.0, 0x66 as f32 / 255.0]);
        assert_eq!(bg, [0x77 as f32 / 255.0, 0x88 as f32 / 255.0, 0x99 as f32 / 255.0]);
    }

    #[test]
    fn unknown_palette_name_returns_none() {
        assert!(preset("neon").is_none());
    }
}
