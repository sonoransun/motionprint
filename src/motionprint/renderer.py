"""Offscreen 3D renderer using moderngl.

Creates a standalone OpenGL context, renders meshes with Blinn-Phong
shading, and reads back RGB frames for video encoding.
"""

from __future__ import annotations

import numpy as np
import moderngl
import pyrr

from motionprint.geometry import MeshData
from motionprint.shaders import VERTEX_SHADER, FRAGMENT_SHADER


class Renderer:
    """Offscreen 3D renderer with Blinn-Phong lighting."""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

        # Create standalone context (no window)
        self.ctx = moderngl.create_context(standalone=True)
        self.ctx.enable(moderngl.DEPTH_TEST)

        # Compile shaders
        self.prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )

        # Create framebuffer
        self.color_tex = self.ctx.texture((width, height), 4)
        self.depth_rb = self.ctx.depth_renderbuffer((width, height))
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color_tex],
            depth_attachment=self.depth_rb,
        )

        self.vbo: moderngl.Buffer | None = None
        self.ibo: moderngl.Buffer | None = None
        self.vao: moderngl.VertexArray | None = None

    def update_geometry(self, mesh: MeshData) -> None:
        """Upload mesh data to GPU buffers."""
        interleaved = mesh.interleaved()
        flat_idx = mesh.flat_indices()

        if self.vbo is not None:
            self.vbo.release()
        if self.ibo is not None:
            self.ibo.release()
        if self.vao is not None:
            self.vao.release()

        self.vbo = self.ctx.buffer(interleaved.tobytes())
        self.ibo = self.ctx.buffer(flat_idx.tobytes())
        self.vao = self.ctx.vertex_array(
            self.prog,
            [(self.vbo, "3f 3f", "in_position", "in_normal")],
            index_buffer=self.ibo,
            index_element_size=4,
        )

    def set_uniforms(
        self,
        model: np.ndarray,
        view: np.ndarray,
        projection: np.ndarray,
        object_color: tuple[float, float, float],
        light_pos: tuple[float, float, float],
        light_color: tuple[float, float, float],
        camera_pos: tuple[float, float, float],
        shininess: float,
        specular_strength: float,
        ambient_strength: float = 0.15,
    ) -> None:
        """Set shader uniform values."""
        mvp = pyrr.matrix44.multiply(
            pyrr.matrix44.multiply(model, view), projection
        )

        self.prog["u_mvp"].write(mvp.astype("f4").tobytes())
        self.prog["u_model"].write(model.astype("f4").tobytes())
        self.prog["u_object_color"].value = object_color
        self.prog["u_light_pos"].value = light_pos
        self.prog["u_light_color"].value = light_color
        self.prog["u_camera_pos"].value = camera_pos
        self.prog["u_shininess"].value = shininess
        self.prog["u_specular_strength"].value = specular_strength
        self.prog["u_ambient_strength"].value = ambient_strength

    def render_frame(
        self, bg_color: tuple[float, float, float] = (0.05, 0.05, 0.08)
    ) -> bytes:
        """Render current scene and return RGB frame bytes (top-down)."""
        self.fbo.use()
        self.ctx.clear(bg_color[0], bg_color[1], bg_color[2], 1.0)

        if self.vao is not None:
            self.vao.render(moderngl.TRIANGLES)

        # Read RGB pixels
        data = self.fbo.read(components=3)

        # Flip vertically (OpenGL is bottom-up)
        frame = np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3)
        frame = np.flip(frame, axis=0).copy()

        return frame.tobytes()

    def release(self) -> None:
        """Release all GPU resources."""
        if self.vao is not None:
            self.vao.release()
        if self.vbo is not None:
            self.vbo.release()
        if self.ibo is not None:
            self.ibo.release()
        self.fbo.release()
        self.color_tex.release()
        self.depth_rb.release()
        self.prog.release()
        self.ctx.release()
