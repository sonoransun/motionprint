FROM rust:1.77-bookworm AS builder
WORKDIR /build
COPY service/Cargo.toml service/Cargo.lock ./
COPY service/src/ ./src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/target/release/motionprint-service /usr/local/bin/
RUN mkdir -p /var/cache/motionprint
ENV PORT=3000 \
    MOTIONPRINT_CACHE_DIR=/var/cache/motionprint \
    MOTIONPRINT_CACHE_MAX=2147483648 \
    RUST_LOG=info
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1
ENTRYPOINT ["motionprint-service"]
