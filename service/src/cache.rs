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

    fn cache_key(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
    ) -> String {
        let mut hasher = Sha256::new();
        hasher.update(digest);
        hasher.update(format.extension().as_bytes());
        hasher.update(width.to_le_bytes());
        hasher.update(height.to_le_bytes());
        hasher.update(fps.to_le_bytes());
        hasher.update(((duration * 1000.0) as u32).to_le_bytes());
        hex::encode(hasher.finalize())
    }

    fn path_for(&self, key: &str, format: VideoFormat) -> PathBuf {
        self.dir.join(format!("{key}.{}", format.extension()))
    }

    pub fn get(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
    ) -> Option<Vec<u8>> {
        let key = self.cache_key(digest, format, width, height, fps, duration);
        let path = self.path_for(&key, format);
        fs::read(&path).ok()
    }

    pub fn put(
        &self,
        digest: &[u8; 32],
        format: VideoFormat,
        width: u32,
        height: u32,
        fps: u32,
        duration: f32,
        data: &[u8],
    ) {
        let key = self.cache_key(digest, format, width, height, fps, duration);
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
