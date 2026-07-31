#!/usr/bin/env python3
"""Mux and verify a static-image Bilibili podcast video."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path


def probe(ffprobe: str, path: Path) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def format_duration(report: dict) -> float:
    return float(report.get("format", {}).get("duration", 0.0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--min-duration", type=float, default=360.0)
    parser.add_argument("--max-duration", type=float, default=720.0)
    parser.add_argument("--duration-tolerance", type=float, default=1.5)
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe are required but were not found on PATH")
    for path in (args.image, args.audio):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.min_duration <= 0 or args.max_duration <= args.min_duration:
        raise ValueError("invalid duration range")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    input_image_probe = probe(ffprobe, args.image)
    input_audio_probe = probe(ffprobe, args.audio)
    audio_duration = format_duration(input_audio_probe)
    if audio_duration <= 0:
        raise ValueError("input audio has no measurable duration")
    if not args.min_duration <= audio_duration <= args.max_duration:
        raise ValueError(
            f"input audio duration {audio_duration:.3f}s is outside "
            f"{args.min_duration:.1f}-{args.max_duration:.1f}s"
        )
    image_streams = [
        stream
        for stream in input_image_probe.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    if len(image_streams) != 1:
        raise ValueError("input image must contain one visual stream")
    image_width = int(image_streams[0].get("width", 0))
    image_height = int(image_streams[0].get("height", 0))
    if image_width <= 0 or image_height <= 0:
        raise ValueError("input image dimensions are unavailable")
    image_ratio = image_width / image_height
    if abs(image_ratio - 16 / 9) > 0.02:
        raise ValueError(
            f"input image ratio {image_ratio:.4f} is not sufficiently close to 16:9"
        )
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        "30",
        "-loop",
        "1",
        "-i",
        str(args.image),
        "-i",
        str(args.audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{audio_duration:.6f}",
        "-shortest", "-movflags", "+faststart",
        str(args.output),
    ]
    started = time.perf_counter()
    subprocess.run(command, check=True)
    elapsed = time.perf_counter() - started
    output_probe = probe(ffprobe, args.output)
    output_duration = format_duration(output_probe)
    video_streams = [
        stream
        for stream in output_probe.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream
        for stream in output_probe.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    errors: list[str] = []
    if len(video_streams) != 1:
        errors.append(f"expected one video stream, found {len(video_streams)}")
    else:
        video = video_streams[0]
        if video.get("codec_name") != "h264":
            errors.append(f"video codec is {video.get('codec_name')}, expected h264")
        if (video.get("width"), video.get("height")) != (1920, 1080):
            errors.append(
                f"video dimensions are {video.get('width')}x{video.get('height')}, "
                "expected 1920x1080"
            )
    if len(audio_streams) != 1:
        errors.append(f"expected one audio stream, found {len(audio_streams)}")
    elif audio_streams[0].get("codec_name") != "aac":
        errors.append(
            f"audio codec is {audio_streams[0].get('codec_name')}, expected aac"
        )
    if not args.min_duration <= output_duration <= args.max_duration:
        errors.append(
            f"duration {output_duration:.3f}s is outside "
            f"{args.min_duration:.1f}-{args.max_duration:.1f}s"
        )
    drift = abs(output_duration - audio_duration)
    if drift > args.duration_tolerance:
        errors.append(
            f"video/audio duration drift {drift:.3f}s exceeds "
            f"{args.duration_tolerance:.3f}s"
        )
    report = {
        "output": str(args.output),
        "render_seconds": round(elapsed, 3),
        "input_audio_duration_seconds": round(audio_duration, 3),
        "input_image": {
            "width": image_width,
            "height": image_height,
            "aspect_ratio": round(image_ratio, 5),
        },
        "output_duration_seconds": round(output_duration, 3),
        "duration_drift_seconds": round(drift, 3),
        "validation": {
            "passed": not errors,
            "errors": errors,
            "required_duration_seconds": [args.min_duration, args.max_duration],
        },
        "probe": output_probe,
        "command": command,
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.report.with_name("05-render-command.txt").write_text(
        " ".join(command) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit("render validation failed: " + "; ".join(errors))


if __name__ == "__main__":
    main()
