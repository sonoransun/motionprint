/// Blinn-Phong per-pixel shading.
///
/// Direct port of the GLSL fragment shader in `shaders.py`.

use glam::Vec3;

pub struct ShadeUniforms {
    pub light_pos: Vec3,
    pub light_color: Vec3,
    pub camera_pos: Vec3,
    pub object_color: Vec3,
    pub shininess: f32,
    pub specular_strength: f32,
    pub ambient_strength: f32,
}

/// Evaluate Blinn-Phong shading at a surface point.
pub fn blinn_phong(world_pos: Vec3, normal: Vec3, u: &ShadeUniforms) -> [f32; 3] {
    let norm = normal.normalize();
    let light_dir = (u.light_pos - world_pos).normalize();
    let view_dir = (u.camera_pos - world_pos).normalize();
    let halfway = (light_dir + view_dir).normalize();

    // Ambient
    let ambient = u.ambient_strength * u.light_color;

    // Diffuse
    let diff = norm.dot(light_dir).max(0.0);
    let diffuse = diff * u.light_color;

    // Specular (Blinn-Phong)
    let spec = norm.dot(halfway).max(0.0).powf(u.shininess);
    let specular = u.specular_strength * spec * u.light_color;

    let result = (ambient + diffuse + specular) * u.object_color;
    [result.x, result.y, result.z]
}
