/// Scene orchestrator: per-frame render loop.
///
/// Port of Python `scene.py`. Ties hash mapping, animation, geometry,
/// rasterization, and encoding into the full video generation pipeline.

use glam::{Mat4, Vec3};

use crate::animation::{generate_keyframes, interpolate_keyframes};
use crate::encoder::{EncoderError, FfmpegEncoder, VideoFormat};
use crate::geometry::{deform_mesh, generate_mesh};
use crate::math_util::{hue_shift_rgb, lerp_color, light_color_from_warmth, spherical_to_cartesian};
use crate::params::compute_visual_params;
use crate::rasterizer::{rasterize_mesh, FrameBuffer};
use crate::shading::ShadeUniforms;

/// Generate a motionprint video from a 32-byte digest.
///
/// Returns the encoded video bytes.
pub fn render_video(
    digest: &[u8; 32],
    format: VideoFormat,
    width: u32,
    height: u32,
    fps: u32,
    duration: f32,
) -> Result<Vec<u8>, EncoderError> {
    let params = compute_visual_params(digest);
    let keyframes = generate_keyframes(digest);
    let base_mesh = generate_mesh(params.base_shape, params.subdivision);
    let total_frames = (fps as f32 * duration) as u32;

    let mut fb = FrameBuffer::new(width, height);
    let mut encoder = FfmpegEncoder::new(format, width, height, fps)?;

    let aspect = width as f32 / height as f32;
    let projection = Mat4::perspective_rh_gl(params.camera_fov.to_radians(), aspect, 0.1, 100.0);

    for frame_idx in 0..total_frames {
        let t = if total_frames > 1 {
            frame_idx as f32 / (total_frames - 1) as f32
        } else {
            0.0
        };

        // Interpolate keyframes
        let animated = interpolate_keyframes(&keyframes, t);
        let deform_blend = animated[0];
        let hue_shift_val = (animated[1] - 0.5) * 60.0;
        let light_offset = animated[2] * 45.0;
        let cam_dist_mod = (animated[3] - 0.5) * 0.6;
        let rotation_offset = animated[4] * 15.0;
        let spec_mod = 0.5 + animated[5];
        let color_blend = animated[6];
        let noise_amount = animated[7] * 0.05;

        // Deform mesh
        let mesh = deform_mesh(
            &base_mesh,
            &params.deformation_amplitudes,
            &params.morph_seed,
            deform_blend,
            noise_amount,
        );

        // Model matrix: rotation around tilted axis + pulse scale
        let pulse = 1.0
            + params.pulse_amplitude
                * (2.0 * std::f32::consts::PI * params.pulse_frequency * t).sin();
        let angle = params.rotation_speed * t * 360.0 + rotation_offset;
        let tilt_rad = params.axis_tilt.to_radians();
        let axis = Vec3::new(tilt_rad.sin(), tilt_rad.cos(), 0.0).normalize();
        let model = Mat4::from_scale(Vec3::splat(pulse))
            * Mat4::from_axis_angle(axis, angle.to_radians());

        // Camera
        let cam_azimuth = t * 360.0 * 0.5;
        let cam_radius = params.camera_radius + cam_dist_mod;
        let cam_pos_arr = spherical_to_cartesian(cam_azimuth, params.camera_elevation, cam_radius);
        let cam_pos = Vec3::from(cam_pos_arr);
        let view = Mat4::look_at_rh(cam_pos, Vec3::ZERO, Vec3::Z);

        // Light
        let light_az = params.light_azimuth_start + t * 90.0 + light_offset;
        let light_pos_arr = spherical_to_cartesian(light_az, params.light_elevation, 5.0);
        let light_color = light_color_from_warmth(params.light_warmth);

        // Object color
        let blended = lerp_color(params.primary_color, params.secondary_color, color_blend);
        let obj_color = hue_shift_rgb(blended, hue_shift_val);

        let mvp = projection * view * model;

        let uniforms = ShadeUniforms {
            light_pos: Vec3::from(light_pos_arr),
            light_color: Vec3::from(light_color),
            camera_pos: cam_pos,
            object_color: Vec3::from(obj_color),
            shininess: params.shininess,
            specular_strength: params.specular_strength * spec_mod,
            ambient_strength: 0.15,
        };

        // Render frame
        fb.clear(params.background_color);
        rasterize_mesh(
            &mut fb,
            &mesh.vertices,
            &mesh.normals,
            &mesh.indices,
            &mvp,
            &model,
            &uniforms,
        );

        encoder.write_frame(&fb.to_rgb_bytes())?;
    }

    encoder.finish()
}
