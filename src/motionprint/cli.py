"""Command-line interface for motionprint."""

from __future__ import annotations

import argparse
import sys

from motionprint.scene import generate


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="motionprint",
        description="Generate an animated 3D video visualization of a SHA-256 hash digest.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Input file to hash (reads stdin if omitted and -s not given)",
    )
    parser.add_argument(
        "-s", "--string",
        help="Hash this string instead of a file",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output video path (default: motionprint_<hash8>.mp4)",
    )
    parser.add_argument(
        "-r", "--resolution",
        default="1280x720",
        help="Video resolution WxH (default: 1280x720)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Frames per second (default: 30)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=6.0,
        help="Video duration in seconds (default: 6.0)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print hash, parameters, and progress",
    )
    parser.add_argument(
        "--qr",
        action="store_true",
        help="Embed QR code of hash digest in video and save standalone QR PNG",
    )

    args = parser.parse_args(argv)

    # Read input
    if args.string is not None:
        data = args.string.encode("utf-8")
    elif args.file is not None:
        with open(args.file, "rb") as f:
            data = f.read()
    else:
        if sys.stdin.isatty():
            parser.error("No input provided. Use -s STRING, provide a FILE, or pipe to stdin.")
        data = sys.stdin.buffer.read()

    # Parse resolution
    try:
        width, height = (int(x) for x in args.resolution.split("x"))
    except ValueError:
        parser.error(f"Invalid resolution format: {args.resolution!r} (expected WxH)")

    # Compute hash to determine default output name
    import hashlib
    hash8 = hashlib.sha256(data).hexdigest()[:8]
    output_path = args.output or f"motionprint_{hash8}.mp4"

    hex_digest = generate(
        data=data,
        output_path=output_path,
        width=width,
        height=height,
        fps=args.fps,
        duration=args.duration,
        verbose=args.verbose,
        qr=args.qr,
    )

    # Save standalone QR PNG alongside the video
    if args.qr:
        import os
        from motionprint.qr import generate_qr_matrix, save_qr_png
        qr_path = os.path.splitext(output_path)[0] + "_qr.png"
        qr_matrix = generate_qr_matrix(hex_digest)
        save_qr_png(qr_matrix, qr_path)
        print(f"{hex_digest}  {output_path}")
        print(f"{hex_digest}  {qr_path}")
    else:
        print(f"{hex_digest}  {output_path}")
