/// On-disk LRU cache for rendered videos.
///
/// Cache key is SHA-256 of (digest, format, width, height, fps, duration_millis).
/// Files are stored in a configurable directory with LRU eviction.

use std::fs;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::encoder::VideoFormat;

pub struct VideoCache {
    dir: PathBuf,
    max_size_bytes: u64,
}

impl VideoCache {
    pub fn new(dir: PathBuf, max_size_bytes: u64) -> Self {
        fs::create_dir_all(&dir).ok();
        Self { dir, max_size_bytes }
    }

    #[allow(clippy::too_many_arguments)]
    fn cache_key(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
        palette_name: &str,
        primary_hex: Option<&str>,
        secondary_hex: Option<&str>,
        background_hex: Option<&str>,
        speed: f32,
    ) -> String {
        let mut hasher = Sha256::new();
        hasher.update(digest);
        hasher.update(format.extension().as_bytes());
        hasher.update(width.to_le_bytes());
        hasher.update(height.to_le_bytes());
        hasher.update(fps.to_le_bytes());
        hasher.update(((duration * 1000.0) as u32).to_le_bytes());
        // 0-byte separators prevent adjacent string fields from colliding
        // ("vibra" + "ntX" vs "vibrant" + "X").
        hasher.update(palette_name.as_bytes());
        hasher.update([0u8]);
        for h in [primary_hex, secondary_hex, background_hex] {
            hasher.update(h.unwrap_or("").as_bytes());
            hasher.update([0u8]);
        }
        hasher.update(((speed * 1000.0) as u32).to_le_bytes());
        hex::encode(hasher.finalize())
    }

    fn path_for(&self, key: &str, format: VideoFormat) -> PathBuf {
        self.dir.join(format!("{key}.{}", format.extension()))
    }

    #[allow(clippy::too_many_arguments)]
    pub fn get(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
        palette_name: &str,
        primary_hex: Option<&str>,
        secondary_hex: Option<&str>,
        background_hex: Option<&str>,
        speed: f32,
    ) -> Option<Vec<u8>> {
        let key = self.cache_key(
            digest,
            format,
            width,
            height,
            fps,
            duration,
            palette_name,
            primary_hex,
            secondary_hex,
            background_hex,
            speed,
        );
        let path = self.path_for(&key, format);
        fs::read(&path).ok()
    }

    #[allow(clippy::too_many_arguments)]
    pub fn put(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
        palette_name: &str,
        primary_hex: Option<&str>,
        secondary_hex: Option<&str>,
        background_hex: Option<&str>,
        speed: f32,
        data: &[u8],
    ) {
        let key = self.cache_key(
            digest,
            format,
            width,
            height,
            fps,
            duration,
            palette_name,
            primary_hex,
            secondary_hex,
            background_hex,
            speed,
        );
        let path = self.path_for(&key, format);
        fs::write(&path, data).ok();
        self.maybe_evict();
    }

    fn maybe_evict(&self) {
        let entries = match fs::read_dir(&self.dir) {
            Ok(e) => e,
            Err(_) => return,
        };

        let mut files: Vec<(PathBuf, u64, std::time::SystemTime)> = entries
            .filter_map(|e| e.ok())
            .filter_map(|e| {
                let meta = e.metadata().ok()?;
                let accessed = meta.accessed().or_else(|_| meta.modified()).ok()?;
                Some((e.path(), meta.len(), accessed))
            })
            .collect();

        let total: u64 = files.iter().map(|(_, s, _)| s).sum();
        if total <= self.max_size_bytes {
            return;
        }

        // Sort by access time ascending (oldest first)
        files.sort_by_key(|(_, _, t)| *t);

        let target = self.max_size_bytes * 4 / 5; // Evict to 80%
        let mut current = total;
        for (path, size, _) in &files {
            if current <= target {
                break;
            }
            fs::remove_file(path).ok();
            current -= size;
        }
    }

    pub fn total_size(&self) -> u64 {
        dir_size(&self.dir)
    }
}

fn dir_size(path: &Path) -> u64 {
    fs::read_dir(path)
        .ok()
        .map(|entries| {
            entries
                .filter_map(|e| e.ok())
                .filter_map(|e| e.metadata().ok())
                .map(|m| m.len())
                .sum()
        })
        .unwrap_or(0)
}
