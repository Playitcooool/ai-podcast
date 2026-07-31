from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sys
from types import ModuleType

import numpy as np
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "synthesize_episode.py"
)
FIXTURE_EPISODE = Path(
    "/Volumes/Samsung/Projects/emotional-podcast-video/"
    "2026-07-30-shujia-haizi-shangwang-baohu-haishi-guankong"
)


def load_synthesis_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "emotional_podcast_candidate_selection",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synth() -> ModuleType:
    return load_synthesis_module()


def performance_line(
    *,
    move: str = "承接",
    claim_type: str = "opinion",
    intensity: float = 0.4,
    pace: str = "natural",
) -> dict[str, object]:
    return {
        "index": 2,
        "speaker": "男声·理性",
        "segment": "讨论",
        "move": move,
        "claim_type": claim_type,
        "text": "这是一句用于测试表达候选选择的自然对话。",
        "performance": {
            "emotion": "专注",
            "intensity": intensity,
            "pace": pace,
            "energy": "medium",
            "pitch": "natural",
            "ending": "level",
            "key_emphasis": [],
        },
    }


@pytest.mark.parametrize("intensity", [0.7, 0.85, 1.0])
def test_high_intensity_line_is_expressive(
    synth: ModuleType,
    intensity: float,
) -> None:
    assert synth.is_expressive_line(
        performance_line(intensity=intensity)
    )


@pytest.mark.parametrize("move", ["追问", "反例", "修正", "综合", "邀请"])
def test_dialogue_moves_that_need_performance_get_candidates(
    synth: ModuleType,
    move: str,
) -> None:
    assert synth.is_expressive_line(
        performance_line(move=move, intensity=0.3)
    )


def test_ordinary_fact_line_does_not_generate_extra_candidates(
    synth: ModuleType,
) -> None:
    assert not synth.is_expressive_line(
        performance_line(
            move="新事实",
            claim_type="fact",
            intensity=0.35,
        )
    )


def amplitude_ramp_sine(
    frequency_hz: float,
    sample_rate: int,
    seconds: float,
) -> np.ndarray:
    count = round(sample_rate * seconds)
    time_axis = np.arange(count, dtype=np.float64) / sample_rate
    envelope = np.linspace(0.02, 0.10, count)
    return np.asarray(
        envelope * np.sin(2.0 * np.pi * frequency_hz * time_axis),
        dtype=np.float32,
    )


def test_prosody_metrics_detect_pitch_dynamic_range_slope_and_pauses(
    synth: ModuleType,
) -> None:
    sample_rate = 8000
    first = amplitude_ramp_sine(200.0, sample_rate, 1.0)
    second = amplitude_ramp_sine(200.0, sample_rate, 1.0)
    pause = np.zeros(round(sample_rate * 0.22), dtype=np.float32)
    wav = np.concatenate((first, pause, second))

    metrics = synth.prosody_metrics(wav, sample_rate)

    assert set(metrics) >= {
        "voiced_dynamic_range_db",
        "energy_slope_db_per_second",
        "pause_count",
        "pitch_median_hz",
        "pitch_range_hz",
    }
    assert metrics["voiced_dynamic_range_db"] >= 5.0
    assert metrics["energy_slope_db_per_second"] > 0
    assert metrics["pause_count"] >= 1
    assert metrics["pitch_median_hz"] == pytest.approx(200.0, abs=20.0)
    assert metrics["pitch_range_hz"] < 35.0


def test_prosody_metrics_detect_pitch_change(synth: ModuleType) -> None:
    sample_rate = 8000
    low = amplitude_ramp_sine(160.0, sample_rate, 0.8)
    high = amplitude_ramp_sine(280.0, sample_rate, 0.8)
    metrics = synth.prosody_metrics(np.concatenate((low, high)), sample_rate)
    assert 160.0 <= metrics["pitch_median_hz"] <= 280.0
    assert metrics["pitch_range_hz"] >= 70.0


def candidate_metrics(
    *,
    rate: float = 4.5,
    dynamic_range: float = 8.0,
    peak: float = 0.55,
    rms: float = -21.0,
    clipping: float = 0.0,
    issues: list[str] | None = None,
) -> dict[str, object]:
    return {
        "duration_seconds": 8.0,
        "rms_dbfs": rms,
        "active_rms_dbfs": rms,
        "peak": peak,
        "clipping_ratio": clipping,
        "silence_ratio": 0.08,
        "spoken_characters_per_second": rate,
        "dynamic_range_db": dynamic_range,
        "energy_slope_db_per_second": 0.2,
        "pause_count": 1,
        "pitch_median_hz": 205.0,
        "pitch_range_hz": 42.0,
        "quality_issues": issues or [],
    }


def test_score_candidate_rewards_target_pace_dynamics_and_clean_quality(
    synth: ModuleType,
) -> None:
    line = performance_line(move="追问", intensity=0.7)
    good = synth.score_candidate(candidate_metrics(), line, -21.0)
    rushed = synth.score_candidate(
        candidate_metrics(rate=8.2, dynamic_range=1.0),
        line,
        -21.0,
    )
    clipped = synth.score_candidate(
        candidate_metrics(
            peak=1.0,
            clipping=0.02,
            issues=["clipping", "speech_rate_out_of_range"],
        ),
        line,
        -21.0,
    )

    assert set(good) >= {"score", "reasons"}
    assert good["score"] > rushed["score"] > clipped["score"]
    assert good["reasons"]
    assert any(
        "pace" in reason.lower()
        or "dynamic" in reason.lower()
        or "节奏" in reason
        or "动态" in reason
        for reason in good["reasons"]
    )
    assert any(
        "clipping" in reason.lower() or "削波" in reason
        for reason in clipped["reasons"]
    )


def test_select_best_candidate_returns_winner_and_reports_every_option(
    synth: ModuleType,
) -> None:
    candidates = [
        {
            "candidate": 1,
            "evaluation": {"score": 61.0, "reasons": ["节奏稍快"]},
            "wav": "one",
        },
        {
            "candidate": 2,
            "evaluation": {"score": 88.0, "reasons": ["动态自然"]},
            "wav": "two",
        },
        {
            "candidate": 3,
            "evaluation": {"score": 72.0, "reasons": ["停顿合理"]},
            "wav": "three",
        },
    ]

    winner, report = synth.select_best_candidate(candidates)

    assert winner["candidate"] == 2
    assert winner["wav"] == "two"
    assert report["selected_candidate"] == 2
    assert len(report["candidates"]) == 3
    assert [item["candidate"] for item in report["candidates"]] == [1, 2, 3]
    assert [
        item["evaluation"]["score"] for item in report["candidates"]
    ] == [
        61.0,
        88.0,
        72.0,
    ]


def test_main_defaults_to_two_expressive_candidates(synth: ModuleType) -> None:
    source = inspect.getsource(synth.main)
    assert "--expressive-candidates" in source
    assert "default=2" in source


@pytest.mark.parametrize("value", ["0", "4"])
def test_main_rejects_candidate_count_outside_one_to_three(
    synth: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--episode-dir",
            str(FIXTURE_EPISODE),
            "--expressive-candidates",
            value,
            "--natural-dialogue-policy",
            "advisory",
            "--validate-only",
        ],
    )
    with pytest.raises(ValueError, match="expressive|candidate|1|3"):
        synth.main()
