"""GLSL shader sources for Blinn-Phong 3D rendering (OpenGL 3.3 core)."""

VERTEX_SHADER = """
#version 330

uniform mat4 u_mvp;
uniform mat4 u_model;

in vec3 in_position;
in vec3 in_normal;

out vec3 v_world_pos;
out vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(in_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * in_normal;
    gl_Position = u_mvp * vec4(in_position, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330

uniform vec3 u_light_pos;
uniform vec3 u_light_color;
uniform vec3 u_camera_pos;
uniform vec3 u_object_color;
uniform float u_shininess;
uniform float u_specular_strength;
uniform float u_ambient_strength;

in vec3 v_world_pos;
in vec3 v_normal;

out vec4 f_color;

void main() {
    vec3 norm = normalize(v_normal);
    vec3 light_dir = normalize(u_light_pos - v_world_pos);
    vec3 view_dir = normalize(u_camera_pos - v_world_pos);
    vec3 halfway = normalize(light_dir + view_dir);

    // Ambient
    vec3 ambient = u_ambient_strength * u_light_color;

    // Diffuse
    float diff = max(dot(norm, light_dir), 0.0);
    vec3 diffuse = diff * u_light_color;

    // Specular (Blinn-Phong)
    float spec = pow(max(dot(norm, halfway), 0.0), u_shininess);
    vec3 specular = u_specular_strength * spec * u_light_color;

    vec3 result = (ambient + diffuse + specular) * u_object_color;
    f_color = vec4(result, 1.0);
}
"""
