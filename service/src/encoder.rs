/// Video encoding via ffmpeg subprocess.
///
/// Supports VP9/WebM and H.264/MP4 output formats.
/// Frames are piped as raw RGB24 via stdin.

use std::io::Write;
use std::process::{Child, Command, Stdio};

use serde::Deserialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum VideoFormat {
    Webm,
    Mp4,
}

impl VideoFormat {
    pub fn content_type(self) -> &'static str {
        match self {
            Self::Webm => "video/webm",
            Self::Mp4 => "video/mp4",
        }
    }

    pub fn extension(self) -> &'static str {
        match self {
            Self::Webm => "webm",
            Self::Mp4 => "mp4",
        }
    }
}

impl Default for VideoFormat {
    fn default() -> Self {
        Self::Webm
    }
}

pub struct FfmpegEncoder {
    child: Child,
    output_path: std::path::PathBuf,
    _temp_dir: tempfile::TempDir,
}

#[derive(Debug)]
pub enum EncoderError {
    FfmpegNotFound,
    SpawnFailed(std::io::Error),
    WriteFailed(std::io::Error),
    EncodingFailed(String),
    ReadOutputFailed(std::io::Error),
}

impl std::fmt::Display for EncoderError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::FfmpegNotFound => write!(f, "ffmpeg not found in PATH"),
            Self::SpawnFailed(e) => write!(f, "failed to spawn ffmpeg: {e}"),
            Self::WriteFailed(e) => write!(f, "failed to write frame: {e}"),
            Self::EncodingFailed(s) => write!(f, "ffmpeg encoding failed: {s}"),
            Self::ReadOutputFailed(e) => write!(f, "failed to read output: {e}"),
        }
    }
}

impl FfmpegEncoder {
    pub fn new(
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
    ) -> Result<Self, EncoderError> {
        let temp_dir = tempfile::tempdir().map_err(EncoderError::SpawnFailed)?;
        let output_path = temp_dir
            .path()
            .join(format!("output.{}", format.extension()));

        let mut cmd = Command::new("ffmpeg");
        cmd.args(["-y", "-threads", "1"]);
        cmd.args(["-f", "rawvideo", "-vcodec", "rawvideo"]);
        cmd.args(["-s", &format!("{width}x{height}")]);
        cmd.args(["-pix_fmt", "rgb24", "-r", &fps.to_string()]);
        cmd.args(["-i", "pipe:0"]);

        match format {
            VideoFormat::Webm => {
                cmd.args([
                    "-c:v", "libvpx-vp9",
                    "-pix_fmt", "yuv420p",
                    "-crf", "30",
                    "-b:v", "0",
                    "-row-mt", "1",
                    "-deadline", "good",
                ]);
            }
            VideoFormat::Mp4 => {
                cmd.args([
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "medium",
                    "-crf", "18",
                    "-movflags", "+faststart",
                ]);
            }
        }

        cmd.arg(output_path.to_str().unwrap());
        cmd.stdin(Stdio::piped());
        cmd.stdout(Stdio::null());
        cmd.stderr(Stdio::piped());

        let child = cmd.spawn().map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                EncoderError::FfmpegNotFound
            } else {
                EncoderError::SpawnFailed(e)
            }
        })?;

        Ok(Self {
            child,
            output_path,
            _temp_dir: temp_dir,
        })
    }

    pub fn write_frame(&mut self, rgb_bytes: &[u8]) -> Result<(), EncoderError> {
        self.child
            .stdin
            .as_mut()
            .unwrap()
            .write_all(rgb_bytes)
            .map_err(EncoderError::WriteFailed)
    }

    pub fn finish(mut self) -> Result<Vec<u8>, EncoderError> {
        // Close stdin to signal EOF
        drop(self.child.stdin.take());
        let output = self.child.wait_with_output().map_err(EncoderError::SpawnFailed)?;
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(EncoderError::EncodingFailed(stderr));
        }
        std::fs::read(&self.output_path).map_err(EncoderError::ReadOutputFailed)
    }
}
