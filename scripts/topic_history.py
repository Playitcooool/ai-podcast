#!/usr/bin/env python3
"""Safely manage persistent topic history for social-discussion podcast episodes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


DEFAULT_EPISODES_ROOT = Path(
    os.environ.get(
        "EMOTIONAL_PODCAST_OUTPUT_ROOT",
        "/Volumes/Samsung/Projects/emotional-podcast-video",
    )
)
DEFAULT_HISTORY = DEFAULT_EPISODES_ROOT / "topic-history.json"
VALID_STATUSES = {"selected", "in_production", "complete", "abandoned"}
REQUIRED_FIELDS = {
    "topic",
    "slug",
    "selected_at",
    "status",
    "central_conflict",
    "audience",
    "angle",
    "topic_family",
    "source_episode",
}


def now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold(), flags=re.UNICODE)


def similarity(left: str, right: str) -> float:
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def fingerprint(entry: dict[str, Any]) -> str:
    parts = (
        entry.get("topic_family", ""),
        entry.get("central_conflict", ""),
        entry.get("audience", ""),
        entry.get("angle", ""),
    )
    return "|".join(normalize(str(part)) for part in parts)


def empty_history() -> dict[str, Any]:
    return {
        "version": 2,
        "description": (
            "Persistent selected-topic history for emotional-podcast-video. "
            "All non-abandoned entries are unavailable for automatic reuse."
        ),
        "entries": [],
    }


def validate_history(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("history must be an object with an entries array")
    slugs: set[str] = set()
    for index, entry in enumerate(data["entries"]):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {index} must be an object")
        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            raise ValueError(f"entry {index} missing fields: {sorted(missing)}")
        if entry["status"] not in VALID_STATUSES:
            raise ValueError(f"entry {index} has invalid status: {entry['status']}")
        if entry["slug"] in slugs:
            raise ValueError(f"duplicate slug in history: {entry['slug']}")
        slugs.add(entry["slug"])


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_history()
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_history(data)
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    validate_history(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@contextmanager
def locked_history(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield load_history(path)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def candidate_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "topic": args.topic,
        "slug": args.slug,
        "selected_at": args.selected_at or now_iso(),
        "status": "selected",
        "central_conflict": args.central_conflict,
        "audience": args.audience,
        "angle": args.angle,
        "topic_family": args.topic_family,
        "source_episode": args.source_episode or "",
    }


def compare_candidate(candidate: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    scores = {
        "topic": similarity(candidate["topic"], entry["topic"]),
        "central_conflict": similarity(
            candidate["central_conflict"], entry["central_conflict"]
        ),
        "audience": similarity(candidate["audience"], entry["audience"]),
        "angle": similarity(candidate["angle"], entry["angle"]),
        "topic_family": similarity(candidate["topic_family"], entry["topic_family"]),
    }
    weighted = (
        scores["topic"] * 0.30
        + scores["central_conflict"] * 0.25
        + scores["audience"] * 0.10
        + scores["angle"] * 0.15
        + scores["topic_family"] * 0.20
    )
    likely_duplicate = (
        scores["topic"] >= 0.82
        or weighted >= 0.78
        or (
            scores["topic_family"] >= 0.90
            and scores["central_conflict"] >= 0.70
        )
    )
    return {
        "slug": entry["slug"],
        "topic": entry["topic"],
        "status": entry["status"],
        "similarity": round(weighted, 4),
        "component_scores": {key: round(value, 4) for key, value in scores.items()},
        "likely_duplicate": likely_duplicate,
    }


def check_candidate(
    candidate: dict[str, Any], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons = [
        compare_candidate(candidate, entry)
        for entry in entries
        if entry["status"] != "abandoned"
    ]
    comparisons.sort(key=lambda item: item["similarity"], reverse=True)
    closest = comparisons[0] if comparisons else None
    return {
        "candidate": candidate,
        "likely_duplicate": bool(closest and closest["likely_duplicate"]),
        "closest_match": closest,
        "top_matches": comparisons[:5],
        "note": (
            "Use this deterministic signal as evidence; the LLM must still compare "
            "the core question, conflict, audience, and promise semantically."
        ),
    }


def map_manifest_status(value: str) -> str:
    normalized = value.casefold()
    if normalized in {"selected", "in_production", "complete", "abandoned"}:
        return normalized
    if "abandon" in normalized:
        return "abandoned"
    if any(token in normalized for token in ("complete", "ready", "publish")):
        return "complete"
    return "in_production"


def bootstrap(history_path: Path, episodes_root: Path) -> dict[str, Any]:
    added: list[str] = []
    with locked_history(history_path) as data:
        existing_slugs = {entry["slug"] for entry in data["entries"]}
        for manifest_path in sorted(episodes_root.glob("*/00-manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            topic = str(manifest.get("topic", "")).strip()
            slug = str(manifest.get("slug") or manifest_path.parent.name).strip()
            if not topic or slug in existing_slugs:
                continue
            fingerprint = manifest.get("topic_fingerprint")
            if not isinstance(fingerprint, dict):
                fingerprint = {}
            entry = {
                "topic": topic,
                "slug": slug,
                "selected_at": str(manifest.get("created_at") or now_iso()),
                "status": map_manifest_status(str(manifest.get("status", ""))),
                "central_conflict": str(
                    fingerprint.get("central_conflict")
                    or manifest.get("central_conflict", "")
                ),
                "audience": str(
                    fingerprint.get("audience") or manifest.get("audience", "")
                ),
                "angle": str(
                    fingerprint.get("angle") or manifest.get("angle", "")
                ),
                "topic_family": str(
                    fingerprint.get("topic_family")
                    or manifest.get("topic_family", "")
                ),
                "source_episode": str(manifest_path.parent),
                "notes": "Bootstrapped from an existing episode manifest.",
            }
            data["entries"].append(entry)
            existing_slugs.add(slug)
            added.append(slug)
        data["version"] = 2
        atomic_write(history_path, data)
    return {"added": added, "count": len(added), "history": str(history_path)}


def command_check(args: argparse.Namespace) -> dict[str, Any]:
    data = load_history(args.history)
    return check_candidate(candidate_from_args(args), data["entries"])


def command_reserve(args: argparse.Namespace) -> dict[str, Any]:
    candidate = candidate_from_args(args)
    with locked_history(args.history) as data:
        result = check_candidate(candidate, data["entries"])
        duplicate_slug = any(
            entry["slug"] == candidate["slug"] for entry in data["entries"]
        )
        duplicate_topic = any(
            normalize(entry["topic"]) == normalize(candidate["topic"])
            and entry["status"] != "abandoned"
            for entry in data["entries"]
        )
        if duplicate_slug or duplicate_topic or result["likely_duplicate"]:
            raise SystemExit(
                "topic reservation rejected as duplicate: "
                + json.dumps(result, ensure_ascii=False)
            )
        candidate["fingerprint"] = fingerprint(candidate)
        data["entries"].append(candidate)
        data["version"] = 2
        atomic_write(args.history, data)
    return {"reserved": candidate, "history": str(args.history)}


def command_update(args: argparse.Namespace) -> dict[str, Any]:
    with locked_history(args.history) as data:
        matches = [entry for entry in data["entries"] if entry["slug"] == args.slug]
        if len(matches) != 1:
            raise SystemExit(f"expected one history entry for slug {args.slug!r}")
        entry = matches[0]
        entry["status"] = args.status
        entry["updated_at"] = now_iso()
        if args.source_episode is not None:
            entry["source_episode"] = args.source_episode
        if args.notes is not None:
            entry["notes"] = args.notes
        atomic_write(args.history, data)
    return {"updated": entry, "history": str(args.history)}


def add_candidate_arguments(parser: argparse.ArgumentParser, *, need_slug: bool) -> None:
    parser.add_argument("--topic", required=True)
    parser.add_argument("--slug", required=need_slug, default="candidate")
    parser.add_argument("--selected-at")
    parser.add_argument("--central-conflict", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--angle", required=True)
    parser.add_argument("--topic-family", required=True)
    parser.add_argument("--source-episode")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.set_defaults(handler=lambda args: {
        "valid": True,
        "entries": len(load_history(args.history)["entries"]),
        "history": str(args.history),
    })

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(handler=lambda args: load_history(args.history))

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument(
        "--episodes-root", type=Path, default=DEFAULT_EPISODES_ROOT
    )
    bootstrap_parser.set_defaults(
        handler=lambda args: bootstrap(args.history, args.episodes_root)
    )

    check_parser = subparsers.add_parser("check")
    add_candidate_arguments(check_parser, need_slug=False)
    check_parser.set_defaults(handler=command_check)

    reserve_parser = subparsers.add_parser("reserve")
    add_candidate_arguments(reserve_parser, need_slug=True)
    reserve_parser.set_defaults(handler=command_reserve)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--slug", required=True)
    update_parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    update_parser.add_argument("--source-episode")
    update_parser.add_argument("--notes")
    update_parser.set_defaults(handler=command_update)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.handler(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
