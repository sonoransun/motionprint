use std::path::PathBuf;
use std::sync::Arc;

use tokio::net::TcpListener;
use tracing_subscriber::EnvFilter;

use motionprint_service::api::{self, AppState};
use motionprint_service::cache::VideoCache;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();

    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(3000);

    let cache_dir = std::env::var("MOTIONPRINT_CACHE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp/motionprint-cache"));

    let max_cache_bytes: u64 = std::env::var("MOTIONPRINT_CACHE_MAX")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(1_073_741_824); // 1 GB

    let max_concurrent: usize = std::env::var("MOTIONPRINT_MAX_CONCURRENT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| num_cpus().min(8));

    let state = Arc::new(AppState {
        cache: VideoCache::new(cache_dir, max_cache_bytes),
        semaphore: tokio::sync::Semaphore::new(max_concurrent),
    });

    let app = api::router(state);

    let addr = format!("0.0.0.0:{port}");
    tracing::info!("motionprint-service listening on {addr}");
    let listener = TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
}
