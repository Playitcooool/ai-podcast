from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
import wave

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "audio_review.py"
)
RATING_FIELDS = (
    "emotion_match",
    "context_response",
    "natural_pause",
    "emphasis_accuracy",
)


def load_review_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "emotional_podcast_audio_review",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def review() -> ModuleType:
    return load_review_module()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 800)


def episode_fixture(tmp_path: Path) -> tuple[dict, Path]:
    script = [
        {"index": 1, "speaker": "女声·感性", "text": "第一句"},
        {"index": 2, "speaker": "男声·理性", "text": "第二句"},
    ]
    script_path = tmp_path / "02-script.json"
    script_path.write_text(
        json.dumps(script, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = []
    for index, role, speaker in (
        (1, "female", "女声·感性"),
        (2, "male", "男声·理性"),
    ):
        relative = f"audio/line-{index:03d}-{role}.wav"
        audio_path = tmp_path / relative
        write_wav(audio_path)
        lines.append(
            {
                "index": index,
                "speaker": speaker,
                "path": relative,
                "wav_sha256": sha256(audio_path),
                "issues": [],
                "attempts": [{"issues": []}],
            }
        )
    report = {
        "script_sha256": sha256(script_path),
        "line_count": 2,
        "automated_passed": True,
        "lines": lines,
    }
    report_path = tmp_path / "03-audio-qc.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False),
        encoding="utf-8",
    )
    return report, report_path


def ratings(**overrides: int) -> dict[str, int]:
    result = {
        "emotion_match": 4,
        "context_response": 4,
        "natural_pause": 4,
        "emphasis_accuracy": 4,
    }
    result.update(overrides)
    return result


def test_passed_review_requires_and_persists_all_four_ratings(
    review: ModuleType,
    tmp_path: Path,
) -> None:
    report, report_path = episode_fixture(tmp_path)
    updated = review.record(
        report=report,
        line_indexes={1},
        status="passed",
        notes="四项听感均符合台词要求",
        report_path=report_path,
        ratings=ratings(emotion_match=5),
    )
    manual = updated["lines"][0]["manual_review"]
    assert manual["status"] == "passed"
    assert manual["ratings"] == ratings(emotion_match=5)


@pytest.mark.parametrize("low_field", RATING_FIELDS)
def test_any_rating_below_three_cannot_be_marked_passed(
    review: ModuleType,
    tmp_path: Path,
    low_field: str,
) -> None:
    report, report_path = episode_fixture(tmp_path)
    with pytest.raises(ValueError, match=low_field + "|rating|评分|3"):
        review.record(
            report=report,
            line_indexes={1},
            status="passed",
            notes="仍有一项听感不合格",
            report_path=report_path,
            ratings=ratings(**{low_field: 2}),
        )


@pytest.mark.parametrize(
    "bad_ratings",
    [
        {},
        {"emotion_match": 4},
        ratings(natural_pause=0),
        ratings(emphasis_accuracy=6),
        ratings(context_response=True),
    ],
)
def test_record_rejects_missing_or_out_of_range_ratings(
    review: ModuleType,
    tmp_path: Path,
    bad_ratings: dict[str, object],
) -> None:
    report, report_path = episode_fixture(tmp_path)
    with pytest.raises(ValueError, match="rating|评分|1|5"):
        review.record(
            report=report,
            line_indexes={1},
            status="passed",
            notes="评分结构不完整",
            report_path=report_path,
            ratings=bad_ratings,
        )


def test_check_aggregates_rating_averages(
    review: ModuleType,
    tmp_path: Path,
) -> None:
    report, report_path = episode_fixture(tmp_path)
    review.record(
        report,
        {1},
        "passed",
        "第一句四项评分完成",
        report_path,
        ratings(emotion_match=5, natural_pause=3),
    )
    review.record(
        report,
        {2},
        "passed",
        "第二句四项评分完成",
        report_path,
        ratings(emotion_match=3, natural_pause=5),
    )

    result = review.check(report, report_path)

    assert result["passed"] is True
    assert set(result["rating_summary"]) == set(RATING_FIELDS)
    assert result["rating_summary"]["emotion_match"] == pytest.approx(4.0)
    assert result["rating_summary"]["natural_pause"] == pytest.approx(4.0)
