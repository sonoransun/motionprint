/// HTTP API: Axum router, request validation, and response handling.

use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::Router;
use serde::Deserialize;
use serde_json::json;
use tokio::sync::Semaphore;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;

use crate::cache::VideoCache;
use crate::encoder::VideoFormat;
use crate::palette::{resolve_palette, KNOWN_PALETTES};
use crate::scene::render_video;

pub struct AppState {
    pub cache: VideoCache,
    pub semaphore: Semaphore,
}

fn default_format() -> VideoFormat { VideoFormat::Webm }
fn default_width() -> u32 { 1280 }
fn default_height() -> u32 { 720 }
fn default_fps() -> u32 { 30 }
fn default_duration() -> f32 { 6.0 }
fn default_speed() -> f32 { 1.0 }

const TEMPO_CALM: f32 = 0.5;
const TEMPO_NORMAL: f32 = 1.0;
const TEMPO_ENERGETIC: f32 = 2.0;

#[derive(Debug, Deserialize)]
pub struct RenderQuery {
    #[serde(default = "default_format")]
    pub format: VideoFormat,
    #[serde(default = "default_width")]
    pub width: u32,
    #[serde(default = "default_height")]
    pub height: u32,
    #[serde(default = "default_fps")]
    pub fps: u32,
    #[serde(default = "default_duration")]
    pub duration: f32,
    #[serde(default)]
    pub palette: Option<String>,
    #[serde(default)]
    pub primary_color: Option<String>,
    #[serde(default)]
    pub secondary_color: Option<String>,
    #[serde(default)]
    pub background_color: Option<String>,
    #[serde(default)]
    pub tempo: Option<String>,
    #[serde(default = "default_speed")]
    pub speed: f32,
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/v1/motionprint/{sha256_hex}", get(render_handler))
        .route("/health", get(health_handler))
        .layer(TraceLayer::new_for_http())
        .layer(CorsLayer::permissive())
        .with_state(state)
}

async fn health_handler() -> &'static str {
    "ok"
}

async fn render_handler(
    Path(sha256_hex): Path<String>,
    Query(query): Query<RenderQuery>,
    State(state): State<Arc<AppState>>,
) -> Result<Response, ApiError> {
    // Validate digest
    if sha256_hex.len() != 64 {
        return Err(ApiError::InvalidDigest(
            "SHA-256 digest must be exactly 64 hexadecimal characters".into(),
        ));
    }
    let digest_bytes = hex::decode(&sha256_hex).map_err(|_| {
        ApiError::InvalidDigest("digest contains invalid hexadecimal characters".into())
    })?;
    let digest: [u8; 32] = digest_bytes
        .try_into()
        .map_err(|_| ApiError::InvalidDigest("digest must be 32 bytes".into()))?;

    // Validate params
    if !(64..=3840).contains(&query.width) || !(64..=2160).contains(&query.height) {
        return Err(ApiError::InvalidParams("resolution out of range".into()));
    }
    if !(1..=60).contains(&query.fps) {
        return Err(ApiError::InvalidParams("fps must be 1–60".into()));
    }
    if !(0.5..=30.0).contains(&query.duration) {
        return Err(ApiError::InvalidParams("duration must be 0.5–30.0".into()));
    }
    if !(0.1..=10.0).contains(&query.speed) {
        return Err(ApiError::InvalidParams("speed must be 0.1–10.0".into()));
    }

    // Resolve palette + overrides
    let palette_name = query.palette.as_deref().unwrap_or("default");
    if !KNOWN_PALETTES.contains(&palette_name) {
        return Err(ApiError::InvalidParams(format!(
            "unknown palette: {palette_name:?} (known: {})",
            KNOWN_PALETTES.join(", ")
        )));
    }
    let palette = resolve_palette(
        palette_name,
        query.primary_color.as_deref(),
        query.secondary_color.as_deref(),
        query.background_color.as_deref(),
    )
    .map_err(|e| ApiError::InvalidParams(e.to_string()))?;

    // Resolve tempo * speed into a final multiplier.
    let tempo_factor = match query.tempo.as_deref() {
        None | Some("normal") => TEMPO_NORMAL,
        Some("calm") => TEMPO_CALM,
        Some("energetic") => TEMPO_ENERGETIC,
        Some(other) => {
            return Err(ApiError::InvalidParams(format!(
                "unknown tempo: {other:?} (known: calm, normal, energetic)"
            )))
        }
    };
    let final_speed = tempo_factor * query.speed;

    // Check cache
    if let Some(data) = state.cache.get(
        &digest,
        query.format,
        query.width,
        query.height,
        query.fps,
        query.duration,
        palette_name,
        query.primary_color.as_deref(),
        query.secondary_color.as_deref(),
        query.background_color.as_deref(),
        final_speed,
    ) {
        return Ok(video_response(data, &sha256_hex, query.format));
    }

    // Acquire render permit
    let _permit = state
        .semaphore
        .try_acquire()
        .map_err(|_| ApiError::TooManyRequests)?;

    // Render (blocking work on a thread)
    let format = query.format;
    let width = query.width;
    let height = query.height;
    let fps = query.fps;
    let duration = query.duration;
    let render_palette = palette;

    let data = tokio::task::spawn_blocking(move || {
        render_video(&digest, format, width, height, fps, duration, &render_palette, final_speed)
    })
    .await
    .map_err(|e| ApiError::Internal(format!("render task failed: {e}")))?
    .map_err(|e| ApiError::Internal(e.to_string()))?;

    // Cache result
    state.cache.put(
        &digest,
        query.format,
        query.width,
        query.height,
        query.fps,
        query.duration,
        palette_name,
        query.primary_color.as_deref(),
        query.secondary_color.as_deref(),
        query.background_color.as_deref(),
        final_speed,
        &data,
    );

    Ok(video_response(data, &sha256_hex, query.format))
}

fn video_response(data: Vec<u8>, digest_hex: &str, format: VideoFormat) -> Response {
    let ext = format.extension();
    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, format.content_type().to_string()),
            (
                header::CONTENT_DISPOSITION,
                format!("inline; filename=\"motionprint_{}.{ext}\"", &digest_hex[..8]),
            ),
            (
                header::CACHE_CONTROL,
                "public, max-age=31536000, immutable".to_string(),
            ),
            (
                "x-motionprint-digest".parse().unwrap(),
                digest_hex.to_string(),
            ),
        ],
        data,
    )
        .into_response()
}

#[derive(Debug)]
pub enum ApiError {
    InvalidDigest(String),
    InvalidParams(String),
    TooManyRequests,
    Internal(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, error_type, message) = match self {
            Self::InvalidDigest(msg) => (StatusCode::BAD_REQUEST, "invalid_digest", msg),
            Self::InvalidParams(msg) => (StatusCode::BAD_REQUEST, "invalid_params", msg),
            Self::TooManyRequests => (
                StatusCode::SERVICE_UNAVAILABLE,
                "busy",
                "Server is at render capacity, try again shortly".into(),
            ),
            Self::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, "internal_error", msg),
        };
        (
            status,
            axum::Json(json!({ "error": error_type, "message": message })),
        )
            .into_response()
    }
}
