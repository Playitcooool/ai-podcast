#!/usr/bin/env python3
"""Record and verify human/agent listening review for generated podcast lines."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import wave


ALLOWED_STATUSES = {"passed", "regenerate"}
RATING_FIELDS = (
    "emotion_match",
    "context_response",
    "natural_pause",
    "emphasis_accuracy",
)
MIN_PASSING_RATING = 3


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing audio quality report: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("lines"), list):
        raise ValueError("03-audio-qc.json has invalid structure")
    if not report["lines"]:
        raise ValueError("03-audio-qc.json contains no line records")
    return report


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_audio_path(report_path: Path, line: dict[str, Any]) -> Path:
    relative = Path(str(line.get("path", "")))
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"line {line.get('index')} has invalid audio path")
    audio_path = (report_path.parent / relative).resolve()
    if report_path.parent.resolve() not in audio_path.parents:
        raise ValueError(f"line {line.get('index')} audio path escapes episode folder")
    if not audio_path.exists():
        raise ValueError(f"line {line.get('index')} audio file is missing: {relative}")
    try:
        with wave.open(str(audio_path), "rb") as handle:
            if handle.getnframes() <= 0 or handle.getframerate() <= 0:
                raise ValueError("empty WAV")
    except (wave.Error, EOFError, ValueError) as exc:
        raise ValueError(
            f"line {line.get('index')} audio file is not a readable WAV"
        ) from exc
    return audio_path


def validate_automated_results(
    report: dict[str, Any], report_path: Path
) -> dict[int, str]:
    script_path = report_path.parent / "02-script.json"
    if not script_path.exists():
        raise ValueError("missing 02-script.json for audio review")
    script = json.loads(script_path.read_text(encoding="utf-8"))
    if not isinstance(script, list) or not script:
        raise ValueError("02-script.json must contain a non-empty array")
    script_sha256 = sha256_file(script_path)
    if report.get("script_sha256") != script_sha256:
        raise ValueError("audio quality report does not match 02-script.json")
    if report.get("line_count") != len(script):
        raise ValueError("audio quality line_count does not match 02-script.json")
    indexes = [int(line.get("index", -1)) for line in report["lines"]]
    expected = list(range(1, len(indexes) + 1))
    if indexes != expected or len(indexes) != len(script):
        raise ValueError(
            f"audio quality line indexes must be unique and sequential: {indexes}"
        )
    hashes: dict[int, str] = {}
    paths: set[str] = set()
    automated_passed = True
    for line, script_line in zip(report["lines"], script):
        index = int(line["index"])
        if index != script_line.get("index"):
            raise ValueError(f"line {index} does not match script index")
        if line.get("speaker") != script_line.get("speaker"):
            raise ValueError(f"line {index} speaker does not match 02-script.json")
        role = "female" if line["speaker"] == "女声·感性" else "male"
        expected_path = f"audio/line-{index:03d}-{role}.wav"
        if line.get("path") != expected_path:
            raise ValueError(
                f"line {index} path must be the canonical path: {expected_path}"
            )
        if expected_path in paths:
            raise ValueError(f"duplicate audio path: {expected_path}")
        paths.add(expected_path)
        issues = line.get("issues")
        attempts = line.get("attempts")
        if not isinstance(issues, list) or not isinstance(attempts, list) or not attempts:
            raise ValueError(f"line {index} has incomplete automated quality records")
        final_issues = attempts[-1].get("issues")
        if not isinstance(final_issues, list):
            raise ValueError(f"line {index} final attempt has invalid issues")
        if issues or final_issues:
            automated_passed = False
        audio_path = line_audio_path(report_path, line)
        current_hash = sha256_file(audio_path)
        if line.get("wav_sha256") != current_hash:
            raise ValueError(f"line {index} WAV hash does not match 03-audio-qc.json")
        hashes[index] = current_hash
    if bool(report.get("automated_passed")) != automated_passed:
        raise ValueError("top-level automated_passed disagrees with line results")
    report["automated_passed"] = automated_passed
    return hashes


def refresh_summary(
    report: dict[str, Any], report_path: Path
) -> dict[str, Any]:
    hashes = validate_automated_results(report, report_path)
    statuses = [
        str(line.get("manual_review", {}).get("status", "pending"))
        for line in report["lines"]
    ]
    manual_passed = True
    for line, status in zip(report["lines"], statuses):
        review = line.get("manual_review", {})
        ratings = review.get("ratings", {})
        ratings_passed = isinstance(ratings, dict) and all(
            type(ratings.get(field)) is int
            and MIN_PASSING_RATING <= ratings[field] <= 5
            for field in RATING_FIELDS
        )
        if (
            status != "passed"
            or review.get("audio_sha256") != hashes[int(line["index"])]
            or not str(review.get("reviewed_at", "")).strip()
            or len(str(review.get("notes", "")).strip()) < 4
            or not ratings_passed
        ):
            manual_passed = False
    report["manual_review_passed"] = bool(statuses) and manual_passed
    report["passed"] = bool(
        report.get("automated_passed") and report["manual_review_passed"]
    )
    return report


def record(
    report: dict[str, Any],
    line_indexes: set[int] | None,
    status: str,
    notes: str,
    report_path: Path,
    ratings: dict[str, int] | None = None,
) -> dict[str, Any]:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"status must be one of: {sorted(ALLOWED_STATUSES)}")
    if len(notes.strip()) < 4:
        raise ValueError("review notes must contain at least four characters")
    ratings = ratings or {}
    invalid_rating_fields = [
        field
        for field in RATING_FIELDS
        if type(ratings.get(field)) is not int
        or not 1 <= int(ratings[field]) <= 5
    ]
    if status == "passed" and invalid_rating_fields:
        raise ValueError(
            "passed review requires 1-5 ratings for: "
            + "、".join(invalid_rating_fields)
        )
    if status == "passed":
        low_ratings = [
            field for field in RATING_FIELDS if ratings[field] < MIN_PASSING_RATING
        ]
        if low_ratings:
            raise ValueError(
                "passed review requires every rating to be at least "
                f"{MIN_PASSING_RATING}: "
                + "、".join(low_ratings)
            )
    current_hashes = validate_automated_results(report, report_path)
    matched = 0
    for line in report["lines"]:
        index = int(line["index"])
        if line_indexes is not None and index not in line_indexes:
            continue
        previous_review = line.get("manual_review", {})
        current_hash = current_hashes[index]
        rejected_hashes = set(previous_review.get("rejected_audio_hashes", []))
        if previous_review.get("rejected_sha256"):
            rejected_hashes.add(previous_review["rejected_sha256"])
        if status == "passed" and current_hash in rejected_hashes:
            raise ValueError(
                f"line {index} must be regenerated before it can pass review"
            )
        line["manual_review"] = {
            "status": status,
            "reviewed_at": now_iso(),
            "notes": notes.strip(),
            "audio_sha256": current_hash,
            "ratings": {
                field: ratings.get(field) for field in RATING_FIELDS
            },
            "rejected_audio_hashes": sorted(rejected_hashes),
        }
        if status == "regenerate":
            rejected_hashes.add(current_hash)
            line["manual_review"]["rejected_audio_hashes"] = sorted(rejected_hashes)
        matched += 1
    if matched == 0:
        raise ValueError("no requested line indexes were found")
    if line_indexes is not None and matched != len(line_indexes):
        found = {int(line["index"]) for line in report["lines"]}
        missing = sorted(line_indexes - found)
        raise ValueError(f"unknown line indexes: {missing}")
    return refresh_summary(report, report_path)


def check(report: dict[str, Any], report_path: Path) -> dict[str, Any]:
    refresh_summary(report, report_path)
    pending = []
    regenerate = []
    for line in report["lines"]:
        status = str(line.get("manual_review", {}).get("status", "pending"))
        if status == "regenerate":
            regenerate.append(int(line["index"]))
        elif status != "passed":
            pending.append(int(line["index"]))
    result = {
        "passed": bool(report.get("passed")),
        "automated_passed": bool(report.get("automated_passed")),
        "manual_review_passed": bool(report.get("manual_review_passed")),
        "pending_lines": pending,
        "regenerate_lines": regenerate,
        "rating_summary": {
            field: round(
                sum(
                    int(line["manual_review"]["ratings"][field])
                    for line in report["lines"]
                    if type(
                        line.get("manual_review", {}).get("ratings", {}).get(field)
                    )
                    is int
                )
                / max(
                    1,
                    sum(
                        type(
                            line.get("manual_review", {})
                            .get("ratings", {})
                            .get(field)
                        )
                        is int
                        for line in report["lines"]
                    ),
                ),
                2,
            )
            for field in RATING_FIELDS
        },
    }
    if not result["passed"]:
        raise ValueError(json.dumps(result, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-dir", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record")
    target = record_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--line", type=int, action="append")
    target.add_argument("--all", action="store_true")
    record_parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), required=True)
    record_parser.add_argument("--notes", required=True)
    for field in RATING_FIELDS:
        record_parser.add_argument(
            f"--{field.replace('_', '-')}",
            dest=field,
            type=int,
            choices=range(1, 6),
        )

    subparsers.add_parser("check")
    args = parser.parse_args()

    report_path = args.episode_dir.resolve() / "03-audio-qc.json"
    report = load_report(report_path)
    if args.command == "record":
        indexes = None if args.all else set(args.line)
        ratings = {field: getattr(args, field) for field in RATING_FIELDS}
        report = record(
            report,
            indexes,
            args.status,
            args.notes,
            report_path,
            ratings=ratings,
        )
        atomic_write(report_path, report)
        print(
            json.dumps(
                refresh_summary(report, report_path), ensure_ascii=False, indent=2
            )
        )
        return
    result = check(report, report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
