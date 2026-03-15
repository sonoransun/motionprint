"""Video encoding via ffmpeg subprocess pipe."""

from __future__ import annotations

import shutil
import subprocess


class FFmpegNotFoundError(RuntimeError):
    pass


class VideoEncoder:
    """Encodes raw RGB frames to MP4 via ffmpeg stdin pipe."""

    def __init__(
        self,
        output_path: str,
        width: int,
        height: int,
        fps: int = 30,
    ):
        if shutil.which("ffmpeg") is None:
            raise FFmpegNotFoundError(
                "ffmpeg not found. Install it: https://ffmpeg.org/download.html"
            )

        self.output_path = output_path
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "rgb24",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            "-movflags", "+faststart",
            output_path,
        ]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write_frame(self, frame_bytes: bytes) -> None:
        """Write one RGB frame to the encoder."""
        self.process.stdin.write(frame_bytes)

    def close(self) -> None:
        """Finalize the video file."""
        self.process.stdin.close()
        self.process.wait()
        if self.process.returncode != 0:
            stderr = self.process.stderr.read().decode(errors="replace")
            raise RuntimeError(f"ffmpeg encoding failed:\n{stderr}")
